# -*- coding: utf-8 -*-
"""
FastAPI Application Main Module

Initializes FastAPI application with:
- Lifespan event handlers (startup/shutdown)
- Router registration
- Dependency injection
- Configuration loading
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.middleware.observability import ObservabilityContextMiddleware
from backend.middleware.feature_flag_context import FeatureFlagContextMiddleware

from mgx_observability import ObservabilityConfig, initialize_otel, get_langsmith_logger
# Lazy import MGXTeamProvider to avoid Pydantic validation errors during module import
from backend.services import (
    get_task_runner,
    AgentRegistry,
    SharedContextService,
)
from backend.routers import (
    health_router,
    workspaces_router,
    projects_router,
    repositories_router,
    tasks_router,
    runs_router,
    metrics_router,
    agents_router,
    workflows_router,
    ws_router,
    quality_gates_router,
    rbac_router,
    audit_router,
    secrets_router,
    generator_router,
    artifacts_router,
    costs_router,
    validators_router,
    templates_router,
    knowledge_router,
    llm_router,
    escalation_router,
    observability_router,
    file_approvals_router,
    feature_flags_admin_router,
    webhooks_router,
    pull_requests_router,
    issues_router,
    activity_router,
    branches_router,
    diffs_router,
)
from backend.routers.performance import router as performance_router

# Import database session factory and workflow engine integration
from backend.db.engine import get_session_factory
from backend.services.workflows.integration import get_workflow_engine_integration

# Structured logging configuration
from backend.middleware.logging import setup_logging, get_logger

# Configure structured logging
setup_logging(log_level=settings.log_level)
logger = get_logger(__name__)


# ============================================
# Lifespan Events
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    FastAPI lifespan context manager.
    
    Handles startup and shutdown events for the application.
    
    Startup:
    - Initialize MGXTeamProvider
    - Start background task runner
    - Log startup information
    
    Shutdown:
    - Stop background task runner
    - Cleanup team resources
    - Log shutdown information
    """
    # ========== STARTUP ==========
    logger.info("=" * 60)
    logger.info("FastAPI Application Startup")
    logger.info("=" * 60)
    logger.info(f"Settings: {settings}")

    # Initialize observability (OpenTelemetry + LangSmith) early to capture startup spans
    obs_config = ObservabilityConfig(
        otel_enabled=settings.otel_enabled,
        service_name=settings.otel_service_name,
        otlp_endpoint=settings.otel_otlp_endpoint,
        otlp_protocol=settings.otel_otlp_protocol,
        otlp_headers=settings.otel_otlp_headers,
        sample_ratio=settings.otel_sample_ratio,
        langsmith_enabled=settings.langsmith_enabled,
        langsmith_api_key=settings.langsmith_api_key,
        langsmith_project=settings.langsmith_project,
        langsmith_endpoint=settings.langsmith_endpoint,
        phoenix_enabled=settings.phoenix_enabled,
        phoenix_endpoint=settings.phoenix_endpoint,
    )

    engine_for_otel = None
    try:
        session_factory = await get_session_factory()
        engine = getattr(session_factory, "bind", None)
        if engine is not None and hasattr(engine, "sync_engine"):
            engine_for_otel = engine.sync_engine
    except Exception as e:
        logger.debug(f"Observability: failed to resolve engine for SQL instrumentation: {e}")

    initialize_otel(obs_config, fastapi_app=app, sqlalchemy_engine=engine_for_otel)
    app.state.observability_config = obs_config
    app.state.langsmith_logger = get_langsmith_logger(obs_config)

    # Initialize team provider (lazy import to avoid Pydantic validation errors)
    try:
        from backend.services import MGXTeamProvider
        team_provider = MGXTeamProvider(config=None)  # Uses default config
        app.state.team_provider = team_provider
        logger.info("✓ MGXTeamProvider initialized")
    except Exception as e:
        logger.error(f"Failed to initialize MGXTeamProvider: {e}")
        logger.warning("Continuing without MGXTeamProvider - some features may be unavailable")
        app.state.team_provider = None
    
    # Start background task runner
    task_runner = get_task_runner()
    await task_runner.start(num_workers=2)
    app.state.task_runner = task_runner
    logger.info("✓ BackgroundTaskRunner started")
    
    # Initialize agent services (if enabled)
    if settings.agents_enabled:
        agent_registry = AgentRegistry()
        app.state.agent_registry = agent_registry
        logger.info("✓ AgentRegistry initialized")
        
        context_service = SharedContextService()
        app.state.context_service = context_service
        logger.info("✓ SharedContextService initialized")
        
        # Initialize workflow engine integration
        try:
            from backend.services.workflows.integration import initialize_workflow_integration
            
            workflow_integration = await initialize_workflow_integration(
                session_factory=await get_session_factory(),
                agent_registry=agent_registry,
                context_service=context_service,
                task_runner=task_runner,
            )
            app.state.workflow_integration = workflow_integration
            logger.info("✓ WorkflowEngineIntegration initialized")
        except Exception as e:
            logger.error(f"Failed to initialize workflow engine: {str(e)}")
            # Continue without workflow functionality
            app.state.workflow_integration = None
        
        # Auto-load agent modules if specified
        if settings.agent_registry_modules:
            modules = [m.strip() for m in settings.agent_registry_modules.split(",")]
            for module_name in modules:
                try:
                    __import__(module_name)
                    logger.info(f"✓ Loaded agent module: {module_name}")
                except ImportError as e:
                    logger.warning(f"Failed to load agent module {module_name}: {str(e)}")
    else:
        logger.info("Agent system disabled (set AGENTS_ENABLED=true to enable)")
    
    # Initialize secret management system
    try:
        from backend.services.secrets.encryption import encryption_service
        from backend.db.models.enums import SecretBackend
        
        # Initialize encryption service based on configuration
        backend_type = SecretBackend(settings.secret_encryption_backend.lower())
        
        if backend_type == SecretBackend.FERNET:
            encryption_kwargs = {}
            if settings.secret_encryption_key:
                encryption_kwargs['encryption_key'] = settings.secret_encryption_key
        elif backend_type == SecretBackend.AWS_KMS:
            encryption_kwargs = {
                'kms_key_id': settings.aws_kms_key_id,
                'region': settings.aws_region
            }
        elif backend_type == SecretBackend.VAULT:
            encryption_kwargs = {
                'vault_url': settings.vault_url,
                'vault_token': settings.vault_token,
                'mount_point': settings.vault_mount_point
            }
        else:
            raise ValueError(f"Unsupported secret encryption backend: {backend_type}")
        
        await encryption_service.initialize(backend_type, **encryption_kwargs)
        app.state.encryption_service = encryption_service
        logger.info(f"✓ Secret management initialized with {backend_type} backend")
        
    except Exception as e:
        logger.error(f"Failed to initialize secret management: {str(e)}")
        # Continue without secret management
        app.state.encryption_service = None
    
    logger.info("FastAPI Application Ready")
    logger.info("=" * 60)
    
    yield  # Application is now running
    
    # ========== SHUTDOWN ==========
    logger.info("=" * 60)
    logger.info("FastAPI Application Shutdown")
    logger.info("=" * 60)
    
    # Stop background task runner
    try:
        await task_runner.stop()
        logger.info("✓ BackgroundTaskRunner stopped")
    except Exception as e:
        logger.error(f"Error stopping task runner: {str(e)}")
    
    # Shutdown team provider
    try:
        await team_provider.shutdown()
        logger.info("✓ MGXTeamProvider shutdown")
    except Exception as e:
        logger.error(f"Error shutting down team provider: {str(e)}")
    
    logger.info("FastAPI Application Shutdown Complete")
    logger.info("=" * 60)


