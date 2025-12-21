# -*- coding: utf-8 -*-
"""Test File-Level Approval System

Comprehensive tests for the granular human approval system with file-level control.
Tests individual file approval, diff review interface, inline comments, and approval history.
"""

import pytest
from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.models import (
    WorkflowStepApproval,
    FileChange,
    FileApproval,
    ApprovalHistory,
    FileApprovalStatus,
    ApprovalStatus,
)
from backend.db.session import get_session_factory
from backend.services.workflows.file_approval import FileApprovalService
from backend.services.workflows.approval import ApprovalService


class TestFileLevelApprovals:
    """Test suite for file-level approval functionality."""
    
    @pytest.fixture
    async def session_factory(self):
        """Get session factory for testing."""
        return get_session_factory()
    
    @pytest.fixture
    async def file_approval_service(self):
        """Get file approval service instance."""
        return FileApprovalService()
    
    @pytest.fixture
    async def approval_service(self):
        """Get approval service instance."""
        return ApprovalService()
    
    @pytest.fixture
    async def mock_workflow_approval(self, session_factory, approval_service):
        """Create a mock workflow approval for testing."""
        async with session_factory() as session:
            # Create a mock workflow approval
            approval = await approval_service.create_approval_request(
                session=session,
                step_execution_id="test-step-exec-123",
                workflow_execution_id="test-workflow-exec-456",
                workspace_id="test-workspace-789",
                project_id="test-project-abc",
                title="Test File Approval Request",
                description="Testing file-level approvals",
                approval_data={"test": "data"},
            )
            await session.commit()
            return approval
    
    async def test_create_file_changes_from_approval_data(
        self, session_factory, file_approval_service, mock_workflow_approval
    ):
        """Test creating file changes from approval data."""
        async with session_factory() as session:
            # Sample file changes data
            approval_data = {
                "file_changes": [
                    {
                        "file_path": "src/app.py",
                        "file_name": "app.py",
                        "file_type": "py",
                        "change_type": "modified",
                        "is_new_file": False,
                        "is_binary": False,
                        "original_content": "print('old')",
                        "new_content": "print('new')",
                        "diff_summary": {"additions": 1, "deletions": 1},
                        "line_changes": [
                            {"old_line": "print('old')", "new_line": "print('new')", "line_number": 1}
                        ],
                    },
                    {
                        "file_path": "README.md",
                        "file_name": "README.md",
                        "file_type": "md",
                        "change_type": "created",
                        "is_new_file": True,
                        "is_binary": False,
                        "original_content": None,
                        "new_content": "# New Project",
                        "diff_summary": {"additions": 1, "deletions": 0},
                        "line_changes": [],
                    },
                ]
            }
            
            # Create file changes
            file_changes = await file_approval_service.create_file_changes_from_approval_data(
                session, mock_workflow_approval.id, approval_data
            )
            
            await session.commit()
            
            # Verify results
            assert len(file_changes) == 2
            
            # Check first file change
            first_change = file_changes[0]
            assert first_change.file_path == "src/app.py"
            assert first_change.file_name == "app.py"
            assert first_change.change_type == "modified"
            assert first_change.is_new_file == False
            assert first_change.original_content == "print('old')"
            assert first_change.new_content == "print('new')"
            
            # Check second file change
            second_change = file_changes[1]
            assert second_change.file_path == "README.md"
            assert second_change.file_name == "README.md"
            assert second_change.change_type == "created"
            assert second_change.is_new_file == True
            assert second_change.original_content is None
            assert second_change.new_content == "# New Project"
            
            # Verify file approvals were created
            assert len(first_change.file_approvals) == 1
            assert len(second_change.file_approvals) == 1
            
            first_approval = first_change.file_approvals[0]
            second_approval = second_change.file_approvals[0]
            
            assert first_approval.status == FileApprovalStatus.PENDING
            assert second_approval.status == FileApprovalStatus.PENDING
            assert first_approval.workflow_step_approval_id == mock_workflow_approval.id
            assert second_approval.workflow_step_approval_id == mock_workflow_approval.id
    
    async def test_approve_file(
        self, session_factory, file_approval_service, mock_workflow_approval
    ):
        """Test approving a specific file."""
        async with session_factory() as session:
            # Create a file change first
            approval_data = {
                "file_changes": [
                    {
                        "file_path": "src/test.py",
                        "file_name": "test.py",
                        "file_type": "py",
                        "change_type": "created",
                        "is_new_file": True,
                        "is_binary": False,
                        "original_content": None,
                        "new_content": "print('hello')",
                        "diff_summary": {"additions": 1, "deletions": 0},
                        "line_changes": [],
                    }
                ]
            }
            
            file_changes = await file_approval_service.create_file_changes_from_approval_data(
                session, mock_workflow_approval.id, approval_data
            )
            await session.commit()
            
            file_approval = file_changes[0].file_approvals[0]
            file_approval_id = file_approval.id
            
            # Test approving the file
            approved_file = await file_approval_service.approve_file(
                session=session,
                file_approval_id=file_approval_id,
                approved_by="test-user",
                reviewer_comment="Looks good!",
                review_metadata={"reviewed_quickly": True}
            )
            
            await session.commit()
            
            # Verify the approval
            assert approved_file.status == FileApprovalStatus.APPROVED
            assert approved_file.approved_by == "test-user"
            assert approved_file.reviewer_comment == "Looks good!"
            assert approved_file.reviewed_at is not None
            assert approved_file.review_metadata["reviewed_quickly"] == True
            
            # Verify history record was created
            history_records = await file_approval_service.get_approval_history(
                session, mock_workflow_approval.id
            )
            
            assert len(history_records) > 0
            latest_history = history_records[0]  # Most recent first
            assert latest_history.action_type == "approve"
            assert latest_history.actor_id == "test-user"
            assert latest_history.new_status == "approved"
            assert latest_history.action_comment == "Looks good!"
    
    async def test_reject_file(
        self, session_factory, file_approval_service, mock_workflow_approval
    ):
        """Test rejecting a specific file."""
        async with session_factory() as session:
            # Create a file change first
            approval_data = {
                "file_changes": [
                    {
                        "file_path": "src/problematic.py",
                        "file_name": "problematic.py",
                        "file_type": "py",
                        "change_type": "modified",
                        "is_new_file": False,
                        "is_binary": False,
                        "original_content": "def old_func(): pass",
                        "new_content": "def new_func(): raise Exception('bad')",
                        "diff_summary": {"additions": 1, "deletions": 1},
                        "line_changes": [],
                    }
                ]
            }
            
            file_changes = await file_approval_service.create_file_changes_from_approval_data(
                session, mock_workflow_approval.id, approval_data
            )
            await session.commit()
            
            file_approval = file_changes[0].file_approvals[0]
            file_approval_id = file_approval.id
            
            # Test rejecting the file
            rejected_file = await file_approval_service.reject_file(
                session=session,
                file_approval_id=file_approval_id,
                rejected_by="test-reviewer",
                reviewer_comment="This change introduces exceptions and breaks functionality",
                review_metadata={"severity": "high"}
            )
            
            await session.commit()
            
            # Verify the rejection
            assert rejected_file.status == FileApprovalStatus.REJECTED
            assert rejected_file.approved_by == "test-reviewer"
            assert "breaks functionality" in rejected_file.reviewer_comment
            assert rejected_file.review_metadata["severity"] == "high"
            
            # Verify parent workflow approval status was updated
            workflow_result = await session.execute(
                select(WorkflowStepApproval).where(WorkflowStepApproval.id == mock_workflow_approval.id)
            )
            workflow_approval = workflow_result.scalar_one_or_none()
            assert workflow_approval.status == ApprovalStatus.REJECTED
    
    async def test_request_file_changes(
        self, session_factory, file_approval_service, mock_workflow_approval
    ):
        """Test requesting changes for a specific file."""
        async with session_factory() as session:
            # Create a file change first
            approval_data = {
                "file_changes": [
                    {
                        "file_path": "src/style.py",
                        "file_name": "style.py",
                        "file_type": "py",
                        "change_type": "modified",
                        "is_new_file": False,
                        "is_binary": False,
                        "original_content": "def func():\n    x=1\n    return x",
                        "new_content": "def func():\n    x = 1\n    return x",
                        "diff_summary": {"additions": 1, "deletions": 1},
                        "line_changes": [],
                    }
                ]
            }
            
            file_changes = await file_approval_service.create_file_changes_from_approval_data(
                session, mock_workflow_approval.id, approval_data
            )
            await session.commit()
            
            file_approval = file_changes[0].file_approvals[0]
            file_approval_id = file_approval.id
            
            # Test requesting changes
            changed_file = await file_approval_service.request_file_changes(
                session=session,
                file_approval_id=file_approval_id,
                requested_by="code-reviewer",
                reviewer_comment="Please follow PEP 8 guidelines for spacing",
                review_metadata={"guideline": "PEP8"}
            )
            
            await session.commit()
            
            # Verify the change request
            assert changed_file.status == FileApprovalStatus.CHANGES_REQUESTED
            assert changed_file.approved_by == "code-reviewer"
            assert "PEP 8" in changed_file.reviewer_comment
            assert changed_file.review_metadata["guideline"] == "PEP8"
    
    async def test_add_inline_comment(
        self, session_factory, file_approval_service, mock_workflow_approval
    ):
        """Test adding inline comments to specific lines."""
        async with session_factory() as session:
            # Create a file change first
            approval_data = {
                "file_changes": [
                    {
                        "file_path": "src/commented.py",
                        "file_name": "commented.py",
                        "file_type": "py",
                        "change_type": "modified",
                        "is_new_file": False,
                        "is_binary": False,
                        "original_content": "def old_func():\n    return 1",
                        "new_content": "def new_func():\n    return 2",
                        "diff_summary": {"additions": 2, "deletions": 2},
                        "line_changes": [
                            {"old_line": "def old_func():", "new_line": "def new_func():", "line_number": 1},
                            {"old_line": "    return 1", "new_line": "    return 2", "line_number": 2}
                        ],
                    }
                ]
            }
            
            file_changes = await file_approval_service.create_file_changes_from_approval_data(
                session, mock_workflow_approval.id, approval_data
            )
            await session.commit()
            
            file_approval = file_changes[0].file_approvals[0]
            file_approval_id = file_approval.id
            
            # Test adding inline comments
            commented_file = await file_approval_service.add_inline_comment(
                session=session,
                file_approval_id=file_approval_id,
                line_number=1,
                comment_text="Consider using a more descriptive function name",
                commented_by="reviewer-1"
            )
            
            await session.commit()
            
            # Verify the comment was added
            assert len(commented_file.inline_comments) == 1
            comment = commented_file.inline_comments[0]
            assert comment["line_number"] == 1
            assert "descriptive function name" in comment["comment_text"]
            assert comment["commented_by"] == "reviewer-1"
            
            # Test adding another comment
            commented_file = await file_approval_service.add_inline_comment(
                session=session,
                file_approval_id=file_approval_id,
                line_number=2,
                comment_text="Good use of consistent indentation",
                commented_by="reviewer-2"
            )
            
            await session.commit()
            
            # Verify both comments are present
            assert len(commented_file.inline_comments) == 2
            assert commented_file.inline_comments[0]["line_number"] == 1
            assert commented_file.inline_comments[1]["line_number"] == 2
    
    async def test_rollback_file_approval(
        self, session_factory, file_approval_service, mock_workflow_approval
    ):
        """Test rolling back a file approval to PENDING status."""
        async with session_factory() as session:
            # Create a file change first
            approval_data = {
                "file_changes": [
                    {
                        "file_path": "src/rollback_test.py",
                        "file_name": "rollback_test.py",
                        "file_type": "py",
                        "change_type": "created",
                        "is_new_file": True,
                        "is_binary": False,
                        "original_content": None,
                        "new_content": "print('test')",
                        "diff_summary": {"additions": 1, "deletions": 0},
                        "line_changes": [],
                    }
                ]
            }
            
            file_changes = await file_approval_service.create_file_changes_from_approval_data(
                session, mock_workflow_approval.id, approval_data
            )
            await session.commit()
            
            file_approval = file_changes[0].file_approvals[0]
            file_approval_id = file_approval.id
            
            # First approve the file
            await file_approval_service.approve_file(
                session=session,
                file_approval_id=file_approval_id,
                approved_by="test-user",
                reviewer_comment="Initial approval"
            )
            await session.commit()
            
            # Verify it's approved
            result = await session.execute(
                select(FileApproval).where(FileApproval.id == file_approval_id)
            )
            approved_state = result.scalar_one_or_none()
            assert approved_state.status == FileApprovalStatus.APPROVED
            
            # Now rollback to pending
            rolled_back_file = await file_approval_service.rollback_file_approval(
                session=session,
                file_approval_id=file_approval_id,
                rolled_back_by="admin-user",
                rollback_reason="Need to make additional changes"
            )
            await session.commit()
            
            # Verify rollback
            assert rolled_back_file.status == FileApprovalStatus.PENDING
            assert rolled_back_file.approved_by is None
            assert rolled_back_file.reviewer_comment is None
            assert rolled_back_file.reviewed_at is None
            assert rolled_back_file.review_metadata["rollback_reason"] == "Need to make additional changes"
            assert rolled_back_file.review_metadata["rolled_back_by"] == "admin-user"
    
    async def test_mixed_file_status_workflow_approval(
        self, session_factory, file_approval_service, mock_workflow_approval
    ):
        """Test that workflow approval status updates based on mixed file statuses."""
        async with session_factory() as session:
            # Create multiple file changes
            approval_data = {
                "file_changes": [
                    {
                        "file_path": "src/file1.py",
                        "file_name": "file1.py",
                        "file_type": "py",
                        "change_type": "created",
                        "is_new_file": True,
                        "is_binary": False,
                        "original_content": None,
                        "new_content": "print('file1')",
                        "diff_summary": {"additions": 1, "deletions": 0},
                        "line_changes": [],
                    },
                    {
                        "file_path": "src/file2.py",
                        "file_name": "file2.py",
                        "file_type": "py",
                        "change_type": "created",
                        "is_new_file": True,
                        "is_binary": False,
                        "original_content": None,
                        "new_content": "print('file2')",
                        "diff_summary": {"additions": 1, "deletions": 0},
                        "line_changes": [],
                    },
                    {
                        "file_path": "src/file3.py",
                        "file_name": "file3.py",
                        "file_type": "py",
                        "change_type": "created",
                        "is_new_file": True,
                        "is_binary": False,
                        "original_content": None,
                        "new_content": "print('file3')",
                        "diff_summary": {"additions": 1, "deletions": 0},
                        "line_changes": [],
                    },
                ]
            }
            
            file_changes = await file_approval_service.create_file_changes_from_approval_data(
                session, mock_workflow_approval.id, approval_data
            )
            await session.commit()
            
            file_approval_ids = [fc.file_approvals[0].id for fc in file_changes]
            
            # Initially workflow approval should be pending
            workflow_result = await session.execute(
                select(WorkflowStepApproval).where(WorkflowStepApproval.id == mock_workflow_approval.id)
            )
            workflow_approval = workflow_result.scalar_one_or_none()
            assert workflow_approval.status == ApprovalStatus.PENDING
            
            # Approve first file
            await file_approval_service.approve_file(
                session=session,
                file_approval_id=file_approval_ids[0],
                approved_by="reviewer"
            )
            await session.commit()
            
            # Request changes for second file
            await file_approval_service.request_file_changes(
                session=session,
                file_approval_id=file_approval_ids[1],
                requested_by="reviewer",
                reviewer_comment="Need improvements"
            )
            await session.commit()
            
            # Workflow should now be in REQUEST_CHANGES state
            workflow_result = await session.execute(
                select(WorkflowStepApproval).where(WorkflowStepApproval.id == mock_workflow_approval.id)
            )
            workflow_approval = workflow_result.scalar_one_or_none()
            assert workflow_approval.status == ApprovalStatus.REQUEST_CHANGES
            
            # Reject third file
            await file_approval_service.reject_file(
                session=session,
                file_approval_id=file_approval_ids[2],
                rejected_by="reviewer",
                reviewer_comment="This file is problematic"
            )
            await session.commit()
            
            # Workflow should now be in REJECTED state (any rejection wins)
            workflow_result = await session.execute(
                select(WorkflowStepApproval).where(WorkflowStepApproval.id == mock_workflow_approval.id)
            )
            workflow_approval = workflow_result.scalar_one_or_none()
            assert workflow_approval.status == ApprovalStatus.REJECTED
    
    async def test_approval_history_tracking(
        self, session_factory, file_approval_service, mock_workflow_approval
    ):
        """Test that approval history is properly tracked for audit purposes."""
        async with session_factory() as session:
            # Create a file change
            approval_data = {
                "file_changes": [
                    {
                        "file_path": "src/history_test.py",
                        "file_name": "history_test.py",
                        "file_type": "py",
                        "change_type": "created",
                        "is_new_file": True,
                        "is_binary": False,
                        "original_content": None,
                        "new_content": "print('history test')",
                        "diff_summary": {"additions": 1, "deletions": 0},
                        "line_changes": [],
                    }
                ]
            }
            
            file_changes = await file_approval_service.create_file_changes_from_approval_data(
                session, mock_workflow_approval.id, approval_data
            )
            await session.commit()
            
            file_approval = file_changes[0].file_approvals[0]
            file_approval_id = file_approval.id
            
            # Get initial history (should be empty)
            history = await file_approval_service.get_approval_history(
                session, mock_workflow_approval.id
            )
            initial_history_count = len(history)
            
            # Add a comment
            await file_approval_service.add_inline_comment(
                session=session,
                file_approval_id=file_approval_id,
                line_number=1,
                comment_text="Good start",
                commented_by="reviewer-1"
            )
            await session.commit()
            
            # Approve the file
            await file_approval_service.approve_file(
                session=session,
                file_approval_id=file_approval_id,
                approved_by="reviewer-1",
                reviewer_comment="Looks good after review"
            )
            await session.commit()
            
            # Get final history
            final_history = await file_approval_service.get_approval_history(
                session, mock_workflow_approval.id
            )
            
            # Verify history records
            assert len(final_history) > initial_history_count
            
            # Find specific history records
            comment_history = [h for h in final_history if h.action_type == "comment"]
            approval_history = [h for h in final_history if h.action_type == "approve"]
            
            assert len(comment_history) == 1
            assert len(approval_history) == 1
            
            # Verify comment history
            comment_record = comment_history[0]
            assert comment_record.actor_id == "reviewer-1"
            assert "line 1" in comment_record.action_comment
            assert "Good start" in comment_record.action_comment
            
            # Verify approval history
            approval_record = approval_history[0]
            assert approval_record.actor_id == "reviewer-1"
            assert approval_record.old_status == "pending"
            assert approval_record.new_status == "approved"
            assert "after review" in approval_record.action_comment
    
    async def test_get_file_approvals_for_workflow_approval(
        self, session_factory, file_approval_service, mock_workflow_approval
    ):
        """Test retrieving file approvals for a workflow approval."""
        async with session_factory() as session:
            # Create multiple file changes
            approval_data = {
                "file_changes": [
                    {
                        "file_path": "src/a.py",
                        "file_name": "a.py",
                        "file_type": "py",
                        "change_type": "created",
                        "is_new_file": True,
                        "is_binary": False,
                        "original_content": None,
                        "new_content": "print('a')",
                        "diff_summary": {"additions": 1, "deletions": 0},
                        "line_changes": [],
                    },
                    {
                        "file_path": "src/b.py",
                        "file_name": "b.py",
                        "file_type": "py",
                        "change_type": "created",
                        "is_new_file": True,
                        "is_binary": False,
                        "original_content": None,
                        "new_content": "print('b')",
                        "diff_summary": {"additions": 1, "deletions": 0},
                        "line_changes": [],
                    },
                ]
            }
            
            file_changes = await file_approval_service.create_file_changes_from_approval_data(
                session, mock_workflow_approval.id, approval_data
            )
            await session.commit()
            
            # Get all file approvals
            file_approvals = await file_approval_service.get_file_approvals_for_workflow_approval(
                session, mock_workflow_approval.id
            )
            
            # Verify results
            assert len(file_approvals) == 2
            
            # Verify file paths are correct
            file_paths = [fa.file_change.file_path for fa in file_approvals]
            assert "src/a.py" in file_paths
            assert "src/b.py" in file_paths
            
            # Verify all are pending
            for fa in file_approvals:
                assert fa.status == FileApprovalStatus.PENDING
            
            # Approve one file
            await file_approval_service.approve_file(
                session=session,
                file_approval_id=file_approvals[0].id,
                approved_by="test-user"
            )
            await session.commit()
            
            # Get file approvals again
            updated_approvals = await file_approval_service.get_file_approvals_for_workflow_approval(
                session, mock_workflow_approval.id
            )
            
            # Verify status update
            assert updated_approvals[0].status == FileApprovalStatus.APPROVED
            assert updated_approvals[1].status == FileApprovalStatus.PENDING


