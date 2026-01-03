# -*- coding: utf-8 -*-
"""
Health Check Router

Provides endpoints for monitoring application health and status.
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


async def _check_database() -> Dict[str, Any]:
    """Check database connectivity."""
    try:
        from backend.db.engine import get_session_factory
        session_factory = await get_session_factory()
        # Try to execute a simple query
        async with session_factory() as session:
            await session.execute("SELECT 1")
        return {"status": "healthy", "message": "Database connection successful"}
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return {"status": "unhealthy", "message": str(e)}


async def _check_cache() -> Dict[str, Any]:
    """Check cache (Redis) connectivity."""
    try:
        import redis.asyncio as redis
        from backend.config import settings

        if not settings.redis_url:
            return {"status": "not_configured", "message": "Redis not configured"}

        redis_client = redis.from_url(settings.redis_url)
        await redis_client.ping()
        await redis_client.close()
        return {"status": "healthy", "message": "Cache connection successful"}
    except Exception as e:
        logger.error(f"Cache health check failed: {str(e)}")
        return {"status": "unhealthy", "message": str(e)}


async def _check_llm_provider() -> Dict[str, Any]:
    """Check LLM provider availability."""
    try:
        from backend.services.llm.llm_service import llm_service

        # Just check if service is initialized
        if hasattr(llm_service, 'providers') and llm_service.providers:
            return {"status": "healthy", "message": f"LLM provider configured: {list(llm_service.providers.keys())}"}
        else:
            return {"status": "degraded", "message": "LLM provider not fully configured"}
    except Exception as e:
        logger.error(f"LLM provider health check failed: {str(e)}")
        return {"status": "unhealthy", "message": str(e)}


async def _check_vector_db() -> Dict[str, Any]:
    """Check vector database connectivity."""
    try:
        from backend.services.knowledge.factory import get_vector_store

        vector_store = get_vector_store()
        if vector_store:
            return {"status": "healthy", "message": "Vector database configured"}
        else:
            return {"status": "not_configured", "message": "Vector database not configured"}
    except Exception as e:
        logger.error(f"Vector database health check failed: {str(e)}")
        return {"status": "unhealthy", "message": str(e)}


@router.get("/", response_model=Dict[str, Any])
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint.

    Returns:
        200 OK with status information
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "mgx-agent-api",
    }


@router.get("/ready", response_model=Dict[str, Any])
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness check endpoint.

    Indicates whether the service is ready to handle requests.
    Checks database, cache, and other critical dependencies.

    Returns:
        200 OK if ready, 503 Service Unavailable otherwise
    """
    try:
        # Run all dependency checks in parallel
        db_health, cache_health, llm_health = await asyncio.gather(
            _check_database(),
            _check_cache(),
            _check_llm_provider(),
            return_exceptions=True
        )

        # Check for critical failures
        critical_failures = []
        dependencies = {}

        if isinstance(db_health, dict):
            dependencies["database"] = db_health
            if db_health["status"] == "unhealthy":
                critical_failures.append("database")

        if isinstance(cache_health, dict):
            dependencies["cache"] = cache_health
            # Cache is not critical (service can run without it)

        if isinstance(llm_health, dict):
            dependencies["llm_provider"] = llm_health
            # LLM provider is important but not critical for health endpoint

        if critical_failures:
            return {
                "ready": False,
                "timestamp": datetime.utcnow().isoformat(),
                "dependencies": dependencies,
                "critical_failures": critical_failures,
            }

        return {
            "ready": True,
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": dependencies,
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: {str(e)}",
        )


@router.get("/live", response_model=Dict[str, Any])
async def liveness_check() -> Dict[str, Any]:
    """
    Liveness check endpoint.

    Indicates whether the service is running and responsive.
    This should always return 200 OK if the process is alive.

    Returns:
        200 OK if alive, 503 Service Unavailable otherwise
    """
    return {
        "alive": True,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/status", response_model=Dict[str, Any])
async def get_status() -> Dict[str, Any]:
    """
    Get detailed service status.

    Returns:
        Service status information including uptime and resource info
    """
    try:
        # Run detailed checks
        db_health, cache_health, llm_health, vector_db_health = await asyncio.gather(
            _check_database(),
            _check_cache(),
            _check_llm_provider(),
            _check_vector_db(),
            return_exceptions=True
        )

        dependencies = {}

        if isinstance(db_health, dict):
            dependencies["database"] = db_health

        if isinstance(cache_health, dict):
            dependencies["cache"] = cache_health

        if isinstance(llm_health, dict):
            dependencies["llm_provider"] = llm_health

        if isinstance(vector_db_health, dict):
            dependencies["vector_database"] = vector_db_health

        # Calculate overall status
        all_healthy = all(
            dep.get("status") in ["healthy", "not_configured"]
            for dep in dependencies.values()
        )

        return {
            "status": "ok" if all_healthy else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "mgx-agent-api",
            "version": "0.1.0",
            "dependencies": dependencies,
        }
    except Exception as e:
        logger.error(f"Status check failed: {str(e)}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "mgx-agent-api",
            "version": "0.1.0",
            "error": str(e),
        }


__all__ = ['router']
