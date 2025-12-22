# -*- coding: utf-8 -*-
"""
Pytest configuration and shared fixtures for MGX Agent tests
"""

import tempfile
import yaml
from pathlib import Path
from typing import Dict, Any
import pytest


@pytest.fixture
def tmp_yaml_file(tmp_path):
    """Create a temporary YAML file with test configuration data"""
    def _create_yaml_file(data: Dict[str, Any]) -> Path:
        yaml_file = tmp_path / "test_config.yaml"
        with open(yaml_file, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        return yaml_file
    return _create_yaml_file


@pytest.fixture
def sample_config_data():
    """Sample configuration data for testing"""
    return {
        'max_rounds': 8,
        'max_revision_rounds': 3,
        'max_memory_size': 100,
        'enable_caching': False,
        'enable_streaming': True,
        'enable_progress_bar': False,
        'enable_metrics': True,
        'enable_memory_cleanup': False,
        'human_reviewer': True,
        'auto_approve_plan': True,
        'default_investment': 5.0,
        'budget_multiplier': 2.5,
        'use_multi_llm': True,
        'log_level': 'debug',
        'verbose': True,
        'cache_ttl_seconds': 7200
    }


@pytest.fixture
def sample_task_metrics():
    """Sample task metrics data for testing"""
    import time
    
    start_time = time.time()
    end_time = start_time + 150.5  # 2.5 minutes
    
    return {
        'task_name': 'test_task',
        'start_time': start_time,
        'end_time': end_time,
        'success': True,
        'complexity': 'M',
        'token_usage': 1250,
        'estimated_cost': 2.75,
        'revision_rounds': 2,
        'error_message': ''
    }


@pytest.fixture
def mock_logger():
    """Mock logger for testing warning messages"""
    import logging
    
    logger = logging.getLogger('mgx_agent.config')
    logger.setLevel(logging.WARNING)
    
    handler = logging.StreamHandler()
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger