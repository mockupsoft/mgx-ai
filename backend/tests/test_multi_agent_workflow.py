# -*- coding: utf-8 -*-
"""Multi-agent workflow lifecycle tests.

These tests focus on the task execution lifecycle implemented by ``TaskExecutor``:
analysis -> plan -> approval -> execution -> completion/failure.

The actual MGX agents live in the external ``mgx_agent`` package; for this repo we
validate orchestration, event emission, and approval gating using mocks.
"""

import asyncio
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.schemas import EventTypeEnum
from backend.services.events import EventBroadcaster
from backend.services.executor import TaskExecutor


async def _collect_run_events(queue: asyncio.Queue, *, stop_event_types: set[str], timeout: float = 2.0):
    events: list[dict] = []
    while True:
        evt = await asyncio.wait_for(queue.get(), timeout=timeout)
        events.append(evt)
        if evt.get("event_type") in stop_event_types:
            return events


class TestTaskLifecycle:
    @pytest.mark.asyncio
    async def test_execute_task_happy_path_emits_events_in_order(self):
        broadcaster = EventBroadcaster()

        fake_team = MagicMock()
        fake_team.run = AsyncMock(
            return_value={
                "mike": {"analysis": "ok", "plan": ["step1", "step2"]},
                "alex": {"implementation": "done"},
                "bob": {"tests": "done"},
                "charlie": {"review": "approved"},
            }
        )

        team_provider = MagicMock()
        team_provider.get_team = AsyncMock(return_value=fake_team)

        fake_git = MagicMock()
        fake_git.cleanup_branch = AsyncMock(return_value=None)

        executor = TaskExecutor(team_provider=team_provider, git_service=fake_git)

        task_id = str(uuid4())
        run_id = str(uuid4())

        queue = await broadcaster.subscribe("sub-happy", [f"run:{run_id}"])

        with patch("backend.services.executor.get_event_broadcaster", return_value=broadcaster):
            task = asyncio.create_task(
                executor.execute_task(
                    task_id=task_id,
                    run_id=run_id,
                    task_description="Generate a small feature",
                    max_rounds=3,
                ),
            )

            seen_event_types: list[str] = []
            completed = False

            while not completed:
                evt = await asyncio.wait_for(queue.get(), timeout=2.0)
                seen_event_types.append(evt["event_type"])

                if evt["event_type"] == EventTypeEnum.APPROVAL_REQUIRED.value:
                    await executor.approve_plan(run_id, approved=True)

                if evt["event_type"] in {
                    EventTypeEnum.COMPLETION.value,
                    EventTypeEnum.FAILURE.value,
                }:
                    completed = True

            result = await asyncio.wait_for(task, timeout=2.0)

        assert result["status"] == "completed"
        assert fake_team.run.await_count == 1

        assert seen_event_types[:4] == [
            EventTypeEnum.ANALYSIS_START.value,
            EventTypeEnum.PLAN_READY.value,
            EventTypeEnum.APPROVAL_REQUIRED.value,
            EventTypeEnum.APPROVED.value,
        ]
        assert seen_event_types[-1] == EventTypeEnum.COMPLETION.value

    @pytest.mark.asyncio
    async def test_execute_task_rejected_plan_short_circuits_execution(self):
        broadcaster = EventBroadcaster()

        fake_team = MagicMock()
        fake_team.run = AsyncMock(return_value={"should_not": "run"})

        team_provider = MagicMock()
        team_provider.get_team = AsyncMock(return_value=fake_team)

        fake_git = MagicMock()
        fake_git.cleanup_branch = AsyncMock(return_value=None)

        executor = TaskExecutor(team_provider=team_provider, git_service=fake_git)

        task_id = str(uuid4())
        run_id = str(uuid4())

        queue = await broadcaster.subscribe("sub-reject", [f"run:{run_id}"])

        with patch("backend.services.executor.get_event_broadcaster", return_value=broadcaster):
            task = asyncio.create_task(
                executor.execute_task(
                    task_id=task_id,
                    run_id=run_id,
                    task_description="Do something risky",
                ),
            )

            # Wait until approval is requested, then reject.
            while True:
                evt = await asyncio.wait_for(queue.get(), timeout=2.0)
                if evt["event_type"] == EventTypeEnum.APPROVAL_REQUIRED.value:
                    await executor.approve_plan(run_id, approved=False)
                    break

            events = await _collect_run_events(
                queue,
                stop_event_types={EventTypeEnum.FAILURE.value, EventTypeEnum.COMPLETION.value},
            )

            result = await asyncio.wait_for(task, timeout=2.0)

        assert result["status"] == "rejected"
        assert fake_team.run.await_count == 0

        assert events[-1]["event_type"] == EventTypeEnum.FAILURE.value
        assert "rejected" in (events[-1].get("message") or "").lower()

    @pytest.mark.asyncio
    async def test_concurrent_runs_emit_isolated_events(self):
        broadcaster = EventBroadcaster()

        fake_team = MagicMock()
        fake_team.run = AsyncMock(return_value={"ok": True})

        team_provider = MagicMock()
        team_provider.get_team = AsyncMock(return_value=fake_team)

        fake_git = MagicMock()
        fake_git.cleanup_branch = AsyncMock(return_value=None)

        executor = TaskExecutor(team_provider=team_provider, git_service=fake_git)

        run_ids = [str(uuid4()) for _ in range(5)]
        queues = [await broadcaster.subscribe(f"sub-{i}", [f"run:{rid}"]) for i, rid in enumerate(run_ids)]

        with patch("backend.services.executor.get_event_broadcaster", return_value=broadcaster):
            tasks = [
                asyncio.create_task(
                    executor.execute_task(
                        task_id=str(uuid4()),
                        run_id=run_id,
                        task_description="Simple task",
                    )
                )
                for run_id in run_ids
            ]

            async def approve_when_requested(queue: asyncio.Queue, run_id: str):
                while True:
                    evt = await asyncio.wait_for(queue.get(), timeout=2.0)
                    if evt["event_type"] == EventTypeEnum.APPROVAL_REQUIRED.value:
                        await executor.approve_plan(run_id, approved=True)
                    if evt["event_type"] in {EventTypeEnum.COMPLETION.value, EventTypeEnum.FAILURE.value}:
                        return evt["event_type"]

            pairs = zip(queues, run_ids, strict=True)
            final_event_types = await asyncio.gather(
                *[approve_when_requested(q, rid) for q, rid in pairs]
            )

            results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=4.0)

        assert all(r["status"] == "completed" for r in results)
        assert all(evt_type == EventTypeEnum.COMPLETION.value for evt_type in final_event_types)
