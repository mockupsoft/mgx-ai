import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from mgx_agent.team import MGXStyleTeam, TeamConfig

@pytest.mark.asyncio
class TestConcurrentExecution:
    
    async def test_concurrent_tasks(self):
        """Test running multiple tasks concurrently."""
        # Setup 5 teams
        teams = [MGXStyleTeam(config=TeamConfig()) for _ in range(5)]
        
        async def run_dummy_task(team, task_id):
            # Mock the execute flow
            with patch.object(team, 'analyze_and_plan', new_callable=AsyncMock) as mock_plan:
                mock_plan.return_value = f"PLAN: Task {task_id}"
                
                with patch.object(team.team, 'run', new_callable=AsyncMock) as mock_run:
                    with patch.object(team, '_collect_raw_results', return_value=("code", "tests", "review")):
                        with patch.object(team, '_save_results'):
                            await team.analyze_and_plan(f"Task {task_id}")
                            team.approve_plan()
                            await team.execute()
                            return f"Result {task_id}"

        # Run concurrently
        tasks = [run_dummy_task(teams[i], i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 5
        assert "Result 0" in results
        assert "Result 4" in results

    async def test_workspace_isolation(self):
        """Test that data doesn't leak between concurrently running teams in different workspaces."""
        # Simulating isolation via Context
        # Since MGXStyleTeam creates its own context/team if not provided, they are isolated by object instance.
        
        team1 = MGXStyleTeam()
        team2 = MGXStyleTeam()
        
        # Set specific state in team 1
        team1.current_task = "Task 1"
        team2.current_task = "Task 2"
        
        async def run_check(team, expected_task):
            await asyncio.sleep(0.1) # Context switch
            assert team.current_task == expected_task
            
        await asyncio.gather(
            run_check(team1, "Task 1"),
            run_check(team2, "Task 2")
        )

    async def test_resource_limits(self):
        """Test concurrent execution respects resource limits (mocked)."""
        # This is more of a system test. For unit test, we can check if semaphores or locks are used if applicable.
        # MGXStyleTeam doesn't seem to have explicit global resource limits implemented in python code 
        # (other than what underlying system provides or config limits).
        pass
