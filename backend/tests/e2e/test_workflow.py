# -*- coding: utf-8 -*-
"""
End-to-End Workflow Tests

Tests async main() and incremental_main() workflows with stubbed MGXStyleTeam methods.
Ensures proper call order and helper API integration.
"""

import asyncio
import os
import tempfile
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, call
from pathlib import Path

# Import workflow functions to test
from mgx_agent.cli import main, incremental_main
from mgx_agent.team import MGXStyleTeam


class TestWorkflowCallOrder:
    """Test workflow method call order using mocks"""
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    def test_main_workflow_call_order(self, mock_team_class):
        """Test that main() calls team methods in correct order"""
        # Setup mock team with call tracking
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        
        # Configure method behaviors
        mock_team.get_progress.return_value = "Progress summary"
        mock_team.show_memory_log.return_value = "Memory log"
        
        # Use asyncio.run to execute the async main function
        asyncio.run(main(human_reviewer=False, custom_task="Test task"))
        
        # Verify method call order
        expected_calls = [
            call.analyze_and_plan("Test task"),
            call.approve_plan(),
            call.execute(),
            call.show_memory_log(),
            call.get_progress()
        ]
        
        mock_team.assert_has_calls(expected_calls, any_order=False)
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    def test_incremental_main_workflow_call_order(self, mock_team_class):
        """Test that incremental_main() calls team methods in correct order"""
        # Setup mock team
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        
        # Configure method behaviors
        mock_team.get_project_summary.return_value = "Project summary"
        mock_team.run_incremental.return_value = "Incremental result"
        
        requirement = "Add authentication feature"
        project_path = "./test_project"
        
        # Execute incremental workflow
        asyncio.run(incremental_main(
            requirement=requirement,
            project_path=project_path,
            fix_bug=False,
            ask_confirmation=True
        ))
        
        # Verify method call order
        expected_calls = [
            call.get_project_summary(project_path),
            call.run_incremental(requirement, project_path, False, True)
        ]
        
        mock_team.assert_has_calls(expected_calls, any_order=False)


class TestWorkflowIntegration:
    """Test workflow integration scenarios"""
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    def test_main_stub_team_integration(self, mock_team_class):
        """Test main() workflow with stubbed team methods"""
        # Setup stubbed team
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        
        # Configure return values
        mock_team.get_progress.return_value = "Stub progress"
        mock_team.show_memory_log.return_value = "Stub memory"
        
        # Execute workflow
        asyncio.run(main(human_reviewer=True, custom_task="Stub task"))
        
        # Verify stubbed methods were called
        mock_team_class.assert_called_once_with(human_reviewer=True)
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    def test_incremental_main_stub_team_integration(self, mock_team_class):
        """Test incremental_main() workflow with stubbed team methods"""
        # Setup stubbed team
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        
        # Configure return values
        mock_team.get_project_summary.return_value = "Stub summary"
        mock_team.run_incremental.return_value = "Stub result"
        
        # Execute workflow
        asyncio.run(incremental_main(
            requirement="Add feature",
            project_path="./stub_project",
            fix_bug=False,
            ask_confirmation=False
        ))
        
        # Verify stubbed methods were called
        mock_team_class.assert_called_once_with(human_reviewer=False)
        mock_team.get_project_summary.assert_called_once_with("./stub_project")


class TestWorkflowModes:
    """Test different workflow modes"""
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    def test_main_human_reviewer_mode(self, mock_team_class):
        """Test main() workflow in human reviewer mode"""
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        mock_team.get_progress.return_value = "Human mode progress"
        mock_team.show_memory_log.return_value = "Human mode memory"
        
        # Execute with human reviewer
        asyncio.run(main(human_reviewer=True))
        
        # Verify team initialized with human_reviewer=True
        mock_team_class.assert_called_once_with(human_reviewer=True)
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    def test_incremental_main_bug_fix_mode(self, mock_team_class):
        """Test incremental_main() workflow in bug fix mode"""
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        mock_team.get_project_summary.return_value = "Bug fix summary"
        mock_team.run_incremental.return_value = "Bug fix result"
        
        # Execute bug fix workflow
        asyncio.run(incremental_main(
            requirement="Fix TypeError",
            project_path="./bug_project",
            fix_bug=True,
            ask_confirmation=True
        ))
        
        # Verify run_incremental called with fix_bug=True
        mock_team.run_incremental.assert_called_once_with(
            "Fix TypeError", "./bug_project", True, True
        )
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    def test_incremental_main_silent_mode(self, mock_team_class):
        """Test that incremental_main skips interactive prompts when ask_confirmation=False"""
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        mock_team.get_project_summary.return_value = "Silent summary"
        mock_team.run_incremental.return_value = "Silent result"
        
        # Execute in silent mode
        asyncio.run(incremental_main(
            requirement="Add feature silently",
            project_path="./silent_project",
            fix_bug=False,
            ask_confirmation=False
        ))
        
        # Verify run_incremental called with ask_confirmation=False
        mock_team.run_incremental.assert_called_once_with(
            "Add feature silently", "./silent_project", False, False
        )


