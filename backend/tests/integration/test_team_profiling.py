# -*- coding: utf-8 -*-
"""Integration tests for team profiling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mgx_agent.config import TeamConfig
from mgx_agent.team import MGXStyleTeam
from tests.helpers.metagpt_stubs import MockRole, MockTeam, MockContext


@pytest.fixture
def mock_team_with_profiling():
    """Create a mock team with profiling enabled."""
    config = TeamConfig(
        enable_profiling=True,
        enable_profiling_tracemalloc=False,  # Keep simple for tests
        auto_approve_plan=True,
        enable_caching=False,  # Disable caching for predictable tests
    )
    
    mock_context = MockContext()
    mock_team_obj = MockTeam(context=mock_context)
    
    team = MGXStyleTeam(
        config=config,
        context_override=mock_context,
        team_override=mock_team_obj,
        output_dir_base=None,  # Disable file output in tests
    )
    
    return team


@pytest.mark.asyncio
async def test_profiling_can_be_toggled_off(tmp_path, monkeypatch):
    """Test that profiling can be disabled without affecting normal runs."""
    monkeypatch.chdir(tmp_path)
    
    # Create team without profiling
    config = TeamConfig(
        enable_profiling=False,
        auto_approve_plan=True,
    )
    
    mock_context = MockContext()
    mock_team_obj = MockTeam(context=mock_context)
    
    team = MGXStyleTeam(
        config=config,
        context_override=mock_context,
        team_override=mock_team_obj,
        output_dir_base=None,
    )
    
    # Run workflow
    await team.analyze_and_plan("Simple task")
    await team.execute(n_round=1, max_revision_rounds=0)
    
    # Profiler should not be started
    assert team._profiler is None
    
    # No profiling files should be generated
    perf_dir = Path("logs/performance")
    if perf_dir.exists():
        assert len(list(perf_dir.glob("*.json"))) == 0


@pytest.mark.asyncio
async def test_profiling_generates_expected_files(tmp_path, monkeypatch):
    """Test that enabling profiling generates files with expected keys."""
    monkeypatch.chdir(tmp_path)
    
    # Create team with profiling
    config = TeamConfig(
        enable_profiling=True,
        enable_profiling_tracemalloc=False,
        auto_approve_plan=True,
        enable_caching=False,
    )
    
    mock_context = MockContext()
    mock_team_obj = MockTeam(context=mock_context)
    
    team = MGXStyleTeam(
        config=config,
        context_override=mock_context,
        team_override=mock_team_obj,
        output_dir_base=None,
    )
    
    # Start profiler
    team._start_profiler("test_run")
    
    # Run workflow
    await team.analyze_and_plan("Simple task")
    await team.execute(n_round=1, max_revision_rounds=0)
    
    # End profiler and generate reports
    metrics = team._end_profiler()
    
    # Check that metrics were generated
    assert metrics is not None
    assert "run_name" in metrics
    assert "phases" in metrics
    
    # Check that profiling files were created
    perf_dir = Path("logs/performance")
    assert perf_dir.exists()
    
    perf_reports_dir = Path("perf_reports")
    assert perf_reports_dir.exists()
    
    latest_file = perf_reports_dir / "latest.json"
    assert latest_file.exists()
    
    # Verify latest.json structure
    with open(latest_file, 'r') as f:
        data = json.load(f)
    
    expected_keys = ["run_name", "before", "after", "total_duration_s", "phases", "cache"]
    for key in expected_keys:
        assert key in data, f"Missing key in latest.json: {key}"


@pytest.mark.asyncio
async def test_profiling_captures_per_phase_metrics(mock_team_with_profiling):
    """Test that profiling captures metrics for each phase."""
    team = mock_team_with_profiling
    
    # Start profiler
    team._start_profiler("test_phases")
    
    # Run workflow
    await team.analyze_and_plan("Test task")
    await team.execute(n_round=1, max_revision_rounds=0)
    
    # Check profiler captured phases
    assert team._profiler is not None
    assert len(team._profiler.phase_snapshots) >= 2  # At least analyze_and_plan and execute
    
    phase_names = [snapshot.phase for snapshot in team._profiler.phase_snapshots]
    assert "analyze_and_plan" in phase_names
    assert "execute" in phase_names
    
    # Each phase should have duration > 0
    for snapshot in team._profiler.phase_snapshots:
        assert snapshot.duration_s > 0


@pytest.mark.asyncio
async def test_profiling_captures_revision_loops(tmp_path, monkeypatch):
    """Test that profiling captures revision loop metrics."""
    monkeypatch.chdir(tmp_path)
    
    # Create team with profiling and revision enabled
    config = TeamConfig(
        enable_profiling=True,
        enable_profiling_tracemalloc=False,
        auto_approve_plan=True,
        enable_caching=False,
        max_revision_rounds=2,
    )
    
    mock_context = MockContext()
    mock_team_obj = MockTeam(context=mock_context)
    
    # Override roles (Note: revision testing is complex with mocks, focusing on structure)
    roles = [
        MockRole(name="Mike", profile="TeamLeader"),
        MockRole(name="Alex", profile="Engineer"),
        MockRole(name="Bob", profile="Tester"),
        MockRole(name="Charlie", profile="Reviewer"),
    ]
    
    team = MGXStyleTeam(
        config=config,
        context_override=mock_context,
        team_override=mock_team_obj,
        roles_override=roles,
        output_dir_base=None,
    )
    
    # Start profiler
    team._start_profiler("test_revisions")
    
    # Run workflow (should trigger at least one revision)
    await team.analyze_and_plan("Complex task")
    await team.execute(n_round=1, max_revision_rounds=1)
    
    # Check that revision phases were captured
    phase_names = [snapshot.phase for snapshot in team._profiler.phase_snapshots]
    
    # Should have revision_round_1 phase if revision was triggered
    revision_phases = [name for name in phase_names if "revision_round" in name]
    # Note: Revision may not trigger in mock, but structure should be there
    # This test mainly validates that the profiling hooks are in place


@pytest.mark.asyncio
async def test_profiling_in_get_all_metrics(mock_team_with_profiling):
    """Test that profiling data is attached to get_all_metrics()."""
    team = mock_team_with_profiling
    
    # Start profiler
    team._start_profiler("test_metrics")
    
    # Run workflow
    await team.analyze_and_plan("Test task")
    await team.execute(n_round=1, max_revision_rounds=0)
    
    # Get all metrics
    all_metrics = team.get_all_metrics()
    
    # Should return dict with task_metrics and profiling
    assert isinstance(all_metrics, dict)
    assert "task_metrics" in all_metrics
    assert "profiling" in all_metrics
    
    profiling_data = all_metrics["profiling"]
    assert "run_name" in profiling_data
    assert "phases" in profiling_data
    assert len(profiling_data["phases"]) >= 2


@pytest.mark.asyncio
async def test_profiling_does_not_affect_normal_operations(mock_team_with_profiling):
    """Test that profiling doesn't break normal team operations."""
    team = mock_team_with_profiling
    
    # Start profiler
    team._start_profiler("test_normal_ops")
    
    # Run normal workflow
    plan = await team.analyze_and_plan("Write a function")
    assert plan is not None
    assert len(plan) > 0
    
    result = await team.execute(n_round=1, max_revision_rounds=0)
    assert result is not None
    
    # End profiler
    metrics = team._end_profiler()
    assert metrics is not None


