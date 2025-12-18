# -*- coding: utf-8 -*-
"""backend.db.models.enums

Database enums for status types and other constants.

These enums are used both by SQLAlchemy (as database enums) and by the API
layer (as response-friendly string values).
"""

from enum import Enum


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"  # Task is queued for execution
    RUNNING = "running"  # Task is currently executing
    COMPLETED = "completed"  # Task completed successfully
    FAILED = "failed"  # Task failed with error
    CANCELLED = "cancelled"  # Task was cancelled
    TIMEOUT = "timeout"  # Task timed out


class RunStatus(str, Enum):
    """Task run execution status."""

    PENDING = "pending"  # Run is queued for execution
    RUNNING = "running"  # Run is currently executing
    COMPLETED = "completed"  # Run completed successfully
    FAILED = "failed"  # Run failed with error
    CANCELLED = "cancelled"  # Run was cancelled
    TIMEOUT = "timeout"  # Run timed out


class MetricType(str, Enum):
    """Types of metrics that can be captured."""

    COUNTER = "counter"  # Incrementing counter
    GAUGE = "gauge"  # Current value
    HISTOGRAM = "histogram"  # Distribution of values
    TIMER = "timer"  # Time-based measurement
    STATUS = "status"  # Status indicator
    ERROR_RATE = "error_rate"  # Error rate percentage
    THROUGHPUT = "throughput"  # Operations per time unit
    LATENCY = "latency"  # Response time
    CUSTOM = "custom"  # Custom metric type


class ArtifactType(str, Enum):
    """Types of artifacts that can be stored."""

    DOCUMENT = "document"  # Document files (PDF, DOC, etc.)
    IMAGE = "image"  # Image files
    VIDEO = "video"  # Video files
    AUDIO = "audio"  # Audio files
    CODE = "code"  # Source code files
    DATA = "data"  # Data files (JSON, CSV, etc.)
    LOG = "log"  # Log files
    CONFIG = "config"  # Configuration files
    MODEL = "model"  # ML models
    REPORT = "report"  # Generated reports
    SUMMARY = "summary"  # Summary documents
    CHART = "chart"  # Charts and graphs


class ArtifactBuildStatus(str, Enum):
    """Status of an artifact build pipeline execution."""

    PENDING = "pending"
    BUILDING = "building"
    COMPLETED = "completed"
    FAILED = "failed"


class RepositoryProvider(str, Enum):
    """Source control provider for a linked repository."""

    GITHUB = "github"


