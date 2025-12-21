"""file_level_approval_001

Revision ID: file_level_approval_001
Revises: 
Create Date: 2024-12-21 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'file_level_approval_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create file-level approval system tables."""
    
    # Create file_approval_status enum
    file_approval_status = sa.Enum('pending', 'approved', 'rejected', 'changes_requested', 'reviewed', 
                                   name='file_approval_status')
    file_approval_status.create(op.get_bind())
    
    # Create file_changes table
    op.create_table('file_changes',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('workflow_step_approval_id', sa.String(36), sa.ForeignKey('workflow_step_approvals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workspace_id', sa.String(36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False, comment='Relative path to the file'),
        sa.Column('file_name', sa.String(255), nullable=False, comment='File name'),
        sa.Column('file_type', sa.String(100), comment='File type/extension'),
        sa.Column('change_type', sa.String(50), nullable=False, comment='Type of change: created, modified, deleted, renamed'),
        sa.Column('is_new_file', sa.Boolean(), default=False, comment='Whether this is a new file'),
        sa.Column('is_binary', sa.Boolean(), default=False, comment='Whether file is binary'),
        sa.Column('original_content', sa.Text(), comment='Original file content'),
        sa.Column('new_content', sa.Text(), comment='New file content'),
        sa.Column('diff_summary', sa.JSON(), comment='Summary of changes (additions, deletions)'),
        sa.Column('line_changes', sa.JSON(), comment='Detailed line-by-line changes'),
        sa.Column('change_status', sa.String(50), default='pending', comment='Status of the change'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_file_changes_approval', 'workflow_step_approval_id'),
        sa.Index('idx_file_changes_workspace', 'workspace_id'),
        sa.Index('idx_file_changes_file_path', 'file_path'),
        sa.Index('idx_file_changes_change_type', 'change_type'),
        sa.Index('idx_file_changes_status', 'change_status'),
        sa.ForeignKeyConstraint(['workspace_id', 'project_id'], ['projects.workspace_id', 'projects.id'], 
                               name='fk_file_changes_project_in_workspace', ondelete='RESTRICT'),
    )
    
    # Create file_approvals table
    op.create_table('file_approvals',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('file_change_id', sa.String(36), sa.ForeignKey('file_changes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workflow_step_approval_id', sa.String(36), sa.ForeignKey('workflow_step_approvals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workspace_id', sa.String(36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'changes_requested', 'reviewed', 
                                   name='file_approval_status'), nullable=False),
        sa.Column('approved_by', sa.String(255), comment='User who approved/rejected'),
        sa.Column('reviewer_comment', sa.Text(), comment='Reviewers comment'),
        sa.Column('inline_comments', sa.JSON(), default=list, comment='List of inline comments with line numbers'),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), comment='When file was reviewed'),
        sa.Column('review_metadata', sa.JSON(), default=dict, comment='Additional review metadata'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_file_approvals_file_change', 'file_change_id'),
        sa.Index('idx_file_approvals_workflow_approval', 'workflow_step_approval_id'),
        sa.Index('idx_file_approvals_status', 'status'),
        sa.Index('idx_file_approvals_workspace', 'workspace_id'),
        sa.Index('idx_file_approvals_reviewed_at', 'reviewed_at'),
        sa.ForeignKeyConstraint(['workspace_id', 'project_id'], ['projects.workspace_id', 'projects.id'], 
                               name='fk_file_approvals_project_in_workspace', ondelete='RESTRICT'),
    )
    
    # Create approval_history table
    op.create_table('approval_history',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('workflow_step_approval_id', sa.String(36), sa.ForeignKey('workflow_step_approvals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_approval_id', sa.String(36), sa.ForeignKey('file_approvals.id', ondelete='CASCADE'), nullable=True),
        sa.Column('workspace_id', sa.String(36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False, comment='Type of action: approve, reject, request_changes, comment'),
        sa.Column('actor_id', sa.String(255), nullable=False, comment='User who performed the action'),
        sa.Column('actor_name', sa.String(255), comment='Display name of actor'),
        sa.Column('old_status', sa.String(50), comment='Previous status'),
        sa.Column('new_status', sa.String(50), nullable=False, comment='New status after action'),
        sa.Column('action_comment', sa.Text(), comment='Comment from actor'),
        sa.Column('action_data', sa.JSON(), comment='Additional action metadata'),
        sa.Column('context_info', sa.JSON(), comment='Context information for the action'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_approval_history_workflow_approval', 'workflow_step_approval_id'),
        sa.Index('idx_approval_history_file_approval', 'file_approval_id'),
        sa.Index('idx_approval_history_workspace', 'workspace_id'),
        sa.Index('idx_approval_history_action_type', 'action_type'),
        sa.Index('idx_approval_history_actor', 'actor_id'),
        sa.Index('idx_approval_history_created_at', 'created_at'),
        sa.ForeignKeyConstraint(['workspace_id', 'project_id'], ['projects.workspace_id', 'projects.id'], 
                               name='fk_approval_history_project_in_workspace', ondelete='RESTRICT'),
    )


def downgrade():
    """Drop file-level approval system tables."""
    
    # Drop tables in reverse order
    op.drop_table('approval_history')
    op.drop_table('file_approvals')
    op.drop_table('file_changes')
    
    # Drop enum
    op.execute('DROP TYPE file_approval_status')