# -*- coding: utf-8 -*-
"""backend.routers.audit

Audit Logging API endpoints for viewing and managing audit trails.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
import logging

from ..db.models.entities import AuditLog, Workspace
from ..schemas import (
    AuditLogResponse, AuditLogListResponse, AuditLogFilter,
    AuditLogExportRequest, AuditLogExportResponse, AuditLogStatistics
)
from ..services.audit.logger import get_audit_logger
from ..services.auth.rbac import require_permission
from ..db.session import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/workspaces/{workspace_id}/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    workspace_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=200, description="Items per page"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    date_from: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("audit", "read"))
):
    """Get audit trail with filtering and pagination."""
    
    # Build filters
    filters = AuditLogFilter()
    if user_id:
        filters.user_id = user_id
    if action:
        filters.action = action
    if resource_type:
        filters.resource_type = resource_type
    if resource_id:
        filters.resource_id = resource_id
    if status:
        filters.status = status
    if ip_address:
        filters.ip_address = ip_address
    
    if date_from:
        try:
            from datetime import datetime
            filters.date_from = datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format. Use YYYY-MM-DD")
    
    if date_to:
        try:
            from datetime import datetime, timedelta
            date_to_dt = datetime.strptime(date_to, "%Y-%m-%d")
            # Add end of day
            filters.date_to = date_to_dt + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format. Use YYYY-MM-DD")
    
    # Get audit logs
    audit_logger = await get_audit_logger()
    logs = await audit_logger.get_audit_trail(
        workspace_id=workspace_id,
        filters=filters,
        limit=per_page,
        offset=(page - 1) * per_page,
        sort_by="created_at",
        sort_order="desc"
    )
    
    # Convert to response format
    log_responses = [AuditLogResponse.from_orm(log) for log in logs]
    
    # Get total count for pagination
    total_stmt = select(func.count(AuditLog.id)).where(
        AuditLog.workspace_id == workspace_id
    )
    
    # Apply same filters for count
    count_filters = AuditLogFilter()
    if user_id:
        count_filters.user_id = user_id
    if action:
        count_filters.action = action
    if resource_type:
        count_filters.resource_type = resource_type
    if resource_id:
        count_filters.resource_id = resource_id
    if status:
        count_filters.status = status
    if ip_address:
        count_filters.ip_address = ip_address
    if date_from:
        count_filters.date_from = filters.date_from
    if date_to:
        count_filters.date_to = filters.date_to
    
    # Apply filters to count query
    audit_stmt = total_stmt
    if count_filters.user_id:
        audit_stmt = audit_stmt.where(AuditLog.user_id == count_filters.user_id)
    if count_filters.action:
        from ..db.models.enums import AuditAction
        audit_stmt = audit_stmt.where(AuditLog.action == AuditAction(count_filters.action))
    if count_filters.resource_type:
        audit_stmt = audit_stmt.where(AuditLog.resource_type == count_filters.resource_type)
    if count_filters.resource_id:
        audit_stmt = audit_stmt.where(AuditLog.resource_id == count_filters.resource_id)
    if count_filters.status:
        from ..db.models.enums import AuditLogStatus
        audit_stmt = audit_stmt.where(AuditLog.status == AuditLogStatus(count_filters.status))
    if count_filters.date_from:
        audit_stmt = audit_stmt.where(AuditLog.created_at >= count_filters.date_from)
    if count_filters.date_to:
        audit_stmt = audit_stmt.where(AuditLog.created_at <= count_filters.date_to)
    if count_filters.ip_address:
        audit_stmt = audit_stmt.where(AuditLog.ip_address.like(f"%{count_filters.ip_address}%"))
    
    total_result = await session.execute(audit_stmt)
    total = total_result.scalar()
    
    return AuditLogListResponse(
        logs=log_responses,
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/workspaces/{workspace_id}/audit-logs/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    workspace_id: str,
    log_id: str,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("audit", "read"))
):
    """Get specific audit log entry."""
    
    audit_logger = await get_audit_logger()
    log = await audit_logger.get_audit_log(log_id, workspace_id)
    
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    
    return AuditLogResponse.from_orm(log)


@router.post("/workspaces/{workspace_id}/audit-logs/export", response_model=AuditLogExportResponse)
async def export_audit_logs(
    workspace_id: str,
    export_request: AuditLogExportRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("audit", "read"))
):
    """Export audit logs in specified format."""
    
    audit_logger = await get_audit_logger()
    
    try:
        export_response = await audit_logger.export_audit_logs(
            workspace_id=workspace_id,
            export_request=export_request,
            export_format=export_request.format or "json"
        )
        
        # Log the export action
        await audit_logger.log_action(
            user_id=user_context["user_id"],
            workspace_id=workspace_id,
            action="DATA_EXPORTED",
            resource_type="audit_logs",
            resource_id=None,
            changes={
                "format": export_request.format,
                "record_count": export_response.record_count,
                "filters": export_request.filters.dict() if export_request.filters else None
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent")
        )
        
        return export_response
        
    except Exception as e:
        logger.error(f"Error exporting audit logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to export audit logs")


@router.get("/workspaces/{workspace_id}/audit-logs/statistics")
async def get_audit_statistics(
    workspace_id: str,
    date_range_days: int = Query(30, ge=1, le=365, description="Analysis period in days"),
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("audit", "read"))
):
    """Get audit log statistics for dashboard."""
    
    audit_logger = get_audit_logger()
    statistics = await audit_logger.get_audit_statistics(
        workspace_id=workspace_id,
        date_range_days=date_range_days
    )
    
    return statistics


@router.delete("/workspaces/{workspace_id}/audit-logs/cleanup")
async def cleanup_old_audit_logs(
    workspace_id: str,
    request: Request,
    retention_days: int = Query(365, ge=30, le=3650, description="Retention period in days"),
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("audit", "manage"))
):
    """Clean up old audit logs based on retention policy."""
    
    audit_logger = get_audit_logger()
    deleted_count = await audit_logger.cleanup_old_logs(
        workspace_id=workspace_id,
        retention_days=retention_days
    )
    
    # Log the cleanup action
    await audit_logger.log_action(
        user_id=user_context["user_id"],
        workspace_id=workspace_id,
        action="BULK_OPERATION_PERFORMED",
        resource_type="audit_logs",
        resource_id=None,
        changes={
            "operation": "cleanup",
            "retention_days": retention_days,
            "deleted_count": deleted_count
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent")
    )
    
    return {
        "deleted_count": deleted_count,
        "retention_days": retention_days,
        "message": f"Cleaned up {deleted_count} old audit logs"
    }


@router.post("/workspaces/{workspace_id}/test-audit-log")
async def test_audit_log_entry(
    workspace_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_context = Depends(require_permission("audit", "read"))
):
    """Create a test audit log entry for verification."""
    
    audit_logger = get_audit_logger()
    
    log = await audit_logger.log_action(
        user_id=user_context["user_id"],
        workspace_id=workspace_id,
        action="USER_LOGIN",
        resource_type="system",
        resource_id=None,
        changes={
            "test": True,
            "message": "Test audit log entry",
            "endpoint": "/api/audit/workspaces/{workspace_id}/test-audit-log"
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        context={
            "test_entry": True,
            "timestamp": "now"
        }
    )
    
    return {
        "message": "Test audit log created",
        "log_id": log.id,
        "created_at": log.created_at
    }