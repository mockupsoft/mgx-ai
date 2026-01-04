import subprocess

import pytest

from backend.app.deployment.traffic_switcher import TrafficSwitcher, TrafficSwitchConfig
from backend.services.security.ssrf import validate_outbound_url


def test_traffic_switcher_uses_safe_subprocess_args(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, ...]] = []

    def fake_run(cmd, check):
        calls.append((cmd, check))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    switcher = TrafficSwitcher(TrafficSwitchConfig(namespace="ns", service_name="svc"))
    switcher.switch("green")

    assert calls
    cmd, check = calls[0]
    assert isinstance(cmd, list)
    assert "--type" in cmd
    assert check is True


def test_ssrf_validation_rejects_non_http_schemes() -> None:
    assert validate_outbound_url("gopher://example.com").allowed is False