class RepositoryLinkStatus(str, Enum):
    """Status of a repository link."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class AgentStatus(str, Enum):
    """Agent lifecycle status."""

    IDLE = "idle"  # Agent is idle, ready to accept work
    INITIALIZING = "initializing"  # Agent is initializing
    ACTIVE = "active"  # Agent is active and running
    BUSY = "busy"  # Agent is busy processing
    ERROR = "error"  # Agent encountered an error
    OFFLINE = "offline"  # Agent is offline or disconnected


class AgentMessageDirection(str, Enum):
    """Direction of an agent message in the message log."""

    INBOUND = "inbound"  # Client/user -> agent
    OUTBOUND = "outbound"  # Agent -> client/user
    SYSTEM = "system"  # System-generated lifecycle/event log


class ContextRollbackState(str, Enum):
    """State of context rollback operation."""

    PENDING = "pending"  # Rollback is pending
    SUCCESS = "success"  # Rollback succeeded
    FAILED = "failed"  # Rollback failed


class ProjectTemplateStatus(str, Enum):
    """Status of a project template."""

    DRAFT = "draft"  # Template is being created/edited
    ACTIVE = "active"  # Template is available for use
    DEPRECATED = "deprecated"  # Template is deprecated but still available
    ARCHIVED = "archived"  # Template is archived and not available


class ProjectGenerationStatus(str, Enum):
    """Status of a project generation process."""

    PENDING = "pending"  # Generation is queued
    RUNNING = "running"  # Generation is in progress
    COMPLETED = "completed"  # Generation completed successfully
    FAILED = "failed"  # Generation failed with error
    CANCELLED = "cancelled"  # Generation was cancelled


class StackType(str, Enum):
    """Programming stack types for project templates."""

    EXPRESS_TS = "express_ts"  # Express.js with TypeScript
    FASTAPI = "fastapi"  # FastAPI Python framework
    NEXTJS = "nextjs"  # Next.js React framework
    LARAVEL = "laravel"  # Laravel PHP framework


class TemplateFeatureType(str, Enum):
    """Types of features that can be added to project templates."""

    AUTH = "auth"  # Authentication system
    DATABASE = "database"  # Database integration
    LOGGING = "logging"  # Logging system
    VALIDATION = "validation"  # Input validation
    TESTING = "testing"  # Testing framework
    DOCKER = "docker"  # Docker configuration
    CICD = "cicd"  # CI/CD pipeline
    MONITORING = "monitoring"  # Monitoring and metrics
    API_DOCS = "api_docs"  # API documentation
    WEBSOCKET = "websocket"  # WebSocket support
    FILE_UPLOAD = "file_upload"  # File upload handling
    EMAIL = "email"  # Email service integration
    CACHE = "cache"  # Caching system
    QUEUE = "queue"  # Job queue system
    SUCCESS = "success"  # Rollback succeeded
    FAILED = "failed"  # Rollback failed


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    PENDING = "pending"  # Workflow is queued for execution
    RUNNING = "running"  # Workflow is currently executing
    COMPLETED = "completed"  # Workflow completed successfully
    FAILED = "failed"  # Workflow failed with error
    CANCELLED = "cancelled"  # Workflow was cancelled
    TIMEOUT = "timeout"  # Workflow timed out


class WorkflowStepStatus(str, Enum):
    """Workflow step execution status."""

    PENDING = "pending"  # Step is queued for execution
    RUNNING = "running"  # Step is currently executing
    COMPLETED = "completed"  # Step completed successfully
    FAILED = "failed"  # Step failed with error
    CANCELLED = "cancelled"  # Step was cancelled
    SKIPPED = "skipped"  # Step was skipped


class WorkflowStepType(str, Enum):
    """Types of workflow steps."""

    TASK = "task"  # Simple task execution
    CONDITION = "condition"  # Conditional branching
    PARALLEL = "parallel"  # Parallel execution
    SEQUENTIAL = "sequential"  # Sequential steps
    AGENT = "agent"  # Agent execution


class SandboxExecutionStatus(str, Enum):
    """Sandbox execution status."""

    PENDING = "pending"  # Execution is queued
    RUNNING = "running"  # Execution is currently running
    COMPLETED = "completed"  # Execution completed successfully
    FAILED = "failed"  # Execution failed with error
    CANCELLED = "cancelled"  # Execution was cancelled
    TIMEOUT = "timeout"  # Execution timed out


class SandboxExecutionLanguage(str, Enum):
    """Supported programming languages for sandbox execution."""

    JAVASCRIPT = "javascript"
    NODE = "node"
    PYTHON = "python"
    PHP = "php"
    DOCKER = "docker"


class QualityGateType(str, Enum):
    """Types of quality gates."""

    LINT = "lint"  # Code linting (ESLint, Ruff, Pint)
    COVERAGE = "coverage"  # Test coverage enforcement
    CONTRACT = "contract"  # API endpoint contract testing
    PERFORMANCE = "performance"  # Performance smoke tests
    SECURITY = "security"  # Security audit and vulnerability scanning
    COMPLEXITY = "complexity"  # Code complexity limits
    TYPE_CHECK = "type_check"  # Type checking (TypeScript, MyPy)


class QualityGateStatus(str, Enum):
    """Quality gate evaluation status."""

    PENDING = "pending"  # Gate evaluation is queued
    RUNNING = "running"  # Gate is currently being evaluated
    PASSED = "passed"  # Gate passed all checks
    FAILED = "failed"  # Gate failed one or more checks
    WARNING = "warning"  # Gate passed but has warnings
    SKIPPED = "skipped"  # Gate was skipped due to configuration
    ERROR = "error"  # Gate evaluation encountered an error
    TIMEOUT = "timeout"  # Gate evaluation timed out


class GateSeverity(str, Enum):
    """Severity levels for gate failures."""

    CRITICAL = "critical"  # Blocking failure
    HIGH = "high"  # Blocking failure
    MEDIUM = "medium"  # Warning level
    LOW = "low"  # Info level


class RoleName(str, Enum):
    """System-defined role names."""

    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"
    AUDITOR = "auditor"


class PermissionResource(str, Enum):
    """Resource types for permissions."""

    TASKS = "tasks"
    WORKFLOWS = "workflows"
    REPOSITORIES = "repositories"
    REPOS = "repos"
    AGENTS = "agents"
    SETTINGS = "settings"
    USERS = "users"
    AUDIT = "audit"
    METRICS = "metrics"
    WORKSPACES = "workspaces"
    PROJECTS = "projects"
    SECRETS = "secrets"


class PermissionAction(str, Enum):
    """Action types for permissions."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    APPROVE = "approve"
    MANAGE = "manage"
    CONNECT = "connect"


class AuditAction(str, Enum):
    """Audit log action types."""

    # User management
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_DELETED = "USER_DELETED"
    
    # Role and permission management
    ROLE_CREATED = "ROLE_CREATED"
    ROLE_UPDATED = "ROLE_UPDATED"
    ROLE_DELETED = "ROLE_DELETED"
    ROLE_ASSIGNED = "ROLE_ASSIGNED"
    ROLE_REVOKED = "ROLE_REVOKED"
    PERMISSION_GRANTED = "PERMISSION_GRANTED"
    PERMISSION_REVOKED = "PERMISSION_REVOKED"
    
    # Workspace management
    WORKSPACE_CREATED = "WORKSPACE_CREATED"
    WORKSPACE_UPDATED = "WORKSPACE_UPDATED"
    WORKSPACE_DELETED = "WORKSPACE_DELETED"
    WORKSPACE_ACCESS_GRANTED = "WORKSPACE_ACCESS_GRANTED"
    WORKSPACE_ACCESS_REVOKED = "WORKSPACE_ACCESS_REVOKED"
    
    # Project management
    PROJECT_CREATED = "PROJECT_CREATED"
    PROJECT_UPDATED = "PROJECT_UPDATED"
    PROJECT_DELETED = "PROJECT_DELETED"
    
    # Task management
    TASK_CREATED = "TASK_CREATED"
    TASK_UPDATED = "TASK_UPDATED"
    TASK_DELETED = "TASK_DELETED"
    TASK_EXECUTED = "TASK_EXECUTED"
    TASK_RUN_STARTED = "TASK_RUN_STARTED"
    TASK_RUN_COMPLETED = "TASK_RUN_COMPLETED"
    TASK_RUN_FAILED = "TASK_RUN_FAILED"
    
    # Workflow management
    WORKFLOW_CREATED = "WORKFLOW_CREATED"
    WORKFLOW_UPDATED = "WORKFLOW_UPDATED"
    WORKFLOW_DELETED = "WORKFLOW_DELETED"
    WORKFLOW_EXECUTED = "WORKFLOW_EXECUTED"
    WORKFLOW_STEP_EXECUTED = "WORKFLOW_STEP_EXECUTED"
    
    # Repository management
    REPOSITORY_CONNECTED = "REPOSITORY_CONNECTED"
    REPOSITORY_DISCONNECTED = "REPOSITORY_DISCONNECTED"
    REPOSITORY_ACCESS_GRANTED = "REPOSITORY_ACCESS_GRANTED"
    
    # Agent management
    AGENT_CREATED = "AGENT_CREATED"
    AGENT_UPDATED = "AGENT_UPDATED"
    AGENT_DELETED = "AGENT_DELETED"
    AGENT_ENABLED = "AGENT_ENABLED"
    AGENT_DISABLED = "AGENT_DISABLED"
    AGENT_MESSAGE_SENT = "AGENT_MESSAGE_SENT"
    
    # System and settings
    SETTINGS_CHANGED = "SETTINGS_CHANGED"
    SYSTEM_BACKUP_CREATED = "SYSTEM_BACKUP_CREATED"
    SYSTEM_MAINTENANCE_MODE_ENABLED = "SYSTEM_MAINTENANCE_MODE_ENABLED"
    
    # Security events
    UNAUTHORIZED_ACCESS_ATTEMPT = "UNAUTHORIZED_ACCESS_ATTEMPT"
    SECURITY_VIOLATION_DETECTED = "SECURITY_VIOLATION_DETECTED"
    
    # Data operations
    DATA_EXPORTED = "DATA_EXPORTED"
    DATA_IMPORTED = "DATA_IMPORTED"
    BULK_OPERATION_PERFORMED = "BULK_OPERATION_PERFORMED"
    
    # Sandbox operations
    SANDBOX_EXECUTION_STARTED = "SANDBOX_EXECUTION_STARTED"
    SANDBOX_EXECUTION_COMPLETED = "SANDBOX_EXECUTION_COMPLETED"
    SANDBOX_EXECUTION_FAILED = "SANDBOX_EXECUTION_FAILED"


