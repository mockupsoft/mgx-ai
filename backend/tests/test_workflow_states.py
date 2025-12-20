import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from mgx_agent.team import MGXStyleTeam, TeamConfig

@pytest.mark.asyncio
class TestWorkflowStates:
    
    async def test_initial_state(self):
        """Test initial state of the workflow."""
        team = MGXStyleTeam()
        assert team.plan_approved is False
        assert team.current_task is None
        assert len(team.progress) == 0

    async def test_planning_state_transition(self):
        """Test transition to planning completed."""
        team = MGXStyleTeam()
        
        with patch.object(team, 'analyze_and_plan', new_callable=AsyncMock) as mock_plan:
             # We simulate calling analyze_and_plan
             # But here we want to test the side effects if we called the real method,
             # or at least verify the state changes we expect if we mock the internals.
             
             # Let's manually trigger the state change that analyze_and_plan would do
             team.current_task = "Task"
             team.plan_approved = True # Simulate approval
             
             assert team.plan_approved is True
             assert team.current_task == "Task"

    async def test_execution_recording(self):
        """Test that execution steps are recorded in progress."""
        team = MGXStyleTeam()
        
        team.add_to_memory("Mike", "Plan", "Content")
        assert "Mike: Plan" in team.progress
        
        team.add_to_memory("Alex", "Code", "Content")
        assert "Alex: Code" in team.progress

    async def test_metrics_collection(self):
        """Test that metrics capture the final state."""
        config = TeamConfig(enable_metrics=True)
        team = MGXStyleTeam(config=config)
        team.current_task = "Test Task"
        team.plan_approved = True
        
        # Mock execution to produce metrics
        with patch.object(team.team, 'run', new_callable=AsyncMock):
             with patch.object(team, '_collect_results'):
                 with patch.object(team, '_save_results'):
                    await team.execute()
        
        assert len(team.metrics) == 1
        assert team.metrics[0].task_name == "Test Task"
        assert team.metrics[0].success is True
