import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from mgx_agent.team import MGXStyleTeam, TeamConfig
from mgx_agent.roles import Mike

@pytest.mark.asyncio
class TestComplexScenarios:
    
    async def test_full_human_loop_workflow(self):
        """
        Complex Scenario:
        1. User requests feature
        2. Agent plans
        3. User approves
        4. Agent implements
        5. Tests fail (simulated via review feedback)
        6. Agent fixes
        7. Success
        """
        config = TeamConfig(
            auto_approve_plan=False,
            max_revision_rounds=2
        )
        team = MGXStyleTeam(config=config)
        
        task = "Build a complex feature"
        
        # 1. Plan
        mock_plan_msg = MagicMock()
        mock_plan_msg.content = "PLAN: Complex Plan"
        mock_plan_msg.role = "TeamLeader"
        
        with patch.object(Mike, 'analyze_task', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_plan_msg
            
            await team.analyze_and_plan(task)
            assert team.plan_approved is False
            
            # 2. Approve
            team.approve_plan()
            assert team.plan_approved is True
            
            # 3. Execute with Revision
            with patch.object(team.team, 'run', new_callable=AsyncMock) as mock_run:
                # Simulate feedback loop:
                # Round 1: Code written, Reviewer says "CHANGE REQUESTED"
                # Round 2: Code fixed, Reviewer says "APPROVED"
                
                with patch.object(team, '_collect_raw_results') as mock_collect:
                    mock_collect.side_effect = [
                        ("code_v1", "test_v1", "DEĞİŞİKLİK GEREKLİ: Fix logic error"),
                        ("code_v2", "test_v2", "APPROVED"),
                        ("code_v2", "test_v2", "APPROVED")
                    ]
                    
                    with patch.object(team, '_save_results'):
                        await team.execute()
            
            # Verify outcome
            metric = team.metrics[-1]
            assert metric.success is True
            assert metric.revision_rounds == 1
            assert metric.task_name == task

    async def test_concurrent_complex_workflows(self):
        """Test multiple complex workflows running in parallel."""
        # Using a helper to run the workflow
        async def run_workflow(id):
            team = MGXStyleTeam(config=TeamConfig(auto_approve_plan=True))
            
            with patch.object(Mike, 'analyze_task', new_callable=AsyncMock) as mock_analyze:
                mock_analyze.return_value = MagicMock(content=f"Plan {id}", role="TeamLeader")
                
                with patch.object(team.team, 'run', new_callable=AsyncMock):
                    with patch.object(team, '_collect_raw_results', return_value=("code", "test", "APPROVED")):
                         with patch.object(team, '_save_results'):
                            await team.analyze_and_plan(f"Task {id}")
                            await team.execute()
                            return team.metrics[-1]

        import asyncio
        results = await asyncio.gather(run_workflow(1), run_workflow(2), run_workflow(3))
        
        assert len(results) == 3
        assert all(r.success for r in results)
