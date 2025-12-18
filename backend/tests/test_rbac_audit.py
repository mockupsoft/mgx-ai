# -*- coding: utf-8 -*-
"""backend.tests.test_rbac_audit

Comprehensive tests for RBAC and audit logging functionality.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.db.models.entities import Role, UserRole, Permission, AuditLog, Workspace
from backend.db.models.enums import RoleName, PermissionResource, PermissionAction, AuditAction, AuditLogStatus
from backend.services.auth.rbac import RBACService, require_permission, get_rbac_service
from backend.services.audit.logger import AuditLogger, get_audit_logger
from backend.services.auth.default_roles import DefaultRolesSetup
from backend.schemas import (
    RoleCreate,
    UserRoleCreate,
    PermissionCheck,
    AuditLogCreate,
    AuditLogFilter,
    AuditLogExportRequest,
)
from backend.routers.rbac import router as rbac_router
from backend.routers.audit import router as audit_router

# Import base metadata for test database setup
from backend.db.models.base import Base


class TestRBACService:
    """Test cases for RBAC service functionality."""
    
    @pytest.fixture
    async def rbac_service(self):
        """Create RBAC service with test session factory."""
        # Create test database
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        service = RBACService(session_factory)
        return service
    
    @pytest.fixture
    def sample_workspace_id(self):
        """Sample workspace ID for testing."""
        return str(uuid4())
    
    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID for testing."""
        return str(uuid4())
    
    @pytest.mark.asyncio
    async def test_check_permission_no_roles(self, rbac_service, sample_workspace_id):
        """Test permission check with no roles assigned."""
        user_id = str(uuid4())
        
        has_permission = await rbac_service.check_permission(
            user_id, sample_workspace_id, "tasks", "create"
        )
        
        assert not has_permission
    
    @pytest.mark.asyncio
    async def test_check_permission_with_admin_role(self, rbac_service, sample_workspace_id, sample_user_id):
        """Test permission check with admin role."""
        # Create admin role
        admin_role = Role(
            workspace_id=sample_workspace_id,
            name=RoleName.ADMIN,
            permissions=["tasks:*", "workflows:*"],
            description="Admin role",
            is_system_role=True,
            is_active=True
        )
        
        # Create user role assignment
        user_role = UserRole(
            user_id=sample_user_id,
            workspace_id=sample_workspace_id,
            role_id=admin_role.id,
            is_active=True
        )
        
        async with rbac_service.session_factory() as session:
            session.add(admin_role)
            session.add(user_role)
            await session.commit()
            await session.refresh(admin_role)
            user_role.role_id = admin_role.id
            await session.commit()
        
        # Test permissions
        has_task_create = await rbac_service.check_permission(
            sample_user_id, sample_workspace_id, "tasks", "create"
        )
        has_workflow_delete = await rbac_service.check_permission(
            sample_user_id, sample_workspace_id, "workflows", "delete"
        )
        has_agent_create = await rbac_service.check_permission(
            sample_user_id, sample_workspace_id, "agents", "create"
        )
        
        assert has_task_create
        assert has_workflow_delete
        assert has_agent_create
    
    @pytest.mark.asyncio
    async def test_create_role(self, rbac_service, sample_workspace_id):
        """Test role creation."""
        role_data = RoleCreate(
            name="custom_role",
            permissions=["tasks:read", "workflows:read"],
            description="Custom test role"
        )
        
        role = await rbac_service.create_role(
            workspace_id=sample_workspace_id,
            role_data=role_data
        )
        
        assert role.name == "custom_role"
        assert role.permissions == ["tasks:read", "workflows:read"]
        assert role.description == "Custom test role"
        assert not role.is_system_role
        assert role.is_active
    
    @pytest.mark.asyncio
    async def test_assign_role(self, rbac_service, sample_workspace_id, sample_user_id):
        """Test role assignment to user."""
        # Create a role
        role = Role(
            workspace_id=sample_workspace_id,
            name=RoleName.DEVELOPER,
            permissions=["tasks:create", "tasks:read"],
            description="Developer role",
            is_system_role=True,
            is_active=True
        )
        
        async with rbac_service.session_factory() as session:
            session.add(role)
            await session.commit()
            await session.refresh(role)
        
        # Assign role
        user_role = await rbac_service.assign_role(
            user_id=sample_user_id,
            workspace_id=sample_workspace_id,
            role_id=role.id,
            assigned_by_user_id=str(uuid4())
        )
        
        assert user_role.user_id == sample_user_id
        assert user_role.role_id == role.id
        assert user_role.is_active
        
        # Verify role can be retrieved
        user_roles = await rbac_service.get_user_roles(sample_user_id, sample_workspace_id)
        assert len(user_roles) == 1
        assert user_roles[0].id == role.id
    
    @pytest.mark.asyncio
    async def test_revoke_role(self, rbac_service, sample_workspace_id, sample_user_id):
        """Test role revocation."""
        # Create and assign role
        role = Role(
            workspace_id=sample_workspace_id,
            name=RoleName.VIEWER,
            permissions=["tasks:read"],
            description="Viewer role",
            is_system_role=True,
            is_active=True
        )
        
        async with rbac_service.session_factory() as session:
            session.add(role)
            await session.commit()
            await session.refresh(role)
        
        user_role = await rbac_service.assign_role(
            user_id=sample_user_id,
            workspace_id=sample_workspace_id,
            role_id=role.id,
            assigned_by_user_id=str(uuid4())
        )
        
        # Verify assignment
        user_roles_before = await rbac_service.get_user_roles(sample_user_id, sample_workspace_id)
        assert len(user_roles_before) == 1
        
        # Revoke role
        success = await rbac_service.revoke_role(
            user_id=sample_user_id,
            workspace_id=sample_workspace_id,
            role_id=role.id
        )
        
        assert success
        
        # Verify revocation
        user_roles_after = await rbac_service.get_user_roles(sample_user_id, sample_workspace_id)
        assert len(user_roles_after) == 0
    
    @pytest.mark.asyncio
    async def test_has_role(self, rbac_service, sample_workspace_id, sample_user_id):
        """Test role checking functionality."""
        # Create and assign developer role
        role = Role(
            workspace_id=sample_workspace_id,
            name=RoleName.DEVELOPER,
            permissions=["tasks:create"],
            description="Developer role",
            is_system_role=True,
            is_active=True
        )
        
        async with rbac_service.session_factory() as session:
            session.add(role)
            await session.commit()
            await session.refresh(role)
        
        await rbac_service.assign_role(
            user_id=sample_user_id,
            workspace_id=sample_workspace_id,
            role_id=role.id,
            assigned_by_user_id=str(uuid4())
        )
        
        # Test role checking
        has_developer = await rbac_service.has_role(sample_user_id, sample_workspace_id, "developer")
        has_admin = await rbac_service.has_role(sample_user_id, sample_workspace_id, "admin")
        
        assert has_developer
        assert not has_admin


