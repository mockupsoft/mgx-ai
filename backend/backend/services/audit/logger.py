# -*- coding: utf-8 -*-
"""backend.services.audit.logger

Audit logging service for tracking user actions and system changes.
"""

from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, asc, func
from sqlalchemy.orm import selectinload
import json
import logging

from ...db.models.entities import AuditLog, Workspace, UserRole
from ...db.models.enums import AuditAction, AuditLogStatus
from ...schemas import (
    AuditLogCreate, AuditLogResponse, AuditLogFilter, 
    AuditLogExportRequest, AuditLogExportResponse
)

logger = logging.getLogger(__name__)


class AuditLogger:
    """Service for comprehensive audit logging and trail management."""
    
    def __init__(self, session_factory):
        """Initialize audit logger with database session factory."""
        self.session_factory = session_factory
    
    async def log_action(
        self,
        user_id: Optional[str],
        workspace_id: str,
        action: Union[str, AuditAction],
        resource_type: str,
        resource_id: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        status: Union[str, AuditLogStatus] = AuditLogStatus.SUCCESS,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """Log a user action or system event.
        
        Args:
            user_id: User ID (nullable for system actions)
            workspace_id: Workspace ID
            action: Action performed
            resource_type: Type of resource affected
            resource_id: Specific resource ID
            changes: Before/after values or operation details
            status: Operation status
            ip_address: Client IP address
            user_agent: Client user agent
            execution_time_ms: Operation execution time
            error_message: Error message if operation failed
            context: Additional context information
            
        Returns:
            Created AuditLog object
        """
        try:
            # Normalize action to enum
            if isinstance(action, str):
                action = AuditAction(action)
            
            if isinstance(status, str):
                status = AuditLogStatus(status)
            
            # Prepare changes data
            changes_data = self._prepare_changes(changes, context)
            
            async with self.session_factory() as session:
                audit_log = AuditLog(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    changes=changes_data,
                    status=status,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    execution_time_ms=execution_time_ms,
                    error_message=error_message
                )
                
                session.add(audit_log)
                await session.commit()
                await session.refresh(audit_log)
                
                logger.debug(
                    f"Logged audit action: {action.value} by {user_id} "
                    f"on {resource_type}:{resource_id} in workspace {workspace_id}"
                )
                
                return audit_log
                
        except Exception as e:
            logger.error(f"Failed to log audit action: {e}")
            # Don't raise - audit logging failure shouldn't break the main operation
            raise
    
    async def get_audit_trail(
        self,
        workspace_id: str,
        filters: Optional[AuditLogFilter] = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> List[AuditLog]:
        """Get audit trail with filtering and pagination.
        
        Args:
            workspace_id: Workspace ID
            filters: Filter criteria
            limit: Maximum number of records
            offset: Offset for pagination
            sort_by: Field to sort by
            sort_order: Sort direction ('asc' or 'desc')
            
        Returns:
            List of AuditLog objects
        """
        try:
            filters = filters or AuditLogFilter()
            
            async with self.session_factory() as session:
                # Build base query
                stmt = select(AuditLog).where(
                    AuditLog.workspace_id == workspace_id
                )
                
                # Apply filters
                stmt = self._apply_filters(stmt, filters)
                
                # Apply sorting
                sort_field = getattr(AuditLog, sort_by, AuditLog.created_at)
                if sort_order.lower() == "desc":
                    stmt = stmt.order_by(desc(sort_field))
                else:
                    stmt = stmt.order_by(asc(sort_field))
                
                # Apply pagination
                stmt = stmt.offset(offset).limit(limit)
                
                result = await session.execute(stmt)
                logs = result.scalars().all()
                
                logger.debug(
                    f"Retrieved {len(logs)} audit logs for workspace {workspace_id}"
                )
                
                return list(logs)
                
        except Exception as e:
            logger.error(f"Error retrieving audit trail: {e}")
            raise
    
    async def get_audit_log(
        self, 
        log_id: str, 
        workspace_id: str
    ) -> Optional[AuditLog]:
        """Get specific audit log entry.
        
        Args:
            log_id: Audit log ID
            workspace_id: Workspace ID for security
            
        Returns:
            AuditLog object or None
        """
        try:
            async with self.session_factory() as session:
                stmt = select(AuditLog).where(
                    and_(
                        AuditLog.id == log_id,
                        AuditLog.workspace_id == workspace_id
                    )
                )
                
                result = await session.execute(stmt)
                log = result.scalar_one_or_none()
                
                return log
                
        except Exception as e:
            logger.error(f"Error retrieving audit log {log_id}: {e}")
            return None
    
    async def export_audit_logs(
        self,
        workspace_id: str,
        export_request: AuditLogExportRequest,
        export_format: str = "json"
    ) -> AuditLogExportResponse:
        """Export audit logs in specified format.
        
        Args:
            workspace_id: Workspace ID
            export_request: Export request parameters
            export_format: Export format ('json' or 'csv')
            
        Returns:
            Export response with data
        """
        try:
            # Get filtered logs
            logs = await self.get_audit_trail(
                workspace_id,
                filters=export_request.filters,
                limit=export_request.limit or 10000,  # Reasonable limit
                offset=export_request.offset or 0,
                sort_by=export_request.sort_by or "created_at",
                sort_order=export_request.sort_order or "desc"
            )
            
            # Format export data
            export_data = self._format_export_data(logs, export_format)
            
            # Create response
            response = AuditLogExportResponse(
                format=export_format,
                record_count=len(logs),
                exported_at=datetime.utcnow(),
                data=export_data
            )
            
            logger.info(
                f"Exported {len(logs)} audit logs for workspace {workspace_id} "
                f"in {export_format} format"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error exporting audit logs: {e}")
            raise
    
    async def get_audit_statistics(
        self,
        workspace_id: str,
        date_range_days: int = 30
    ) -> Dict[str, Any]:
        """Get audit log statistics for dashboard.
        
        Args:
            workspace_id: Workspace ID
            date_range_days: Number of days to analyze
            
        Returns:
            Dictionary with statistics
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=date_range_days)
            
            async with self.session_factory() as session:
                # Total logs in period
                total_stmt = select(func.count(AuditLog.id)).where(
                    and_(
                        AuditLog.workspace_id == workspace_id,
                        AuditLog.created_at >= start_date
                    )
                )
                total_result = await session.execute(total_stmt)
                total_logs = total_result.scalar() or 0
                
                # Logs by action
                action_stmt = select(
                    AuditLog.action,
                    func.count(AuditLog.id)
                ).where(
                    and_(
                        AuditLog.workspace_id == workspace_id,
                        AuditLog.created_at >= start_date
                    )
                ).group_by(AuditLog.action)
                
                action_result = await session.execute(action_stmt)
                action_counts = dict(action_result.all())
                
                # Logs by status
                status_stmt = select(
                    AuditLog.status,
                    func.count(AuditLog.id)
                ).where(
                    and_(
                        AuditLog.workspace_id == workspace_id,
                        AuditLog.created_at >= start_date
                    )
                ).group_by(AuditLog.status)
                
                status_result = await session.execute(status_stmt)
                status_counts = dict(status_result.all())
                
                # Daily activity
                daily_stmt = select(
                    func.date(AuditLog.created_at),
                    func.count(AuditLog.id)
                ).where(
                    and_(
                        AuditLog.workspace_id == workspace_id,
                        AuditLog.created_at >= start_date
                    )
                ).group_by(func.date(AuditLog.created_at))
                
                daily_result = await session.execute(daily_stmt)
                daily_counts = dict(daily_result.all())
                
                statistics = {
                    "total_logs": total_logs,
                    "date_range_days": date_range_days,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "action_distribution": action_counts,
                    "status_distribution": status_counts,
                    "daily_activity": daily_counts
                }
                
                return statistics
                
        except Exception as e:
            logger.error(f"Error getting audit statistics: {e}")
            return {}
    
    async def cleanup_old_logs(
        self,
        workspace_id: str,
        retention_days: int = 365
    ) -> int:
        """Clean up old audit logs based on retention policy.
        
        Args:
            workspace_id: Workspace ID
            retention_days: Number of days to retain
            
        Returns:
            Number of logs deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            async with self.session_factory() as session:
                # Get count before deletion
                count_stmt = select(func.count(AuditLog.id)).where(
                    and_(
                        AuditLog.workspace_id == workspace_id,
                        AuditLog.created_at < cutoff_date
                    )
                )
                count_result = await session.execute(count_stmt)
                count_to_delete = count_result.scalar() or 0
                
                # Delete old logs
                delete_stmt = AuditLog.__table__.delete().where(
                    and_(
                        AuditLog.workspace_id == workspace_id,
                        AuditLog.created_at < cutoff_date
                    )
                )
                
                await session.execute(delete_stmt)
                await session.commit()
                
                logger.info(
                    f"Cleaned up {count_to_delete} old audit logs "
                    f"for workspace {workspace_id} (older than {retention_days} days)"
                )
                
                return count_to_delete
                
        except Exception as e:
            logger.error(f"Error cleaning up old audit logs: {e}")
            return 0
    
    def _prepare_changes(
        self, 
        changes: Optional[Dict[str, Any]], 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Prepare changes data for storage.
        
        Args:
            changes: Raw changes data
            context: Additional context
            
        Returns:
            Prepared changes dictionary
        """
        if not changes and not context:
            return {}
        
        result = {}
        
        if changes:
            # Serialize complex objects
            for key, value in changes.items():
                if isinstance(value, (dict, list)):
                    result[key] = json.dumps(value, default=str)
                else:
                    result[key] = value
        
        if context:
            result["_context"] = context
        
        return result
    
    def _apply_filters(self, stmt, filters: AuditLogFilter):
        """Apply filters to query.
        
        Args:
            stmt: SQLAlchemy select statement
            filters: Filter criteria
            
        Returns:
            Filtered statement
        """
        if filters.user_id:
            stmt = stmt.where(AuditLog.user_id == filters.user_id)
        
        if filters.action:
            if isinstance(filters.action, str):
                action = AuditAction(filters.action)
            else:
                action = filters.action
            stmt = stmt.where(AuditLog.action == action)
        
        if filters.resource_type:
            stmt = stmt.where(AuditLog.resource_type == filters.resource_type)
        
        if filters.resource_id:
            stmt = stmt.where(AuditLog.resource_id == filters.resource_id)
        
        if filters.status:
            if isinstance(filters.status, str):
                status = AuditLogStatus(filters.status)
            else:
                status = filters.status
            stmt = stmt.where(AuditLog.status == status)
        
        if filters.date_from:
            stmt = stmt.where(AuditLog.created_at >= filters.date_from)
        
        if filters.date_to:
            stmt = stmt.where(AuditLog.created_at <= filters.date_to)
        
        if filters.ip_address:
            stmt = stmt.where(AuditLog.ip_address.like(f"%{filters.ip_address}%"))
        
        return stmt
    
    def _format_export_data(
        self, 
        logs: List[AuditLog], 
        format_type: str
    ) -> Union[List[Dict[str, Any]], str]:
        """Format audit logs for export.
        
        Args:
            logs: List of audit logs
            format_type: Export format
            
        Returns:
            Formatted data
        """
        if format_type.lower() == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                "ID", "Timestamp", "User ID", "Action", "Resource Type",
                "Resource ID", "Status", "IP Address", "User Agent",
                "Execution Time (ms)", "Error Message", "Changes"
            ])
            
            # Data rows
            for log in logs:
                writer.writerow([
                    log.id,
                    log.created_at.isoformat() if log.created_at else "",
                    log.user_id or "",
                    log.action.value if log.action else "",
                    log.resource_type,
                    log.resource_id or "",
                    log.status.value if log.status else "",
                    log.ip_address or "",
                    log.user_agent or "",
                    log.execution_time_ms or "",
                    log.error_message or "",
                    json.dumps(log.changes, default=str) if log.changes else ""
                ])
            
            return output.getvalue()
        
        else:  # JSON format
            return [
                {
                    "id": log.id,
                    "timestamp": log.created_at.isoformat() if log.created_at else None,
                    "user_id": log.user_id,
                    "action": log.action.value if log.action else None,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "status": log.status.value if log.status else None,
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                    "execution_time_ms": log.execution_time_ms,
                    "error_message": log.error_message,
                    "changes": log.changes
                }
                for log in logs
            ]

    async def log_secret_action(
        self,
        secret_id: str,
        action: Union[str, Any],  # SecretAuditAction
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> Any:  # SecretAudit
        """Log a secret-related action.
        
        Args:
            secret_id: ID of the secret
            action: Action performed on the secret
            user_id: User who performed the action
            ip_address: Client IP address
            user_agent: Client user agent
            request_id: Unique request identifier
            details: Additional operation details
            metadata: Additional metadata
            success: Whether the operation was successful
            error_message: Error message if the operation failed
            
        Returns:
            Created SecretAudit record
        """
        try:
            from ...db.models.entities import SecretAudit
            from ...db.models.enums import SecretAuditAction
            
            # Convert action to enum if it's a string
            if isinstance(action, str):
                action = SecretAuditAction(action)
            
            secret_audit = SecretAudit(
                secret_id=secret_id,
                action=action,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                details=details or {},
                metadata=metadata or {},
                success=success,
                error_message=error_message
            )
            
            async with self.session_factory() as session:
                session.add(secret_audit)
                await session.commit()
                await session.refresh(secret_audit)
                
                logger.debug(f"Logged secret audit: {action} for secret {secret_id}")
                return secret_audit
                
        except Exception as e:
            logger.error(f"Failed to log secret action: {e}")
            # Don't raise here to avoid disrupting the main operation
            return None


# Global audit logger instance
audit_logger = None


async def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance."""
    global audit_logger
    if audit_logger is None:
        from ...db.engine import get_session_factory
        session_factory = await get_session_factory()
        audit_logger = AuditLogger(session_factory)
    return audit_logger