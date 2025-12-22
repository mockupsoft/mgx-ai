# -*- coding: utf-8 -*-

import os
from typing import Optional

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.main import create_app
from backend.db.models import Base
from backend.services.git import RepoInfo, RepositoryAccessError, get_git_service

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

os.environ.setdefault("OPENAI_API_KEY", "test_key")


class FakeGitService:
    def __init__(self):
        self.next_info = RepoInfo(full_name="octocat/Hello-World", default_branch="main", private=False, html_url=None)
        self.raise_exc: Optional[Exception] = None

    async def fetch_repo_info(self, repo_full_name: str, installation_id=None, token_override=None) -> RepoInfo:
        if self.raise_exc:
            raise self.raise_exc
        return self.next_info


@pytest.fixture
async def test_db():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def app():
    return create_app()


@pytest.fixture
async def client(app, test_db):
    async def override_get_session():
        session_factory = async_sessionmaker(test_db, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            yield session

    from backend.db.session import get_session

    app.dependency_overrides[get_session] = override_get_session

    fake_git = FakeGitService()
    app.dependency_overrides[get_git_service] = lambda: fake_git

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac, fake_git


@pytest.mark.asyncio
class TestRepositoryLinking:
    async def test_connect_refresh_disconnect_flow(self, client):
        http, fake_git = client

        # Create a project
        resp = await http.post("/api/projects/", json={"name": "Repo Project"})
        assert resp.status_code == 201
        project = resp.json()

        # Connect repository
        resp = await http.post(
            "/api/repositories/connect",
            json={
                "project_id": project["id"],
                "repo_full_name": "https://github.com/octocat/Hello-World",
                "installation_id": 123,
                "set_as_primary": True,
            },
        )
        assert resp.status_code == 201
        link = resp.json()
        assert link["provider"] == "github"
        assert link["repo_full_name"] == "octocat/Hello-World"
        assert link["default_branch"] == "main"
        assert link["status"] == "connected"

        # Project defaults updated
        resp = await http.get(f"/api/projects/{project['id']}")
        assert resp.status_code == 200
        proj_detail = resp.json()
        assert proj_detail["repo_full_name"] == "octocat/Hello-World"
        assert proj_detail["default_branch"] == "main"
        assert proj_detail["primary_repository_link_id"] == link["id"]

        # Refresh changes default branch
        fake_git.next_info = RepoInfo(full_name="octocat/Hello-World", default_branch="develop", private=False, html_url=None)
        resp = await http.post(f"/api/repositories/{link['id']}/refresh")
        assert resp.status_code == 200
        refreshed = resp.json()
        assert refreshed["default_branch"] == "develop"

        resp = await http.get(f"/api/projects/{project['id']}")
        proj_detail = resp.json()
        assert proj_detail["default_branch"] == "develop"

        # Disconnect clears project defaults
        resp = await http.delete(f"/api/repositories/{link['id']}")
        assert resp.status_code == 200
        disconnected = resp.json()
        assert disconnected["status"] == "disconnected"

        resp = await http.get(f"/api/projects/{project['id']}")
        proj_detail = resp.json()
        assert proj_detail["repo_full_name"] is None
        assert proj_detail["default_branch"] is None
        assert proj_detail["primary_repository_link_id"] is None

    async def test_connect_rolls_back_on_github_validation_failure(self, client):
        http, fake_git = client

        resp = await http.post("/api/projects/", json={"name": "Repo Project 2"})
        project_id = resp.json()["id"]

        fake_git.raise_exc = RepositoryAccessError("Access denied")

        resp = await http.post(
            "/api/repositories/connect",
            json={
                "project_id": project_id,
                "repo_full_name": "octocat/Hello-World",
                "installation_id": 123,
            },
        )
        assert resp.status_code == 403

        # No links persisted
        resp = await http.get(f"/api/repositories/?project_id={project_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []
