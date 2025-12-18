# -*- coding: utf-8 -*-
"""backend.config

Backend Configuration Module

Pydantic settings with .env support for:
- API server configuration (host, port)
- MGX agent defaults (team settings, cache)
- PostgreSQL connection information
- GitHub integration (repository linking)

GitHub-related environment variables:
- GITHUB_APP_ID: GitHub App ID (optional)
- GITHUB_CLIENT_ID: GitHub OAuth App client ID (optional)
- GITHUB_PRIVATE_KEY_PATH: Path to GitHub App private key PEM (optional)
- GITHUB_PAT: Personal Access Token fallback (optional; required if app auth is not configured)
- GITHUB_CLONE_CACHE_DIR: Local directory used for cached clones
"""

from typing import Optional

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False
        extra = 'ignore'
    
    # API Server Settings
    api_host: str = Field(default="127.0.0.1", description="API server host")
    api_port: int = Field(default=8000, ge=1024, le=65535, description="API server port")
    api_reload: bool = Field(default=False, description="Enable auto-reload (development only)")
    api_workers: int = Field(default=1, ge=1, le=16, description="Number of Uvicorn workers")
    
    # MGX Team Settings (Defaults)
    mgx_max_rounds: int = Field(default=5, ge=1, le=20, description="Default max rounds for team execution")
    mgx_max_revision_rounds: int = Field(default=2, ge=0, le=5, description="Default max revision rounds")
    mgx_max_memory_size: int = Field(default=50, ge=10, le=500, description="Default team memory size limit")
    mgx_enable_caching: bool = Field(default=True, description="Enable response caching")
    mgx_cache_backend: str = Field(default="memory", description="Cache backend: none | memory | redis")
    mgx_cache_max_entries: int = Field(default=1024, ge=1, le=100_000, description="Max cache entries for LRU")
    mgx_cache_ttl_seconds: int = Field(default=3600, ge=60, le=86400, description="Cache TTL in seconds")
    
    # Database Settings
    db_host: str = Field(default="localhost", description="PostgreSQL host")
    db_port: int = Field(default=5432, ge=1024, le=65535, description="PostgreSQL port")
    db_user: str = Field(default="postgres", description="PostgreSQL user")
    db_password: str = Field(default="postgres", description="PostgreSQL password")
    db_name: str = Field(default="mgx_agent", description="PostgreSQL database name")
    db_pool_size: int = Field(default=10, ge=1, le=100, description="Database connection pool size")
    db_max_overflow: int = Field(default=20, ge=0, le=200, description="Max overflow connections")
    
    # Redis Settings (for distributed caching)
    redis_url: Optional[str] = Field(default=None, description="Redis URL (e.g., redis://localhost:6379)")

    # GitHub Integration Settings
    github_app_id: Optional[int] = Field(default=None, description="GitHub App ID (optional)")
    github_client_id: Optional[str] = Field(default=None, description="GitHub OAuth App client ID (optional)")
    github_private_key_path: Optional[str] = Field(
        default=None,
        description="Path to GitHub App private key PEM (optional)",
    )
    github_pat: Optional[str] = Field(default=None, description="GitHub Personal Access Token fallback (optional)")
    github_clone_cache_dir: str = Field(
        default="/tmp/mgx-agent-repos",
        description="Local directory used for cached git clones",
    )

    # Agent Configuration
    agents_enabled: bool = Field(default=False, description="Enable multi-agent system")
    agent_registry_modules: str = Field(
        default="",
        description="Comma-separated list of Python modules containing agent definitions to auto-load",
    )
    agent_max_concurrency: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum concurrent agent instances per workspace",
    )
    agent_context_history_limit: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Maximum number of context versions to retain per agent context",
    )

    agent_message_retention_limit: int = Field(
        default=1000,
        ge=10,
        le=100_000,
        description="Maximum number of agent messages to retain per agent instance",
    )

    agent_message_ack_window_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Best-effort ACK retention window for WebSocket subscribers",
    )
    
    # Application Settings
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Secret Management Settings
    secret_encryption_backend: str = Field(
        default="fernet",
        description="Secret encryption backend: fernet | vault | aws_kms"
    )
    secret_encryption_key: Optional[str] = Field(
        default=None,
        description="Encryption key for Fernet backend (base64 encoded)"
    )
    vault_url: Optional[str] = Field(
        default=None,
        description="HashiCorp Vault URL"
    )
    vault_token: Optional[str] = Field(
        default=None,
        description="HashiCorp Vault authentication token"
    )
    vault_mount_point: str = Field(
        default="secret",
        description="Vault mount point for secrets"
    )
    vault_namespace: Optional[str] = Field(
        default=None,
        description="Vault namespace for multi-tenancy"
    )
    aws_kms_key_id: Optional[str] = Field(
        default=None,
        description="AWS KMS key ID for encryption"
    )
    aws_region: str = Field(
        default="us-east-1",
        description="AWS region for KMS and Secrets Manager"
    )
    secret_rotation_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="Default secret rotation period in days"
    )
    enable_secret_audit_logging: bool = Field(
        default=True,
        description="Enable comprehensive audit logging for secret operations"
    )
    secret_audit_retention_days: int = Field(
        default=365,
        ge=1,
        le=2555,
        description="How long to retain secret audit logs (in days)"
    )
    
    # LLM Provider Settings
    llm_default_provider: str = Field(
        default="openai",
        description="Default LLM provider: openai | anthropic | mistral | ollama | together"
    )
    llm_routing_strategy: str = Field(
        default="balanced",
        description="LLM routing strategy: cost_optimized | latency_optimized | quality_optimized | local_first | balanced"
    )
    llm_enable_fallback: bool = Field(
        default=True,
        description="Enable automatic fallback to alternative providers on failure"
    )
    llm_prefer_local: bool = Field(
        default=False,
        description="Prefer local models when available"
    )
    llm_max_latency_ms: int = Field(
        default=10000,
        ge=1000,
        le=60000,
        description="Maximum acceptable latency in milliseconds"
    )
    
    # Provider-specific API Keys
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    openai_organization: Optional[str] = Field(default=None, description="OpenAI organization ID")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    mistral_api_key: Optional[str] = Field(default=None, description="Mistral AI API key")
    together_api_key: Optional[str] = Field(default=None, description="Together AI API key")
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server base URL"
    )
    
    # Knowledge Base & Vector Database Settings
    vector_db_provider: str = Field(
        default="chroma",
        description="Vector database provider: pinecone | weaviate | milvus | qdrant | chroma | elasticsearch | pgvector"
    )
    vector_db_enabled: bool = Field(
        default=True,
        description="Enable knowledge base and RAG functionality"
    )
    embedding_model: str = Field(
        default="openai-text-embedding-3-small",
        description="Default embedding model: openai-text-embedding-3-small | openai-text-embedding-3-large | huggingface-all-MiniLM-L6-v2"
    )
    knowledge_base_auto_index: bool = Field(
        default=True,
        description="Automatically index new knowledge items"
    )
    knowledge_base_deduplication: bool = Field(
        default=True,
        description="Enable automatic deduplication of knowledge items"
    )
    knowledge_base_max_results: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of knowledge results to retrieve per query"
    )
    knowledge_base_min_relevance_score: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score for knowledge search results"
    )
    
    # Provider-specific Vector Database Configuration
    pinecone_api_key: Optional[str] = Field(default=None, description="Pinecone API key")
    pinecone_environment: str = Field(default="us-west1-gcp", description="Pinecone environment")
    pinecone_index_name: str = Field(default="knowledge-base", description="Pinecone index name")
    
    weaviate_url: str = Field(default="http://localhost:8080", description="Weaviate server URL")
    weaviate_username: Optional[str] = Field(default=None, description="Weaviate username")
    weaviate_password: Optional[str] = Field(default=None, description="Weaviate password")
    weaviate_class_name: str = Field(default="KnowledgeItem", description="Weaviate class name")
    
    chromadb_path: str = Field(default="./chromadb", description="ChromaDB persistent storage path")
    chromadb_collection_name: str = Field(default="knowledge_items", description="ChromaDB collection name")
    
    milvus_host: str = Field(default="localhost", description="Milvus server host")
    milvus_port: int = Field(default=19530, description="Milvus server port")
    milvus_collection_name: str = Field(default="knowledge_items", description="Milvus collection name")
    
    qdrant_host: str = Field(default="localhost", description="Qdrant server host")
    qdrant_port: int = Field(default=6333, description="Qdrant server port")
    qdrant_collection_name: str = Field(default="knowledge_items", description="Qdrant collection name")
    
    @property
    def database_url(self) -> str:
        """Generate PostgreSQL connection URL."""
        return (
            f"postgresql://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )
    
    @property
    def async_database_url(self) -> str:
        """Generate async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )
    
    def __str__(self) -> str:
        """String representation of settings (hide sensitive data)."""

        github_auth = (
            "app"
            if (self.github_app_id and self.github_private_key_path)
            else ("pat" if self.github_pat else "none")
        )

        return f"""Settings(
    API: {self.api_host}:{self.api_port} (workers={self.api_workers}, reload={self.api_reload})
    MGX: max_rounds={self.mgx_max_rounds}, cache={self.mgx_cache_backend}
    DB: {self.db_host}:{self.db_port}/{self.db_name}
    Redis: {self.redis_url or 'not configured'}
    GitHub: auth={github_auth}, cache_dir={self.github_clone_cache_dir}
    Agents: enabled={self.agents_enabled}, max_concurrency={self.agent_max_concurrency}
)"""


# Global settings instance
settings = Settings()

__all__ = ['Settings', 'settings']