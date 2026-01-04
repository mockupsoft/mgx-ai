# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.middleware.logging import get_logger


@dataclass(frozen=True)
class SecurityEvent:
    event_type: str
    severity: str
    message: str
    user_id: str | None = None
    workspace_id: str | None = None
    ip_address: str | None = None
    details: dict[str, Any] | None = None


def log_security_event(event: SecurityEvent) -> None:
    logger = get_logger("security")
    logger.warning(
        event.message,
        event_type=event.event_type,
        severity=event.severity,
        user_id=event.user_id,
        workspace_id=event.workspace_id,
        ip_address=event.ip_address,
        details=event.details or {},
    )
