# -*- coding: utf-8 -*-

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.main import create_app
from backend.db.engine import create_test_engine
from backend.db.models import AgentDefinition, Base
from backend.db.session import get_session


async def _init_db():
    engine = await create_test_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    return engine, session_factory


@pytest.fixture()
def client_and_session_factory():
    engine, session_factory = asyncio.run(_init_db())

    async def override_get_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        yield client, session_factory

    asyncio.run(engine.dispose())


def test_agents_rest_and_ws_smoke(client_and_session_factory):
    client, session_factory = client_and_session_factory

    async def seed_definition():
        async with session_factory() as session:
            session.add(
                AgentDefinition(
                    id=str(uuid4()),
                    name="Demo Agent",
                    slug="demo-agent",
                    agent_type="demo",
                    description="Demo definition",
                    capabilities=["demo"],
                    is_enabled=True,
                    meta_data={},
                )
            )
            await session.commit()

    asyncio.run(seed_definition())

    # 1) List definitions
    resp = client.get("/api/agents/definitions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["slug"] == "demo-agent"

    # 2) Activate an agent
    resp = client.post(
        "/api/agents",
        json={"definition_slug": "demo-agent", "activate": True, "config": {"k": "v"}},
    )
    assert resp.status_code == 201
    agent = resp.json()
    assert agent["status"] == "active"
    agent_id = agent["id"]

    # 3) Write context and read it back
    resp = client.post(
        f"/api/agents/{agent_id}/context",
        json={"context_name": "default", "data": {"foo": "bar"}},
    )
    assert resp.status_code == 200
    ctx_body = resp.json()
    assert ctx_body["current_version"] == 1
    assert ctx_body["data"]["foo"] == "bar"

    resp = client.get(f"/api/agents/{agent_id}/context")
    assert resp.status_code == 200
    assert resp.json()["data"]["foo"] == "bar"

    # 4) Message history
    resp = client.post(
        f"/api/agents/{agent_id}/messages",
        json={"direction": "inbound", "payload": {"text": "hello"}, "correlation_id": "c1"},
    )
    assert resp.status_code == 201
    msg = resp.json()
    assert msg["payload"]["text"] == "hello"

    resp = client.get(f"/api/agents/{agent_id}/messages")
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) >= 1

    # 5) WebSocket stream smoke test
    with client.websocket_connect("/ws/agents/stream") as ws:
        client.post(
            f"/api/agents/{agent_id}/messages",
            json={"direction": "inbound", "payload": {"text": "ws"}},
        )
        event = ws.receive_json()
        assert event.get("event_type") in {"agent_message", "agent_activity"}