class TestAuditLogger:
    """Test cases for audit logging functionality."""
    
    @pytest.fixture
    async def audit_logger(self):
        """Create audit logger with test session factory."""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        logger = AuditLogger(session_factory)
        return logger
    
    @pytest.fixture
    def sample_workspace_id(self):
        """Sample workspace ID for testing."""
        return str(uuid4())
    
    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID for testing."""
        return str(uuid4())
    
    @pytest.mark.asyncio
    async def test_log_action(self, audit_logger, sample_workspace_id, sample_user_id):
        """Test basic audit log creation."""
        log = await audit_logger.log_action(
            user_id=sample_user_id,
            workspace_id=sample_workspace_id,
            action=AuditAction.TASK_CREATED,
            resource_type="task",
            resource_id=str(uuid4()),
            changes={"name": "Test Task", "status": "created"},
            status=AuditLogStatus.SUCCESS,
            ip_address="192.168.1.1",
            user_agent="TestClient/1.0"
        )
        
        assert log.id is not None
        assert log.user_id == sample_user_id
        assert log.workspace_id == sample_workspace_id
        assert log.action == AuditAction.TASK_CREATED
        assert log.resource_type == "task"
        assert log.status == AuditLogStatus.SUCCESS
        assert log.ip_address == "192.168.1.1"
        assert log.user_agent == "TestClient/1.0"
        assert log.changes["name"] == "Test Task"
    
    @pytest.mark.asyncio
    async def test_get_audit_trail(self, audit_logger, sample_workspace_id, sample_user_id):
        """Test retrieving audit trail with filtering."""
        # Create multiple audit logs
        for i in range(5):
            await audit_logger.log_action(
                user_id=sample_user_id,
                workspace_id=sample_workspace_id,
                action=AuditAction.TASK_CREATED,
                resource_type="task",
                changes={"task_id": f"task_{i}"}
            )
        
        # Get all logs
        logs = await audit_logger.get_audit_trail(
            workspace_id=sample_workspace_id,
            limit=10
        )
        
        assert len(logs) == 5
        
        # Filter by user
        user_logs = await audit_logger.get_audit_trail(
            workspace_id=sample_workspace_id,
            filters=AuditLogFilter(user_id=sample_user_id),
            limit=10
        )
        
        assert len(user_logs) == 5
    
    @pytest.mark.asyncio
    async def test_get_audit_log(self, audit_logger, sample_workspace_id):
        """Test retrieving specific audit log."""
        created_log = await audit_logger.log_action(
            user_id=str(uuid4()),
            workspace_id=sample_workspace_id,
            action=AuditAction.WORKFLOW_EXECUTED,
            resource_type="workflow",
            changes={"workflow_id": "wf_123"}
        )
        
        # Retrieve the log
        retrieved_log = await audit_logger.get_audit_log(
            log_id=created_log.id,
            workspace_id=sample_workspace_id
        )
        
        assert retrieved_log is not None
        assert retrieved_log.id == created_log.id
        assert retrieved_log.action == AuditAction.WORKFLOW_EXECUTED
        assert retrieved_log.changes["workflow_id"] == "wf_123"
    
    @pytest.mark.asyncio
    async def test_export_audit_logs_json(self, audit_logger, sample_workspace_id):
        """Test audit log export in JSON format."""
        # Create some logs
        for i in range(3):
            await audit_logger.log_action(
                user_id=str(uuid4()),
                workspace_id=sample_workspace_id,
                action=AuditAction.USER_LOGIN,
                resource_type="user",
                changes={"attempt": i}
            )
        
        # Export logs
        export_request = AuditLogExportRequest(
            format="json",
            limit=10
        )
        
        export_response = await audit_logger.export_audit_logs(
            workspace_id=sample_workspace_id,
            export_request=export_request
        )
        
        assert export_response.format == "json"
        assert export_response.record_count == 3
        assert isinstance(export_response.data, list)
        assert len(export_response.data) == 3
    
    @pytest.mark.asyncio
    async def test_audit_statistics(self, audit_logger, sample_workspace_id):
        """Test audit log statistics generation."""
        user_id = str(uuid4())
        
        # Create logs with different actions
        for i in range(3):
            await audit_logger.log_action(
                user_id=user_id,
                workspace_id=sample_workspace_id,
                action=AuditAction.TASK_CREATED,
                resource_type="task",
                status=AuditLogStatus.SUCCESS
            )
        
        for i in range(2):
            await audit_logger.log_action(
                user_id=user_id,
                workspace_id=sample_workspace_id,
                action=AuditAction.TASK_DELETED,
                resource_type="task",
                status=AuditLogStatus.FAILURE
            )
        
        # Get statistics
        stats = await audit_logger.get_audit_statistics(
            workspace_id=sample_workspace_id,
            date_range_days=30
        )
        
        assert stats["total_logs"] == 5
        assert "action_distribution" in stats
        assert "status_distribution" in stats
        assert stats["action_distribution"]["TASK_CREATED"] == 3
        assert stats["action_distribution"]["TASK_DELETED"] == 2


class TestRBACIntegration:
    """Integration tests for RBAC system."""
    
    @pytest.fixture
    def app(self):
        """Create test FastAPI application."""
        app = FastAPI()
        app.include_router(rbac_router)
        app.include_router(audit_router)
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)
    
    def test_rbac_endpoints_health(self, client):
        """Test that RBAC endpoints are available."""
        # This test verifies the routers are properly included
        # Actual endpoint testing would require database setup
        response = client.get("/api/rbac/workspaces/test/roles")
        # Should get authentication error, not 404
        assert response.status_code in [401, 403, 422]  # auth, permission, or validation error


class TestDefaultRolesSetup:
    """Test cases for default roles setup."""
    
    @pytest.fixture
    async def setup_service(self):
        """Create default roles setup service."""
        return DefaultRolesSetup()
    
    @pytest.mark.asyncio
    async def test_get_default_configuration(self, setup_service):
        """Test retrieving default roles configuration."""
        config = await setup_service.get_default_roles_permissions()
        
        assert "roles" in config
        assert "fine_grained_permissions" in config
        
        # Check required roles exist
        required_roles = ["admin", "developer", "viewer", "auditor"]
        for role_name in required_roles:
            assert role_name in config["roles"]
            assert role_name in config["fine_grained_permissions"]
    
    @pytest.mark.asyncio
    async def test_validate_role_permissions(self, setup_service):
        """Test role permission validation."""
        # Create mock role
        role = Role(
            workspace_id=str(uuid4()),
            name=RoleName.ADMIN,
            permissions=["tasks:*", "workflows:*"],
            is_system_role=True,
            is_active=True
        )
        
        validation = await setup_service.validate_role_permissions(role)
        
        assert validation["role_name"] == "admin"
        assert validation["has_string_permissions"] is True
        assert "recommendations" in validation


# Note: For actual database tests, you would need to:
# 1. Set up proper test database with migrations
# 2. Mock or provide actual database connections
# 3. Handle async test setup/teardown properly

if __name__ == "__main__":
    pytest.main([__file__])