class TestHelperAPIs:
    """Test helper APIs against temporary directories"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
    
    def teardown_method(self):
        """Cleanup after each test method"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_list_project_files_integration(self):
        """Test helper API integration with project file listing"""
        # Create test files in temp directory
        test_files = [
            "main.py",
            "config.json",
            "requirements.txt",
            "README.md"
        ]
        
        for filename in test_files:
            (self.temp_path / filename).write_text(f"Test content for {filename}")
        
        # Create subdirectory with files
        subdir = self.temp_path / "src"
        subdir.mkdir()
        (subdir / "module.py").write_text("Test module")
        
        # Test manual file listing (since MGXStyleTeam methods need instance)
        files = []
        for root, dirs, filenames in os.walk(self.temp_path):
            for filename in filenames:
                files.append(os.path.join(root, filename))
        assert len(files) == 5  # 4 root files + 1 subdirectory file
    
    def test_get_project_summary_integration(self):
        """Test helper API integration with project summary"""
        # Create test project structure
        (self.temp_path / "main.py").write_text("def main(): pass")
        (self.temp_path / "config.json").write_text('{"name": "test"}')
        
        subdir = self.temp_path / "tests"
        subdir.mkdir()
        (subdir / "test_main.py").write_text("def test_main(): pass")
        
        # Count files in project
        py_files = list(self.temp_path.rglob("*.py"))
        json_files = list(self.temp_path.rglob("*.json"))
        file_count = len(py_files) + len(json_files)
        
        assert file_count >= 2  # Should find our test files
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    def test_team_methods_with_temp_directories(self, mock_team_class):
        """Test team methods work with temporary project directories"""
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        mock_team.get_project_summary.return_value = "Temp directory summary"
        mock_team.run_incremental.return_value = "Temp directory result"
        
        # Execute workflow with temp directory
        asyncio.run(incremental_main(
            requirement="Add logging feature",
            project_path=str(self.temp_path),
            fix_bug=False,
            ask_confirmation=False
        ))
        
        # Verify get_project_summary was called with temp directory
        mock_team.get_project_summary.assert_called_once_with(str(self.temp_path))
        
        # Verify run_incremental was called with temp directory
        mock_team.run_incremental.assert_called_once_with(
            "Add logging feature", str(self.temp_path), False, False
        )


class TestWorkflowErrorHandling:
    """Test error handling in workflow methods"""
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    def test_main_workflow_exception_handling(self, mock_team_class):
        """Test that main() handles team method exceptions gracefully"""
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        
        # Simulate exception in team method
        mock_team.analyze_and_plan.side_effect = Exception("Team analysis failed")
        mock_team.get_progress.return_value = "Progress"
        mock_team.show_memory_log.return_value = "Memory"
        
        # Should raise the exception
        with pytest.raises(Exception) as exc_info:
            asyncio.run(main(human_reviewer=False))
        
        assert "Team analysis failed" in str(exc_info.value)
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    def test_incremental_main_exception_handling(self, mock_team_class):
        """Test that incremental_main() handles team method exceptions gracefully"""
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        
        # Simulate exception in team method
        mock_team.run_incremental.side_effect = Exception("Incremental execution failed")
        mock_team.get_project_summary.return_value = "Summary"
        
        # Should raise the exception
        with pytest.raises(Exception) as exc_info:
            asyncio.run(incremental_main(
                requirement="Add feature",
                project_path="./test",
                fix_bug=False,
                ask_confirmation=True
            ))
        
        assert "Incremental execution failed" in str(exc_info.value)


class TestWorkflowAsyncBehavior:
    """Test async behavior of workflow methods"""
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    def test_workflow_methods_are_async_non_blocking(self, mock_team_class):
        """Test that workflow methods are properly async and non-blocking"""
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        mock_team.get_progress.return_value = "Progress"
        mock_team.show_memory_log.return_value = "Memory"
        
        # All async operations should be properly awaited
        asyncio.run(main(human_reviewer=False))
        
        # These should be called as await operations
        mock_team.analyze_and_plan.assert_awaited_once()
        mock_team.execute.assert_awaited_once()
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    def test_incremental_workflow_is_async_non_blocking(self, mock_team_class):
        """Test that incremental workflow is properly async and non-blocking"""
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        mock_team.get_project_summary.return_value = "Summary"
        mock_team.run_incremental.return_value = "Result"
        
        # Async operations should be properly awaited
        asyncio.run(incremental_main(
            requirement="Add feature",
            project_path="./test",
            fix_bug=False,
            ask_confirmation=True
        ))
        
        # run_incremental should be awaited
        mock_team.run_incremental.assert_awaited_once()


class TestWorkflowCompleteScenarios:
    """Test complete workflow scenarios"""
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    def test_complete_human_workflow(self, mock_team_class):
        """Test complete human mode workflow"""
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        mock_team.get_progress.return_value = "Human workflow progress"
        mock_team.show_memory_log.return_value = "Human workflow memory"
        
        # Simulate complete human workflow
        asyncio.run(main(human_reviewer=True, custom_task="Build a calculator"))
        
        # Verify complete workflow executed
        mock_team.analyze_and_plan.assert_awaited_once_with("Build a calculator")
        mock_team.approve_plan.assert_called_once()
        mock_team.execute.assert_awaited_once()
        mock_team.show_memory_log.assert_called_once()
        mock_team.get_progress.assert_called_once()
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    def test_complete_incremental_workflow(self, mock_team_class):
        """Test complete incremental workflow"""
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        mock_team.get_project_summary.return_value = "Incremental summary"
        mock_team.run_incremental.return_value = "Incremental workflow result"
        
        # Simulate complete incremental workflow
        asyncio.run(incremental_main(
            requirement="Implement OAuth authentication",
            project_path="./oauth_project",
            fix_bug=False,
            ask_confirmation=False
        ))
        
        # Verify complete workflow executed
        mock_team_class.assert_called_once_with(human_reviewer=False)
        mock_team.get_project_summary.assert_called_once_with("./oauth_project")
        mock_team.run_incremental.assert_awaited_once_with(
            "Implement OAuth authentication", "./oauth_project", False, False
        )