import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from mgx_agent.team import MGXStyleTeam, TeamConfig
from mgx_agent.roles import Mike

@pytest.mark.asyncio
class TestHumanApprovalWorkflow:
    
    async def test_approval_workflow_pauses(self):
        """Test that workflow pauses for approval when auto_approve is False."""
        # Setup
        config = TeamConfig(auto_approve_plan=False)
        team = MGXStyleTeam(config=config)
        
        # Mock Mike's analyze_task to return a dummy plan
        mock_message = MagicMock()
        mock_message.content = "PLAN: Do something"
        mock_message.role = "TeamLeader"
        
        # We need to mock the internal mike instance or the method used in analyze_and_plan
        # Looking at analyze_and_plan, it uses self._mike or creates a new Mike
        
        with patch.object(Mike, 'analyze_task', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_message
            
            # Execute analysis
            plan = await team.analyze_and_plan("Create a simple script")
            
            # Verify
            assert plan == "PLAN: Do something"
            assert team.plan_approved is False
            
            # Verify execution is blocked
            result = await team.execute()
            assert "Plan henüz onaylanmadı" in result

    async def test_approval_process(self):
        """Test the full approval process."""
        # Setup
        config = TeamConfig(auto_approve_plan=False)
        team = MGXStyleTeam(config=config)
        
        # Mock Mike's analyze_task
        mock_message = MagicMock()
        mock_message.content = "PLAN: Do something"
        mock_message.role = "TeamLeader"
        
        with patch.object(Mike, 'analyze_task', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_message
            
            # 1. Analysis
            await team.analyze_and_plan("Create a simple script")
            assert team.plan_approved is False
            
            # 2. Approval
            team.approve_plan()
            assert team.plan_approved is True
            
            # 3. Execution (Mocking the actual execution to avoid LLM calls)
            with patch.object(team.team, 'run', new_callable=AsyncMock) as mock_run:
                with patch.object(team, '_collect_results', return_value="Success"):
                    # We need to mock _collect_raw_results too to avoid errors in the loop
                    with patch.object(team, '_collect_raw_results', return_value=("code", "tests", "review")):
                        await team.execute()
                        assert mock_run.called

    async def test_auto_approve(self):
        """Test that workflow continues automatically when auto_approve is True."""
        # Setup
        config = TeamConfig(auto_approve_plan=True)
        team = MGXStyleTeam(config=config)
        
        # Mock Mike's analyze_task
        mock_message = MagicMock()
        mock_message.content = "PLAN: Do something"
        mock_message.role = "TeamLeader"
        
        with patch.object(Mike, 'analyze_task', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_message
            
            # Execute analysis
            await team.analyze_and_plan("Create a simple script")
            
            # Verify approved automatically
            assert team.plan_approved is True

    async def test_reviewer_request_changes(self):
        """Test the revision workflow when reviewer requests changes."""
        # Setup
        config = TeamConfig(
            auto_approve_plan=True,
            max_revision_rounds=2
        )
        team = MGXStyleTeam(config=config)
        
        # Mock Mike
        mock_message = MagicMock()
        mock_message.content = "PLAN: Do something"
        mock_message.role = "TeamLeader"
        
        with patch.object(Mike, 'analyze_task', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_message
            await team.analyze_and_plan("Task")
            
            # Mock execution with feedback loop
            # First call: Returns code + "CHANGE REQUESTED"
            # Second call: Returns code + "APPROVED"
            
            with patch.object(team.team, 'run', new_callable=AsyncMock) as mock_run:
                # We need to control the loop in execute()
                # The loop checks _collect_raw_results()
                
                # Mock _collect_raw_results to return different values on consecutive calls
                # 1. Initial run results
                # 2. First revision results
                # 3. Final results
                
                with patch.object(team, '_collect_raw_results') as mock_collect:
                    mock_collect.side_effect = [
                        ("code1", "test1", "DEĞİŞİKLİK GEREKLİ: Fix bugs"), # Initial run
                        ("code2", "test2", "APPROVED"),  # Revision run
                        ("code2", "test2", "APPROVED")   # Final collection
                    ]
                    
                    with patch.object(team, '_save_results'):
                        result = await team.execute()
                        
                        # Verify revision happened
                        assert team.metrics[-1].revision_rounds >= 1
                        assert team.metrics[-1].success is True
