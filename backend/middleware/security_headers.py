# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Awaitable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


@dataclass(frozen=True)
class SecurityHeadersConfig:
    environment: str = "development"
    content_security_policy: str | None = None
    hsts_max_age_seconds: int = 31_536_000  # 1 year
    enable_hsts: bool = False


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        config: SecurityHeadersConfig | None = None,
    ) -> None:
        super().__init__(app)
        self._config = config or SecurityHeadersConfig()

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)

        self._set_if_missing(response, "X-Content-Type-Options", "nosniff")
        self._set_if_missing(response, "X-Frame-Options", "DENY")
        self._set_if_missing(response, "Referrer-Policy", "no-referrer")
        self._set_if_missing(
            response,
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )

        csp = self._config.content_security_policy
        if csp:
            self._set_if_missing(response, "Content-Security-Policy", csp)

        if self._config.enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self._config.hsts_max_age_seconds}; includeSubDomains"
            )

        return response

    @staticmethod
    def _set_if_missing(response: Response, header_name: str, header_value: str) -> None:
        if header_name not in response.headers:
            response.headers[header_name] = header_value
