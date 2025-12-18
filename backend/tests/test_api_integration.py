# -*- coding: utf-8 -*-
"""Backend API integration & E2E tests.

These tests exercise the FastAPI app as a black box via HTTP/WebSocket calls.

Design goals:
- No external services required (Postgres, GitHub, hosted LLMs, Docker daemon)
- Use the real routers + SQLAlchemy models against in-memory SQLite
- Verify multi-tenant scoping via workspace headers

Note:
The production API surface in this repo differs slightly from the ticket's
example paths. The tests below target the actual implemented routes:
- /api/workspaces
- /api/projects (workspace-scoped via X-Workspace-Id)
- /api/tasks (workspace-scoped via X-Workspace-Id)
- /api/runs  (workspace-scoped via X-Workspace-Id)
- /api/repositories (workspace-scoped via X-Workspace-Id)
- /ws/* WebSocket event streams

The suite is intentionally verbose/parametrized to provide broad router coverage.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional

import pytest

from backend.schemas import EventPayload, EventTypeEnum
from backend.services.events import get_event_broadcaster

from backend.tests.ws_client import WSClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _headers_for_workspace(workspace_id: str) -> Dict[str, str]:
    return {"X-Workspace-Id": workspace_id}


def _create_workspace(client, name: str, slug: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"name": name, "metadata": {"source": "test"}}
    if slug is not None:
        payload["slug"] = slug

    resp = client.post("/api/workspaces/", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_project(client, workspace_id: str, name: str, slug: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"name": name, "metadata": {"source": "test"}}
    if slug is not None:
        payload["slug"] = slug

    resp = client.post("/api/projects/", json=payload, headers=_headers_for_workspace(workspace_id))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_task(
    client,
    workspace_id: str,
    name: str,
    project_id: Optional[str] = None,
    description: str = "test desc",
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"name": name, "description": description, "config": {"k": "v"}}
    if project_id:
        payload["project_id"] = project_id

    resp = client.post("/api/tasks/", json=payload, headers=_headers_for_workspace(workspace_id))
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# REST: Workspaces
# ---------------------------------------------------------------------------


def test_workspaces_list_empty(client):
    resp = client.get("/api/workspaces/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["skip"] == 0
    assert body["limit"] == 10


@pytest.mark.parametrize(
    "payload,status",
    [
        ({}, 422),
        ({"name": ""}, 422),
        ({"name": 123}, 422),
        ({"name": "ok", "metadata": "nope"}, 422),
    ],
)
def test_workspaces_create_invalid_payloads(client, payload, status):
    resp = client.post("/api/workspaces/", json=payload)
    assert resp.status_code == status


def test_workspaces_create_get_update_delete(client):
    ws = _create_workspace(client, name="WS One", slug="ws-one")

    # Read
    resp = client.get(f"/api/workspaces/{ws['id']}")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "ws-one"

    # Update
    resp = client.put(
        f"/api/workspaces/{ws['id']}",
        json={"name": "WS One Renamed", "metadata": {"a": 1}},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "WS One Renamed"
    assert resp.json()["metadata"]["a"] == 1

    # Update slug conflict
    ws2 = _create_workspace(client, name="WS Two", slug="ws-two")
    resp = client.put(f"/api/workspaces/{ws2['id']}", json={"slug": "ws-one"})
    assert resp.status_code == 409

    # Delete
    resp = client.delete(f"/api/workspaces/{ws['id']}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    resp = client.get(f"/api/workspaces/{ws['id']}")
    assert resp.status_code == 404


def test_workspaces_pagination_and_sql_injection_strings(client):
    _create_workspace(client, name="WS A")
    _create_workspace(client, name="WS B")

    # SQL injection-like string should not crash or break DB.
    inj = _create_workspace(client, name="WS C", slug="';DROP TABLE workspaces;--")
    assert "DROP TABLE" in inj["slug"]

    resp = client.get("/api/workspaces/", params={"skip": 1, "limit": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 1


# ---------------------------------------------------------------------------
# REST: Projects (workspace-scoped)
# ---------------------------------------------------------------------------


def test_projects_crud_and_isolation(client):
    ws1 = _create_workspace(client, "Projects WS1")
    ws2 = _create_workspace(client, "Projects WS2")

    # List includes default project created at workspace creation.
    resp = client.get("/api/projects/", headers=_headers_for_workspace(ws1["id"]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1

    proj = _create_project(client, ws1["id"], "My Project", slug="my-project")

    resp = client.get(f"/api/projects/{proj['id']}", headers=_headers_for_workspace(ws1["id"]))
    assert resp.status_code == 200
    assert resp.json()["slug"] == "my-project"

    # Cross-workspace isolation
    resp = client.get(f"/api/projects/{proj['id']}", headers=_headers_for_workspace(ws2["id"]))
    assert resp.status_code == 404

    # Update
    resp = client.put(
        f"/api/projects/{proj['id']}",
        headers=_headers_for_workspace(ws1["id"]),
        json={"name": "My Project Renamed", "run_branch_prefix": "mgx2"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "My Project Renamed"
    assert resp.json()["run_branch_prefix"] == "mgx2"

    # Duplicate slug
    _ = _create_project(client, ws1["id"], "Other", slug="other")
    resp = client.put(
        f"/api/projects/{proj['id']}",
        headers=_headers_for_workspace(ws1["id"]),
        json={"slug": "other"},
    )
    assert resp.status_code == 409

    # Delete
    resp = client.delete(f"/api/projects/{proj['id']}", headers=_headers_for_workspace(ws1["id"]))
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


def test_projects_missing_workspace_header_defaults_to_default_workspace(client):
    # get_workspace_context will create a default workspace if none is provided.
    resp = client.get("/api/projects/")
    assert resp.status_code == 200
    assert "items" in resp.json()


# ---------------------------------------------------------------------------
# REST: Tasks (workspace-scoped)
# ---------------------------------------------------------------------------


def test_tasks_crud_filtering_and_isolation(client):
    ws1 = _create_workspace(client, "Tasks WS1")
    ws2 = _create_workspace(client, "Tasks WS2")

    task = _create_task(client, ws1["id"], "Task A")

    # List
    resp = client.get("/api/tasks/", headers=_headers_for_workspace(ws1["id"]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == task["id"]

    # Cross-workspace isolation
    resp = client.get("/api/tasks/", headers=_headers_for_workspace(ws2["id"]))
    assert resp.status_code == 200
    assert resp.json()["items"] == []

    # Filtering - invalid status
    resp = client.get("/api/tasks/", headers=_headers_for_workspace(ws1["id"]), params={"status": "nope"})
    assert resp.status_code == 400

    # Read
    resp = client.get(f"/api/tasks/{task['id']}", headers=_headers_for_workspace(ws1["id"]))
    assert resp.status_code == 200

    # Update via PATCH
    resp = client.patch(
        f"/api/tasks/{task['id']}",
        headers=_headers_for_workspace(ws1["id"]),
        json={"description": "updated"},
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "updated"

    # Update via PUT alias
    resp = client.put(
        f"/api/tasks/{task['id']}",
        headers=_headers_for_workspace(ws1["id"]),
        json={"name": "Task A+"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Task A+"

    # Delete
    resp = client.delete(f"/api/tasks/{task['id']}", headers=_headers_for_workspace(ws1["id"]))
    assert resp.status_code == 200

    resp = client.get(f"/api/tasks/{task['id']}", headers=_headers_for_workspace(ws1["id"]))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# REST: Runs (workspace-scoped)
# ---------------------------------------------------------------------------


@dataclass
class DummyTaskExecutor:
    async def execute_task(self, **kwargs):  # noqa: ANN003
        await asyncio.sleep(0)
        return {"ok": True, **kwargs}

    async def approve_plan(self, run_id: str, approved: bool):
        await asyncio.sleep(0)
        return {"run_id": run_id, "approved": approved}


def test_runs_crud_and_status_transitions(client, monkeypatch):
    # Patch router-level get_task_executor() to avoid spawning real long-running jobs.
    import backend.routers.runs as runs_router

    monkeypatch.setattr(runs_router, "get_task_executor", lambda: DummyTaskExecutor())

    ws = _create_workspace(client, "Runs WS")
    task = _create_task(client, ws["id"], "Task for runs")

    # Create run
    resp = client.post("/api/runs/", headers=_headers_for_workspace(ws["id"]), json={"task_id": task["id"]})
    assert resp.status_code == 201, resp.text
    run = resp.json()
    assert run["task_id"] == task["id"]
    assert run["status"] == "pending"

    # List
    resp = client.get("/api/runs/", headers=_headers_for_workspace(ws["id"]), params={"task_id": task["id"]})
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    # Update status via PATCH
    resp = client.patch(
        f"/api/runs/{run['id']}",
        headers=_headers_for_workspace(ws["id"]),
        params={"status": "running"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"

    # Update status via PUT alias
    resp = client.put(
        f"/api/runs/{run['id']}",
        headers=_headers_for_workspace(ws["id"]),
        params={"status": "completed"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    # Approve endpoint (smoke)
    resp = client.post(
        f"/api/runs/{run['id']}/approve",
        headers=_headers_for_workspace(ws["id"]),
        json={"approved": True},
    )
    assert resp.status_code == 200

    # Delete
    resp = client.delete(f"/api/runs/{run['id']}", headers=_headers_for_workspace(ws["id"]))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# REST: Git repositories (mocked GitService)
# ---------------------------------------------------------------------------


class DummyRepoInfo:
    def __init__(self, full_name: str, default_branch: str):
        self.full_name = full_name
        self.default_branch = default_branch
        self.private = False
        self.html_url = f"https://github.com/{full_name}"


class DummyGitService:
    async def fetch_repo_info(self, repo_full_name: str, installation_id: Optional[int] = None):  # noqa: ARG002
        # Basic normalization check is performed in the real GitService; we keep it simple here.
        if repo_full_name == "missing/repo":
            from backend.services.git import RepositoryNotFoundError

            raise RepositoryNotFoundError("Repository not found")
        return DummyRepoInfo(full_name=repo_full_name, default_branch="main")


def test_repositories_connect_refresh_disconnect(client):
    from backend.services.git import get_git_service

    client.app.dependency_overrides[get_git_service] = lambda: DummyGitService()

    ws = _create_workspace(client, "Repo WS")
    proj = _create_project(client, ws["id"], "Repo Project")

    # Test access
    resp = client.post(
        "/api/repositories/test",
        headers=_headers_for_workspace(ws["id"]),
        json={"repo_full_name": "acme/repo", "installation_id": None},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Connect
    resp = client.post(
        "/api/repositories/connect",
        headers=_headers_for_workspace(ws["id"]),
        json={
            "project_id": proj["id"],
            "repo_full_name": "acme/repo",
            "installation_id": None,
            "set_as_primary": True,
            "reference_branch": None,
        },
    )
    assert resp.status_code == 201, resp.text
    link = resp.json()
    assert link["repo_full_name"] == "acme/repo"
    assert link["status"] == "connected"

    # Duplicate connect -> conflict
    resp = client.post(
        "/api/repositories/connect",
        headers=_headers_for_workspace(ws["id"]),
        json={
            "project_id": proj["id"],
            "repo_full_name": "acme/repo",
            "installation_id": None,
            "set_as_primary": False,
            "reference_branch": None,
        },
    )
    assert resp.status_code == 409

    # List
    resp = client.get("/api/repositories/", headers=_headers_for_workspace(ws["id"]))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    # Refresh
    resp = client.post(f"/api/repositories/{link['id']}/refresh", headers=_headers_for_workspace(ws["id"]))
    assert resp.status_code == 200
    assert resp.json()["status"] == "connected"

    # Disconnect
    resp = client.delete(f"/api/repositories/{link['id']}", headers=_headers_for_workspace(ws["id"]))
    assert resp.status_code == 200
    assert resp.json()["status"] == "disconnected"


def test_repositories_errors(client):
    from backend.services.git import get_git_service

    client.app.dependency_overrides[get_git_service] = lambda: DummyGitService()

    ws = _create_workspace(client, "Repo Errors")
    proj = _create_project(client, ws["id"], "Repo Errors Project")

    resp = client.post(
        "/api/repositories/test",
        headers=_headers_for_workspace(ws["id"]),
        json={"repo_full_name": "missing/repo", "installation_id": None},
    )
    assert resp.status_code == 404

    # Connect with non-existent project id
    resp = client.post(
        "/api/repositories/connect",
        headers=_headers_for_workspace(ws["id"]),
        json={
            "project_id": "does-not-exist",
            "repo_full_name": "acme/repo",
            "installation_id": None,
            "set_as_primary": False,
            "reference_branch": None,
        },
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# REST: Knowledge base (CRUD + semantic search) with mocked services
# ---------------------------------------------------------------------------


class DummyVectorDB:
    def _get_collection_name(self, workspace_id: str) -> str:  # noqa: D401
        return f"knowledge_{workspace_id}"

    async def delete(self, text_id: str, collection_name: Optional[str] = None):  # noqa: ARG002
        return True


class DummyRetriever:
    class _Result:
        def __init__(self, items: list):
            self.items = items
            self.total_count = len(items)
            self.search_time_ms = 1
            self.metadata = {"source": "dummy"}

    async def search_knowledge(self, req):  # noqa: ANN001
        # Return an empty list (search is mocked).
        return self._Result(items=[])


async def _override_knowledge_services() -> AsyncGenerator[dict, None]:
    yield {
        "vector_db": DummyVectorDB(),
        "retriever": DummyRetriever(),
        "rag_service": type("Dummy", (), {"get_knowledge_stats": lambda self, wid: {"total_items": 0}})(),
        "factory": type("Dummy", (), {"health_check": lambda self: {"overall": "healthy"}})(),
    }


def test_knowledge_crud_and_search(client):
    from backend.routers.knowledge import get_knowledge_services

    client.app.dependency_overrides[get_knowledge_services] = _override_knowledge_services

    ws = _create_workspace(client, "KB WS")

    # Create knowledge item
    resp = client.post(
        f"/api/workspaces/{ws['id']}/knowledge",
        json={
            "title": "Doc",
            "content": "Hello world",
            "category": "documentation",
            "language": "en",
            "tags": ["t1"],
            "source": "manual",
            "author": "tester",
        },
    )
    assert resp.status_code in (200, 201)
    item = resp.json()

    # List
    resp = client.get(f"/api/workspaces/{ws['id']}/knowledge")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Get
    resp = client.get(f"/api/workspaces/{ws['id']}/knowledge/{item['id']}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Doc"

    # Update
    resp = client.put(
        f"/api/workspaces/{ws['id']}/knowledge/{item['id']}",
        json={"content": "Hello updated"},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "Hello updated"

    # Search (mocked)
    resp = client.post(
        f"/api/workspaces/{ws['id']}/knowledge/search",
        json={"query": "hello", "top_k": 5, "min_relevance_score": 0.0},
    )
    assert resp.status_code == 200
    assert resp.json()["items"] == []

    # Delete (uses mocked vector db)
    resp = client.delete(f"/api/workspaces/{ws['id']}/knowledge/{item['id']}")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# REST: Cost tracking (workspace-level)
# ---------------------------------------------------------------------------


def test_costs_budget_and_summary(client):
    ws = _create_workspace(client, "Cost WS")

    # Create budget
    resp = client.post(
        f"/api/workspaces/{ws['id']}/budget",
        json={"monthly_budget_usd": 100.0, "alert_threshold_percent": 80, "alert_emails": [], "hard_limit": False},
    )
    assert resp.status_code == 200
    budget = resp.json()
    assert budget["workspace_id"] == ws["id"]

    # Costs summary should be available even with no usage.
    resp = client.get(f"/api/workspaces/{ws['id']}/costs")
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["period"] == "month"
    assert "total_cost" in summary

    # Budget read
    resp = client.get(f"/api/workspaces/{ws['id']}/budget")
    assert resp.status_code == 200
    assert resp.json()["workspace_id"] == ws["id"]


def test_costs_execution_costs_empty(client):
    resp = client.get("/api/executions/exec-unknown/costs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["execution_id"] == "exec-unknown"


# ---------------------------------------------------------------------------
# REST: LLM provider inspection (no external calls)
# ---------------------------------------------------------------------------


def test_llm_health_and_route(client):
    resp = client.get("/api/llm/health")
    assert resp.status_code == 200
    health = resp.json()
    assert "providers" in health
    assert any(p["provider"] == "openai" for p in health["providers"])

    resp = client.post("/api/llm/route", json={"required_capability": "code", "strategy": "balanced"})
    assert resp.status_code == 200
    chosen = resp.json()
    assert "provider" in chosen and "model" in chosen

    resp = client.post("/api/llm/route", json={"strategy": "does_not_exist"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# WebSockets: Real-time event streaming
# ---------------------------------------------------------------------------


def test_ws_global_stream_receives_published_events(client):
    broadcaster = get_event_broadcaster()

    with WSClient(client, "/ws/stream") as ws:
        event = EventPayload(
            event_type=EventTypeEnum.PROGRESS,
            task_id="task-123",
            run_id="run-456",
            message="hi",
            payload={"step": 1},
            source="test",
        )

        asyncio.get_event_loop().run_until_complete(broadcaster.publish(event))

        received = ws.receive_json()
        assert received["event_type"] == EventTypeEnum.PROGRESS.value
        assert received["task_id"] == "task-123"
        assert received["run_id"] == "run-456"


def test_ws_task_stream_filters_by_task_id(client):
    broadcaster = get_event_broadcaster()

    with WSClient(client, "/ws/tasks/t1") as ws1, WSClient(client, "/ws/tasks/t2") as ws2:
        event1 = EventPayload(
            event_type=EventTypeEnum.ANALYSIS_START,
            task_id="t1",
            run_id=None,
            message="start",
            payload={},
            source="test",
        )

        asyncio.get_event_loop().run_until_complete(broadcaster.publish(event1))

        received1 = ws1.receive_json()
        assert received1["task_id"] == "t1"

        # ws2 should not receive the t1 event; publish a t2 event to confirm it still works.
        event2 = EventPayload(
            event_type=EventTypeEnum.ANALYSIS_START,
            task_id="t2",
            run_id=None,
            message="start",
            payload={},
            source="test",
        )
        asyncio.get_event_loop().run_until_complete(broadcaster.publish(event2))

        received2 = ws2.receive_json()
        assert received2["task_id"] == "t2"


def test_ws_multiple_concurrent_connections_receive_ordered_messages(client):
    broadcaster = get_event_broadcaster()

    with WSClient(client, "/ws/stream") as ws_a, WSClient(client, "/ws/stream") as ws_b:
        event1 = EventPayload(
            event_type=EventTypeEnum.PROGRESS,
            task_id="t-order",
            run_id="r-order",
            message="1",
            payload={"i": 1},
            source="test",
        )
        event2 = EventPayload(
            event_type=EventTypeEnum.PROGRESS,
            task_id="t-order",
            run_id="r-order",
            message="2",
            payload={"i": 2},
            source="test",
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(broadcaster.publish(event1))
        loop.run_until_complete(broadcaster.publish(event2))

        a1 = ws_a.receive_json()
        a2 = ws_a.receive_json()
        b1 = ws_b.receive_json()
        b2 = ws_b.receive_json()

        assert [a1["payload"]["i"], a2["payload"]["i"]] == [1, 2]
        assert [b1["payload"]["i"], b2["payload"]["i"]] == [1, 2]


# ---------------------------------------------------------------------------
# Auth-ish checks (RBAC dependency errors are deterministic)
# ---------------------------------------------------------------------------


def test_rbac_requires_user_header(client):
    # RBAC endpoints require X-User-ID header; we verify missing auth is rejected.
    resp = client.get("/api/rbac/workspaces/any/roles")
    assert resp.status_code in (401, 422)


# ---------------------------------------------------------------------------
# Error schema smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,url,expected",
    [
        ("get", "/api/workspaces/does-not-exist", 404),
        ("get", "/api/tasks/does-not-exist", 404),
        ("get", "/api/runs/does-not-exist", 404),
    ],
)
def test_common_404s(client, method, url, expected):
    resp = getattr(client, method)(url)
    assert resp.status_code == expected
    # FastAPI default error format uses {"detail": ...}
    assert "detail" in resp.json()
