import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from mgx_agent.actions import AnalyzeTask, DraftPlan, WriteCode
from mgx_agent.team import MGXStyleTeam, TeamConfig

@pytest.mark.asyncio
class TestIncrementalDevelopment:
    
    async def test_add_feature_to_existing_project(self):
        """Test adding a feature to an existing project structure."""
        # Setup
        action = AnalyzeTask()
        
        # Mock LLM response to simulate understanding of existing structure
        mock_response = """
KARMAŞIKLIK: S
ÖNERİLEN_STACK: python
DOSYA_MANİFESTO:
- src/new_feature.py: New feature implementation
- tests/test_new_feature.py: Tests for new feature
TEST_STRATEJİSİ: pytest with 5 tests
"""
        action._aask = AsyncMock(return_value=mock_response)
        
        # Run analysis with existing stack context
        task = "Add a user profile feature"
        result = await action.run(task, target_stack="python")
        
        assert "DOSYA_MANİFESTO" in result
        assert "src/new_feature.py" in result
        
    async def test_fix_bug_in_existing_code(self):
        """Test fixing a bug in existing code."""
        # Setup
        action = WriteCode()
        
        # Mock LLM response for bug fix
        mock_response = """
FILE: src/buggy_module.py
def calculate_total(items):
    # Fixed off-by-one error
    return sum(item.price for item in items)
"""
        action._aask = AsyncMock(return_value=mock_response)
        action._execute_sandbox_testing = AsyncMock(return_value=True)
        
        # Run write code with bug fix instruction
        instruction = "Fix off-by-one error in calculate_total"
        result = await action.run(instruction, strict_mode=True)
        
        assert "FILE: src/buggy_module.py" in result
        assert "Fixed off-by-one error" in result
        
    async def test_refactor_existing_code(self):
        """Test refactoring existing code."""
        # Setup
        action = WriteCode()
        
        # Mock LLM response for refactor
        mock_response = """
FILE: src/legacy_module.py
class RefactoredClass:
    def new_method(self):
        pass
"""
        action._aask = AsyncMock(return_value=mock_response)
        action._execute_sandbox_testing = AsyncMock(return_value=True)
        
        # Run write code with refactor instruction
        instruction = "Refactor LegacyClass to use new pattern"
        result = await action.run(instruction, strict_mode=True)
        
        assert "FILE: src/legacy_module.py" in result
        assert "RefactoredClass" in result

    async def test_knowledge_reuse_conventions(self):
        """Test that agent reuses knowledge and follows conventions."""
        # Setup
        action = AnalyzeTask()
        
        # Mock LLM to simulate recognizing conventions
        mock_response = """
KARMAŞIKLIK: XS
ÖNERİLEN_STACK: python
DOSYA_MANİFESTO:
- src/utils.py: Reuse existing helper functions
TEST_STRATEJİSİ: pytest matching existing patterns
"""
        action._aask = AsyncMock(return_value=mock_response)
        
        task = "Add helper function"
        result = await action.run(task)
        
        assert "Reuse existing helper functions" in result

    async def test_incremental_workflow(self):
        """Test the full incremental development workflow."""
        config = TeamConfig(auto_approve_plan=True)
        team = MGXStyleTeam(config=config)
        
        # We need a plan first for execute to proceed (in auto approve mode, analyze_and_plan approves it)
        # Or we can just manually set approved
        team.plan_approved = True
        team.current_task = "Task"
        
        # Mock the team execution
        with patch.object(team.team, 'run', new_callable=AsyncMock) as mock_run:
             # Simulate collecting results from the run
            with patch.object(team, '_collect_raw_results') as mock_collect:
                mock_collect.return_value = ("code", "tests", "review")
                with patch.object(team, '_save_results'):
                     await team.execute()
                     assert mock_run.called
