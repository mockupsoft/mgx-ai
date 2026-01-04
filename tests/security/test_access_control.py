import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.services.auth.rbac import require_permission


def test_require_permission_enforces_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.services.auth import rbac as rbac_module
    from backend.db.session import get_session as original_get_session

    class DummyRBAC:
        async def check_permission(self, *args, **kwargs):
            return True

    async def dummy_get_rbac_service():
        return DummyRBAC()

    async def dummy_get_session():
        yield None

    monkeypatch.setattr(rbac_module, "get_rbac_service", dummy_get_rbac_service)

    app = FastAPI()
    app.dependency_overrides[original_get_session] = dummy_get_session

    @app.get("/protected")
    async def protected(user_info=Depends(require_permission("tasks", "read"))):
        return user_info

    client = TestClient(app)

    assert client.get("/protected").status_code == 401
    assert client.get("/protected", headers={"X-User-ID": "u1"}).status_code == 400

    ok = client.get("/protected", headers={"X-User-ID": "u1", "X-Workspace-ID": "w1"})
    assert ok.status_code == 200
    assert ok.json()["user_id"] == "u1"
    assert ok.json()["workspace_id"] == "w1"