class TestFileApprovalIntegration:
    """Integration tests for file approval system."""
    
    async def test_approve_all_files_bulk_operation(
        self, session_factory, file_approval_service, mock_workflow_approval
    ):
        """Test bulk approval of all pending files."""
        async with session_factory() as session:
            # Create multiple file changes
            approval_data = {
                "file_changes": [
                    {
                        "file_path": f"src/file{i}.py",
                        "file_name": f"file{i}.py",
                        "file_type": "py",
                        "change_type": "created",
                        "is_new_file": True,
                        "is_binary": False,
                        "original_content": None,
                        "new_content": f"print('file{i}')",
                        "diff_summary": {"additions": 1, "deletions": 0},
                        "line_changes": [],
                    }
                    for i in range(5)
                ]
            }
            
            file_changes = await file_approval_service.create_file_changes_from_approval_data(
                session, mock_workflow_approval.id, approval_data
            )
            await session.commit()
            
            file_approval_ids = [fc.file_approvals[0].id for fc in file_changes]
            
            # Manually approve all files (simulating bulk approve)
            for file_approval_id in file_approval_ids:
                await file_approval_service.approve_file(
                    session=session,
                    file_approval_id=file_approval_id,
                    approved_by="bulk-approver",
                    reviewer_comment="Bulk approved"
                )
            
            await session.commit()
            
            # Verify all files are approved
            file_approvals = await file_approval_service.get_file_approvals_for_workflow_approval(
                session, mock_workflow_approval.id
            )
            
            assert len(file_approvals) == 5
            for fa in file_approvals:
                assert fa.status == FileApprovalStatus.APPROVED
                assert fa.approved_by == "bulk-approver"
                assert fa.reviewer_comment == "Bulk approved"
            
            # Verify workflow approval is also approved
            workflow_result = await session.execute(
                select(WorkflowStepApproval).where(WorkflowStepApproval.id == mock_workflow_approval.id)
            )
            workflow_approval = workflow_result.scalar_one_or_none()
            assert workflow_approval.status == ApprovalStatus.APPROVED
    
    async def test_large_file_handling(
        self, session_factory, file_approval_service, mock_workflow_approval
    ):
        """Test handling of large files with substantial content."""
        async with session_factory() as session:
            # Create a large file with substantial content
            large_content = "\n".join([f"def function_{i}():\n    return {i}" for i in range(100)])
            
            approval_data = {
                "file_changes": [
                    {
                        "file_path": "src/large_file.py",
                        "file_name": "large_file.py",
                        "file_type": "py",
                        "change_type": "created",
                        "is_new_file": True,
                        "is_binary": False,
                        "original_content": None,
                        "new_content": large_content,
                        "diff_summary": {"additions": 200, "deletions": 0},
                        "line_changes": [
                            {"old_line": "", "new_line": line, "line_number": i+1}
                            for i, line in enumerate(large_content.split("\n"))
                        ],
                    }
                ]
            }
            
            file_changes = await file_approval_service.create_file_changes_from_approval_data(
                session, mock_workflow_approval.id, approval_data
            )
            await session.commit()
            
            file_approval = file_changes[0].file_approvals[0]
            
            # Verify large content was stored
            assert file_changes[0].new_content == large_content
            assert len(file_changes[0].line_changes) == 100
            
            # Test adding inline comments to large file
            await file_approval_service.add_inline_comment(
                session=session,
                file_approval_id=file_approval.id,
                line_number=50,
                comment_text="Consider breaking this function into smaller ones",
                commented_by="code-reviewer"
            )
            await session.commit()
            
            # Verify comment was added
            updated_approval = await session.execute(
                select(FileApproval).where(FileApproval.id == file_approval.id)
            )
            file_approval_obj = updated_approval.scalar_one_or_none()
            
            assert len(file_approval_obj.inline_comments) == 1
            assert file_approval_obj.inline_comments[0]["line_number"] == 50
            assert "smaller ones" in file_approval_obj.inline_comments[0]["comment_text"]


if __name__ == "__main__":
    pytest.main([__file__])