class AuditLogStatus(str, Enum):
    """Status of audit log entries."""

    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    WARNING = "warning"


class SecretType(str, Enum):
    """Types of secrets that can be stored."""

    API_KEY = "api_key"  # General API keys
    DATABASE_CREDENTIAL = "database_cred"  # Database passwords/credentials
    OAUTH_TOKEN = "oauth_token"  # OAuth access/refresh tokens
    WEBHOOK_SECRET = "webhook_secret"  # Webhook verification secrets
    SSH_KEY = "ssh_key"  # SSH private keys
    CERTIFICATE = "certificate"  # SSL/TLS certificates
    ENCRYPTION_KEY = "encryption_key"  # Encryption keys
    PASSWORD = "password"  # General passwords
    JWT_SECRET = "jwt_secret"  # JWT signing secrets


class SecretRotationPolicy(str, Enum):
    """Rotation policies for secrets."""

    MANUAL = "manual"  # Manual rotation only
    AUTO_30_DAYS = "auto_30_days"  # Auto rotate every 30 days
    AUTO_60_DAYS = "auto_60_days"  # Auto rotate every 60 days
    AUTO_90_DAYS = "auto_90_days"  # Auto rotate every 90 days
    AUTO_180_DAYS = "auto_180_days"  # Auto rotate every 180 days
    AUTO_365_DAYS = "auto_365_days"  # Auto rotate every 365 days


class SecretBackend(str, Enum):
    """Secret storage backend types."""

    FERNET = "fernet"  # Built-in Fernet encryption
    VAULT = "vault"  # HashiCorp Vault
    AWS_KMS = "aws_kms"  # AWS KMS + Secrets Manager
    AZURE_KEYVAULT = "azure_keyvault"  # Azure Key Vault


class SecretAuditAction(str, Enum):
    """Actions tracked in secret audit logs."""

    CREATED = "created"  # Secret was created
    ACCESSED = "accessed"  # Secret value was retrieved
    ROTATED = "rotated"  # Secret was rotated
    DELETED = "deleted"  # Secret was deleted
    UPDATED = "updated"  # Secret metadata was updated
    ENCRYPTION_KEY_ROTATED = "encryption_key_rotated"  # Encryption key was rotated
    BACKUP_CREATED = "backup_created"  # Secret backup was created
    RESTORE_PERFORMED = "restore_performed"  # Secret was restored from backup


class LLMProvider(str, Enum):
    """LLM provider types for cost tracking."""

    OPENAI = "openai"  # OpenAI (GPT models)
    ANTHROPIC = "anthropic"  # Anthropic (Claude models)
    CLAUDE = "claude"  # Claude (alias for Anthropic)
    MISTRAL = "mistral"  # Mistral AI
    COHERE = "cohere"  # Cohere
    GOOGLE = "google"  # Google (Gemini, PaLM)
    HUGGINGFACE = "huggingface"  # HuggingFace models
    LOCAL = "local"  # Local models (Ollama, etc.)
    OTHER = "other"  # Other providers


