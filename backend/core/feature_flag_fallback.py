# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any

from backend.services.feature_flag_service import FeatureFlagService


def safe_is_enabled(
    service: FeatureFlagService | None,
    flag_name: str,
    *,
    user_id: str | None = None,
    workspace_id: str | None = None,
    default: bool = False,
) -> bool:
    """Safe feature flag lookup.

    This function should never raise.
    """

    if service is None:
        return default

    try:
        return service.is_enabled(flag_name, user_id=user_id, workspace_id=workspace_id)
    except Exception:
        service.metrics.record_fallback(flag_name)
        return default


def safe_call(service: FeatureFlagService | None, fn_name: str, *args: Any, **kwargs: Any) -> Any:
    if service is None:
        return None

    try:
        fn = getattr(service, fn_name)
    except AttributeError:
        return None

    try:
        return fn(*args, **kwargs)
    except Exception:
        service.metrics.record_fallback(fn_name)
        return None
