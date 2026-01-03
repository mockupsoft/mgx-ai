# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class FeatureFlag:
    name: str
    enabled: bool
    rollout_percentage: int = 100
    user_overrides: dict[str, bool] = field(default_factory=dict)
    workspace_overrides: dict[str, bool] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)
    created_by: str = "system"
    description: str = ""

    def with_updates(
        self,
        *,
        enabled: bool | None = None,
        rollout_percentage: int | None = None,
        user_overrides: dict[str, bool] | None = None,
        workspace_overrides: dict[str, bool] | None = None,
        created_by: str | None = None,
        description: str | None = None,
    ) -> FeatureFlag:
        return FeatureFlag(
            name=self.name,
            enabled=self.enabled if enabled is None else enabled,
            rollout_percentage=self.rollout_percentage if rollout_percentage is None else rollout_percentage,
            user_overrides=self.user_overrides if user_overrides is None else dict(user_overrides),
            workspace_overrides=self.workspace_overrides if workspace_overrides is None else dict(workspace_overrides),
            created_at=self.created_at,
            created_by=self.created_by if created_by is None else created_by,
            description=self.description if description is None else description,
        )


def normalize_rollout_percentage(value: Any) -> int:
    try:
        percentage = int(value)
    except (TypeError, ValueError) as e:
        raise ValueError("rollout_percentage must be an int") from e

    if percentage < 0 or percentage > 100:
        raise ValueError("rollout_percentage must be within 0..100")
    return percentage


def stable_bucket(flag_name: str, *, user_id: str | None, workspace_id: str | None) -> int:
    """Return a stable bucket (0..99) for deterministic rollout decisions."""

    user_part = user_id or "anonymous"
    workspace_part = workspace_id or "default"
    key = f"{flag_name}:{workspace_part}:{user_part}".encode("utf-8")
    digest = hashlib.sha256(key).digest()
    return int.from_bytes(digest[:4], "big") % 100


def feature_flag_from_config(flag_key: str, config: Mapping[str, Any]) -> FeatureFlag:
    """Parse a FeatureFlag from YAML config.

    The YAML format is expected to be:

        features:
          some_flag:
            enabled: true
            rollout_percentage: 10
            description: ...
            user_overrides: {"user_id": true}
            workspace_overrides: {"workspace_id": false}

    The mapping key ("some_flag") is treated as the stable flag identifier.
    """

    rollout_percentage = normalize_rollout_percentage(config.get("rollout_percentage", 100))

    enabled_raw = config.get("enabled", False)
    enabled = bool(enabled_raw)

    user_overrides = config.get("user_overrides")
    workspace_overrides = config.get("workspace_overrides")

    if user_overrides is None:
        user_overrides_dict: dict[str, bool] = {}
    else:
        user_overrides_dict = {str(k): bool(v) for k, v in dict(user_overrides).items()}

    if workspace_overrides is None:
        workspace_overrides_dict: dict[str, bool] = {}
    else:
        workspace_overrides_dict = {str(k): bool(v) for k, v in dict(workspace_overrides).items()}

    description = str(config.get("description") or config.get("name") or "")

    return FeatureFlag(
        name=flag_key,
        enabled=enabled,
        rollout_percentage=rollout_percentage,
        user_overrides=user_overrides_dict,
        workspace_overrides=workspace_overrides_dict,
        created_at=utcnow(),
        created_by=str(config.get("created_by") or "system"),
        description=description,
    )
