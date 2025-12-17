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
from backend.services import (
    MGXTeamProvider,
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
)

# Import database session factory and workflow engine integration
from backend.db.engine import get_session_factory
from backend.services.workflows.integration import get_workflow_engine_integration

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s [%(levelname)8s] %(name)s - %(message)s',
)
logger = logging.getLogger(__name__)


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
    
    # Initialize team provider
    team_provider = MGXTeamProvider(config=None)  # Uses default config
    app.state.team_provider = team_provider
    logger.info("✓ MGXTeamProvider initialized")
    
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    logger.info("CORS middleware configured")
    
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
