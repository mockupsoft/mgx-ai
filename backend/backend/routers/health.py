# -*- coding: utf-8 -*-
"""
Health Check Router

Provides endpoints for monitoring application health and status.
"""

import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


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
    
    Returns:
        200 OK if ready, 503 Service Unavailable otherwise
    """
    try:
        # Add readiness checks here (DB, cache, etc.)
        return {
            "ready": True,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Service not ready",
        )


@router.get("/live", response_model=Dict[str, Any])
async def liveness_check() -> Dict[str, Any]:
    """
    Liveness check endpoint.
    
    Indicates whether the service is running and responsive.
    
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
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "mgx-agent-api",
        "version": "0.1.0",
    }


__all__ = ['router']
