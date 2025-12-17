# -*- coding: utf-8 -*-
"""backend.services.auth.rbac

Role-Based Access Control (RBAC) service for permission checking and user authorization.
"""

from typing import List, Optional, Dict, Any, Set, Tuple
from uuid import UUID
import asyncio
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
import logging

from ...db.models.entities import Role, UserRole, Permission, Workspace
from ...db.models.enums import RoleName, PermissionResource, PermissionAction
from ...schemas import (
    RoleCreate, RoleUpdate, UserRoleCreate, UserRoleUpdate, 
    PermissionCheck, PermissionResult
)

logger = logging.getLogger(__name__)


class RBACService:
    """Service for handling role-based access control and permissions."""
    
    def __init__(self, session_factory):
        """Initialize RBAC service with database session factory."""
        self.session_factory = session_factory
        self._cache = {}  # Simple cache for permissions
        self._cache_ttl = 300  # 5 minutes
    
    async def check_permission(
        self, 
        user_id: str, 
        workspace_id: str, 
        resource: str, 
        action: str,
        resource_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if user has permission for specific resource action.
        
        Args:
            user_id: User ID to check
            workspace_id: Workspace ID
            resource: Resource type (e.g., 'tasks', 'workflows')
            action: Action type (e.g., 'create', 'read', 'update')
            resource_id: Optional specific resource ID
            context: Additional context for permission evaluation
            
        Returns:
            True if permission granted, False otherwise
        """
        try:
            # Normalize inputs
            resource = PermissionResource(resource)
            action = PermissionAction(action)
            
            # Check cache first
            cache_key = f"{user_id}:{workspace_id}:{resource}:{action}"
            cached_result = self._get_cached_permission(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Get user roles for workspace
            user_roles = await self.get_user_roles(user_id, workspace_id)
            if not user_roles:
                logger.debug(f"No roles found for user {user_id} in workspace {workspace_id}")
                self._cache_permission(cache_key, False)
                return False
            
            # Check each role for the permission
            for role in user_roles:
                if await self._role_has_permission(role, resource, action, context):
                    self._cache_permission(cache_key, True)
                    return True
            
            self._cache_permission(cache_key, False)
            return False
            
        except ValueError as e:
            logger.error(f"Invalid permission resource/action: {e}")
            return False
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return False
    
    async def get_user_roles(
        self, 
        user_id: str, 
        workspace_id: str
    ) -> List[Role]:
        """Get all roles assigned to user in workspace.
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID
            
        Returns:
            List of Role objects
        """
        async with self.session_factory() as session:
            stmt = select(Role).join(
                UserRole, Role.id == UserRole.role_id
            ).where(
                and_(
                    UserRole.user_id == user_id,
                    UserRole.workspace_id == workspace_id,
                    UserRole.is_active == True,  # noqa: E712
                    Role.is_active == True  # noqa: E712
                )
            )
            
            result = await session.execute(stmt)
            roles = result.scalars().all()
            
            logger.debug(f"Found {len(roles)} roles for user {user_id} in workspace {workspace_id}")
            return list(roles)
    
    async def has_role(
        self, 
        user_id: str, 
        workspace_id: str, 
        role_name: str
    ) -> bool:
        """Check if user has specific role in workspace.
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID
            role_name: Role name to check
            
        Returns:
            True if user has the role
        """
        roles = await self.get_user_roles(user_id, workspace_id)
        return any(role.name == RoleName(role_name) for role in roles)
    
    async def list_permitted_resources(
        self, 
        user_id: str, 
        workspace_id: str, 
        resource_type: str
    ) -> List[str]:
        """List actions permitted for user on specific resource type.
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID
            resource_type: Resource type
            
        Returns:
            List of permitted action strings
        """
        resource = PermissionResource(resource_type)
        user_roles = await self.get_user_roles(user_id, workspace_id)
        
        permitted_actions = set()
        
        for role in user_roles:
            permissions = await self._get_role_permissions(role.id)
            for permission in permissions:
                if permission.resource == resource and permission.is_active:
                    permitted_actions.add(permission.action.value)
        
        return list(permitted_actions)
    
    async def create_role(
        self, 
        workspace_id: str, 
        role_data: RoleCreate,
        created_by_user_id: Optional[str] = None
    ) -> Role:
        """Create a new role.
        
        Args:
            workspace_id: Workspace ID
            role_data: Role creation data
            created_by_user_id: User creating the role
            
        Returns:
            Created Role object
        """
        async with self.session_factory() as session:
            # Check if role name already exists in workspace
            stmt = select(Role).where(
                and_(
                    Role.workspace_id == workspace_id,
                    Role.name == role_data.name
                )
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Role with name '{role_data.name}' already exists in workspace"
                )
            
            role = Role(
                workspace_id=workspace_id,
                name=role_data.name,
                permissions=role_data.permissions,
                description=role_data.description,
                is_system_role=False,
                is_active=True
            )
            
            session.add(role)
            await session.commit()
            await session.refresh(role)
            
            # Clear cache
            self._clear_cache()
            
            logger.info(f"Created role '{role_data.name}' in workspace {workspace_id}")
            return role
    
    async def assign_role(
        self, 
        user_id: str, 
        workspace_id: str, 
        role_id: str,
        assigned_by_user_id: str
    ) -> UserRole:
        """Assign role to user.
        
        Args:
            user_id: User ID to assign role to
            workspace_id: Workspace ID
            role_id: Role ID to assign
            assigned_by_user_id: User assigning the role
            
        Returns:
            Created UserRole object
        """
        async with self.session_factory() as session:
            # Check if assignment already exists
            stmt = select(UserRole).where(
                and_(
                    UserRole.user_id == user_id,
                    UserRole.workspace_id == workspace_id,
                    UserRole.role_id == role_id,
                    UserRole.is_active == True  # noqa: E712
                )
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Role already assigned to user in workspace"
                )
            
            user_role = UserRole(
                user_id=user_id,
                workspace_id=workspace_id,
                role_id=role_id,
                assigned_by_user_id=assigned_by_user_id,
                is_active=True
            )
            
            session.add(user_role)
            await session.commit()
            await session.refresh(user_role)
            
            # Clear cache
            self._clear_cache()
            
            logger.info(f"Assigned role {role_id} to user {user_id} in workspace {workspace_id}")
            return user_role
    
    async def revoke_role(
        self, 
        user_id: str, 
        workspace_id: str, 
        role_id: str
    ) -> bool:
        """Revoke role from user.
        
        Args:
            user_id: User ID to revoke role from
            workspace_id: Workspace ID
            role_id: Role ID to revoke
            
        Returns:
            True if role was revoked
        """
        async with self.session_factory() as session:
            stmt = select(UserRole).where(
                and_(
                    UserRole.user_id == user_id,
                    UserRole.workspace_id == workspace_id,
                    UserRole.role_id == role_id,
                    UserRole.is_active == True  # noqa: E712
                )
            )
            result = await session.execute(stmt)
            user_role = result.scalar_one_or_none()
            
            if not user_role:
                return False
            
            user_role.is_active = False
            await session.commit()
            
            # Clear cache
            self._clear_cache()
            
            logger.info(f"Revoked role {role_id} from user {user_id} in workspace {workspace_id}")
            return True
    
    async def _role_has_permission(
        self, 
        role: Role, 
        resource: PermissionResource, 
        action: PermissionAction,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if role has specific permission.
        
        Args:
            role: Role to check
            resource: Resource type
            action: Action type
            context: Additional context
            
        Returns:
            True if role has permission
        """
        # Check system permissions list
        permission_str = f"{resource.value}:{action.value}"
        wildcard_str = f"{resource.value}:*"
        
        if permission_str in role.permissions or wildcard_str in role.permissions:
            return True
        
        # Check database permissions table for fine-grained control
        permissions = await self._get_role_permissions(role.id)
        for permission in permissions:
            if permission.resource == resource and permission.action == action:
                # Apply additional conditions if any
                if permission.conditions:
                    if not self._evaluate_conditions(permission.conditions, context):
                        continue
                return True
        
        return False
    
    async def _get_role_permissions(self, role_id: str) -> List[Permission]:
        """Get all permissions for a role.
        
        Args:
            role_id: Role ID
            
        Returns:
            List of Permission objects
        """
        async with self.session_factory() as session:
            stmt = select(Permission).where(
                and_(
                    Permission.role_id == role_id,
                    Permission.is_active == True  # noqa: E712
                )
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
    
    def _evaluate_conditions(
        self, 
        conditions: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Evaluate permission conditions against context.
        
        Args:
            conditions: Permission conditions
            context: Execution context
            
        Returns:
            True if conditions are met
        """
        if not conditions:
            return True
        
        context = context or {}
        
        # Simple condition evaluation - can be extended
        for key, expected_value in conditions.items():
            if key in context:
                if context[key] != expected_value:
                    return False
            else:
                return False
        
        return True
    
    def _get_cached_permission(self, cache_key: str) -> Optional[bool]:
        """Get permission from cache.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached result or None
        """
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            import time
            if time.time() - entry['timestamp'] < self._cache_ttl:
                return entry['result']
            else:
                del self._cache[cache_key]
        return None
    
    def _cache_permission(self, cache_key: str, result: bool) -> None:
        """Cache permission result.
        
        Args:
            cache_key: Cache key
            result: Permission result
        """
        import time
        self._cache[cache_key] = {
            'result': result,
            'timestamp': time.time()
        }
    
    def _clear_cache(self) -> None:
        """Clear permission cache."""
        self._cache.clear()


# Global RBAC service instance
rbac_service = None


async def get_rbac_service() -> RBACService:
    """Get global RBAC service instance."""
    global rbac_service
    if rbac_service is None:
        from ...db.engine import get_session_factory
        session_factory = await get_session_factory()
        rbac_service = RBACService(session_factory)
    return rbac_service


# FastAPI dependency for permission checking
async def require_permission(resource: str, action: str):
    """FastAPI dependency to require specific permission.
    
    Usage:
        @app.get("/tasks")
        async def list_tasks(request: Request, session: AsyncSession = Depends(get_session), 
                           user_info = Depends(require_permission("tasks", "read"))):
            # Endpoint logic here
    """
    async def dependency(request: Request, session: AsyncSession = Depends(get_session)):
        # Extract user and workspace from headers or request
        user_id = request.headers.get("X-User-ID")
        workspace_id = request.headers.get("X-Workspace-ID")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not provided")
        
        if not workspace_id:
            raise HTTPException(status_code=400, detail="Workspace ID not provided")
        
        # Check permission
        service = await get_rbac_service()
        has_permission = await service.check_permission(
            user_id, workspace_id, resource, action
        )
        
        if not has_permission:
            raise HTTPException(
                status_code=403, 
                detail=f"Permission denied: {resource}:{action}"
            )
        
        return {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "session": session,
            "service": service
        }
    
    return dependency