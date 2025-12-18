"""phase_21_knowledge_base_rag_001

Phase 21: Knowledge Base & RAG Integration

Tables:
- knowledge_items: Knowledge base items (patterns, standards, best practices)

Enums:
- knowledgecategory: Code patterns, best practices, standards, etc.
- knowledgesourcetype: Source types (repository, documentation, etc.)
- knowledgeitemstatus: Status types (active, draft, archived, etc.)
- vector_db_provider: Vector database providers (pinecone, weaviate, etc.)
- embedding_model: Embedding models (openai, anthropic, etc.)

Revision ID: phase_21_knowledge_base_rag_001
Revises: phase_19_template_library_001
Create Date: 2024-12-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'phase_21_knowledge_base_rag_001'
down_revision = 'phase_19_template_library_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema."""
    
    # Create knowledge categories enum
    knowledge_category_enum = postgresql.ENUM(
        'code_pattern',
        'best_practice', 
        'standard',
        'architecture',
        'technology_choice',
        'api_contract',
        'security_guideline',
        'performance_tip',
        'style_guide',
        'testing_standard',
        name='knowledgecategory'
    )
    knowledge_category_enum.create(op.get_bind())
    
    # Create knowledge source types enum
    knowledge_source_type_enum = postgresql.ENUM(
        'internal_repository',
        'documentation',
        'best_practice_guide',
        'architecture_decision',
        'code_review',
        'project_template',
        'manual_entry',
        'imported_content',
        'team_standard',
        'compliance_rule',
        name='knowledgesourcetype'
    )
    knowledge_source_type_enum.create(op.get_bind())
    
    # Create knowledge item status enum
    knowledge_item_status_enum = postgresql.ENUM(
        'active',
        'draft',
        'archived',
        'deprecated',
        'under_review',
        'verified',
        name='knowledgeitemstatus'
    )
    knowledge_item_status_enum.create(op.get_bind())
    
    # Create vector DB provider enum
    vector_db_provider_enum = postgresql.ENUM(
        'pinecone',
        'weaviate',
        'milvus',
        'qdrant',
        'chroma',
        'elasticsearch',
        'pgvector',
        name='vector_db_provider'
    )
    vector_db_provider_enum.create(op.get_bind())
    
    # Create embedding model enum
    embedding_model_enum = postgresql.ENUM(
        'openai-ada-002',
        'openai-text-embedding-3-small',
        'openai-text-embedding-3-large',
        'anthropic-claude-embeddings',
        'huggingface-all-MiniLM-L6-v2',
        'sentence-transformers-all-mpnet-base-v2',
        'local-sentence-transformers',
        name='embeddingmodel'
    )
    embedding_model_enum.create(op.get_bind())
    
    # Create knowledge_items table
    op.create_table(
        'knowledge_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('category', sa.Enum('code_pattern', 'best_practice', 'standard', 'architecture', 'technology_choice', 'api_contract', 'security_guideline', 'performance_tip', 'style_guide', 'testing_standard', name='knowledgecategory'), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('language', sa.String(length=100), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('source', sa.Enum('internal_repository', 'documentation', 'best_practice_guide', 'architecture_decision', 'code_review', 'project_template', 'manual_entry', 'imported_content', 'team_standard', 'compliance_rule', name='knowledgesourcetype'), nullable=False),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('status', sa.Enum('active', 'draft', 'archived', 'deprecated', 'under_review', 'verified', name='knowledgeitemstatus'), nullable=False),
        sa.Column('embedding_id', sa.String(length=255), nullable=True),
        sa.Column('embedding_model', sa.Enum('openai-ada-002', 'openai-text-embedding-3-small', 'openai-text-embedding-3-large', 'anthropic-claude-embeddings', 'huggingface-all-MiniLM-L6-v2', 'sentence-transformers-all-mpnet-base-v2', 'local-sentence-transformers', name='embeddingmodel'), nullable=True),
        sa.Column('vector_dimension', sa.Integer(), nullable=True),
        sa.Column('relevance_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_accessed', sa.DateTime(timezone=True), nullable=True),
        sa.Column('file_path', sa.String(length=1000), nullable=True),
        sa.Column('line_start', sa.Integer(), nullable=True),
        sa.Column('line_end', sa.Integer(), nullable=True),
        sa.Column('chunk_hash', sa.String(length=64), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='Knowledge base items for patterns, standards, and best practices'
    )
    
    # Create indexes for knowledge_items table
    op.create_index('idx_knowledge_items_workspace', 'knowledge_items', ['workspace_id'])
    op.create_index('idx_knowledge_items_category', 'knowledge_items', ['category'])
    op.create_index('idx_knowledge_items_status', 'knowledge_items', ['status'])
    op.create_index('idx_knowledge_items_language', 'knowledge_items', ['language'])
    op.create_index('idx_knowledge_items_embedding_id', 'knowledge_items', ['embedding_id'])
    op.create_index('idx_knowledge_items_relevance_score', 'knowledge_items', ['relevance_score'])
    op.create_index('idx_knowledge_items_usage_count', 'knowledge_items', ['usage_count'])
    op.create_index('idx_knowledge_items_tags', 'knowledge_items', ['tags'], postgresql_using='gin')
    op.create_index('idx_knowledge_items_created_at', 'knowledge_items', ['created_at'])
    op.create_index('idx_knowledge_items_updated_at', 'knowledge_items', ['updated_at'])
    op.create_index(op.f('ix_knowledge_items_id'), 'knowledge_items', ['id'])


def downgrade() -> None:
    """Downgrade database schema."""
    
    # Drop knowledge_items table
    op.drop_table('knowledge_items')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS embeddingmodel')
    op.execute('DROP TYPE IF EXISTS vector_db_provider')
    op.execute('DROP TYPE IF EXISTS knowledgeitemstatus')
    op.execute('DROP TYPE IF EXISTS knowledgesourcetype')
    op.execute('DROP TYPE IF EXISTS knowledgecategory')