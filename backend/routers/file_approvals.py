# -*- coding: utf-8 -*-
"""File Approvals Router

REST API endpoints for granular file-level approvals within approval workflows.
Supports individual file approval, inline comments, and approval history.
"""

import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.db.models import (
    WorkflowStepApproval,
    FileChange,
    FileApproval,
    ApprovalHistory,
    FileApprovalStatus,
)
from backend.db.session import get_session_factory
from backend.routers.deps import WorkspaceContext, get_workspace_context
from backend.schemas import (
    BaseResponse,
    ErrorResponse,
)
from backend.services.workflows.file_approval import FileApprovalService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks/{task_id}/approvals", tags=["file-approvals"])


# ============================================
# Request/Response Schemas
# ============================================

class FileChangeResponse(BaseResponse):
    """Schema for file change response."""
    
    id: str
    file_path: str
    file_name: str
    file_type: Optional[str]
    change_type: str
    is_new_file: bool
    is_binary: bool
    original_content: Optional[str]
    new_content: Optional[str]
    diff_summary: dict
    line_changes: List[dict]
    change_status: str
    created_at: datetime
    updated_at: datetime


class FileApprovalResponse(BaseResponse):
    """Schema for file approval response."""
    
    id: str
    file_change_id: str
    workflow_step_approval_id: str
    status: str
    approved_by: Optional[str]
    reviewer_comment: Optional[str]
    inline_comments: List[dict]
    reviewed_at: Optional[datetime]
    review_metadata: dict
    file_change: Optional[FileChangeResponse]
    created_at: datetime
    updated_at: datetime


class FileApprovalCreate(BaseResponse):
    """Schema for creating file approval."""
    
    file_path: str
    file_name: str
    file_type: Optional[str]
    change_type: str = "modified"
    is_new_file: bool = False
    is_binary: bool = False
    original_content: Optional[str] = None
    new_content: Optional[str] = None
    diff_summary: Optional[dict] = None
    line_changes: Optional[List[dict]] = None


class FileApprovalUpdate(BaseResponse):
    """Schema for updating file approval."""
    
    status: str
    reviewer_comment: Optional[str] = None
    review_metadata: Optional[dict] = None


class InlineCommentRequest(BaseResponse):
    """Schema for adding inline comment."""
    
    line_number: int
    comment_text: str


class ApprovalHistoryResponse(BaseResponse):
    """Schema for approval history response."""
    
    id: str
    workflow_step_approval_id: str
    file_approval_id: Optional[str]
    action_type: str
    actor_id: str
    actor_name: Optional[str]
    old_status: Optional[str]
    new_status: str
    action_comment: Optional[str]
    action_data: dict
    context_info: dict
    created_at: datetime


class FileApprovalsListResponse(BaseResponse):
    """Schema for list of file approvals."""
    
    items: List[FileApprovalResponse]
    total: int
    pending_count: int
    approved_count: int
    rejected_count: int
    changes_requested_count: int


class ApprovalHistoryListResponse(BaseResponse):
    """Schema for list of approval history."""
    
    items: List[ApprovalHistoryResponse]
    total: int


# ============================================
# Router Dependencies
# ============================================

async def get_file_approval_service() -> FileApprovalService:
    """Get file approval service instance."""
    return FileApprovalService()


