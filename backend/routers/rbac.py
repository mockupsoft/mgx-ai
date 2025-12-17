# -*- coding: utf-8 -*-
"""backend.routers.rbac

RBAC (Role-Based Access Control) API endpoints for user and role management.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
import logging

from ...db.models.entities import Role, UserRole, Permission, Workspace
from ...db.models.enums import RoleName
from ...schemas import (
    RoleCreate, RoleUpdate, RoleResponse, RoleListResponse,
    UserRoleCreate, UserRoleUpdate, UserRoleResponse, UserRoleListResponse,
    PermissionResponse, PermissionListResponse, PermissionCheck, PermissionResult
)
from ...services.auth.rbac import require_permission, get_rbac_service
from ...services.audit.logger import get_audit_logger
from ...db.session import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rbac", tags=["rbac"])


# User Management Endpoints

@router.post("/workspaces/{workspace_id}/users", response_model=UserRoleResponse)
async def add_user_to_workspace(
    workspace_id: str,
    user_role_data: UserRoleCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("users", "manage"))
):
    """Add user to workspace with role assignment."""
    
    user_id = user_context["user_id"]
    
    # Get role details
    role_stmt = select(Role).where(Role.id == user_role_data.role_id)
    role_result = await session.execute(role_stmt)
    role = role_result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    if role.workspace_id != workspace_id:
        raise HTTPException(status_code=400, detail="Role belongs to different workspace")
    
    # Create user role assignment
    rbac_service = await get_rbac_service()
    user_role = await rbac_service.assign_role(
        user_id=user_role_data.user_id,
        workspace_id=workspace_id,
        role_id=user_role_data.role_id,
        assigned_by_user_id=user_id
    )
    
    # Log the action
    audit_logger = await get_audit_logger()
    await audit_logger.log_action(
        user_id=user_id,
        workspace_id=workspace_id,
        action="ROLE_ASSIGNED",
        resource_type="user",
        resource_id=user_role_data.user_id,
        changes={
            "role_id": user_role_data.role_id,
            "role_name": role.name,
            "assigned_to": user_role_data.user_id
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent")
    )
    
    # Get the role response with nested data
    role_response = RoleResponse.from_orm(role)
    
    return UserRoleResponse(
        id=user_role.id,
        user_id=user_role.user_id,
        workspace_id=user_role.workspace_id,
        role_id=user_role.role_id,
        assigned_at=user_role.assigned_at,
        assigned_by_user_id=user_role.assigned_by_user_id,
        is_active=user_role.is_active,
        role=role_response
    )


@router.get("/workspaces/{workspace_id}/users/{user_id}/roles", response_model=List[UserRoleResponse])
async def get_user_roles(
    workspace_id: str,
    user_id: str,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("users", "read"))
):
    """Get all roles assigned to a user in workspace."""
    
    rbac_service = await get_rbac_service()
    user_roles = await rbac_service.get_user_roles(user_id, workspace_id)
    
    # Get full user role details with roles
    stmt = select(UserRole, Role).join(
        Role, UserRole.role_id == Role.id
    ).where(
        and_(
            UserRole.user_id == user_id,
            UserRole.workspace_id == workspace_id,
            UserRole.is_active == True  # noqa: E712
        )
    )
    
    result = await session.execute(stmt)
    user_role_data = result.all()
    
    responses = []
    for user_role, role in user_role_data:
        role_response = RoleResponse.from_orm(role)
        responses.append(UserRoleResponse(
            id=user_role.id,
            user_id=user_role.user_id,
            workspace_id=user_role.workspace_id,
            role_id=user_role.role_id,
            assigned_at=user_role.assigned_at,
            assigned_by_user_id=user_role.assigned_by_user_id,
            is_active=user_role.is_active,
            role=role_response
        ))
    
    return responses


@router.patch("/workspaces/{workspace_id}/users/{user_id}/roles/{role_id}", response_model=UserRoleResponse)
async def update_user_role(
    workspace_id: str,
    user_id: str,
    role_id: str,
    update_data: UserRoleUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("users", "manage"))
):
    """Update user role assignment."""
    
    rbac_service = await get_rbac_service()
    existing_user_id = user_context["user_id"]
    
    # Get existing user role
    stmt = select(UserRole, Role).join(
        Role, UserRole.role_id == Role.id
    ).where(
        and_(
            UserRole.user_id == user_id,
            UserRole.workspace_id == workspace_id,
            UserRole.role_id == role_id
        )
    )
    
    result = await session.execute(stmt)
    user_role_data = result.one_or_none()
    
    if not user_role_data:
        raise HTTPException(status_code=404, detail="User role assignment not found")
    
    user_role, role = user_role_data
    
    # Update the assignment
    if update_data.is_active is not None:
        user_role.is_active = update_data.is_active
    
    await session.commit()
    await session.refresh(user_role)
    
    # Log the action
    audit_logger = get_audit_logger()
    await audit_logger.log_action(
        user_id=existing_user_id,
        workspace_id=workspace_id,
        action="ROLE_REVOKED" if not update_data.is_active else "ROLE_ASSIGNED",
        resource_type="user",
        resource_id=user_id,
        changes={
            "role_id": role_id,
            "role_name": role.name,
            "is_active": update_data.is_active
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent")
    )
    
    # Get updated response
    role_response = RoleResponse.from_orm(role)
    return UserRoleResponse(
        id=user_role.id,
        user_id=user_role.user_id,
        workspace_id=user_role.workspace_id,
        role_id=user_role.role_id,
        assigned_at=user_role.assigned_at,
        assigned_by_user_id=user_role.assigned_by_user_id,
        is_active=user_role.is_active,
        role=role_response
    )


# Role Management Endpoints

@router.post("/workspaces/{workspace_id}/roles", response_model=RoleResponse)
async def create_role(
    workspace_id: str,
    role_data: RoleCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("users", "manage"))
):
    """Create a new role in workspace."""
    
    rbac_service = await get_rbac_service()
    user_id = user_context["user_id"]
    
    try:
        role = await rbac_service.create_role(
            workspace_id=workspace_id,
            role_data=role_data,
            created_by_user_id=user_id
        )
        
        # Log the action
        audit_logger = get_audit_logger()
        await audit_logger.log_action(
            user_id=user_id,
            workspace_id=workspace_id,
            action="ROLE_CREATED",
            resource_type="role",
            resource_id=role.id,
            changes={
                "name": role_data.name,
                "permissions": role_data.permissions,
                "description": role_data.description
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent")
        )
        
        return RoleResponse.from_orm(role)
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating role: {e}")
        raise HTTPException(status_code=500, detail="Failed to create role")


@router.get("/workspaces/{workspace_id}/roles", response_model=RoleListResponse)
async def list_roles(
    workspace_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    include_system: bool = Query(True, description="Include system roles"),
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("users", "read"))
):
    """List all roles in workspace."""
    
    offset = (page - 1) * per_page
    
    # Build query
    stmt = select(Role).where(
        and_(
            Role.workspace_id == workspace_id,
            Role.is_active == True  # noqa: E712
        )
    )
    
    if not include_system:
        stmt = stmt.where(Role.is_system_role == False)  # noqa: E712
    
    # Get total count
    count_stmt = select(func.count(Role.id)).where(
        and_(
            Role.workspace_id == workspace_id,
            Role.is_active == True  # noqa: E712
        )
    )
    if not include_system:
        count_stmt = count_stmt.where(Role.is_system_role == False)  # noqa: E712
    
    count_result = await session.execute(count_stmt)
    total = count_result.scalar()
    
    # Get roles
    stmt = stmt.offset(offset).limit(per_page)
    result = await session.execute(stmt)
    roles = result.scalars().all()
    
    role_responses = [RoleResponse.from_orm(role) for role in roles]
    
    return RoleListResponse(
        roles=role_responses,
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/workspaces/{workspace_id}/roles/{role_id}", response_model=RoleResponse)
async def get_role(
    workspace_id: str,
    role_id: str,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("users", "read"))
):
    """Get specific role details."""
    
    stmt = select(Role).where(
        and_(
            Role.id == role_id,
            Role.workspace_id == workspace_id,
            Role.is_active == True  # noqa: E712
        )
    )
    
    result = await session.execute(stmt)
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    return RoleResponse.from_orm(role)


@router.patch("/workspaces/{workspace_id}/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    workspace_id: str,
    role_id: str,
    role_update: RoleUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("users", "manage"))
):
    """Update role details."""
    
    # Get existing role
    stmt = select(Role).where(
        and_(
            Role.id == role_id,
            Role.workspace_id == workspace_id,
            Role.is_active == True  # noqa: E712
        )
    )
    
    result = await session.execute(stmt)
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    if role.is_system_role:
        raise HTTPException(status_code=400, detail="Cannot modify system roles")
    
    # Track changes
    changes = {}
    if role_update.permissions is not None:
        changes["permissions_before"] = role.permissions
        changes["permissions_after"] = role_update.permissions
        role.permissions = role_update.permissions
    
    if role_update.description is not None:
        changes["description_before"] = role.description
        changes["description_after"] = role_update.description
        role.description = role_update.description
    
    if role_update.is_active is not None:
        changes["is_active_before"] = role.is_active
        changes["is_active_after"] = role_update.is_active
        role.is_active = role_update.is_active
    
    await session.commit()
    await session.refresh(role)
    
    # Log the action
    audit_logger = get_audit_logger()
    await audit_logger.log_action(
        user_id=user_context["user_id"],
        workspace_id=workspace_id,
        action="ROLE_UPDATED",
        resource_type="role",
        resource_id=role_id,
        changes=changes,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent")
    )
    
    return RoleResponse.from_orm(role)


# Permission Management Endpoints

@router.get("/workspaces/{workspace_id}/permissions", response_model=PermissionListResponse)
async def list_permissions(
    workspace_id: str,
    role_id: Optional[str] = Query(None, description="Filter by role"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("users", "manage"))
):
    """List all permissions in workspace."""
    
    offset = (page - 1) * per_page
    
    # Build query
    stmt = select(Permission).where(Permission.workspace_id == workspace_id)
    
    if role_id:
        stmt = stmt.where(Permission.role_id == role_id)
    
    # Get total count
    count_stmt = select(func.count(Permission.id)).where(Permission.workspace_id == workspace_id)
    count_result = await session.execute(count_stmt)
    total = count_result.scalar()
    
    # Get permissions
    stmt = stmt.offset(offset).limit(per_page)
    result = await session.execute(stmt)
    permissions = result.scalars().all()
    
    permission_responses = [PermissionResponse.from_orm(perm) for perm in permissions]
    
    return PermissionListResponse(
        permissions=permission_responses,
        total=total,
        page=page,
        per_page=per_page
    )


@router.post("/permissions/check", response_model=PermissionResult)
async def check_permission(
    permission_check: PermissionCheck,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("users", "read"))
):
    """Check if user has specific permission."""
    
    rbac_service = await get_rbac_service()
    
    # Check permission
    has_permission = await rbac_service.check_permission(
        user_id=permission_check.user_id,
        workspace_id=permission_check.workspace_id,
        resource=permission_check.resource,
        action=permission_check.action,
        resource_id=permission_check.resource_id
    )
    
    # Get user roles
    user_roles = await rbac_service.get_user_roles(
        permission_check.user_id, 
        permission_check.workspace_id
    )
    
    role_names = [role.name for role in user_roles]
    
    return PermissionResult(
        has_permission=has_permission,
        required_permission=f"{permission_check.resource}:{permission_check.action}",
        user_roles=role_names,
        context={
            "resource_id": permission_check.resource_id,
            "checked_by": user_context["user_id"]
        }
    )


@router.get("/workspaces/{workspace_id}/roles/{role_id}/permitted-actions/{resource}")
async def get_permitted_actions(
    workspace_id: str,
    role_id: str,
    resource: str,
    user_id: Optional[str] = Query(None, description="User ID to check"),
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("users", "read"))
):
    """Get all permitted actions for user on specific resource."""
    
    # Verify role exists and belongs to workspace
    stmt = select(Role).where(
        and_(
            Role.id == role_id,
            Role.workspace_id == workspace_id,
            Role.is_active == True  # noqa: E712
        )
    )
    
    result = await session.execute(stmt)
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Get permitted actions
    if user_id:
        # Check for specific user
        rbac_service = get_rbac_service()
        actions = await rbac_service.list_permitted_resources(
            user_id=user_id,
            workspace_id=workspace_id,
            resource_type=resource
        )
    else:
        # Get actions from role permissions
        stmt = select(Permission.action).where(
            and_(
                Permission.role_id == role_id,
                Permission.resource == resource,
                Permission.is_active == True  # noqa: E712
            )
        )
        
        result = await session.execute(stmt)
        actions = [action for action, in result.all()]
    
    return {
        "resource": resource,
        "role_id": role_id,
        "permitted_actions": actions,
        "user_id": user_id
    }