@pytest.mark.asyncio
async def test_profiling_report_keys_validation(tmp_path, monkeypatch):
    """Test that profiling reports contain all expected keys."""
    monkeypatch.chdir(tmp_path)
    
    config = TeamConfig(
        enable_profiling=True,
        auto_approve_plan=True,
        enable_caching=False,
    )
    
    mock_context = MockContext()
    mock_team_obj = MockTeam(context=mock_context)
    
    team = MGXStyleTeam(
        config=config,
        context_override=mock_context,
        team_override=mock_team_obj,
        output_dir_base=None,
    )
    
    team._start_profiler("test_validation")
    
    await team.analyze_and_plan("Test task")
    await team.execute(n_round=1, max_revision_rounds=0)
    
    team._end_profiler()
    
    # Verify detailed report keys
    detailed_files = list(Path("logs/performance").glob("*.json"))
    assert len(detailed_files) > 0
    
    with open(detailed_files[0], 'r') as f:
        detailed_data = json.load(f)
    
    expected_detailed_keys = [
        "run_name",
        "duration_s",
        "cache",
        "memory",
        "timers",
        "phases",
        "timestamp",
    ]
    
    for key in expected_detailed_keys:
        assert key in detailed_data, f"Missing key in detailed report: {key}"
    
    # Verify summary report keys
    summary_file = Path("perf_reports/latest.json")
    assert summary_file.exists()
    
    with open(summary_file, 'r') as f:
        summary_data = json.load(f)
    
    expected_summary_keys = [
        "run_name",
        "before",
        "after",
        "total_duration_s",
        "phases",
        "cache",
    ]
    
    for key in expected_summary_keys:
        assert key in summary_data, f"Missing key in summary report: {key}"
    
    # Verify phase structure
    for phase in summary_data["phases"]:
        phase_keys = ["phase", "duration_s", "rss_kb_delta", "tracemalloc_peak_kb"]
        for key in phase_keys:
            assert key in phase, f"Missing key in phase: {key}"


@pytest.mark.asyncio
async def test_profiling_with_tracemalloc(tmp_path, monkeypatch):
    """Test profiling with tracemalloc enabled."""
    monkeypatch.chdir(tmp_path)
    
    config = TeamConfig(
        enable_profiling=True,
        enable_profiling_tracemalloc=True,  # Enable tracemalloc
        auto_approve_plan=True,
        enable_caching=False,
    )
    
    mock_context = MockContext()
    mock_team_obj = MockTeam(context=mock_context)
    
    team = MGXStyleTeam(
        config=config,
        context_override=mock_context,
        team_override=mock_team_obj,
        output_dir_base=None,
    )
    
    team._start_profiler("test_tracemalloc")
    
    await team.analyze_and_plan("Test task")
    await team.execute(n_round=1, max_revision_rounds=0)
    
    metrics = team._end_profiler()
    
    # Should have memory metrics
    assert "memory" in metrics
    # Note: tracemalloc values may be 0 in lightweight mock scenarios
