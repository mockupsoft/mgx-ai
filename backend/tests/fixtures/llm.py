# -*- coding: utf-8 -*-
"""
LLM Fixtures

Provides fixtures for LLM testing including:
- Mock LLM providers
- Test LLM responses
- Cost tracking fixtures
"""

import pytest
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any, List


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    provider = Mock()
    provider.generate = AsyncMock(return_value="Mock LLM response")
    provider.generate_stream = AsyncMock()
    provider.calculate_cost = Mock(return_value={"input_tokens": 10, "output_tokens": 20, "cost": 0.001})
    return provider


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response."""
    return {
        "content": "This is a mock LLM response",
        "model": "gpt-4",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
        "cost": 0.01,
    }


@pytest.fixture
def mock_llm_cost_tracker():
    """Create a mock LLM cost tracker."""
    tracker = Mock()
    tracker.log_call = Mock()
    tracker.get_total_cost = Mock(return_value=0.0)
    tracker.get_cost_by_model = Mock(return_value={})
    tracker.get_cost_by_workspace = Mock(return_value={})
    return tracker




