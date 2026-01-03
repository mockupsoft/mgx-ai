# -*- coding: utf-8 -*-

from __future__ import annotations

import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from backend.config import settings
from backend.core.feature_flags import FeatureFlag, feature_flag_from_config, stable_bucket
from backend.services.feature_flag_metrics import FeatureFlagMetrics


class FeatureFlagService:
    def __init__(
        self,
        *,
        config_path: Path,
        cache_ttl_seconds: float = 60.0,
        config_reload_ttl_seconds: float = 30.0,
        metrics: FeatureFlagMetrics | None = None,
    ) -> None:
        self._config_path = config_path
        self._cache_ttl_seconds = float(cache_ttl_seconds)
        self._config_reload_ttl_seconds = float(config_reload_ttl_seconds)
        self._lock = threading.RLock()
        self.metrics = metrics or FeatureFlagMetrics()

        self._defaults: dict[str, FeatureFlag] = {}
        self._flags: dict[str, FeatureFlag] = {}
        self._decision_cache: dict[
            tuple[str, str | None, str | None], tuple[bool, float]
        ] = {}

        self._last_loaded_monotonic = 0.0
        self._last_config_mtime: float | None = None

        self._load_defaults(force=True)

    def list_flags(self) -> list[FeatureFlag]:
        with self._lock:
            self._maybe_reload_defaults()
            return list(self._flags.values())

    def get_flag(self, flag_name: str) -> FeatureFlag | None:
        with self._lock:
            self._maybe_reload_defaults()
            return self._flags.get(flag_name)

    def is_enabled(
        self, flag_name: str, *, user_id: str | None, workspace_id: str | None
    ) -> bool:
        start = time.perf_counter()
        try:
            with self._lock:
                self._maybe_reload_defaults()

                cache_key = (flag_name, user_id, workspace_id)
                cached = self._decision_cache.get(cache_key)
                now = time.monotonic()
                if cached is not None:
                    value, expires_at = cached
                    if expires_at >= now:
                        return value
                    self._decision_cache.pop(cache_key, None)

                flag = self._flags.get(flag_name)
                if flag is None:
                    self.metrics.record_error(flag_name)
                    value = False
                else:
                    value = _evaluate_flag(flag, user_id=user_id, workspace_id=workspace_id)

                self._decision_cache[cache_key] = (value, now + self._cache_ttl_seconds)
                return value
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            self.metrics.record_lookup(flag_name, duration_ms=duration_ms)

    def get_flag_percentage(self, flag_name: str) -> int:
        flag = self.get_flag(flag_name)
        return flag.rollout_percentage if flag else 0

    def override_flag(self, flag_name: str, user_id: str, value: bool) -> None:
        with self._lock:
            flag = self._require_flag(flag_name)
            overrides = dict(flag.user_overrides)
            overrides[str(user_id)] = bool(value)
            self._flags[flag_name] = flag.with_updates(user_overrides=overrides)
            self._invalidate_cache(flag_name)

    def override_flag_for_workspace(self, flag_name: str, workspace_id: str, value: bool) -> None:
        with self._lock:
            flag = self._require_flag(flag_name)
            overrides = dict(flag.workspace_overrides)
            overrides[str(workspace_id)] = bool(value)
            self._flags[flag_name] = flag.with_updates(workspace_overrides=overrides)
            self._invalidate_cache(flag_name)

    def enable_flag(self, flag_name: str, *, actor: str | None = None) -> None:
        with self._lock:
            flag = self._require_flag(flag_name)
            self._flags[flag_name] = flag.with_updates(enabled=True, created_by=actor)
            self._invalidate_cache(flag_name)

    def disable_flag(self, flag_name: str, *, actor: str | None = None) -> None:
        with self._lock:
            flag = self._require_flag(flag_name)
            self._flags[flag_name] = flag.with_updates(enabled=False, created_by=actor)
            self._invalidate_cache(flag_name)

    def set_rollout_percentage(
        self, flag_name: str, percentage: int, *, actor: str | None = None
    ) -> None:
        if percentage < 0 or percentage > 100:
            raise ValueError("rollout percentage must be 0..100")

        with self._lock:
            flag = self._require_flag(flag_name)
            self._flags[flag_name] = flag.with_updates(
                rollout_percentage=int(percentage),
                created_by=actor,
            )
            self._invalidate_cache(flag_name)

    def update_flag(
        self,
        flag_name: str,
        *,
        enabled: bool | None = None,
        rollout_percentage: int | None = None,
        description: str | None = None,
        actor: str | None = None,
    ) -> FeatureFlag:
        if rollout_percentage is not None and (
            rollout_percentage < 0 or rollout_percentage > 100
        ):
            raise ValueError("rollout percentage must be 0..100")

        with self._lock:
            flag = self._require_flag(flag_name)
            updated = flag.with_updates(
                enabled=enabled,
                rollout_percentage=rollout_percentage,
                description=description,
                created_by=actor,
            )
            self._flags[flag_name] = updated
            self._invalidate_cache(flag_name)
            return updated

    def reset_flag_to_default(self, flag_name: str) -> None:
        with self._lock:
            self._maybe_reload_defaults(force=True)
            default_flag = self._defaults.get(flag_name)
            if default_flag is None:
                raise KeyError(f"Unknown feature flag: {flag_name}")
            self._flags[flag_name] = default_flag
            self._invalidate_cache(flag_name)

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return {name: asdict(flag) for name, flag in self._flags.items()}

    def health(self) -> dict[str, Any]:
        with self._lock:
            snapshot = self.metrics.snapshot()
            return {
                "status": "ok" if self._flags else "degraded",
                "flags_loaded": len(self._flags),
                "config_path": str(self._config_path),
                "last_config_mtime": self._last_config_mtime,
                "metrics": {
                    "total_lookups": snapshot.total_lookups,
                    "total_fallbacks": snapshot.total_fallbacks,
                    "total_errors": snapshot.total_errors,
                    "p99_lookup_ms": snapshot.p99_lookup_ms,
                },
            }

    def _invalidate_cache(self, flag_name: str | None = None) -> None:
        if flag_name is None:
            self._decision_cache.clear()
            return

        keys_to_delete = [k for k in self._decision_cache if k[0] == flag_name]
        for k in keys_to_delete:
            self._decision_cache.pop(k, None)

    def _require_flag(self, flag_name: str) -> FeatureFlag:
        self._maybe_reload_defaults()
        flag = self._flags.get(flag_name)
        if flag is None:
            raise KeyError(f"Unknown feature flag: {flag_name}")
        return flag

    def _maybe_reload_defaults(self, *, force: bool = False) -> None:
        if force:
            self._load_defaults(force=True)
            return

        now = time.monotonic()
        if now - self._last_loaded_monotonic < self._config_reload_ttl_seconds:
            return

        self._load_defaults(force=False)

    def _load_defaults(self, *, force: bool) -> None:
        now = time.monotonic()
        config_path = self._config_path

        try:
            stat = config_path.stat()
            mtime = stat.st_mtime
        except FileNotFoundError:
            mtime = None

        if not force and mtime is not None and self._last_config_mtime == mtime:
            self._last_loaded_monotonic = now
            return

        defaults: dict[str, FeatureFlag] = {}
        try:
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            features = raw.get("features") or {}
            if not isinstance(features, dict):
                raise ValueError("feature flag config must define a 'features' mapping")

            for flag_key, flag_cfg in features.items():
                if not isinstance(flag_cfg, dict):
                    continue
                defaults[str(flag_key)] = feature_flag_from_config(str(flag_key), flag_cfg)
        except FileNotFoundError:
            defaults = {}
        except Exception:
            self.metrics.record_error("feature_flags_config")
            defaults = {}

        with self._lock:
            self._defaults = defaults
            # Initialize runtime flags once; subsequent config reloads only refresh defaults.
            if not self._flags:
                self._flags = dict(defaults)
                self._invalidate_cache()

            self._last_loaded_monotonic = now
            self._last_config_mtime = mtime


