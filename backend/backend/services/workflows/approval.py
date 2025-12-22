# -*- coding: utf-8 -*-
"""
Workflow Approval Service

Manages human-in-the-loop approval workflows for workflow steps.
Supports approval, rejection, and revision loops.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.db.models import (
    WorkflowStepApproval,
    WorkflowStepExecution,
    WorkflowExecution,
    ApprovalStatus,
    WorkflowStepStatus,
)
from backend.schemas import EventPayload, EventTypeEnum
from backend.services.events import get_event_broadcaster

logger = logging.getLogger(__name__)


class ApprovalService:
    """
    Service for managing workflow approval workflows.
    
    Features:
    - Create approval requests
    - Handle approval/rejection/change requests
    - Auto-approval configuration
    - Revision loop management
    - Timeout handling
    """
    
    def __init__(self):
        self.pending_approvals: Dict[str, asyncio.Event] = {}
        logger.info("ApprovalService initialized")
    
    async def create_approval_request(
        self,
        session: AsyncSession,
        step_execution_id: str,
        workflow_execution_id: str,
        workspace_id: str,
        project_id: str,
        title: str,
        description: Optional[str] = None,
        approval_data: Optional[Dict[str, Any]] = None,
        auto_approve_after_seconds: Optional[int] = None,
        required_approvers: Optional[List[str]] = None,
        expires_after_seconds: Optional[int] = None,
        parent_approval_id: Optional[str] = None,
    ) -> WorkflowStepApproval:
        """
        Create a new approval request for a workflow step.
        
        Args:
            session: Database session
            step_execution_id: Step execution ID
            workflow_execution_id: Workflow execution ID
            workspace_id: Workspace ID
            project_id: Project ID
            title: Approval request title
            description: Approval request description
            approval_data: Data to be approved
            auto_approve_after_seconds: Auto-approve after N seconds
            required_approvers: List of required approver IDs
            expires_after_seconds: Expiration timeout
            parent_approval_id: Parent approval for revisions
            
        Returns:
            Created approval request
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=expires_after_seconds) if expires_after_seconds else None
        
        approval = WorkflowStepApproval(
            step_execution_id=step_execution_id,
            workflow_execution_id=workflow_execution_id,
            workspace_id=workspace_id,
            project_id=project_id,
            status=ApprovalStatus.PENDING,
            title=title,
            description=description,
            approval_data=approval_data or {},
            requested_at=now,
            expires_at=expires_at,
            auto_approve_after_seconds=auto_approve_after_seconds,
            required_approvers=required_approvers or [],
            parent_approval_id=parent_approval_id,
        )
        
        # Increment revision count if this is a revision
        if parent_approval_id:
            parent_result = await session.execute(
                select(WorkflowStepApproval).where(WorkflowStepApproval.id == parent_approval_id)
            )
            parent = parent_result.scalar_one_or_none()
            if parent:
                approval.revision_count = parent.revision_count + 1
        
        session.add(approval)
        await session.flush()
        
        # Create async event for waiting
        approval_event = asyncio.Event()
        self.pending_approvals[approval.id] = approval_event
        
        # Emit approval requested event
        try:
            broadcaster = get_event_broadcaster()
            await broadcaster.publish(
                EventPayload(
                    event_type=EventTypeEnum.APPROVAL_REQUIRED,
                    workspace_id=workspace_id,
                    workflow_id=workflow_execution_id,
                    workflow_execution_id=workflow_execution_id,
                    data={
                        "approval_id": approval.id,
                        "title": title,
                        "description": description,
                        "approval_data": approval_data,
                        "expires_at": expires_at.isoformat() if expires_at else None,
                        "auto_approve_after_seconds": auto_approve_after_seconds,
                    },
                    message=f"Approval required: {title}",
                )
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast approval request event: {e}")
        
        # Schedule auto-approval if configured
        if auto_approve_after_seconds:
            asyncio.create_task(
                self._schedule_auto_approval(
                    approval.id, auto_approve_after_seconds, workspace_id
                )
            )
        
        # Schedule expiration check if configured
        if expires_after_seconds:
            asyncio.create_task(
                self._schedule_expiration_check(
                    approval.id, expires_after_seconds, workspace_id
                )
            )
        
        logger.info(f"Created approval request {approval.id} for step execution {step_execution_id}")
        return approval
    
    async def approve(
        self,
        session: AsyncSession,
        approval_id: str,
        approved_by: str,
        feedback: Optional[str] = None,
        response_data: Optional[Dict[str, Any]] = None,
    ) -> WorkflowStepApproval:
        """
        Approve a pending approval request.
        
        Args:
            session: Database session
            approval_id: Approval request ID
            approved_by: User who approved
            feedback: Approval feedback
            response_data: Additional response data
            
        Returns:
            Updated approval request
        """
        result = await session.execute(
            select(WorkflowStepApproval).where(WorkflowStepApproval.id == approval_id)
        )
        approval = result.scalar_one_or_none()
        
        if not approval:
            raise ValueError(f"Approval request {approval_id} not found")
        
        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval request {approval_id} is not pending")
        
        # Update approval
        approval.status = ApprovalStatus.APPROVED
        approval.approved_by = approved_by
        approval.feedback = feedback
        approval.response_data = response_data or {}
        approval.responded_at = datetime.utcnow()
        
        await session.flush()
        
        # Signal waiting tasks
        if approval_id in self.pending_approvals:
            self.pending_approvals[approval_id].set()
        
        # Emit approval granted event
        try:
            broadcaster = get_event_broadcaster()
            await broadcaster.publish(
                EventPayload(
                    event_type=EventTypeEnum.APPROVAL_GRANTED,
                    workspace_id=approval.workspace_id,
                    workflow_id=approval.workflow_execution_id,
                    workflow_execution_id=approval.workflow_execution_id,
                    data={
                        "approval_id": approval.id,
                        "approved_by": approved_by,
                        "feedback": feedback,
                    },
                    message=f"Approval granted: {approval.title}",
                )
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast approval granted event: {e}")
        
        logger.info(f"Approval {approval_id} approved by {approved_by}")
        return approval
    
    async def reject(
        self,
        session: AsyncSession,
        approval_id: str,
        rejected_by: str,
        feedback: Optional[str] = None,
        response_data: Optional[Dict[str, Any]] = None,
    ) -> WorkflowStepApproval:
        """
        Reject a pending approval request.
        
        Args:
            session: Database session
            approval_id: Approval request ID
            rejected_by: User who rejected
            feedback: Rejection feedback
            response_data: Additional response data
            
        Returns:
            Updated approval request
        """
        result = await session.execute(
            select(WorkflowStepApproval).where(WorkflowStepApproval.id == approval_id)
        )
        approval = result.scalar_one_or_none()
        
        if not approval:
            raise ValueError(f"Approval request {approval_id} not found")
        
        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval request {approval_id} is not pending")
        
        # Update approval
        approval.status = ApprovalStatus.REJECTED
        approval.approved_by = rejected_by
        approval.feedback = feedback
        approval.response_data = response_data or {}
        approval.responded_at = datetime.utcnow()
        
        await session.flush()
        
        # Signal waiting tasks
        if approval_id in self.pending_approvals:
            self.pending_approvals[approval_id].set()
        
        # Emit approval rejected event
        try:
            broadcaster = get_event_broadcaster()
            await broadcaster.publish(
                EventPayload(
                    event_type=EventTypeEnum.APPROVAL_REJECTED,
                    workspace_id=approval.workspace_id,
                    workflow_id=approval.workflow_execution_id,
                    workflow_execution_id=approval.workflow_execution_id,
                    data={
                        "approval_id": approval.id,
                        "rejected_by": rejected_by,
                        "feedback": feedback,
                    },
                    message=f"Approval rejected: {approval.title}",
                )
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast approval rejected event: {e}")
        
        logger.info(f"Approval {approval_id} rejected by {rejected_by}")
        return approval
    
    async def request_changes(
        self,
        session: AsyncSession,
        approval_id: str,
        requested_by: str,
        feedback: str,
        response_data: Optional[Dict[str, Any]] = None,
    ) -> WorkflowStepApproval:
        """
        Request changes on a pending approval request.
        This triggers a revision loop.
        
        Args:
            session: Database session
            approval_id: Approval request ID
            requested_by: User who requested changes
            feedback: Change request feedback
            response_data: Additional response data
            
        Returns:
            Updated approval request
        """
        result = await session.execute(
            select(WorkflowStepApproval).where(WorkflowStepApproval.id == approval_id)
        )
        approval = result.scalar_one_or_none()
        
        if not approval:
            raise ValueError(f"Approval request {approval_id} not found")
        
        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval request {approval_id} is not pending")
        
        # Update approval
        approval.status = ApprovalStatus.REQUEST_CHANGES
        approval.approved_by = requested_by
        approval.feedback = feedback
        approval.response_data = response_data or {}
        approval.responded_at = datetime.utcnow()
        
        await session.flush()
        
        # Signal waiting tasks
        if approval_id in self.pending_approvals:
            self.pending_approvals[approval_id].set()
        
        # Emit changes requested event
        try:
            broadcaster = get_event_broadcaster()
            await broadcaster.publish(
                EventPayload(
                    event_type=EventTypeEnum.CHANGES_REQUESTED,
                    workspace_id=approval.workspace_id,
                    workflow_id=approval.workflow_execution_id,
                    workflow_execution_id=approval.workflow_execution_id,
                    data={
                        "approval_id": approval.id,
                        "requested_by": requested_by,
                        "feedback": feedback,
                        "revision_count": approval.revision_count,
                    },
                    message=f"Changes requested: {approval.title}",
                )
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast changes requested event: {e}")
        
        logger.info(f"Changes requested on approval {approval_id} by {requested_by}")
        return approval
    
    async def wait_for_approval(
        self,
        session: AsyncSession,
        approval_id: str,
        timeout_seconds: Optional[int] = None,
    ) -> ApprovalStatus:
        """
        Wait for an approval request to be responded to.
        
        Args:
            session: Database session
            approval_id: Approval request ID
            timeout_seconds: Timeout in seconds
            
        Returns:
            Final approval status
        """
        if approval_id not in self.pending_approvals:
            # Approval might already be resolved, check database
            result = await session.execute(
                select(WorkflowStepApproval).where(WorkflowStepApproval.id == approval_id)
            )
            approval = result.scalar_one_or_none()
            
            if not approval:
                raise ValueError(f"Approval request {approval_id} not found")
            
            return approval.status
        
        approval_event = self.pending_approvals[approval_id]
        
        try:
            if timeout_seconds:
                await asyncio.wait_for(approval_event.wait(), timeout=timeout_seconds)
            else:
                await approval_event.wait()
        except asyncio.TimeoutError:
            # Mark as timeout
            result = await session.execute(
                select(WorkflowStepApproval).where(WorkflowStepApproval.id == approval_id)
            )
            approval = result.scalar_one_or_none()
            
            if approval and approval.status == ApprovalStatus.PENDING:
                approval.status = ApprovalStatus.TIMEOUT
                approval.responded_at = datetime.utcnow()
                await session.flush()
            
            return ApprovalStatus.TIMEOUT
        finally:
            # Cleanup
            self.pending_approvals.pop(approval_id, None)
        
        # Get final status
        result = await session.execute(
            select(WorkflowStepApproval).where(WorkflowStepApproval.id == approval_id)
        )
        approval = result.scalar_one_or_none()
        
        return approval.status if approval else ApprovalStatus.CANCELLED
    
    async def get_pending_approvals(
        self,
        session: AsyncSession,
        workspace_id: str,
        project_id: Optional[str] = None,
        workflow_execution_id: Optional[str] = None,
    ) -> List[WorkflowStepApproval]:
        """
        Get pending approval requests for a workspace/project.
        
        Args:
            session: Database session
            workspace_id: Workspace ID
            project_id: Optional project ID filter
            workflow_execution_id: Optional workflow execution filter
            
        Returns:
            List of pending approval requests
        """
        query = select(WorkflowStepApproval).where(
            and_(
                WorkflowStepApproval.workspace_id == workspace_id,
                WorkflowStepApproval.status == ApprovalStatus.PENDING,
            )
        )
        
        if project_id:
            query = query.where(WorkflowStepApproval.project_id == project_id)
        
        if workflow_execution_id:
            query = query.where(WorkflowStepApproval.workflow_execution_id == workflow_execution_id)
        
        query = query.order_by(WorkflowStepApproval.requested_at.desc())
        
        result = await session.execute(query)
        return list(result.scalars().all())
    
    async def _schedule_auto_approval(
        self,
        approval_id: str,
        delay_seconds: int,
        workspace_id: str,
    ):
        """Schedule automatic approval after delay."""
        await asyncio.sleep(delay_seconds)
        
        # Auto-approve if still pending
        from backend.db.session import get_session_factory
        
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(WorkflowStepApproval).where(WorkflowStepApproval.id == approval_id)
            )
            approval = result.scalar_one_or_none()
            
            if approval and approval.status == ApprovalStatus.PENDING:
                await self.approve(
                    session,
                    approval_id,
                    approved_by="system_auto_approval",
                    feedback="Auto-approved after timeout",
                )
                await session.commit()
                logger.info(f"Auto-approved approval {approval_id}")
    
    async def _schedule_expiration_check(
        self,
        approval_id: str,
        delay_seconds: int,
        workspace_id: str,
    ):
        """Schedule expiration check for approval."""
        await asyncio.sleep(delay_seconds)
        
        # Mark as timeout if still pending
        from backend.db.session import get_session_factory
        
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(WorkflowStepApproval).where(WorkflowStepApproval.id == approval_id)
            )
            approval = result.scalar_one_or_none()
            
            if approval and approval.status == ApprovalStatus.PENDING:
                approval.status = ApprovalStatus.TIMEOUT
                approval.responded_at = datetime.utcnow()
                await session.flush()
                
                # Signal waiting tasks
                if approval_id in self.pending_approvals:
                    self.pending_approvals[approval_id].set()
                
                await session.commit()
                logger.info(f"Approval {approval_id} expired")


__all__ = ["ApprovalService"]