async def get_task_approval(
    task_id: str,
    approval_id: str,
    session_factory=Depends(get_session_factory),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> WorkflowStepApproval:
    """Get workflow step approval for a task."""
    async with session_factory() as session:
        result = await session.execute(
            select(WorkflowStepApproval)
            .where(
                and_(
                    WorkflowStepApproval.id == approval_id,
                    WorkflowStepApproval.workspace_id == ctx.workspace_id,
                )
            )
        )
        approval = result.scalar_one_or_none()
        
        if not approval:
            raise HTTPException(
                status_code=404,
                detail=f"Approval {approval_id} not found for task {task_id}"
            )
        
        return approval


# ============================================
# File Approval Endpoints
# ============================================

@router.get("/{approval_id}/files", response_model=FileApprovalsListResponse)
async def list_files_for_approval(
    approval_id: str,
    status: Optional[str] = Query(None, description="Filter by file approval status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session_factory=Depends(get_session_factory),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> FileApprovalsListResponse:
    """List all files with their approval status for a workflow approval."""
    async with session_factory() as session:
        # Get file approvals
        file_approvals = await file_service.get_file_approvals_for_workflow_approval(
            session, approval_id
        )
        
        # Filter by status if specified
        if status:
            file_approvals = [fa for fa in file_approvals if fa.status.value == status]
        
        # Apply pagination
        total = len(file_approvals)
        paginated_approvals = file_approvals[skip:skip + limit]
        
        # Count by status
        status_counts = {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "changes_requested": 0,
        }
        
        for fa in file_approvals:
            status_counts[fa.status.value] += 1
        
        return FileApprovalsListResponse(
            items=[FileApprovalResponse.from_orm(fa) for fa in paginated_approvals],
            total=total,
            pending_count=status_counts["pending"],
            approved_count=status_counts["approved"],
            rejected_count=status_counts["rejected"],
            changes_requested_count=status_counts["changes_requested"],
        )


@router.post("/{approval_id}/files", response_model=FileApprovalResponse)
async def create_file_change(
    approval_id: str,
    file_change_data: FileApprovalCreate,
    session_factory=Depends(get_session_factory),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> FileApprovalResponse:
    """Create a new file change and corresponding file approval."""
    async with session_factory() as session:
        # Create approval data structure
        approval_data = {
            "file_changes": [
                {
                    "file_path": file_change_data.file_path,
                    "file_name": file_change_data.file_name,
                    "file_type": file_change_data.file_type,
                    "change_type": file_change_data.change_type,
                    "is_new_file": file_change_data.is_new_file,
                    "is_binary": file_change_data.is_binary,
                    "original_content": file_change_data.original_content,
                    "new_content": file_change_data.new_content,
                    "diff_summary": file_change_data.diff_summary or {},
                    "line_changes": file_change_data.line_changes or [],
                }
            ]
        }
        
        # Create file changes
        file_changes = await file_service.create_file_changes_from_approval_data(
            session, approval_id, approval_data
        )
        
        await session.commit()
        
        # Return the first created file approval
        file_approval = file_changes[0].file_approvals[0]
        return FileApprovalResponse.from_orm(file_approval)


@router.post("/{approval_id}/files/{file_approval_id}/approve", response_model=FileApprovalResponse)
async def approve_file(
    approval_id: str,
    file_approval_id: str,
    reviewer_comment: Optional[str] = Query(None),
    review_metadata: Optional[dict] = Query(None),
    session_factory=Depends(get_session_factory),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> FileApprovalResponse:
    """Approve a specific file."""
    async with session_factory() as session:
        file_approval = await file_service.approve_file(
            session,
            file_approval_id,
            approved_by=ctx.user_id,
            reviewer_comment=reviewer_comment,
            review_metadata=review_metadata,
        )
        
        await session.commit()
        return FileApprovalResponse.from_orm(file_approval)


@router.post("/{approval_id}/files/{file_approval_id}/reject", response_model=FileApprovalResponse)
async def reject_file(
    approval_id: str,
    file_approval_id: str,
    reviewer_comment: str = Query(..., description="Rejection comment (required)"),
    review_metadata: Optional[dict] = Query(None),
    session_factory=Depends(get_session_factory),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> FileApprovalResponse:
    """Reject a specific file."""
    async with session_factory() as session:
        file_approval = await file_service.reject_file(
            session,
            file_approval_id,
            rejected_by=ctx.user_id,
            reviewer_comment=reviewer_comment,
            review_metadata=review_metadata,
        )
        
        await session.commit()
        return FileApprovalResponse.from_orm(file_approval)


@router.post("/{approval_id}/files/{file_approval_id}/request-changes", response_model=FileApprovalResponse)
async def request_file_changes(
    approval_id: str,
    file_approval_id: str,
    reviewer_comment: str = Query(..., description="Change request comment (required)"),
    review_metadata: Optional[dict] = Query(None),
    session_factory=Depends(get_session_factory),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> FileApprovalResponse:
    """Request changes for a specific file."""
    async with session_factory() as session:
        file_approval = await file_service.request_file_changes(
            session,
            file_approval_id,
            requested_by=ctx.user_id,
            reviewer_comment=reviewer_comment,
            review_metadata=review_metadata,
        )
        
        await session.commit()
        return FileApprovalResponse.from_orm(file_approval)


@router.post("/{approval_id}/files/{file_approval_id}/comments", response_model=FileApprovalResponse)
async def add_inline_comment(
    approval_id: str,
    file_approval_id: str,
    comment_data: InlineCommentRequest,
    session_factory=Depends(get_session_factory),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> FileApprovalResponse:
    """Add an inline comment to a specific line in a file."""
    async with session_factory() as session:
        file_approval = await file_service.add_inline_comment(
            session,
            file_approval_id,
            line_number=comment_data.line_number,
            comment_text=comment_data.comment_text,
            commented_by=ctx.user_id,
        )
        
        await session.commit()
        return FileApprovalResponse.from_orm(file_approval)


@router.get("/{approval_id}/files/{file_approval_id}/history", response_model=ApprovalHistoryListResponse)
async def get_file_approval_history(
    approval_id: str,
    file_approval_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session_factory=Depends(get_session_factory),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> ApprovalHistoryListResponse:
    """Get approval history for a specific file."""
    async with session_factory() as session:
        history = await file_service.get_approval_history(
            session, approval_id, file_approval_id
        )
        
        # Apply pagination
        total = len(history)
        paginated_history = history[skip:skip + limit]
        
        return ApprovalHistoryListResponse(
            items=[ApprovalHistoryResponse.from_orm(h) for h in paginated_history],
            total=total,
        )


@router.get("/{approval_id}/history", response_model=ApprovalHistoryListResponse)
async def get_approval_history(
    approval_id: str,
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    actor_id: Optional[str] = Query(None, description="Filter by actor"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session_factory=Depends(get_session_factory),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> ApprovalHistoryListResponse:
    """Get complete approval history for a workflow approval."""
    async with session_factory() as session:
        history = await file_service.get_approval_history(session, approval_id)
        
        # Apply filters
        if action_type:
            history = [h for h in history if h.action_type == action_type]
        
        if actor_id:
            history = [h for h in history if h.actor_id == actor_id]
        
        # Apply pagination
        total = len(history)
        paginated_history = history[skip:skip + limit]
        
        return ApprovalHistoryListResponse(
            items=[ApprovalHistoryResponse.from_orm(h) for h in paginated_history],
            total=total,
        )


@router.post("/{approval_id}/approve-all", response_model=BaseResponse)
async def approve_all_files(
    approval_id: str,
    reviewer_comment: Optional[str] = Query(None),
    session_factory=Depends(get_session_factory),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> BaseResponse:
    """Approve all pending files in the workflow approval."""
    async with session_factory() as session:
        # Get all pending file approvals
        file_approvals = await file_service.get_file_approvals_for_workflow_approval(
            session, approval_id
        )
        
        pending_approvals = [
            fa for fa in file_approvals 
            if fa.status == FileApprovalStatus.PENDING
        ]
        
        # Approve each pending file
        for file_approval in pending_approvals:
            await file_service.approve_file(
                session,
                file_approval.id,
                approved_by=ctx.user_id,
                reviewer_comment=reviewer_comment,
            )
        
        await session.commit()
        
        return BaseResponse(
            message=f"Approved {len(pending_approvals)} files"
        )


@router.post("/{approval_id}/rollback/{file_approval_id}", response_model=FileApprovalResponse)
async def rollback_file_approval(
    approval_id: str,
    file_approval_id: str,
    rollback_reason: str = Query(..., description="Reason for rollback"),
    session_factory=Depends(get_session_factory),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> FileApprovalResponse:
    """Rollback a file approval to PENDING status."""
    async with session_factory() as session:
        file_approval = await file_service.rollback_file_approval(
            session,
            file_approval_id,
            rolled_back_by=ctx.user_id,
            rollback_reason=rollback_reason,
        )
        
        await session.commit()
        return FileApprovalResponse.from_orm(file_approval)