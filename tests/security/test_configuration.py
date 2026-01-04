import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.middleware.security_headers import SecurityHeadersConfig, SecurityHeadersMiddleware


def test_security_headers_added() -> None:
    app = FastAPI()
    app.add_middleware(
        SecurityHeadersMiddleware,
        config=SecurityHeadersConfig(
            environment="production",
            content_security_policy="default-src 'self'",
            enable_hsts=True,
        ),
    )

    @app.get("/")
    async def root():
        return {"ok": True}

    client = TestClient(app)
    resp = client.get("/")

    assert resp.status_code == 200
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "no-referrer"
    assert "content-security-policy" in resp.headers
    assert "strict-transport-security" in resp.headers


def test_production_error_detail_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.config import settings
    from backend.app.main import create_app

    monkeypatch.setattr(settings, "mgx_env", "production", raising=False)

    app = create_app()

    @app.get("/boom")
    async def boom():
        raise RuntimeError("sensitive")

    client = TestClient(app)
    resp = client.get("/boom")

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Internal server error"
