# -*- coding: utf-8 -*-

import pytest
from unittest.mock import AsyncMock, patch

from tests.helpers.metagpt_stubs import MockContext, MockMemory, MockMessage, MockRole, MockTeam

from mgx_agent.config import TeamConfig
from mgx_agent.team import MGXStyleTeam


@pytest.mark.asyncio
async def test_repeated_analyze_and_plan_hits_cache_and_skips_role_call():
    context = MockContext()
    team = MockTeam(context=context)

    task = "Write a tiny function"
    plan_content = (
        "---JSON_START---\n"
        "{\"task\": \"Write a tiny function\", \"complexity\": \"S\", \"plan\": \"1. Do it\"}\n"
        "---JSON_END---\n\n"
        "PLAN:\n1. Do it\n"
    )

    mike = MockRole(name="Mike", profile="TeamLeader")
    mike.analyze_task = AsyncMock(return_value=MockMessage(role="TeamLeader", content=plan_content))

    roles = [
        mike,
        MockRole(name="Alex", profile="Engineer"),
        MockRole(name="Bob", profile="Tester"),
        MockRole(name="Charlie", profile="Reviewer"),
    ]

    config = TeamConfig(
        enable_caching=True,
        cache_backend="memory",
        cache_max_entries=100,
        cache_ttl_seconds=3600,
        enable_metrics=False,
        enable_progress_bar=False,
        enable_streaming=False,
        human_reviewer=False,
        auto_approve_plan=False,
    )

    mgx = MGXStyleTeam(
        config=config,
        context_override=context,
        team_override=team,
        roles_override=roles,
        output_dir_base=None,
    )

    first = await mgx.analyze_and_plan(task)
    second = await mgx.analyze_and_plan(task)

    assert first == second
    assert mike.analyze_task.call_count == 1
    assert mgx._cache_hits >= 1


@pytest.mark.asyncio
async def test_writecode_caching_skips_mocked_llm_call_on_repeat():
    # Create a minimal MGXStyleTeam to host the cache facade.
    context = MockContext()
    team = MockTeam(context=context)

    config = TeamConfig(
        enable_caching=True,
        cache_backend="memory",
        cache_max_entries=100,
        cache_ttl_seconds=3600,
        enable_metrics=False,
        enable_progress_bar=False,
        enable_streaming=False,
        human_reviewer=False,
    )

    mgx = MGXStyleTeam(
        config=config,
        context_override=context,
        team_override=team,
        roles_override=[],
        output_dir_base=None,
    )
    mgx.set_task_spec(task="Do X", complexity="S", plan="1. Do X", is_revision=False, review_notes="")

    from mgx_agent.roles import Alex

    alex = Alex()
    alex._team_ref = mgx
    alex.llm = AsyncMock()
    alex.rc = MockContext()
    alex.rc.news = []
    alex.rc.memory = MockMemory()

    with patch('mgx_agent.roles.WriteCode') as MockWrite:
        mock_write = AsyncMock()
        mock_write.run = AsyncMock(return_value="def f():\n    return 1")
        MockWrite.return_value = mock_write

        await alex._act()
        await alex._act()

        assert mock_write.run.call_count == 1
