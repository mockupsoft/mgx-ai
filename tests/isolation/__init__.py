"""
Multi-Tenant Isolation Test Suite

This package contains comprehensive tests to validate that workspaces
are completely isolated from each other in the MGX-AI platform.

Test Categories:
- Data Isolation: Workspace data cannot be accessed cross-workspace
- Authentication Isolation: Tokens are workspace-scoped
- Quota Isolation: Resource quotas are enforced per workspace
- Memory Isolation: Memory usage is isolated between workspaces
"""

__version__ = "1.0.0"
