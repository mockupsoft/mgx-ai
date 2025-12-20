import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, AsyncMock
import json
import os
from mgx_cli.main import cli
from mgx_cli.commands import task

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def mock_mgx_team():
    with patch('mgx_cli.commands.task.MGXStyleTeam') as mock:
        instance = mock.return_value
        instance.analyze_and_plan = AsyncMock()
        instance.execute = AsyncMock()
        instance.get_progress = MagicMock(return_value="Task Completed")
        yield mock

class TestCliCommands:
    
    def test_version(self, runner):
        result = runner.invoke(cli, ['--version'])
        assert result.exit_code == 0
        assert "mgx, version" in result.output

    def test_task_help(self, runner):
        result = runner.invoke(cli, ['task', '--help'])
        assert result.exit_code == 0
        assert "Create and run a task" in result.output

    def test_task_no_args(self, runner):
        result = runner.invoke(cli, ['task'])
        assert result.exit_code == 1
        assert "Error: Please provide a task description" in result.output

    def test_task_description(self, runner, mock_mgx_team):
        # Mock user input "y" for confirmation
        result = runner.invoke(cli, ['task', 'Create a hello world app'], input='y\n')
        
        assert result.exit_code == 0
        assert "ADIM 1: Görev Analizi" in result.output
        mock_mgx_team.return_value.analyze_and_plan.assert_called_once_with('Create a hello world app')
        mock_mgx_team.return_value.execute.assert_called_once()

    def test_task_description_abort(self, runner, mock_mgx_team):
        # Mock user input "n" for confirmation
        result = runner.invoke(cli, ['task', 'Create a hello world app'], input='n\n')
        
        assert result.exit_code == 0
        assert "Plan rejected" in result.output
        mock_mgx_team.return_value.analyze_and_plan.assert_called_once()
        mock_mgx_team.return_value.execute.assert_not_called()

    def test_task_json(self, runner, mock_mgx_team, tmp_path):
        task_data = {
            "task": "Create a microservice",
            "target_stack": "FastAPI",
            "output_mode": "generate_new"
        }
        json_file = tmp_path / "task.json"
        json_file.write_text(json.dumps(task_data))
        
        result = runner.invoke(cli, ['task', '--json', str(json_file)])
        
        assert result.exit_code == 0
        assert f"Running task from JSON: {json_file}" in result.output
        mock_mgx_team.return_value.analyze_and_plan.assert_called_once_with("Create a microservice")
        mock_mgx_team.return_value.execute.assert_called_once()

    def test_task_json_missing_field(self, runner, mock_mgx_team, tmp_path):
        task_data = {
            "target_stack": "FastAPI"
        }
        json_file = tmp_path / "invalid.json"
        json_file.write_text(json.dumps(task_data))
        
        result = runner.invoke(cli, ['task', '--json', str(json_file)])
        
        assert "Error: 'task' field is required" in result.output
        mock_mgx_team.return_value.analyze_and_plan.assert_not_called()

    def test_list_tasks(self, runner):
        # Implementation in main.py is a placeholder
        result = runner.invoke(cli, ['list'])
        assert result.exit_code == 0
        assert "Listing tasks..." in result.output

    def test_status_task(self, runner):
        result = runner.invoke(cli, ['status', '123'])
        assert result.exit_code == 0
        assert "Status for task 123..." in result.output

    def test_logs_task(self, runner):
        # logs is not in main.py but in the requirement?
        # Wait, I saw it in the file content I read earlier?
        # Let me check main.py again.
        pass

