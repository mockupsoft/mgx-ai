# -*- coding: utf-8 -*-
"""
File-Level Approval Service

Manages granular file-level approvals within approval workflows.
Supports individual file approval, inline comments, and audit trails.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.db.models import (
    FileChange,
    FileApproval,
    ApprovalHistory,
    WorkflowStepApproval,
    FileApprovalStatus,
    ApprovalStatus,
)
from backend.schemas import EventPayload, EventTypeEnum
from backend.services.events import get_event_broadcaster

logger = logging.getLogger(__name__)


class FileApprovalService:
    """
    Service for managing file-level granular approvals.
    
    Features:
    - Individual file approval/rejection
    - Inline comments on specific lines
    - Approval history tracking
    - Rollback capabilities
    - Integration with existing approval workflows
    """
    
    async def create_file_changes_from_approval_data(
        self,
        session: AsyncSession,
        workflow_approval_id: str,
        approval_data: Dict[str, Any],
    ) -> List[FileChange]:
        """
        Create file change records from approval data.
        
        Args:
            session: Database session
            workflow_approval_id: Parent approval ID
            approval_data: Data containing file changes
            
        Returns:
            List of created file changes
        """
        # Get the workflow approval to get workspace/project info
        approval_result = await session.execute(
            select(WorkflowStepApproval).where(WorkflowStepApproval.id == workflow_approval_id)
        )
        workflow_approval = approval_result.scalar_one_or_none()
        
        if not workflow_approval:
            raise ValueError(f"Workflow approval {workflow_approval_id} not found")
        
        file_changes = []
        
        # Extract file changes from approval data
        changes_data = approval_data.get('file_changes', [])
        
        for change_data in changes_data:
            file_change = FileChange(
                workflow_step_approval_id=workflow_approval_id,
                workspace_id=workflow_approval.workspace_id,
                project_id=workflow_approval.project_id,
                file_path=change_data.get('file_path', ''),
                file_name=change_data.get('file_name', ''),
                file_type=change_data.get('file_type', ''),
                change_type=change_data.get('change_type', 'modified'),
                is_new_file=change_data.get('is_new_file', False),
                is_binary=change_data.get('is_binary', False),
                original_content=change_data.get('original_content'),
                new_content=change_data.get('new_content'),
                diff_summary=change_data.get('diff_summary', {}),
                line_changes=change_data.get('line_changes', []),
                change_status='pending',
            )
            
            session.add(file_change)
            file_changes.append(file_change)
            
            # Create corresponding file approval record
            file_approval = FileApproval(
                file_change_id=file_change.id,
                workflow_step_approval_id=workflow_approval_id,
                workspace_id=workflow_approval.workspace_id,
                project_id=workflow_approval.project_id,
                status=FileApprovalStatus.PENDING,
                inline_comments=[],
                review_metadata={},
            )
            
            session.add(file_approval)
        
        await session.flush()
        
        logger.info(f"Created {len(file_changes)} file changes for approval {workflow_approval_id}")
        return file_changes
    
    async def approve_file(
        self,
        session: AsyncSession,
        file_approval_id: str,
        approved_by: str,
        reviewer_comment: Optional[str] = None,
        review_metadata: Optional[Dict[str, Any]] = None,
    ) -> FileApproval:
        """
        Approve a specific file.
        
        Args:
            session: Database session
            file_approval_id: File approval ID
            approved_by: User who approved
            reviewer_comment: Optional reviewer comment
            review_metadata: Additional review metadata
            
        Returns:
            Updated file approval
        """
        result = await session.execute(
            select(FileApproval).where(FileApproval.id == file_approval_id)
        )
        file_approval = result.scalar_one_or_none()
        
        if not file_approval:
            raise ValueError(f"File approval {file_approval_id} not found")
        
        if file_approval.status != FileApprovalStatus.PENDING:
            raise ValueError(f"File approval {file_approval_id} is not pending")
        
        old_status = file_approval.status
        
        # Update file approval
        file_approval.status = FileApprovalStatus.APPROVED
        file_approval.approved_by = approved_by
        file_approval.reviewer_comment = reviewer_comment
        file_approval.reviewed_at = datetime.utcnow()
        if review_metadata:
            file_approval.review_metadata.update(review_metadata)
        
        await session.flush()
        
        # Create history record
        await self._create_history_record(
            session,
            file_approval.workflow_step_approval_id,
            file_approval_id,
            approved_by,
            'approve',
            old_status.value,
            file_approval.status.value,
            reviewer_comment,
            {'file_path': file_approval.file_change.file_path} if file_approval.file_change else None,
        )
        
        # Emit event
        try:
            broadcaster = get_event_broadcaster()
            await broadcaster.publish(
                EventPayload(
                    event_type=EventTypeEnum.FILE_APPROVED,
                    workspace_id=file_approval.workspace_id,
                    workflow_id=file_approval.workflow_step_approval_id,
                    workflow_execution_id=file_approval.approval.workflow_execution_id,
                    data={
                        "file_approval_id": file_approval_id,
                        "file_path": file_approval.file_change.file_path,
                        "approved_by": approved_by,
                        "reviewer_comment": reviewer_comment,
                    },
                    message=f"File approved: {file_approval.file_change.file_path}",
                )
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast file approval event: {e}")
        
        # Check if all files are approved and update parent approval
        await self._check_and_update_parent_approval(session, file_approval.workflow_step_approval_id)
        
        logger.info(f"File {file_approval_id} approved by {approved_by}")
        return file_approval
    
    async def reject_file(
        self,
        session: AsyncSession,
        file_approval_id: str,
        rejected_by: str,
        reviewer_comment: str,
        review_metadata: Optional[Dict[str, Any]] = None,
    ) -> FileApproval:
        """
        Reject a specific file.
        
        Args:
            session: Database session
            file_approval_id: File approval ID
            rejected_by: User who rejected
            reviewer_comment: Rejection comment (required)
            review_metadata: Additional review metadata
            
        Returns:
            Updated file approval
        """
        result = await session.execute(
            select(FileApproval).where(FileApproval.id == file_approval_id)
        )
        file_approval = result.scalar_one_or_none()
        
        if not file_approval:
            raise ValueError(f"File approval {file_approval_id} not found")
        
        if file_approval.status != FileApprovalStatus.PENDING:
            raise ValueError(f"File approval {file_approval_id} is not pending")
        
        old_status = file_approval.status
        
        # Update file approval
        file_approval.status = FileApprovalStatus.REJECTED
        file_approval.approved_by = rejected_by
        file_approval.reviewer_comment = reviewer_comment
        file_approval.reviewed_at = datetime.utcnow()
        if review_metadata:
            file_approval.review_metadata.update(review_metadata)
        
        await session.flush()
        
        # Create history record
        await self._create_history_record(
            session,
            file_approval.workflow_step_approval_id,
            file_approval_id,
            rejected_by,
            'reject',
            old_status.value,
            file_approval.status.value,
            reviewer_comment,
            {'file_path': file_approval.file_change.file_path} if file_approval.file_change else None,
        )
        
        # Emit event
        try:
            broadcaster = get_event_broadcaster()
            await broadcaster.publish(
                EventPayload(
                    event_type=EventTypeEnum.FILE_REJECTED,
                    workspace_id=file_approval.workspace_id,
                    workflow_id=file_approval.workflow_step_approval_id,
                    workflow_execution_id=file_approval.approval.workflow_execution_id,
                    data={
                        "file_approval_id": file_approval_id,
                        "file_path": file_approval.file_change.file_path,
                        "rejected_by": rejected_by,
                        "reviewer_comment": reviewer_comment,
                    },
                    message=f"File rejected: {file_approval.file_change.file_path}",
                )
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast file rejection event: {e}")
        
        # Update parent approval to reflect mixed status
        await self._check_and_update_parent_approval(session, file_approval.workflow_step_approval_id)
        
        logger.info(f"File {file_approval_id} rejected by {rejected_by}")
        return file_approval
    
    async def request_file_changes(
        self,
        session: AsyncSession,
        file_approval_id: str,
        requested_by: str,
        reviewer_comment: str,
        review_metadata: Optional[Dict[str, Any]] = None,
    ) -> FileApproval:
        """
        Request changes for a specific file.
        
        Args:
            session: Database session
            file_approval_id: File approval ID
            requested_by: User who requested changes
            reviewer_comment: Change request comment
            review_metadata: Additional review metadata
            
        Returns:
            Updated file approval
        """
        result = await session.execute(
            select(FileApproval).where(FileApproval.id == file_approval_id)
        )
        file_approval = result.scalar_one_or_none()
        
        if not file_approval:
            raise ValueError(f"File approval {file_approval_id} not found")
        
        if file_approval.status != FileApprovalStatus.PENDING:
            raise ValueError(f"File approval {file_approval_id} is not pending")
        
        old_status = file_approval.status
        
        # Update file approval
        file_approval.status = FileApprovalStatus.CHANGES_REQUESTED
        file_approval.approved_by = requested_by
        file_approval.reviewer_comment = reviewer_comment
        file_approval.reviewed_at = datetime.utcnow()
        if review_metadata:
            file_approval.review_metadata.update(review_metadata)
        
        await session.flush()
        
        # Create history record
        await self._create_history_record(
            session,
            file_approval.workflow_step_approval_id,
            file_approval_id,
            requested_by,
            'request_changes',
            old_status.value,
            file_approval.status.value,
            reviewer_comment,
            {'file_path': file_approval.file_change.file_path} if file_approval.file_change else None,
        )
        
        # Emit event
        try:
            broadcaster = get_event_broadcaster()
            await broadcaster.publish(
                EventPayload(
                    event_type=EventTypeEnum.FILE_CHANGES_REQUESTED,
                    workspace_id=file_approval.workspace_id,
                    workflow_id=file_approval.workflow_step_approval_id,
                    workflow_execution_id=file_approval.approval.workflow_execution_id,
                    data={
                        "file_approval_id": file_approval_id,
                        "file_path": file_approval.file_change.file_path,
                        "requested_by": requested_by,
                        "reviewer_comment": reviewer_comment,
                    },
                    message=f"Changes requested for file: {file_approval.file_change.file_path}",
                )
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast file changes request event: {e}")
        
        # Update parent approval to reflect mixed status
        await self._check_and_update_parent_approval(session, file_approval.workflow_step_approval_id)
        
        logger.info(f"Changes requested for file {file_approval_id} by {requested_by}")
        return file_approval
    
    async def add_inline_comment(
        self,
        session: AsyncSession,
        file_approval_id: str,
        line_number: int,
        comment_text: str,
        commented_by: str,
    ) -> FileApproval:
        """
        Add an inline comment to a specific line in a file.
        
        Args:
            session: Database session
            file_approval_id: File approval ID
            line_number: Line number to comment on
            comment_text: Comment text
            commented_by: User who added the comment
            
        Returns:
            Updated file approval
        """
        result = await session.execute(
            select(FileApproval).where(FileApproval.id == file_approval_id)
        )
        file_approval = result.scalar_one_or_none()
        
        if not file_approval:
            raise ValueError(f"File approval {file_approval_id} not found")
        
        # Add inline comment
        new_comment = {
            "line_number": line_number,
            "comment_text": comment_text,
            "commented_by": commented_by,
            "commented_at": datetime.utcnow().isoformat(),
        }
        
        file_approval.inline_comments.append(new_comment)
        
        # Create history record
        await self._create_history_record(
            session,
            file_approval.workflow_step_approval_id,
            file_approval_id,
            commented_by,
            'comment',
            file_approval.status.value,
            file_approval.status.value,
            f"Inline comment on line {line_number}: {comment_text}",
            {
                "file_path": file_approval.file_change.file_path if file_approval.file_change else None,
                "line_number": line_number,
            },
        )
        
        await session.flush()
        
        # Emit event
        try:
            broadcaster = get_event_broadcaster()
            await broadcaster.publish(
                EventPayload(
                    event_type=EventTypeEnum.FILE_COMMENT_ADDED,
                    workspace_id=file_approval.workspace_id,
                    workflow_id=file_approval.workflow_step_approval_id,
                    workflow_execution_id=file_approval.approval.workflow_execution_id,
                    data={
                        "file_approval_id": file_approval_id,
                        "file_path": file_approval.file_change.file_path,
                        "line_number": line_number,
                        "comment_text": comment_text,
                        "commented_by": commented_by,
                    },
                    message=f"Inline comment added to {file_approval.file_change.file_path}:{line_number}",
                )
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast inline comment event: {e}")
        
        logger.info(f"Inline comment added to file {file_approval_id} on line {line_number}")
        return file_approval
    
    async def get_file_approvals_for_workflow_approval(
        self,
        session: AsyncSession,
        workflow_approval_id: str,
    ) -> List[FileApproval]:
        """
        Get all file approvals for a workflow approval.
        
        Args:
            session: Database session
            workflow_approval_id: Workflow approval ID
            
        Returns:
            List of file approvals
        """
        result = await session.execute(
            select(FileApproval)
            .where(FileApproval.workflow_step_approval_id == workflow_approval_id)
            .order_by(FileApproval.created_at)
        )
        return list(result.scalars().all())
    
    async def get_approval_history(
        self,
        session: AsyncSession,
        workflow_approval_id: str,
        file_approval_id: Optional[str] = None,
    ) -> List[ApprovalHistory]:
        """
        Get approval history for a workflow approval or specific file.
        
        Args:
            session: Database session
            workflow_approval_id: Workflow approval ID
            file_approval_id: Optional specific file approval ID
            
        Returns:
            List of approval history records
        """
        query = select(ApprovalHistory).where(
            ApprovalHistory.workflow_step_approval_id == workflow_approval_id
        )
        
        if file_approval_id:
            query = query.where(ApprovalHistory.file_approval_id == file_approval_id)
        
        query = query.order_by(ApprovalHistory.created_at.desc())
        
        result = await session.execute(query)
        return list(result.scalars().all())
    
    async def rollback_file_approval(
        self,
        session: AsyncSession,
        file_approval_id: str,
        rolled_back_by: str,
        rollback_reason: str,
    ) -> FileApproval:
        """
        Rollback a file approval to PENDING status.
        
        Args:
            session: Database session
            file_approval_id: File approval ID to rollback
            rolled_back_by: User who initiated rollback
            rollback_reason: Reason for rollback
            
        Returns:
            Updated file approval
        """
        result = await session.execute(
            select(FileApproval).where(FileApproval.id == file_approval_id)
        )
        file_approval = result.scalar_one_or_none()
        
        if not file_approval:
            raise ValueError(f"File approval {file_approval_id} not found")
        
        if file_approval.status == FileApprovalStatus.PENDING:
            raise ValueError(f"File approval {file_approval_id} is already pending")
        
        old_status = file_approval.status
        
        # Rollback to pending
        file_approval.status = FileApprovalStatus.PENDING
        file_approval.approved_by = None
        file_approval.reviewer_comment = None
        file_approval.reviewed_at = None
        file_approval.review_metadata['rollback_reason'] = rollback_reason
        file_approval.review_metadata['rolled_back_by'] = rolled_back_by
        file_approval.review_metadata['rolled_back_at'] = datetime.utcnow().isoformat()
        
        await session.flush()
        
        # Create history record
        await self._create_history_record(
            session,
            file_approval.workflow_step_approval_id,
            file_approval_id,
            rolled_back_by,
            'rollback',
            old_status,
            file_approval.status.value,
            rollback_reason,
            {'file_path': file_approval.file_change.file_path} if file_approval.file_change else None,
        )
        
        # Emit event
        try:
            broadcaster = get_event_broadcaster()
            await broadcaster.publish(
                EventPayload(
                    event_type=EventTypeEnum.FILE_APPROVAL_ROLLED_BACK,
                    workspace_id=file_approval.workspace_id,
                    workflow_id=file_approval.workflow_step_approval_id,
                    workflow_execution_id=file_approval.approval.workflow_execution_id,
                    data={
                        "file_approval_id": file_approval_id,
                        "file_path": file_approval.file_change.file_path,
                        "rolled_back_by": rolled_back_by,
                        "rollback_reason": rollback_reason,
                        "old_status": old_status,
                    },
                    message=f"File approval rolled back: {file_approval.file_change.file_path}",
                )
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast rollback event: {e}")
        
        # Check and update parent approval
        await self._check_and_update_parent_approval(session, file_approval.workflow_step_approval_id)
        
        logger.info(f"File approval {file_approval_id} rolled back by {rolled_back_by}")
        return file_approval
    
    async def _create_history_record(
        self,
        session: AsyncSession,
        workflow_approval_id: str,
        file_approval_id: Optional[str],
        actor_id: str,
        action_type: str,
        old_status: str,
        new_status: str,
        action_comment: Optional[str],
        context_info: Optional[Dict[str, Any]],
    ):
        """Create an approval history record."""
        # Get workflow approval for context
        approval_result = await session.execute(
            select(WorkflowStepApproval).where(WorkflowStepApproval.id == workflow_approval_id)
        )
        workflow_approval = approval_result.scalar_one_or_none()
        
        if not workflow_approval:
            return
        
        history_record = ApprovalHistory(
            workflow_step_approval_id=workflow_approval_id,
            file_approval_id=file_approval_id,
            workspace_id=workflow_approval.workspace_id,
            project_id=workflow_approval.project_id,
            action_type=action_type,
            actor_id=actor_id,
            old_status=old_status,
            new_status=new_status,
            action_comment=action_comment,
            action_data={},
            context_info=context_info or {},
        )
        
        session.add(history_record)
        await session.flush()
    
    async def _check_and_update_parent_approval(
        self,
        session: AsyncSession,
        workflow_approval_id: str,
    ):
        """
        Check file approval status and update parent workflow approval accordingly.
        
        Args:
            session: Database session
            workflow_approval_id: Workflow approval ID
        """
        # Get all file approvals for this workflow approval
        file_approvals = await self.get_file_approvals_for_workflow_approval(
            session, workflow_approval_id
        )
        
        if not file_approvals:
            return
        
        # Check status distribution
        status_counts = {}
        for approval in file_approvals:
            status = approval.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Get workflow approval
        approval_result = await session.execute(
            select(WorkflowStepApproval).where(WorkflowStepApproval.id == workflow_approval_id)
        )
        workflow_approval = approval_result.scalar_one_or_none()
        
        if not workflow_approval:
            return
        
        old_status = workflow_approval.status
        
        # Determine new status based on file approvals
        if status_counts.get(FileApprovalStatus.APPROVED.value, 0) == len(file_approvals):
            # All files approved
            workflow_approval.status = ApprovalStatus.APPROVED
        elif status_counts.get(FileApprovalStatus.REJECTED.value, 0) > 0:
            # Any rejection means workflow is rejected
            workflow_approval.status = ApprovalStatus.REJECTED
        elif status_counts.get(FileApprovalStatus.CHANGES_REQUESTED.value, 0) > 0:
            # Any changes request means workflow needs changes
            workflow_approval.status = ApprovalStatus.REQUEST_CHANGES
        elif all(status == FileApprovalStatus.PENDING.value for status in status_counts.keys()):
            # All pending
            workflow_approval.status = ApprovalStatus.PENDING
        else:
            # Mixed status - some reviewed but not all approved/rejected
            workflow_approval.status = ApprovalStatus.PENDING
        
        # Update responded_at if status changed
        if workflow_approval.status != old_status:
            workflow_approval.responded_at = datetime.utcnow()
            await session.flush()
            
            logger.info(
                f"Updated workflow approval {workflow_approval_id} status from {old_status} "
                f"to {workflow_approval.status} based on file approvals"
            )