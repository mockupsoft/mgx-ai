# -*- coding: utf-8 -*-
"""Deployment validator API endpoints."""

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.db.models import (
    ArtifactBuild,
    DeploymentValidation,
    ValidationCheckResult,
    PreDeploymentChecklist,
    DeploymentSimulation,
    RollbackPlan,
)
from backend.services.validators import DeploymentValidator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/validators", tags=["validators"])


# Request/Response Models
class ValidateArtifactsRequest(BaseModel):
    """Request to validate artifacts."""
    
    build_id: str = Field(..., description="Build ID to validate")
    target_environment: str = Field(default="staging", description="Target environment")
    artifacts: Dict[str, Any] = Field(default_factory=dict, description="Artifact data")


class ValidationCheckResponse(BaseModel):
    """Response for a single validation check."""
    
    name: str
    status: str
    description: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    remediation: Optional[str] = None


class PhaseResultResponse(BaseModel):
    """Response for a validation phase."""
    
    phase: str
    status: str
    passed_checks: int
    failed_checks: int
    warning_checks: int
    total_checks: int
    checks: List[ValidationCheckResponse] = Field(default_factory=list)


class ValidationResponse(BaseModel):
    """Response for validation results."""
    
    validation_id: str
    build_id: str
    status: str
    environment: str
    is_deployable: bool
    started_at: str
    completed_at: Optional[str] = None
    summary: Dict[str, int]
    phases: Dict[str, Any] = Field(default_factory=dict)


class PreDeploymentChecklistResponse(BaseModel):
    """Response for pre-deployment checklist."""
    
    validation_id: str
    all_passed: bool
    status_summary: Dict[str, int]
    items: List[Dict[str, Any]] = Field(default_factory=list)


class HealthStatusResponse(BaseModel):
    """Response for deployment health status."""
    
    deployment_id: str
    status: str
    endpoints_healthy: int
    dependencies_reachable: int
    last_checked_at: Optional[str] = None


# Endpoints

@router.post("/validate-artifacts", response_model=ValidationResponse)
async def validate_artifacts(
    request: ValidateArtifactsRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate artifacts for deployment.
    
    Performs comprehensive validation including:
    - Docker image validation
    - Kubernetes manifest validation
    - Health check validation
    - Security validation
    - Configuration validation
    """
    try:
        # Get build
        build = await db.get(ArtifactBuild, request.build_id)
        if not build:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Build {request.build_id} not found"
            )
        
        validation_id = str(uuid4())
        
        # Run validation
        validator = DeploymentValidator(build.project_id)
        result = await validator.validate_artifacts(
            validation_id=validation_id,
            build_id=request.build_id,
            artifacts=request.artifacts or build.results or {},
            environment=request.target_environment,
        )
        
        # Save to database
        db_validation = DeploymentValidation(
            id=validation_id,
            build_id=request.build_id,
            workspace_id=build.project_id,
            status=result["status"],
            environment=request.target_environment,
            passed_checks=result["summary"]["passed_checks"],
            failed_checks=result["summary"]["failed_checks"],
            warning_checks=result["summary"]["warning_checks"],
            total_checks=result["summary"]["total_checks"],
            validation_results=result,
        )
        db.add(db_validation)
        await db.flush()
        
        logger.info(f"Validation {validation_id} completed with status {result['status']}")
        
        return ValidationResponse(
            validation_id=validation_id,
            build_id=request.build_id,
            status=result["status"],
            environment=request.target_environment,
            is_deployable=result["is_deployable"],
            started_at=result["started_at"],
            completed_at=result.get("completed_at"),
            summary=result["summary"],
            phases=result["phases"],
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}"
        )


@router.get("/validations/{validation_id}", response_model=ValidationResponse)
async def get_validation(
    validation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get validation results."""
    try:
        validation = await db.get(DeploymentValidation, validation_id)
        if not validation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Validation {validation_id} not found"
            )
        
        results = validation.validation_results or {}
        
        return ValidationResponse(
            validation_id=validation.id,
            build_id=validation.build_id,
            status=validation.status.value,
            environment=validation.environment.value,
            is_deployable=validation.failed_checks == 0,
            started_at=validation.started_at.isoformat() if validation.started_at else "",
            completed_at=validation.completed_at.isoformat() if validation.completed_at else None,
            summary={
                "total_checks": validation.total_checks,
                "passed_checks": validation.passed_checks,
                "failed_checks": validation.failed_checks,
                "warning_checks": validation.warning_checks,
            },
            phases=results.get("phases", {}),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get validation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get validation: {str(e)}"
        )


