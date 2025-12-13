import os
import shutil
import pytest
from click.testing import CliRunner
from mgx_cli.main import cli
from mgx_cli import __version__

@pytest.fixture
def runner():
    return CliRunner()

def test_version(runner):
    result = runner.invoke(cli, ['--version'])
    assert result.exit_code == 0
    assert __version__ in result.output

def test_init(runner):
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['init', 'my-project'])
        assert result.exit_code == 0
        assert os.path.exists('my-project/mgx.yaml')
        
        # Check content
        with open('my-project/mgx.yaml', 'r') as f:
            content = f.read()
            assert 'project_name: my-project' in content

def test_config_set_get(runner):
    # Mock config location to avoid messing with user home
    from unittest.mock import patch
    
    with runner.isolated_filesystem():
        mock_config = os.path.abspath('.mgx/config.yaml')
        
        with patch('mgx_cli.utils.config_manager.CONFIG_FILE', new=__import__('pathlib').Path(mock_config)):
             # We also need to mock CONFIG_DIR since it is used in save_config
             with patch('mgx_cli.utils.config_manager.CONFIG_DIR', new=__import__('pathlib').Path(os.path.dirname(mock_config))):
                
                # Test Set
                result = runner.invoke(cli, ['config', 'set', 'test_key', 'test_value'])
                assert result.exit_code == 0
                assert 'Set test_key = test_value' in result.output
                
                # Test Get
                result = runner.invoke(cli, ['config', 'get', 'test_key'])
                assert result.exit_code == 0
                assert 'test_key = test_value' in result.output
                
                # Test List
                result = runner.invoke(cli, ['config', 'list'])
                assert result.exit_code == 0
                assert 'test_key = test_value' in result.output

def test_workspace_list(runner):
    result = runner.invoke(cli, ['workspace', 'list'])
    assert result.exit_code == 0
    assert 'No workspaces found' in result.output

def test_project_list(runner):
    result = runner.invoke(cli, ['project', 'list'])
    assert result.exit_code == 0
    assert 'No projects found' in result.output
