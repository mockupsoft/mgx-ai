# -*- coding: utf-8 -*-
"""backend.services.auth.default_roles

Default role and permission setup for new workspaces.
"""

from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import logging

from ...db.models.entities import Role, Permission, Workspace
from ...db.models.enums import RoleName, PermissionResource, PermissionAction

logger = logging.getLogger(__name__)


class DefaultRolesSetup:
    """Service for setting up default roles and permissions for workspaces."""
    
    # Default role definitions
    DEFAULT_ROLES = {
        "admin": {
            "description": "Full administrative access to workspace",
            "permissions": [
                "tasks:*", "workflows:*", "repositories:*", "repos:*", 
                "agents:*", "settings:*", "users:*", "audit:*", "metrics:*",
                "workspaces:*", "projects:*"
            ]
        },
        "developer": {
            "description": "Development team member with task and workflow access",
            "permissions": [
                "tasks:create", "tasks:read", "tasks:update", "tasks:execute",
                "workflows:create", "workflows:read", "workflows:execute",
                "repositories:read", "repos:read", "agents:read",
                "metrics:read", "projects:read"
            ]
        },
        "viewer": {
            "description": "Read-only access to workspace resources",
            "permissions": [
                "tasks:read", "workflows:read", "repositories:read", 
                "repos:read", "agents:read", "metrics:read", 
                "audit:read", "projects:read"
            ]
        },
        "auditor": {
            "description": "Audit and compliance access",
            "permissions": [
                "audit:read", "metrics:read", "logs:read", "tasks:read",
                "workflows:read", "settings:read"
            ]
        }
    }
    
    # Fine-grained permissions for each role
    ROLE_PERMISSIONS = {
        RoleName.ADMIN: [
            # All resource types with all actions
            (PermissionResource.TASKS, PermissionAction.CREATE),
            (PermissionResource.TASKS, PermissionAction.READ),
            (PermissionResource.TASKS, PermissionAction.UPDATE),
            (PermissionResource.TASKS, PermissionAction.DELETE),
            (PermissionResource.TASKS, PermissionAction.EXECUTE),
            
            (PermissionResource.WORKFLOWS, PermissionAction.CREATE),
            (PermissionResource.WORKFLOWS, PermissionAction.READ),
            (PermissionResource.WORKFLOWS, PermissionAction.UPDATE),
            (PermissionResource.WORKFLOWS, PermissionAction.DELETE),
            (PermissionResource.WORKFLOWS, PermissionAction.EXECUTE),
            
            (PermissionResource.REPOSITORIES, PermissionAction.CREATE),
            (PermissionResource.REPOSITORIES, PermissionAction.READ),
            (PermissionResource.REPOSITORIES, PermissionAction.UPDATE),
            (PermissionResource.REPOSITORIES, PermissionAction.DELETE),
            (PermissionResource.REPOSITORIES, PermissionAction.CONNECT),
            
            (PermissionResource.REPOS, PermissionAction.CREATE),
            (PermissionResource.REPOS, PermissionAction.READ),
            (PermissionResource.REPOS, PermissionAction.UPDATE),
            (PermissionResource.REPOS, PermissionAction.DELETE),
            (PermissionResource.REPOS, PermissionAction.CONNECT),
            
            (PermissionResource.AGENTS, PermissionAction.CREATE),
            (PermissionResource.AGENTS, PermissionAction.READ),
            (PermissionResource.AGENTS, PermissionAction.UPDATE),
            (PermissionResource.AGENTS, PermissionAction.DELETE),
            (PermissionResource.AGENTS, PermissionAction.MANAGE),
            
            (PermissionResource.SETTINGS, PermissionAction.READ),
            (PermissionResource.SETTINGS, PermissionAction.UPDATE),
            (PermissionResource.SETTINGS, PermissionAction.MANAGE),
            
            (PermissionResource.USERS, PermissionAction.CREATE),
            (PermissionResource.USERS, PermissionAction.READ),
            (PermissionResource.USERS, PermissionAction.UPDATE),
            (PermissionResource.USERS, PermissionAction.DELETE),
            (PermissionResource.USERS, PermissionAction.MANAGE),
            
            (PermissionResource.AUDIT, PermissionAction.READ),
            (PermissionResource.AUDIT, PermissionAction.MANAGE),
            
            (PermissionResource.METRICS, PermissionAction.READ),
            (PermissionResource.METRICS, PermissionAction.MANAGE),
            
            (PermissionResource.WORKSPACES, PermissionAction.CREATE),
            (PermissionResource.WORKSPACES, PermissionAction.READ),
            (PermissionResource.WORKSPACES, PermissionAction.UPDATE),
            (PermissionResource.WORKSPACES, PermissionAction.DELETE),
            (PermissionResource.WORKSPACES, PermissionAction.MANAGE),
            
            (PermissionResource.PROJECTS, PermissionAction.CREATE),
            (PermissionResource.PROJECTS, PermissionAction.READ),
            (PermissionResource.PROJECTS, PermissionAction.UPDATE),
            (PermissionResource.PROJECTS, PermissionAction.DELETE),
            (PermissionResource.PROJECTS, PermissionAction.MANAGE),
        ],
        
        RoleName.DEVELOPER: [
            (PermissionResource.TASKS, PermissionAction.CREATE),
            (PermissionResource.TASKS, PermissionAction.READ),
            (PermissionResource.TASKS, PermissionAction.UPDATE),
            (PermissionResource.TASKS, PermissionAction.EXECUTE),
            
            (PermissionResource.WORKFLOWS, PermissionAction.CREATE),
            (PermissionResource.WORKFLOWS, PermissionAction.READ),
            (PermissionResource.WORKFLOWS, PermissionAction.EXECUTE),
            
            (PermissionResource.REPOSITORIES, PermissionAction.READ),
            (PermissionResource.REPOSITORIES, PermissionAction.CONNECT),
            
            (PermissionResource.REPOS, PermissionAction.READ),
            (PermissionResource.REPOS, PermissionAction.CONNECT),
            
            (PermissionResource.AGENTS, PermissionAction.READ),
            
            (PermissionResource.METRICS, PermissionAction.READ),
            
            (PermissionResource.PROJECTS, PermissionAction.READ),
        ],
        
        RoleName.VIEWER: [
            (PermissionResource.TASKS, PermissionAction.READ),
            (PermissionResource.WORKFLOWS, PermissionAction.READ),
            (PermissionResource.REPOSITORIES, PermissionAction.READ),
            (PermissionResource.REPOS, PermissionAction.READ),
            (PermissionResource.AGENTS, PermissionAction.READ),
            (PermissionResource.METRICS, PermissionAction.READ),
            (PermissionResource.AUDIT, PermissionAction.READ),
            (PermissionResource.PROJECTS, PermissionAction.READ),
        ],
        
        RoleName.AUDITOR: [
            (PermissionResource.AUDIT, PermissionAction.READ),
            (PermissionResource.METRICS, PermissionAction.READ),
            
            # Read access to audit relevant resources
            (PermissionResource.TASKS, PermissionAction.READ),
            (PermissionResource.WORKFLOWS, PermissionAction.READ),
            (PermissionResource.SETTINGS, PermissionAction.READ),
            (PermissionResource.REPOSITORIES, PermissionAction.READ),
            (PermissionResource.REPOS, PermissionAction.READ),
            (PermissionResource.AGENTS, PermissionAction.READ),
            (PermissionResource.PROJECTS, PermissionAction.READ),
        ]
    }
    
    async def setup_default_roles(
        self, 
        workspace_id: str, 
        session: AsyncSession
    ) -> List[Role]:
        """Setup default roles for a workspace.
        
        Args:
            workspace_id: Workspace ID
            session: Database session
            
        Returns:
            List of created roles
        """
        created_roles = []
        
        for role_name, role_config in self.DEFAULT_ROLES.items():
            # Check if role already exists
            stmt = select(Role).where(
                and_(
                    Role.workspace_id == workspace_id,
                    Role.name == RoleName(role_name)
                )
            )
            result = await session.execute(stmt)
            existing_role = result.scalar_one_or_none()
            
            if existing_role:
                logger.info(f"Role {role_name} already exists for workspace {workspace_id}")
                created_roles.append(existing_role)
                continue
            
            # Create new role
            role = Role(
                workspace_id=workspace_id,
                name=RoleName(role_name),
                permissions=role_config["permissions"],
                description=role_config["description"],
                is_system_role=True,
                is_active=True
            )
            
            session.add(role)
            created_roles.append(role)
            
            logger.info(f"Created default role {role_name} for workspace {workspace_id}")
        
        await session.commit()
        
        # Create fine-grained permissions
        for role in created_roles:
            permissions = self.ROLE_PERMISSIONS.get(role.name, [])
            
            for resource, action in permissions:
                permission = Permission(
                    workspace_id=workspace_id,
                    role_id=role.id,
                    resource=resource,
                    action=action,
                    is_active=True
                )
                session.add(permission)
            
            logger.info(f"Created {len(permissions)} permissions for role {role.name}")
        
        await session.commit()
        
        # Refresh all roles to get updated data
        for role in created_roles:
            await session.refresh(role)
        
        return created_roles
    
    async def get_default_roles_permissions(self) -> Dict[str, Any]:
        """Get default roles and permissions configuration.
        
        Returns:
            Dictionary with roles and permissions configuration
        """
        return {
            "roles": self.DEFAULT_ROLES,
            "fine_grained_permissions": {
                role_name.value: [
                    f"{resource.value}:{action.value}"
                    for resource, action in permissions
                ]
                for role_name, permissions in self.ROLE_PERMISSIONS.items()
            }
        }
    
    async def validate_role_permissions(
        self, 
        role: Role
    ) -> Dict[str, Any]:
        """Validate that a role has both string and fine-grained permissions.
        
        Args:
            role: Role to validate
            
        Returns:
            Validation results
        """
        validation = {
            "role_id": role.id,
            "role_name": role.name.value,
            "has_string_permissions": bool(role.permissions),
            "has_fine_grained": False,
            "recommendations": []
        }
        
        # Check if fine-grained permissions exist
        if role.id:
            # This would require database lookup
            validation["has_fine_grained"] = True  # Placeholder
        
        # Generate recommendations
        if not role.permissions:
            validation["recommendations"].append(
                "Role should have string-based permissions for compatibility"
            )
        
        expected_permissions = self.ROLE_PERMISSIONS.get(role.name, [])
        if len(expected_permissions) > 0 and not validation["has_fine_grained"]:
            validation["recommendations"].append(
                f"Role should have {len(expected_permissions)} fine-grained permissions"
            )
        
        return validation


# Global default roles setup instance
default_roles_setup = DefaultRolesSetup()


async def setup_workspace_default_roles(
    workspace_id: str, 
    session: AsyncSession
) -> List[Role]:
    """Convenience function to setup default roles for a workspace.
    
    Args:
        workspace_id: Workspace ID
        session: Database session
        
    Returns:
        List of created roles
    """
    setup = DefaultRolesSetup()
    return await setup.setup_default_roles(workspace_id, session)