@router.post("/pre-deployment-checklist", response_model=PreDeploymentChecklistResponse)
async def create_pre_deployment_checklist(
    request: ValidateArtifactsRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create and run pre-deployment checklist.
    
    Runs a comprehensive checklist including:
    - Docker image validation
    - Kubernetes manifests validation
    - Health checks
    - Security validation
    - Configuration validation
    - Backup plan review
    - Rollback procedure review
    - Monitoring configuration
    - Load testing
    - Security review approval
    - Stakeholder approval
    """
    try:
        # First run validation
        validation_request = ValidateArtifactsRequest(
            build_id=request.build_id,
            target_environment=request.target_environment,
            artifacts=request.artifacts,
        )
        
        validation_response = await validate_artifacts(validation_request, db)
        
        # Get validation from DB
        validation = await db.get(DeploymentValidation, validation_response.validation_id)
        
        # Run checklist
        validator = DeploymentValidator(validation.workspace_id)
        checklist_result = await validator.run_pre_deployment_checklist(
            validation.id,
            validation.validation_results,
        )
        
        # Save checklist to DB
        checklist = PreDeploymentChecklist(
            id=str(uuid4()),
            validation_id=validation.id,
            workspace_id=validation.workspace_id,
            all_passed=checklist_result["all_passed"],
            checklist_data=checklist_result["checklist"],
        )
        db.add(checklist)
        await db.flush()
        
        logger.info(f"Checklist for validation {validation.id} completed")
        
        return PreDeploymentChecklistResponse(
            validation_id=validation.id,
            all_passed=checklist_result["all_passed"],
            status_summary=checklist_result["status_summary"],
            items=checklist_result["checklist"]["items"],
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Checklist creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Checklist creation failed: {str(e)}"
        )


@router.get("/health-status/{deployment_id}", response_model=HealthStatusResponse)
async def get_health_status(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get real-time health status of a deployment."""
    try:
        # In a real implementation, this would query the actual deployed service
        # For now, return mock data
        
        return HealthStatusResponse(
            deployment_id=deployment_id,
            status="healthy",
            endpoints_healthy=3,
            dependencies_reachable=4,
            last_checked_at="2024-01-01T00:00:00Z",
        )
        
    except Exception as e:
        logger.error(f"Failed to get health status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get health status: {str(e)}"
        )


@router.get("/validations", response_model=List[ValidationResponse])
async def list_validations(
    build_id: Optional[str] = Query(None, description="Filter by build ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    environment: Optional[str] = Query(None, description="Filter by environment"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List validations with filtering."""
    try:
        from sqlalchemy import select
        
        query = select(DeploymentValidation)
        
        if build_id:
            query = query.where(DeploymentValidation.build_id == build_id)
        if status:
            query = query.where(DeploymentValidation.status == status)
        if environment:
            query = query.where(DeploymentValidation.environment == environment)
        
        query = query.offset(offset).limit(limit)
        
        result = await db.execute(query)
        validations = result.scalars().all()
        
        return [
            ValidationResponse(
                validation_id=v.id,
                build_id=v.build_id,
                status=v.status.value,
                environment=v.environment.value,
                is_deployable=v.failed_checks == 0,
                started_at=v.started_at.isoformat() if v.started_at else "",
                completed_at=v.completed_at.isoformat() if v.completed_at else None,
                summary={
                    "total_checks": v.total_checks,
                    "passed_checks": v.passed_checks,
                    "failed_checks": v.failed_checks,
                    "warning_checks": v.warning_checks,
                },
            )
            for v in validations
        ]
        
    except Exception as e:
        logger.error(f"Failed to list validations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list validations: {str(e)}"
        )