# ============================================
# FastAPI Application Factory
# ============================================

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="MGX Agent API",
        description="RESTful API for MGX Style Multi-Agent Team",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # ========== CORS Configuration ==========
    # Allow requests from development and production origins
    # In development, allow all origins to avoid CORS issues
    cors_origins = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]
    
    # In development mode, also allow all origins (less secure but easier for dev)
    if getattr(settings, 'mgx_env', 'development') == 'development' or getattr(settings, 'log_level', 'INFO') == 'DEBUG':
        cors_origins.append("*")
        allow_credentials = False  # Can't use credentials with wildcard
    else:
        allow_credentials = True
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if "*" not in cors_origins else ["*"],
        allow_credentials=allow_credentials if "*" not in cors_origins else False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600,
    )
    
    logger.info("CORS middleware configured with origins: %s", cors_origins if "*" not in cors_origins else ["*"])

    # Add exception handler to ensure CORS headers are always added, even on errors
    from fastapi import Request, status
    from fastapi.responses import JSONResponse
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler that ensures CORS headers are always present."""
        import traceback
        error_trace = traceback.format_exc()
        logger.error(
            "[global_exception_handler] Unhandled exception on %s %s: %s\n%s",
            request.method,
            request.url.path,
            str(exc),
            error_trace
        )
        
        # Ensure CORS headers are always present
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
        
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(exc)}"},
            headers=cors_headers
        )
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """HTTP exception handler with CORS headers."""
        logger.warning(
            "[http_exception_handler] HTTP exception on %s %s: %s - %s",
            request.method,
            request.url.path,
            exc.status_code,
            exc.detail
        )
        
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
        
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=cors_headers
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Validation exception handler with CORS headers."""
        logger.warning(
            "[validation_exception_handler] Validation error on %s %s: %s",
            request.method,
            request.url.path,
            exc.errors()
        )
        
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
        
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
            headers=cors_headers
        )

    # Add structured logging middleware (replaces old RequestLoggingMiddleware)
    from backend.middleware.logging import StructuredLoggingMiddleware
    app.add_middleware(StructuredLoggingMiddleware)

    # Add middleware that enriches traces with workspace/project context.
    app.add_middleware(ObservabilityContextMiddleware)

    app.add_middleware(FeatureFlagContextMiddleware)

    # ========== Router Registration ==========
    app.include_router(health_router)
    logger.info("✓ Registered: health_router")

    app.include_router(workspaces_router)
    logger.info("✓ Registered: workspaces_router")

    app.include_router(projects_router)
    logger.info("✓ Registered: projects_router")

    app.include_router(repositories_router)
    logger.info("✓ Registered: repositories_router")
    
    app.include_router(tasks_router)
    logger.info("✓ Registered: tasks_router")
    
    app.include_router(runs_router)
    logger.info("✓ Registered: runs_router")
    
    app.include_router(metrics_router)
    logger.info("✓ Registered: metrics_router")

    app.include_router(agents_router)
    logger.info("✓ Registered: agents_router")
    
    app.include_router(workflows_router)
    logger.info("✓ Registered: workflows_router")
    
    app.include_router(ws_router)
    logger.info("✓ Registered: ws_router (WebSocket)")
    
    app.include_router(quality_gates_router)
    logger.info("✓ Registered: quality_gates_router")
    
    app.include_router(rbac_router)
    logger.info("✓ Registered: rbac_router")
    
    app.include_router(audit_router)
    logger.info("✓ Registered: audit_router")
    
    app.include_router(secrets_router)
    logger.info("✓ Registered: secrets_router")
    
    app.include_router(generator_router)
    logger.info("✓ Registered: generator_router")

    app.include_router(artifacts_router)
    logger.info("✓ Registered: artifacts_router")
    
    app.include_router(costs_router)
    logger.info("✓ Registered: costs_router")
    
    app.include_router(validators_router)
    logger.info("✓ Registered: validators_router")
    
    app.include_router(templates_router)
    logger.info("✓ Registered: templates_router")

    app.include_router(knowledge_router)
    logger.info("✓ Registered: knowledge_router")

    app.include_router(llm_router)
    logger.info("✓ Registered: llm_router")
    
    app.include_router(escalation_router)
    logger.info("✓ Registered: escalation_router")

    app.include_router(observability_router)
    logger.info("✓ Registered: observability_router")
    
    app.include_router(file_approvals_router)
    logger.info("✓ Registered: file_approvals_router")

    app.include_router(feature_flags_admin_router)
    logger.info("✓ Registered: feature_flags_admin_router")
    
    app.include_router(webhooks_router)
    logger.info("✓ Registered: webhooks_router")
    
    app.include_router(pull_requests_router)
    logger.info("✓ Registered: pull_requests_router")
    
    app.include_router(issues_router)
    logger.info("✓ Registered: issues_router")
    
    app.include_router(activity_router)
    logger.info("✓ Registered: activity_router")
    
    app.include_router(branches_router)
    logger.info("✓ Registered: branches_router")
    
    app.include_router(diffs_router)
    logger.info("✓ Registered: diffs_router")
    
    app.include_router(performance_router)
    logger.info("✓ Registered: performance_router")
    
    # ========== Root Endpoint ==========
    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint returning API information."""
        return {
            "message": "MGX Agent API",
            "version": "0.1.0",
            "docs": "/docs",
            "redoc": "/redoc",
        }
    
    logger.info("✓ Registered: root endpoint")
    
    return app


# ============================================
# Global Application Instance
# ============================================

app = create_app()


# ============================================
# Uvicorn Entry Point
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Uvicorn server...")
    uvicorn.run(
        "backend.app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        workers=settings.api_workers,
        log_level=settings.log_level.lower(),
    )


__all__ = ['app', 'create_app', 'lifespan']