class ResourceType(str, Enum):
    """Resource types for usage tracking."""

    CPU = "cpu"  # CPU cores
    MEMORY = "memory"  # RAM memory
    GPU = "gpu"  # GPU resources
    STORAGE = "storage"  # Disk storage
    BANDWIDTH = "bandwidth"  # Network bandwidth
    SANDBOX = "sandbox"  # Sandbox execution time
    DATABASE = "database"  # Database operations


class BudgetAlertType(str, Enum):
    """Budget alert threshold types."""

    THRESHOLD_50 = "threshold_50"  # 50% of budget reached
    THRESHOLD_80 = "threshold_80"  # 80% of budget reached
    THRESHOLD_90 = "threshold_90"  # 90% of budget reached
    THRESHOLD_100 = "threshold_100"  # 100% of budget reached
    THRESHOLD_EXCEEDED = "threshold_exceeded"  # Budget exceeded
    ANOMALY_DETECTED = "anomaly_detected"  # Cost anomaly detected


class DeploymentValidationStatus(str, Enum):
    """Status of deployment validation."""

    PENDING = "pending"  # Validation is queued
    RUNNING = "running"  # Validation is in progress
    PASSED = "passed"  # All validations passed
    FAILED = "failed"  # Validation failed
    WARNING = "warning"  # Validation passed with warnings
    COMPLETED = "completed"  # Validation completed


class ValidationCheckStatus(str, Enum):
    """Status of individual validation checks."""

    PENDING = "pending"  # Check is pending
    RUNNING = "running"  # Check is running
    PASSED = "passed"  # Check passed
    FAILED = "failed"  # Check failed
    WARNING = "warning"  # Check passed with warnings
    SKIPPED = "skipped"  # Check was skipped


class ChecklistItemStatus(str, Enum):
    """Status of a pre-deployment checklist item."""

    PENDING = "pending"  # Item is pending
    PASS = "pass"  # Item passed
    FAIL = "fail"  # Item failed
    MANUAL = "manual"  # Requires manual review
    NOT_APPLICABLE = "not_applicable"  # Item not applicable


class DeploymentEnvironment(str, Enum):
    """Deployment target environments."""

    SANDBOX = "sandbox"  # Sandbox/test environment
    STAGING = "staging"  # Staging environment
    PRODUCTION = "production"  # Production environment


class DeploymentPhase(str, Enum):
    """Phases of the deployment validation."""

    DOCKER_VALIDATION = "docker_validation"  # Docker image validation
    KUBERNETES_VALIDATION = "kubernetes_validation"  # Kubernetes manifest validation
    HEALTH_CHECK = "health_check"  # Health check validation
    SECURITY_CHECK = "security_check"  # Security validation
    CONFIGURATION_CHECK = "configuration_check"  # Configuration validation
    DRY_RUN = "dry_run"  # Dry-run simulation
    ROLLBACK_VALIDATION = "rollback_validation"  # Rollback procedure validation


class TemplateCategory(str, Enum):
    """Template categories for organization."""

    AUTHENTICATION = "authentication"  # Auth-related templates
    COMMERCE = "commerce"  # E-commerce templates
    ADMIN = "admin"  # Admin dashboard templates
    INFRASTRUCTURE = "infrastructure"  # Infrastructure templates
    API_DESIGN = "api_design"  # API design templates
    DATABASE = "database"  # Database templates
    TESTING = "testing"  # Testing templates
    DOCUMENTATION = "documentation"  # Documentation templates
    WORKFLOW = "workflow"  # Workflow templates
    SECURITY = "security"  # Security templates


class ADRStatus(str, Enum):
    """Architecture Decision Record status."""

    PROPOSED = "proposed"  # ADR is proposed
    ACCEPTED = "accepted"  # ADR is accepted and implemented
    DEPRECATED = "deprecated"  # ADR is deprecated
    SUPERSEDED = "superseded"  # ADR is superseded by another


class TemplateVisibility(str, Enum):
    """Template visibility levels."""

    PUBLIC = "public"  # Public template, shared
    PRIVATE = "private"  # Private template, organization only
    DRAFT = "draft"  # Draft template, not published


