# -*- coding: utf-8 -*-
"""backend.routers.quality_gates

REST API endpoints for quality gate evaluation and management.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import Dict, List, Optional, Any
import logging
import asyncio
from datetime import datetime

from ..services.quality_gates import get_gate_manager, QualityGateManager
from ..services.quality_gates.gates.base_gate import GateResult
from ..schemas import (
    BaseModel,
    Field
)
from ..db.models.enums import QualityGateType

logger = logging.getLogger(__name__)


class QualityGateEvaluationRequest(BaseModel):
    """Request model for quality gate evaluation."""
    
    execution_id: Optional[str] = Field(None, description="Related execution ID")
    gates: List[str] = Field(..., description="List of gate types to evaluate")
    task_id: Optional[str] = Field(None, description="Task ID context")
    task_run_id: Optional[str] = Field(None, description="Task run ID context")
    sandbox_execution_id: Optional[str] = Field(None, description="Sandbox execution ID context")
    working_directory: Optional[str] = Field(None, description="Working directory for gate execution")
    application_url: Optional[str] = Field(None, description="Application URL for testing gates")
    openapi_spec: Optional[str] = Field(None, description="OpenAPI specification path or content")
    
    class Config:
        schema_extra = {
            "example": {
                "gates": ["lint", "coverage", "security"],
                "working_directory": "/app/src",
                "application_url": "http://localhost:8080",
                "task_run_id": "task_run_123"
            }
        }


class QualityGateResult(BaseModel):
    """Individual gate result."""
    
    gate_type: str = Field(..., description="Type of quality gate")
    status: str = Field(..., description="Gate evaluation status")
    passed: bool = Field(..., description="Whether the gate passed")
    passed_with_warnings: bool = Field(False, description="Whether gate passed with warnings")
    execution_time_ms: Optional[int] = Field(None, description="Execution time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    # Detailed results
    details: Dict[str, Any] = Field(default_factory=dict, description="Detailed gate results")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Gate metrics")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")
    
    # Issue counts
    total_issues: int = Field(0, description="Total number of issues found")
    critical_issues: int = Field(0, description="Number of critical issues")
    high_issues: int = Field(0, description="Number of high severity issues")
    medium_issues: int = Field(0, description="Number of medium severity issues")
    low_issues: int = Field(0, description="Number of low severity issues")


class QualityGateEvaluationResponse(BaseModel):
    """Response model for quality gate evaluation."""
    
    success: bool = Field(..., description="Whether evaluation completed successfully")
    passed: bool = Field(..., description="Overall evaluation result")
    passed_with_warnings: bool = Field(False, description="Overall result with warnings")
    status: str = Field(..., description="Overall status")
    results: Dict[str, QualityGateResult] = Field(default_factory=dict, description="Individual gate results")
    
    # Summary
    summary: Dict[str, Any] = Field(default_factory=dict, description="Evaluation summary")
    execution_time_ms: int = Field(..., description="Total execution time in milliseconds")
    gates_evaluated: int = Field(..., description="Number of gates evaluated")
    blocking_failures: List[str] = Field(default_factory=list, description="Blocking gate failures")
    recommendations: List[str] = Field(default_factory=list, description="All recommendations")
    
    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Evaluation timestamp")


class QualityGateHistoryRequest(BaseModel):
    """Request model for gate history."""
    
    workspace_id: str = Field(..., description="Workspace ID")
    project_id: str = Field(..., description="Project ID")
    gate_type: Optional[str] = Field(None, description="Filter by gate type")
    limit: int = Field(50, ge=1, le=100, description="Number of records to return")
    offset: int = Field(0, ge=0, description="Number of records to skip")


class QualityGateHistoryItem(BaseModel):
    """Individual history item."""
    
    id: str = Field(..., description="Gate execution ID")
    gate_type: str = Field(..., description="Gate type")
    status: str = Field(..., description="Execution status")
    passed: bool = Field(..., description="Whether gate passed")
    passed_with_warnings: bool = Field(False, description="Whether passed with warnings")
    execution_time_ms: Optional[int] = Field(None, description="Execution time")
    issues_found: int = Field(0, description="Number of issues found")
    critical_issues: int = Field(0, description="Critical issues")
    high_issues: int = Field(0, description="High severity issues")
    medium_issues: int = Field(0, description="Medium severity issues")
    low_issues: int = Field(0, description="Low severity issues")
    created_at: str = Field(..., description="Creation timestamp")
    task_run_id: Optional[str] = Field(None, description="Related task run ID")
    error_message: Optional[str] = Field(None, description="Error message")


class QualityGateHistoryResponse(BaseModel):
    """Response model for gate history."""
    
    success: bool = Field(..., description="Whether request was successful")
    total_count: int = Field(..., description="Total number of records")
    history: List[QualityGateHistoryItem] = Field(default_factory=list, description="History items")
    limit: int = Field(..., description="Limit used")
    offset: int = Field(..., description="Offset used")


class QualityGateStatisticsRequest(BaseModel):
    """Request model for gate statistics."""
    
    workspace_id: str = Field(..., description="Workspace ID")
    project_id: str = Field(..., description="Project ID")
    days: int = Field(30, ge=1, le=365, description="Number of days to analyze")


class QualityGateStatisticsResponse(BaseModel):
    """Response model for gate statistics."""
    
    success: bool = Field(..., description="Whether request was successful")
    statistics: Dict[str, Any] = Field(default_factory=dict, description="Gate statistics")


# Create router
router = APIRouter(prefix="/api/quality-gates", tags=["quality-gates"])


@router.post("/evaluate", response_model=QualityGateEvaluationResponse)
async def evaluate_quality_gates(
    request: QualityGateEvaluationRequest,
    background_tasks: BackgroundTasks,
    gate_manager: QualityGateManager = Depends(get_gate_manager)
):
    """Evaluate quality gates for code quality assessment.
    
    This endpoint runs configured quality gates against code and provides
    comprehensive quality metrics and recommendations.
    
    Args:
        request: Evaluation request with gate types and context
        
    Returns:
        QualityGateEvaluationResponse: Complete evaluation results
    """
    
    try:
        logger.info(f"Starting quality gate evaluation: {request.gates}")
        
        # Execute gate evaluation
        result = await gate_manager.evaluate_gates(
            workspace_id="default",  # This should come from auth context
            project_id="default",    # This should come from auth context
            gate_types=request.gates,
            task_id=request.task_id,
            task_run_id=request.task_run_id,
            sandbox_execution_id=request.sandbox_execution_id,
            working_directory=request.working_directory,
            application_url=request.application_url,
            openapi_spec=request.openapi_spec
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Quality gate evaluation failed")
            )
        
        # Convert results to response model
        gate_results = {}
        for gate_type, gate_result in result["results"].items():
            gate_results[gate_type] = QualityGateResult(
                gate_type=gate_type,
                status=gate_result.status.value,
                passed=gate_result.passed,
                passed_with_warnings=gate_result.passed_with_warnings,
                execution_time_ms=gate_result.execution_time_ms,
                error_message=gate_result.error_message,
                details=gate_result.details or {},
                metrics=gate_result.metrics or {},
                recommendations=gate_result.recommendations or [],
                total_issues=gate_result.total_issues,
                critical_issues=gate_result.critical_issues,
                high_issues=gate_result.high_issues,
                medium_issues=gate_result.medium_issues,
                low_issues=gate_result.low_issues
            )
        
        response = QualityGateEvaluationResponse(
            success=True,
            passed=result["passed"],
            passed_with_warnings=result.get("passed_with_warnings", False),
            status=result["status"].value,
            results=gate_results,
            summary=result["summary"],
            execution_time_ms=result["execution_time_ms"],
            gates_evaluated=result["gates_evaluated"],
            blocking_failures=result.get("blocking_failures", []),
            recommendations=result.get("recommendations", [])
        )
        
        # Log results
        if result["passed"]:
            logger.info(f"Quality gate evaluation passed: {result['gates_evaluated']} gates")
        else:
            logger.warning(f"Quality gate evaluation failed: {result.get('blocking_failures', [])}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quality gate evaluation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/history/{execution_id}", response_model=QualityGateHistoryResponse)
async def get_gate_history(
    execution_id: str,
    gate_type: Optional[QualityGateType] = Query(None, description="Filter by gate type"),
    limit: int = Query(50, ge=1, le=100, description="Number of records"),
    offset: int = Query(0, ge=0, description="Records to skip"),
    gate_manager: QualityGateManager = Depends(get_gate_manager)
):
    """Get quality gate execution history.
    
    Args:
        execution_id: Task run or sandbox execution ID
        gate_type: Optional filter by gate type
        limit: Maximum number of records to return
        offset: Number of records to skip
        
    Returns:
        QualityGateHistoryResponse: Gate execution history
    """
    
    try:
        # For now, we'll return a simplified response
        # In a full implementation, this would query the database
        
        return QualityGateHistoryResponse(
            success=True,
            total_count=0,
            history=[],
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Failed to get gate history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve gate history: {str(e)}"
        )


@router.post("/statistics", response_model=QualityGateStatisticsResponse)
async def get_gate_statistics(
    request: QualityGateStatisticsRequest,
    gate_manager: QualityGateManager = Depends(get_gate_manager)
):
    """Get quality gate statistics and trending.
    
    Args:
        request: Statistics request with workspace/project context
        
    Returns:
        QualityGateStatisticsResponse: Gate statistics and trends
    """
    
    try:
        result = await gate_manager.get_gate_statistics(
            workspace_id=request.workspace_id,
            project_id=request.project_id,
            days=request.days
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Failed to get gate statistics")
            )
        
        return QualityGateStatisticsResponse(
            success=True,
            statistics=result["statistics"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get gate statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve gate statistics: {str(e)}"
        )


@router.get("/gates")
async def list_available_gates():
    """List all available quality gates and their configurations.
    
    Returns:
        dict: Available gate types and basic information
    """
    
    try:
        # This should return the actual registered gates
        # For now, return static information
        
        available_gates = {
            "lint": {
                "name": "Code Linting",
                "description": "ESLint, Ruff, and Pint code linting",
                "supported_languages": ["javascript", "python", "php"],
                "blocking": True,
                "default_enabled": True
            },
            "coverage": {
                "name": "Test Coverage",
                "description": "Test coverage enforcement",
                "supported_languages": ["javascript", "python", "php"],
                "blocking": True,
                "default_enabled": True
            },
            "security": {
                "name": "Security Audit",
                "description": "Vulnerability scanning and security checks",
                "supported_languages": ["javascript", "python", "php", "java", "go"],
                "blocking": True,
                "default_enabled": True
            },
            "performance": {
                "name": "Performance Tests",
                "description": "Response time and throughput testing",
                "supported_languages": ["javascript", "python", "php"],
                "blocking": True,
                "default_enabled": True
            },
            "contract": {
                "name": "API Contract",
                "description": "API endpoint contract testing",
                "supported_languages": ["any"],
                "blocking": True,
                "default_enabled": True
            },
            "complexity": {
                "name": "Code Complexity",
                "description": "Cyclomatic complexity analysis",
                "supported_languages": ["javascript", "python", "php"],
                "blocking": True,
                "default_enabled": True
            },
            "type_check": {
                "name": "Type Checking",
                "description": "TypeScript and MyPy type checking",
                "supported_languages": ["typescript", "python"],
                "blocking": True,
                "default_enabled": True
            }
        }
        
        return {
            "success": True,
            "available_gates": available_gates,
            "total_gates": len(available_gates)
        }
        
    except Exception as e:
        logger.error(f"Failed to list available gates: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list available gates: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check for quality gates service.
    
    Returns:
        dict: Service health status
    """
    
    try:
        # Basic health check
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "quality-gates",
            "version": "1.0.0"
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Service unavailable"
        )