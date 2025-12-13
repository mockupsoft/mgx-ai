# -*- coding: utf-8 -*-
"""
End-to-End CLI Tests

Tests the public entry points (mgx_agent.cli) and CLI routing behavior.
Ensures CLI functions are fully exercised without blocking input.
"""

import asyncio
import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call
from io import StringIO

# Import CLI functions to test
from mgx_agent.cli import cli_main, main, incremental_main


class TestCLIEntryPoints:
    """Test CLI entry point routing and flag handling"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.mock_stdout = StringIO()
        self.original_argv = sys.argv.copy()
    
    def teardown_method(self):
        """Cleanup after each test method"""
        sys.argv = self.original_argv
    
    @patch('mgx_agent.cli.asyncio.run')
    @patch('mgx_agent.cli.print')
    def test_cli_main_routes_to_main_no_flags(self, mock_print, mock_asyncio_run):
        """Test that CLI routes to main() when no flags are provided"""
        # Setup command line args
        sys.argv = ['mgx_agent.cli']
        
        # Execute CLI
        cli_main()
        
        # Verify asyncio.run was called (indicates routing worked)
        mock_asyncio_run.assert_called_once()

    @patch('mgx_agent.cli.asyncio.run')
    @patch('mgx_agent.cli.print')
    def test_cli_main_list_stacks_flag(self, mock_print, mock_asyncio_run):
        """Test that --list-stacks prints stacks and exits without running async entrypoints."""
        sys.argv = ['mgx_agent.cli', '--list-stacks']

        cli_main()

        mock_asyncio_run.assert_not_called()
        # Should print a header line about stacks
        assert any("Desteklenen Stack" in str(call.args[0]) for call in mock_print.call_args_list if call.args)
    
    @patch('mgx_agent.cli.asyncio.run')
    @patch('mgx_agent.cli.print')
    def test_cli_main_routes_to_main_human_flag(self, mock_print, mock_asyncio_run):
        """Test that CLI routes to main() with human_reviewer=True when --human flag"""
        # Setup command line args
        sys.argv = ['mgx_agent.cli', '--human']
        
        # Execute CLI
        cli_main()
        
        # Verify asyncio.run was called
        mock_asyncio_run.assert_called_once()
        
        # Verify human mode message is printed
        mock_print.assert_any_call("\n🧑 İNSAN MODU AKTİF: Charlie olarak siz review yapacaksınız!")
    
    @patch('mgx_agent.cli.asyncio.run')
    @patch('mgx_agent.cli.print')
    def test_cli_main_routes_to_main_task_flag(self, mock_print, mock_asyncio_run):
        """Test that CLI routes to main() with custom task when --task flag"""
        # Setup command line args
        sys.argv = ['mgx_agent.cli', '--task', 'Custom task description']
        
        # Execute CLI
        cli_main()
        
        # Verify asyncio.run was called
        mock_asyncio_run.assert_called_once()
        
        # Verify custom task message is printed
        mock_print.assert_any_call("\n📝 ÖZEL GÖREV: Custom task description\n")
    
    @patch('mgx_agent.cli.asyncio.run')
    @patch('mgx_agent.cli.print')
    def test_cli_main_routes_to_incremental_add_feature(self, mock_print, mock_asyncio_run):
        """Test that CLI routes to incremental_main() for --add-feature flag"""
        # Setup command line args
        sys.argv = ['mgx_agent.cli', '--add-feature', 'Add login system', '--project-path', './project']
        
        # Execute CLI
        cli_main()
        
        # Verify asyncio.run was called
        mock_asyncio_run.assert_called_once()
        
        # Verify incremental mode message is printed
        mock_print.assert_any_call("\n➕ YENİ ÖZELLİK EKLEME MODU")
    
    @patch('mgx_agent.cli.asyncio.run')
    @patch('mgx_agent.cli.print')
    def test_cli_main_routes_to_incremental_fix_bug(self, mock_print, mock_asyncio_run):
        """Test that CLI routes to incremental_main() for --fix-bug flag"""
        # Setup command line args
        sys.argv = ['mgx_agent.cli', '--fix-bug', 'TypeError fix', '--project-path', './project']
        
        # Execute CLI
        cli_main()
        
        # Verify asyncio.run was called
        mock_asyncio_run.assert_called_once()
        
        # Verify bug fix mode message is printed
        mock_print.assert_any_call("\n🐛 BUG DÜZELTME MODU")
    
    @patch('mgx_agent.cli.asyncio.run')
    @patch('mgx_agent.cli.print')
    def test_cli_main_no_confirm_flag(self, mock_print, mock_asyncio_run):
        """Test that CLI passes ask_confirmation=False when --no-confirm flag"""
        # Setup command line args
        sys.argv = ['mgx_agent.cli', '--add-feature', 'Add feature', '--no-confirm']
        
        # Execute CLI
        cli_main()
        
        # Verify asyncio.run was called
        mock_asyncio_run.assert_called_once()
        
        # Verify incremental mode message is printed
        mock_print.assert_any_call("\n➕ YENİ ÖZELLİK EKLEME MODU")
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    @patch('mgx_agent.cli.print')
    async def test_main_human_mode_messaging(self, mock_print, mock_team_class):
        """Test that main() propagates human_reviewer flag to MGXStyleTeam via TeamConfig."""
        # Setup mock team
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        mock_team.get_progress.return_value = "Progress summary"
        mock_team.show_memory_log.return_value = "Memory log"

        # Execute main with human mode
        await main(human_reviewer=True, custom_task="Custom task")

        # Verify MGXStyleTeam was created with a config that has human_reviewer=True
        assert mock_team_class.call_count == 1
        _, kwargs = mock_team_class.call_args
        assert "config" in kwargs
        assert kwargs["config"].human_reviewer is True

        # Verify team methods were called
        await mock_team.analyze_and_plan.assert_awaited_once_with("Custom task")
        mock_team.approve_plan.assert_called_once()
        await mock_team.execute.assert_awaited_once()
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    @patch('mgx_agent.cli.print')
    async def test_main_custom_task_propagation(self, mock_print, mock_team_class):
        """Test that main() propagates custom task to team analyze method."""
        # Setup mock team
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        mock_team.get_progress.return_value = "Progress summary"
        mock_team.show_memory_log.return_value = "Memory log"

        custom_task = "Calculate fibonacci numbers"

        # Execute main with custom task
        await main(human_reviewer=False, custom_task=custom_task)

        # Verify analyze_and_plan was called with custom task
        await mock_team.analyze_and_plan.assert_awaited_once_with(custom_task)
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    @patch('mgx_agent.cli.print')
    async def test_incremental_main_stub_team_integration(self, mock_print, mock_team_class):
        """Test that incremental_main() integrates with stub team methods"""
        # Setup mock team
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        mock_team.get_project_summary.return_value = "Project summary"
        mock_team.run_incremental.return_value = "Incremental result"
        
        requirement = "Add user authentication"
        project_path = "./test_project"
        
        # Execute incremental_main
        await incremental_main(
            requirement=requirement,
            project_path=project_path,
            fix_bug=False,
            ask_confirmation=True
        )
        
        # Verify team methods were called appropriately
        mock_team_class.assert_called_once_with(human_reviewer=False)
        mock_team.get_project_summary.assert_called_once_with(project_path)
        await mock_team.run_incremental.assert_awaited_once_with(
            requirement, project_path, False, True
        )
    
    def test_cli_help_flag(self):
        """Test that --help flag displays help and doesn't execute main function"""
        # Setup command line args
        sys.argv = ['mgx_agent.cli', '--help']
        
        # Execute CLI (should not raise, but we can't easily test SystemExit)
        # Just verify it doesn't crash and help is printed
        try:
            cli_main()
        except SystemExit as e:
            # If it does exit, verify it exits successfully (code 0 or None)
            assert e.code is None or e.code == 0
        except SystemError:
            # argparse might raise SystemError instead of SystemExit
            pass
    
    @patch('mgx_agent.cli.argparse.ArgumentParser.parse_args')
    @patch('mgx_agent.cli.asyncio.run')
    def test_cli_argument_parsing_errors(self, mock_asyncio_run, mock_parse_args):
        """Test CLI argument parsing with invalid arguments"""
        # Mock parse_args to raise error
        mock_parse_args.side_effect = SystemExit(2)
        
        # Execute CLI (should exit with error code)
        with pytest.raises(SystemExit) as exc_info:
            cli_main()
        
        assert exc_info.value.code == 2
        mock_asyncio_run.assert_not_called()


