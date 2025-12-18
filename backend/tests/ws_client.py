# -*- coding: utf-8 -*-
"""WebSocket test client helpers.

FastAPI's TestClient exposes a ``websocket_connect`` context manager. This
module wraps it with small convenience helpers to keep API integration tests
readable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi.testclient import TestClient


@dataclass
class WSClient:
    client: TestClient
    path: str

    def __enter__(self):
        self._ws = self.client.websocket_connect(self.path)
        return self

    def __exit__(self, exc_type, exc, tb):
        self._ws.__exit__(exc_type, exc, tb)

    def send_json(self, payload: Dict[str, Any]) -> None:
        self._ws.send_json(payload)

    def receive_json(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        # The underlying implementation doesn't accept timeout; kept for API symmetry.
        _ = timeout
        return self._ws.receive_json()

    def close(self) -> None:
        self._ws.close()


__all__ = ["WSClient"]