class PromptOutputFormat(str, Enum):
    """Prompt template output formats."""

    CODE = "code"  # Generate code
    DOCUMENTATION = "documentation"  # Generate documentation
    SCHEMA = "schema"  # Generate schema
    EXPLANATION = "explanation"  # Generate explanation
    TEST_CASE = "test_case"  # Generate test cases
    CONFIGURATION = "configuration"  # Generate configuration


# ============================================
# Knowledge Base & RAG Enums
# ============================================

class KnowledgeCategory(str, Enum):
    """Categories of knowledge items."""
    
    CODE_PATTERN = "code_pattern"  # Reusable code patterns and snippets
    BEST_PRACTICE = "best_practice"  # Best practices and guidelines
    STANDARD = "standard"  # Company/team standards
    ARCHITECTURE = "architecture"  # Architecture decisions and patterns
    TECHNOLOGY_CHOICE = "technology_choice"  # Technology stack decisions
    API_CONTRACT = "api_contract"  # API definitions and contracts
    SECURITY_GUIDELINE = "security_guideline"  # Security guidelines and requirements
    PERFORMANCE_TIP = "performance_tip"  # Performance optimization tips
    STYLE_GUIDE = "style_guide"  # Code style and formatting guidelines
    TESTING_STANDARD = "testing_standard"  # Testing patterns and standards


class KnowledgeSourceType(str, Enum):
    """Source types for knowledge items."""
    
    INTERNAL_REPOSITORY = "internal_repository"  # From internal code repositories
    DOCUMENTATION = "documentation"  # From project documentation
    BEST_PRACTICE_GUIDE = "best_practice_guide"  # From best practice guides
    ARCHITECTURE_DECISION = "architecture_decision"  # From ADRs
    CODE_REVIEW = "code_review"  # From code review comments
    PROJECT_TEMPLATE = "project_template"  # From project templates
    MANUAL_ENTRY = "manual_entry"  # Manually entered knowledge
    IMPORTED_CONTENT = "imported_content"  # Imported from external sources
    TEAM_STANDARD = "team_standard"  # Team-specific standards
    COMPLIANCE_RULE = "compliance_rule"  # Compliance and regulatory requirements


class VectorDBProvider(str, Enum):
    """Vector database providers."""
    
    PINECONE = "pinecone"  # Pinecone cloud vector database
    WEAVIATE = "weaviate"  # Weaviate (self-hosted or cloud)
    MILVUS = "milvus"  # Milvus (self-hosted)
    QDRANT = "qdrant"  # Qdrant (self-hosted or cloud)
    CHROMA = "chroma"  # Chroma (local/self-hosted)
    ELASTICSEARCH = "elasticsearch"  # Elasticsearch with vector search
    PGVECTOR = "pgvector"  # PostgreSQL with pgvector extension


class KnowledgeItemStatus(str, Enum):
    """Status of knowledge items."""
    
    ACTIVE = "active"  # Active and searchable
    DRAFT = "draft"  # Draft version, not yet searchable
    ARCHIVED = "archived"  # Archived, not searchable
    DEPRECATED = "deprecated"  # Deprecated but still searchable
    UNDER_REVIEW = "under_review"  # Under review process
    VERIFIED = "verified"  # Verified by experts


class EmbeddingModel(str, Enum):
    """Available embedding models."""
    
    OPENAI_ADA_002 = "openai-ada-002"
    OPENAI_TEXT_EMBEDDING_3_SMALL = "openai-text-embedding-3-small"
    OPENAI_TEXT_EMBEDDING_3_LARGE = "openai-text-embedding-3-large"
    ANTHROPIC_CLAUDE_EMBEDDINGS = "anthropic-claude-embeddings"
    HUGGINGFACE_ALL_MINILM_L6_V2 = "huggingface-all-MiniLM-L6-v2"
    SENTENCE_TRANSFORMERS_ALL_MPNET_BASE_V2 = "sentence-transformers-all-mpnet-base-v2"
    LOCAL_SENTENCE_TRANSFORMERS = "local-sentence-transformers"
