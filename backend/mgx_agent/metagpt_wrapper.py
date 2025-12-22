#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MetaGPT compatibility wrapper for missing modules.

This provides mock/stub implementations for MetaGPT modules that are expected
but not available in the current version.
"""

from typing import List, Any, Dict
from metagpt.roles import Role
from metagpt.schema import Message


class MockTeam:
    """Mock Team class for compatibility"""
    
    def __init__(self, *args, **kwargs):
        self.members: List[Role] = []
        self.messages: List[Message] = []
    
    def add_member(self, role: Role):
        """Add a team member"""
        self.members.append(role)
    
    def send_message(self, message: Message):
        """Send a message within the team"""
        self.messages.append(message)


class MockContext:
    """Mock Context class for compatibility"""
    
    def __init__(self, *args, **kwargs):
        self.data: Dict[str, Any] = {}
    
    def set(self, key: str, value: Any):
        """Set context value"""
        self.data[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get context value"""
        return self.data.get(key, default)


# Export the mock classes as if they were the real ones
Team = MockTeam
Context = MockContext