import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from click.testing import CliRunner
from mgx_cli.main import cli
import json

@pytest.fixture
def runner():
    return CliRunner()

@patch('mgx_cli.commands.task.MGXStyleTeam')
@patch('mgx_cli.commands.task.TeamConfig')
def test_task_run_description(MockConfig, MockTeam, runner):
    # Setup mock
    mock_instance = MockTeam.return_value
    mock_instance.analyze_and_plan = AsyncMock()
    mock_instance.execute = AsyncMock()
    mock_instance.get_progress.return_value = "Progress Report"
    
    # Mock click.confirm to return True (approve plan)
    # But click.testing can provide input.
    
    result = runner.invoke(cli, ['task', 'Create a hello world'], input='y\n')
    
    assert result.exit_code == 0
    MockTeam.assert_called_once()
    mock_instance.analyze_and_plan.assert_called_with('Create a hello world')
    # Approve plan is called
    mock_instance.approve_plan.assert_called_once()
    mock_instance.execute.assert_called_once()
    assert "Görev Analizi ve Plan Oluşturma" in result.output
    assert "Sonuç" in result.output

@patch('mgx_cli.commands.task.MGXStyleTeam')
@patch('mgx_cli.commands.task.TeamConfig')
def test_task_run_json(MockConfig, MockTeam, runner):
    mock_instance = MockTeam.return_value
    mock_instance.analyze_and_plan = AsyncMock()
    mock_instance.execute = AsyncMock()
    
    with runner.isolated_filesystem():
        task_data = {
            "task": "Build a website",
            "target_stack": "react",
            "project_type": "web",
            "constraints": ["no-jquery"]
        }
        with open('task.json', 'w') as f:
            json.dump(task_data, f)
            
        result = runner.invoke(cli, ['task', '--json', 'task.json'])
        
        assert result.exit_code == 0
        MockTeam.assert_called_once()
        # Verify Config init
        call_kwargs = MockConfig.call_args.kwargs
        assert call_kwargs['target_stack'] == 'react'
        assert call_kwargs['constraints'] == ['no-jquery']
        
        mock_instance.analyze_and_plan.assert_called_with('Build a website')
        mock_instance.execute.assert_called_once()

@patch('mgx_cli.commands.task.MGXStyleTeam')
def test_task_no_args(MockTeam, runner):
    result = runner.invoke(cli, ['task'])
    assert result.exit_code != 0
    assert "Error: Please provide a task description or a JSON input file." in result.output
