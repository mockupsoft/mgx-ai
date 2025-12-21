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
from pydantic import BaseModel

from backend.db.models import (
    WorkflowStepApproval,
    FileChange,
    FileApproval,
    ApprovalHistory,
    FileApprovalStatus,
)
from backend.db.session import get_session
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

class FileChangeResponse(BaseModel):
    """Schema for file change response."""
    
    id: str
    file_path: str
    file_name: str
    file_type: Optional[str] = None
    change_type: str
    is_new_file: bool
    is_binary: bool
    original_content: Optional[str] = None
    new_content: Optional[str] = None
    diff_summary: Optional[dict] = None
    line_changes: Optional[List[dict]] = None
    change_status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FileApprovalResponse(BaseModel):
    """Schema for file approval response."""
    
    id: str
    file_change_id: str
    workflow_step_approval_id: str
    status: str
    approved_by: Optional[str] = None
    reviewer_comment: Optional[str] = None
    inline_comments: Optional[List[dict]] = None
    reviewed_at: Optional[datetime] = None
    review_metadata: Optional[dict] = None
    file_change: Optional[FileChangeResponse] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FileApprovalCreate(BaseModel):
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


class FileApprovalUpdate(BaseModel):
    """Schema for updating file approval."""
    
    status: str
    reviewer_comment: Optional[str] = None
    review_metadata: Optional[dict] = None


class InlineCommentRequest(BaseModel):
    """Schema for adding inline comment."""
    
    line_number: int
    comment_text: str


class ApprovalHistoryResponse(BaseModel):
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


class FileApprovalsListResponse(BaseModel):
    """Schema for list of file approvals."""
    
    items: List[FileApprovalResponse]
    total: int
    pending_count: int
    approved_count: int
    rejected_count: int
    changes_requested_count: int


class ApprovalHistoryListResponse(BaseModel):
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
    session: AsyncSession = Depends(get_session),
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> WorkflowStepApproval:
    """Get workflow step approval for a task."""
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
    session: AsyncSession = Depends(get_session),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> FileApprovalsListResponse:
    """List all files with their approval status for a workflow approval."""
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
        items=[FileApprovalResponse.model_validate(fa) for fa in paginated_approvals],
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
    session: AsyncSession = Depends(get_session),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> FileApprovalResponse:
    """Create a new file change and corresponding file approval."""
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
    return FileApprovalResponse.model_validate(file_approval)


@router.post("/{approval_id}/files/{file_approval_id}/approve", response_model=FileApprovalResponse)
async def approve_file(
    approval_id: str,
    file_approval_id: str,
    reviewer_comment: Optional[str] = None,
    review_metadata: Optional[dict] = None,
    session: AsyncSession = Depends(get_session),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> FileApprovalResponse:
    """Approve a specific file."""
    file_approval = await file_service.approve_file(
        session,
        file_approval_id,
        approved_by=ctx.user_id,
        reviewer_comment=reviewer_comment,
        review_metadata=review_metadata,
    )
    
    await session.commit()
    return FileApprovalResponse.model_validate(file_approval)


@router.post("/{approval_id}/files/{file_approval_id}/reject", response_model=FileApprovalResponse)
async def reject_file(
    approval_id: str,
    file_approval_id: str,
    reviewer_comment: str,
    review_metadata: Optional[dict] = None,
    session: AsyncSession = Depends(get_session),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> FileApprovalResponse:
    """Reject a specific file."""
    file_approval = await file_service.reject_file(
        session,
        file_approval_id,
        rejected_by=ctx.user_id,
        reviewer_comment=reviewer_comment,
        review_metadata=review_metadata,
    )
    
    await session.commit()
    return FileApprovalResponse.model_validate(file_approval)


@router.post("/{approval_id}/files/{file_approval_id}/request-changes", response_model=FileApprovalResponse)
async def request_file_changes(
    approval_id: str,
    file_approval_id: str,
    reviewer_comment: str,
    review_metadata: Optional[dict] = None,
    session: AsyncSession = Depends(get_session),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> FileApprovalResponse:
    """Request changes for a specific file."""
    file_approval = await file_service.request_file_changes(
        session,
        file_approval_id,
        requested_by=ctx.user_id,
        reviewer_comment=reviewer_comment,
        review_metadata=review_metadata,
    )
    
    await session.commit()
    return FileApprovalResponse.model_validate(file_approval)


@router.post("/{approval_id}/files/{file_approval_id}/comments", response_model=FileApprovalResponse)
async def add_inline_comment(
    approval_id: str,
    file_approval_id: str,
    comment_data: InlineCommentRequest,
    session: AsyncSession = Depends(get_session),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> FileApprovalResponse:
    """Add an inline comment to a specific line in a file."""
    file_approval = await file_service.add_inline_comment(
        session,
        file_approval_id,
        line_number=comment_data.line_number,
        comment_text=comment_data.comment_text,
        commented_by=ctx.user_id,
    )
    
    await session.commit()
    return FileApprovalResponse.model_validate(file_approval)


@router.get("/{approval_id}/files/{file_approval_id}/history", response_model=ApprovalHistoryListResponse)
async def get_file_approval_history(
    approval_id: str,
    file_approval_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> ApprovalHistoryListResponse:
    """Get approval history for a specific file."""
    history = await file_service.get_approval_history(
        session, approval_id, file_approval_id
    )
    
    # Apply pagination
    total = len(history)
    paginated_history = history[skip:skip + limit]
    
    return ApprovalHistoryListResponse(
        items=[ApprovalHistoryResponse.model_validate(h) for h in paginated_history],
        total=total,
    )


@router.get("/{approval_id}/history", response_model=ApprovalHistoryListResponse)
async def get_approval_history(
    approval_id: str,
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    actor_id: Optional[str] = Query(None, description="Filter by actor"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> ApprovalHistoryListResponse:
    """Get complete approval history for a workflow approval."""
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
        items=[ApprovalHistoryResponse.model_validate(h) for h in paginated_history],
        total=total,
    )


@router.post("/{approval_id}/approve-all", response_model=BaseResponse)
async def approve_all_files(
    approval_id: str,
    reviewer_comment: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> BaseResponse:
    """Approve all pending files in the workflow approval."""
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
    rollback_reason: str,
    session: AsyncSession = Depends(get_session),
    ctx: WorkspaceContext = Depends(get_workspace_context),
    approval: WorkflowStepApproval = Depends(get_task_approval),
    file_service: FileApprovalService = Depends(get_file_approval_service),
) -> FileApprovalResponse:
    """Rollback a file approval to PENDING status."""
    file_approval = await file_service.rollback_file_approval(
        session,
        file_approval_id,
        rolled_back_by=ctx.user_id,
        rollback_reason=rollback_reason,
    )
    
    await session.commit()
    return FileApprovalResponse.model_validate(file_approval)