class TestCLIOutputAndErrorHandling:
    """Test CLI output formatting and error handling"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.mock_stdout = StringIO()
    
    @patch('mgx_agent.cli.print')
    async def test_main_mode_specific_output(self, mock_print):
        """Test that main() outputs appropriate mode-specific messages"""
        with patch('sys.stdout', self.mock_stdout):
            # Test human mode output
            await main(human_reviewer=True)
            
            # Verify human mode indicator is printed
            mock_print.assert_any_call("\n🧑 İNSAN MODU AKTİF: Charlie olarak siz review yapacaksınız!")
    
    @patch('mgx_agent.cli.print')
    async def test_incremental_mode_specific_output(self, mock_print):
        """Test that incremental_main() outputs appropriate mode-specific messages"""
        with patch('mgx_agent.cli.MGXStyleTeam') as mock_team_class:
            # Setup mock team
            mock_team = AsyncMock()
            mock_team_class.return_value = mock_team
            mock_team.get_project_summary.return_value = "Test summary"
            mock_team.run_incremental.return_value = "Test result"
            
            # Test feature addition mode
            await incremental_main(
                requirement="Add feature",
                fix_bug=False,
                ask_confirmation=True
            )
            
            # Verify incremental mode header is printed
            mock_print.assert_any_call("\n➕ YENİ ÖZELLİK EKLEME MODU")
    
    @patch('mgx_agent.cli.print')
    async def test_incremental_bug_fix_output(self, mock_print):
        """Test that incremental_main() outputs bug fix specific messages"""
        with patch('mgx_agent.cli.MGXStyleTeam') as mock_team_class:
            # Setup mock team
            mock_team = AsyncMock()
            mock_team_class.return_value = mock_team
            mock_team.get_project_summary.return_value = "Test summary"
            mock_team.run_incremental.return_value = "Test result"
            
            # Test bug fix mode
            await incremental_main(
                requirement="Fix TypeError",
                fix_bug=True,
                ask_confirmation=True
            )
            
            # Verify bug fix mode header is printed
            mock_print.assert_any_call("\n🐛 BUG DÜZELTME MODU")
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    async def test_main_stub_team_human_mode(self, mock_team_class):
        """Test that main() properly configures team for human mode"""
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        mock_team.get_progress.return_value = "Progress"
        mock_team.show_memory_log.return_value = "Memory"
        
        await main(human_reviewer=True)
        
        # Verify team is initialized with human_reviewer=True
        mock_team_class.assert_called_once_with(human_reviewer=True)
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    async def test_main_stub_team_custom_task(self, mock_team_class):
        """Test that main() properly configures team for custom task"""
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        mock_team.get_progress.return_value = "Progress"
        mock_team.show_memory_log.return_value = "Memory"
        
        custom_task = "Write a sorting algorithm"
        
        await main(human_reviewer=False, custom_task=custom_task)
        
        # Verify team is initialized with human_reviewer=False
        mock_team_class.assert_called_once_with(human_reviewer=False)


class TestCLIHumanModeIntegration:
    """Test CLI integration with human mode behavior"""
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    async def test_human_mode_team_configuration(self, mock_team_class):
        """Test that human mode properly configures the team"""
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        mock_team.get_progress.return_value = "Progress"
        mock_team.show_memory_log.return_value = "Memory"
        
        await main(human_reviewer=True, custom_task="Test task")
        
        # Verify team configuration
        mock_team_class.assert_called_once_with(human_reviewer=True)
        
        # Verify task execution
        await mock_team.analyze_and_plan.assert_awaited_once_with("Test task")
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    async def test_stub_team_method_calls(self, mock_team_class):
        """Test that stub team methods are called in correct sequence"""
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        mock_team.get_progress.return_value = "Progress"
        mock_team.show_memory_log.return_value = "Memory"
        
        await main(human_reviewer=False)
        
        # Verify method call sequence
        await mock_team.analyze_and_plan.assert_awaited_once()
        mock_team.approve_plan.assert_called_once()
        await mock_team.execute.assert_awaited_once()
        
        # Verify final output methods
        mock_team.show_memory_log.assert_called_once()
        mock_team.get_progress.assert_called_once()


class TestCLINonBlockingBehavior:
    """Test that CLI tests don't block on input"""
    
    @patch('mgx_agent.cli.asyncio.run')
    def test_cli_no_blocking_on_input(self, mock_asyncio_run):
        """Test that CLI execution doesn't block waiting for user input"""
        # This test verifies the CLI doesn't block by mocking asyncio.run
        sys.argv = ['mgx_agent.cli', '--human']
        
        # Should complete quickly without blocking
        cli_main()
        
        # Verify execution completed
        mock_asyncio_run.assert_called_once()
    
    @patch('mgx_agent.cli.asyncio.run')
    @patch('mgx_agent.cli.input', side_effect=EOFError)
    def test_cli_handles_input_exceptions_gracefully(self, mock_input, mock_asyncio_run):
        """Test that CLI handles input exceptions gracefully"""
        sys.argv = ['mgx_agent.cli', '--human']
        
        # Should not raise input-related exceptions
        try:
            cli_main()
        except (KeyboardInterrupt, EOFError):
            pytest.fail("CLI should handle input exceptions gracefully")
        
        mock_asyncio_run.assert_called_once()
    
    @patch('mgx_agent.cli.MGXStyleTeam')
    async def test_workflow_methods_are_async_non_blocking(self, mock_team_class):
        """Test that workflow methods are properly async and non-blocking"""
        mock_team = AsyncMock()
        mock_team_class.return_value = mock_team
        mock_team.get_progress.return_value = "Progress"
        mock_team.show_memory_log.return_value = "Memory"
        
        # All async operations should be properly awaited
        await main(human_reviewer=False)
        
        # These should be called as await operations
        await mock_team.analyze_and_plan.assert_awaited_once()
        await mock_team.execute.assert_awaited_once()