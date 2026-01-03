from __future__ import annotations

from pathlib import Path

import yaml

from backend.core.feature_flags import stable_bucket
from backend.services.feature_flag_service import FeatureFlagService


def _write_config(path: Path, features: dict[str, dict]) -> None:
    path.write_text(yaml.safe_dump({"features": features}, sort_keys=True), encoding="utf-8")


class TestFeatureFlags:
    def test_enabled_disabled_states(self, tmp_path: Path) -> None:
        config_path = tmp_path / "feature_flags.yaml"
        _write_config(
            config_path,
            {
                "flag_on": {"enabled": True, "rollout_percentage": 100},
                "flag_off": {"enabled": False, "rollout_percentage": 100},
            },
        )

        service = FeatureFlagService(config_path=config_path, cache_ttl_seconds=60, config_reload_ttl_seconds=0)
        assert service.is_enabled("flag_on", user_id="u1", workspace_id="w1") is True
        assert service.is_enabled("flag_off", user_id="u1", workspace_id="w1") is False

    def test_rollout_percentage_deterministic(self, tmp_path: Path) -> None:
        config_path = tmp_path / "feature_flags.yaml"
        _write_config(config_path, {"rollout": {"enabled": True, "rollout_percentage": 50}})

        service = FeatureFlagService(config_path=config_path, cache_ttl_seconds=60, config_reload_ttl_seconds=0)

        user_id = "user-123"
        workspace_id = "ws-1"
        expected = stable_bucket("rollout", user_id=user_id, workspace_id=workspace_id) < 50
        assert service.is_enabled("rollout", user_id=user_id, workspace_id=workspace_id) is expected

        # Deterministic across calls
        assert service.is_enabled("rollout", user_id=user_id, workspace_id=workspace_id) is expected

    def test_user_and_workspace_overrides(self, tmp_path: Path) -> None:
        config_path = tmp_path / "feature_flags.yaml"
        _write_config(
            config_path,
            {
                "flag": {
                    "enabled": False,
                    "rollout_percentage": 0,
                    "user_overrides": {"u1": True},
                    "workspace_overrides": {"w1": True},
                }
            },
        )

        service = FeatureFlagService(config_path=config_path, cache_ttl_seconds=60, config_reload_ttl_seconds=0)

        # user override wins
        assert service.is_enabled("flag", user_id="u1", workspace_id="w0") is True
        # workspace override
        assert service.is_enabled("flag", user_id="u0", workspace_id="w1") is True
        # default remains disabled
        assert service.is_enabled("flag", user_id="u0", workspace_id="w0") is False

    def test_override_invalidates_cache(self, tmp_path: Path) -> None:
        config_path = tmp_path / "feature_flags.yaml"
        _write_config(config_path, {"flag": {"enabled": False, "rollout_percentage": 0}})

        service = FeatureFlagService(config_path=config_path, cache_ttl_seconds=3600, config_reload_ttl_seconds=0)

        assert service.is_enabled("flag", user_id="u1", workspace_id="w1") is False
        service.override_flag("flag", "u1", True)
        assert service.is_enabled("flag", user_id="u1", workspace_id="w1") is True

    def test_reset_to_default(self, tmp_path: Path) -> None:
        config_path = tmp_path / "feature_flags.yaml"
        _write_config(config_path, {"flag": {"enabled": True, "rollout_percentage": 100}})

        service = FeatureFlagService(config_path=config_path, cache_ttl_seconds=60, config_reload_ttl_seconds=0)
        assert service.is_enabled("flag", user_id="u1", workspace_id="w1") is True

        service.disable_flag("flag")
        assert service.is_enabled("flag", user_id="u1", workspace_id="w1") is False

        service.reset_flag_to_default("flag")
        assert service.is_enabled("flag", user_id="u1", workspace_id="w1") is True
