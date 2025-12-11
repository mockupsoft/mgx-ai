# -*- coding: utf-8 -*-
"""
Pytest Configuration and Global Fixtures

This conftest.py file provides:
- Global test configuration
- MetaGPT stub registration in sys.modules
- Reusable fixtures for tests
- Event loop setup for async tests
- Logging configuration
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest

# ============================================
# Register MetaGPT Stubs in sys.modules
# ============================================
# This allows tests to import MetaGPT components without the real package

from tests.helpers.metagpt_stubs import (
    MockAction,
    MockRole,
    MockTeam,
    MockMessage,
    mock_logger,
    MockMemory,
    MockContext,
    MockLLMResponse,
    MessageRole,
)

# Create stub modules
class MetaGPTStub:
    """Stub for metagpt module."""
    Action = MockAction
    Role = MockRole
    Team = MockTeam


class MetaGPTLogsStub:
    """Stub for metagpt.logs module."""
    logger = mock_logger


class MetaGPTTypesStub:
    """Stub for metagpt.types module."""
    Message = MockMessage


# Register stubs before any imports that might use MetaGPT
sys.modules['metagpt'] = MetaGPTStub()
sys.modules['metagpt.logs'] = MetaGPTLogsStub()
sys.modules['metagpt.types'] = MetaGPTTypesStub()


# ============================================
# Logging Configuration
# ============================================

@pytest.fixture(scope="session")
def setup_logging():
    """Configure logging for test session."""
    # Create tests directory if it doesn't exist
    tests_dir = Path(__file__).parent
    logs_dir = tests_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)8s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    
    # Create file handler for test logs
    log_file = logs_dir / "pytest.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)8s] %(name)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    logging.getLogger().addHandler(file_handler)
    
    yield
    
    # Cleanup
    file_handler.close()


# ============================================
# Event Loop Fixtures
# ============================================

@pytest.fixture(scope="function")
def event_loop() -> Generator:
    """
    Create an event loop for async tests.
    
    This fixture ensures each test gets its own isolated event loop,
    preventing issues with event loop state between tests.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    yield loop
    
    # Cleanup pending tasks
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    loop.close()


# ============================================
# Team and Role Fixtures
# ============================================

@pytest.fixture
def fake_team():
    """
    Provide a fake team for testing.
    
    Returns a MockTeam instance with 4 default roles.
    """
    from tests.helpers.factories import create_fake_team
    return create_fake_team(num_roles=4)


@pytest.fixture
def fake_team_with_custom_roles():
    """
    Factory fixture for creating fake teams with custom roles.
    
    Usage:
        def test_something(fake_team_with_custom_roles):
            team = fake_team_with_custom_roles(
                role_names=["Engineer", "Tester", "Reviewer"]
            )
    """
    from tests.helpers.factories import create_fake_team
    
    def _create_team(
        name: str = "TestTeam",
        role_names: list = None,
        num_roles: int = 4,
    ):
        return create_fake_team(
            name=name,
            num_roles=num_roles,
            role_names=role_names,
        )
    
    return _create_team


@pytest.fixture
def fake_role():
    """
    Provide a fake role for testing.
    
    Returns a MockRole instance with 2 default actions.
    """
    from tests.helpers.factories import create_fake_role
    return create_fake_role(num_actions=2)


# ============================================
# Memory and Message Fixtures
# ============================================

@pytest.fixture
def fake_memory():
    """
    Provide a fake memory store for testing.
    
    Returns an empty MockMemory instance.
    """
    from tests.helpers.factories import create_fake_memory_store
    return create_fake_memory_store()


@pytest.fixture
def fake_memory_with_data():
    """
    Provide a fake memory store with initial data.
    
    Returns a MockMemory with sample data and messages.
    """
    from tests.helpers.factories import (
        create_fake_memory_store,
        create_fake_message,
    )
    
    messages = [
        create_fake_message(role="user", content="Hello"),
        create_fake_message(role="assistant", content="Hi there"),
    ]
    
    return create_fake_memory_store(
        initial_data={
            "task": "Test Task",
            "status": "in_progress",
            "iterations": 0,
        },
        initial_messages=messages,
    )


@pytest.fixture
def fake_message():
    """
    Provide a factory for creating fake messages.
    
    Usage:
        def test_something(fake_message):
            msg = fake_message(role="user", content="Test")
    """
    from tests.helpers.factories import create_fake_message
    return create_fake_message


# ============================================
# LLM Response Fixtures
# ============================================

@pytest.fixture
def fake_llm_response():
    """
    Provide a factory for creating fake LLM responses.
    
    Usage:
        def test_something(fake_llm_response):
            response = fake_llm_response(content="Generated code")
    """
    from tests.helpers.factories import create_fake_llm_response
    return create_fake_llm_response


@pytest.fixture
def async_mock_llm():
    """
    Provide a factory for creating async mock LLM callables.
    
    Usage:
        def test_something(async_mock_llm):
            mock = async_mock_llm(responses=["Response 1", "Response 2"])
            result = await mock("prompt")
    """
    from tests.helpers.factories import create_async_mock_llm
    return create_async_mock_llm


# ============================================
# Output Directory Fixtures
# ============================================

@pytest.fixture
def tmp_output_dir(tmp_path):
    """
    Provide a temporary output directory for tests.
    
    Cleans up automatically after test.
    """
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def tmp_logs_dir(tmp_path):
    """
    Provide a temporary logs directory for tests.
    
    Cleans up automatically after test.
    """
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    return logs_dir


# ============================================
# Caplog Configuration
# ============================================

@pytest.fixture
def caplog_setup(caplog):
    """
    Configure caplog with appropriate settings.
    
    Sets log level to DEBUG to capture all messages.
    """
    caplog.set_level(logging.DEBUG)
    return caplog


# ============================================
# Pytest Hooks
# ============================================

def pytest_configure(config):
    """
    Pytest hook for initial configuration.
    
    Adds custom markers and initializes test environment.
    """
    # Ensure logs directory exists
    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(exist_ok=True)


def pytest_collection_modifyitems(config, items):
    """
    Pytest hook for modifying collected items.
    
    Automatically marks asyncio tests.
    """
    for item in items:
        # Check if test is async
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)


@pytest.fixture(autouse=True)
def reset_mock_logger():
    """
    Automatically reset mock logger before each test.
    
    Prevents test isolation issues.
    """
    mock_logger.clear()
    yield
    mock_logger.clear()


__all__ = [
    # Fixtures
    'setup_logging',
    'event_loop',
    'fake_team',
    'fake_team_with_custom_roles',
    'fake_role',
    'fake_memory',
    'fake_memory_with_data',
    'fake_message',
    'fake_llm_response',
    'async_mock_llm',
    'tmp_output_dir',
    'tmp_logs_dir',
    'caplog_setup',
]