def _evaluate_flag(flag: FeatureFlag, *, user_id: str | None, workspace_id: str | None) -> bool:
    if user_id is not None and user_id in flag.user_overrides:
        return bool(flag.user_overrides[user_id])

    if workspace_id is not None and workspace_id in flag.workspace_overrides:
        return bool(flag.workspace_overrides[workspace_id])

    if not flag.enabled:
        return False

    if flag.rollout_percentage <= 0:
        return False

    if flag.rollout_percentage >= 100:
        return True

    bucket = stable_bucket(flag.name, user_id=user_id, workspace_id=workspace_id)
    return bucket < flag.rollout_percentage


_feature_flag_service: FeatureFlagService | None = None
_service_lock = threading.Lock()


def get_feature_flag_service() -> FeatureFlagService:
    global _feature_flag_service

    if _feature_flag_service is not None:
        return _feature_flag_service

    with _service_lock:
        if _feature_flag_service is not None:
            return _feature_flag_service

        config_path = Path(settings.feature_flags_config_path)
        _feature_flag_service = FeatureFlagService(
            config_path=config_path,
            cache_ttl_seconds=float(settings.feature_flags_cache_ttl_seconds),
            config_reload_ttl_seconds=float(settings.feature_flags_config_reload_ttl_seconds),
        )
        return _feature_flag_service
