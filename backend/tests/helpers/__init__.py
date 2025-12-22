# -*- coding: utf-8 -*-
"""
Test Helpers - Stubs, Factories, and Fixtures

This module provides lightweight stubs for MetaGPT components and factory functions
for creating test objects without requiring the real MetaGPT package or network calls.
"""

from .metagpt_stubs import (
    MockAction,
    MockRole,
    MockTeam,
    MockMessage,
    mock_logger,
)

from .factories import (
    create_fake_team,
    create_fake_role,
    create_fake_action,
    create_fake_memory_store,
    create_fake_llm_response,
)

__all__ = [
    # Stubs
    'MockAction',
    'MockRole',
    'MockTeam',
    'MockMessage',
    'mock_logger',
    
    # Factories
    'create_fake_team',
    'create_fake_role',
    'create_fake_action',
    'create_fake_memory_store',
    'create_fake_llm_response',
]
