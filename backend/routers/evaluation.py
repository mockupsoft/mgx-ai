# -*- coding: utf-8 -*-
"""backend.routers.evaluation

Router for AI evaluation framework API endpoints.
Provides endpoints for LLM-as-a-Judge evaluation, regression testing, and determinism testing.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from ..services.evaluation import EvaluationService, ScenarioLibrary
from ..services.evaluation.judge import LLMJudgeService
from ..db.models.entities_evaluation import (
    EvaluationScenario,
    EvaluationResult,
    RegressionTest,
    PassKMetric,
    EvaluationAlert
)
from ..db.models.enums import ComplexityLevel, EvaluationType
from ..schemas import (
    # Request schemas
    EvaluationScenarioCreate,
    EvaluationRunRequest,
    RegressionTestRequest,
    DeterminismTestRequest,
    EvaluationDashboardRequest,
    # Response schemas
    EvaluationScenarioResponse,
    EvaluationRunResponse,
    EvaluationResultResponse,
    RegressionTestResponse,
    DeterminismTestResponse,
    PassKMetricResponse,
    EvaluationDashboardResponse,
    EvaluationAlertResponse,
)
from ..db.database import get_db

router = APIRouter(prefix="/evaluation", tags=["evaluation"])
logger = logging.getLogger(__name__)

# Dependency to get evaluation service
async def get_evaluation_service() -> EvaluationService:
    """Get evaluation service instance."""
    return EvaluationService()

# Dependency to get scenario library
async def get_scenario_library() -> ScenarioLibrary:
    """Get scenario library instance."""
    return ScenarioLibrary()


@router.post("/scenarios", response_model=EvaluationScenarioResponse)
async def create_scenario(
    scenario_data: EvaluationScenarioCreate,
    db=Depends(get_db),
    eval_service: EvaluationService = Depends(get_evaluation_service)
):
    """Create a new evaluation scenario."""
    try:
        # Convert schema to model
        scenario = EvaluationScenario(
            name=scenario_data.name,
            description=scenario_data.description,
            category=scenario_data.category,
            complexity_level=ComplexityLevel(scenario_data.complexity_level),
            language=scenario_data.language,
            framework=scenario_data.framework,
            prompt=scenario_data.prompt,
            expected_output=scenario_data.expected_output,
            evaluation_criteria=scenario_data.evaluation_criteria,
            estimated_duration_minutes=scenario_data.estimated_duration_minutes,
            tags=scenario_data.tags
        )
        
        db.add(scenario)
        db.commit()
        db.refresh(scenario)
        
        logger.info(f"Created evaluation scenario: {scenario.id}")
        return scenario
        
    except Exception as e:
        logger.error(f"Failed to create scenario: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create scenario: {str(e)}")


@router.get("/scenarios", response_model=List[EvaluationScenarioResponse])
async def list_scenarios(
    category: Optional[str] = Query(None, description="Filter by category"),
    complexity: Optional[str] = Query(None, description="Filter by complexity level"),
    active_only: bool = Query(True, description="Only return active scenarios"),
    limit: int = Query(50, le=100, description="Maximum number of scenarios to return"),
    db=Depends(get_db)
):
    """List evaluation scenarios."""
    try:
        query = db.query(EvaluationScenario)
        
        if category:
            query = query.filter(EvaluationScenario.category == category)
        
        if complexity:
            query = query.filter(EvaluationScenario.complexity_level == ComplexityLevel(complexity))
        
        if active_only:
            query = query.filter(EvaluationScenario.is_active == True)
        
        scenarios = query.order_by(
            EvaluationScenario.complexity_level,
            EvaluationScenario.category,
            EvaluationScenario.name
        ).limit(limit).all()
        
        return scenarios
        
    except Exception as e:
        logger.error(f"Failed to list scenarios: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list scenarios: {str(e)}")


@router.get("/scenarios/{scenario_id}", response_model=EvaluationScenarioResponse)
async def get_scenario(
    scenario_id: str,
    db=Depends(get_db)
):
    """Get a specific evaluation scenario."""
    try:
        scenario = db.query(EvaluationScenario).filter(
            EvaluationScenario.id == scenario_id,
            EvaluationScenario.is_active == True
        ).first()
        
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        return scenario
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scenario {scenario_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get scenario: {str(e)}")


@router.post("/run", response_model=EvaluationRunResponse)
async def run_evaluation(
    request: EvaluationRunRequest,
    background_tasks: BackgroundTasks,
    eval_service: EvaluationService = Depends(get_evaluation_service)
):
    """Run a single evaluation using LLM-as-a-Judge."""
    try:
        # Run evaluation
        result = await eval_service.run_evaluation(
            scenario_id=request.scenario_id,
            agent_output=request.agent_output,
            judge_config=request.judge_config,
            context=request.context,
            commit_hash=request.commit_hash,
            branch_name=request.branch_name
        )
        
        # Convert to response format
        response = EvaluationRunResponse(
            evaluation_id=result.id,
            scenario_id=result.scenario_id,
            status=result.status.value,
            overall_score=result.overall_score or 0.0,
            score_breakdown={
                "code_safety": result.code_safety_score or 0.0,
                "code_quality": result.code_quality_score or 0.0,
                "best_practices": result.best_practices_score or 0.0,
                "performance": result.performance_score or 0.0,
                "readability": result.readability_score or 0.0,
                "functionality": result.functionality_score or 0.0,
                "security": result.security_score or 0.0,
                "maintainability": result.maintainability_score or 0.0,
                "overall_score": result.overall_score or 0.0
            },
            feedback={
                "overall_feedback": result.judge_feedback or "",
                "improvement_suggestions": result.improvement_suggestions or [],
                "code_violations": result.code_violations or [],
                "best_practices_mentioned": result.best_practices_mentioned or []
            },
            execution_time_ms=result.execution_time_ms or 0,
            judge_model=result.judge_model,
            judge_provider=result.judge_provider.value,
            created_at=result.started_at,
            completed_at=result.completed_at
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to run evaluation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to run evaluation: {str(e)}")


@router.post("/regression", response_model=RegressionTestResponse)
async def run_regression_test(
    request: RegressionTestRequest,
    eval_service: EvaluationService = Depends(get_evaluation_service)
):
    """Run regression test comparing current vs baseline performance."""
    try:
        regression_test = await eval_service.run_regression_test(
            scenario_id=request.scenario_id,
            current_agent_output=request.current_agent_output,
            judge_config=request.judge_config,
            commit_hash=request.commit_hash,
            branch_name=request.branch_name,
            threshold_degradation=request.threshold_degradation
        )
        
        return regression_test
        
    except Exception as e:
        logger.error(f"Failed to run regression test: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to run regression test: {str(e)}")


@router.post("/determinism", response_model=DeterminismTestResponse)
async def run_determinism_test(
    request: DeterminismTestRequest,
    eval_service: EvaluationService = Depends(get_evaluation_service)
):
    """Run determinism test (Pass@k) for reliability measurement."""
    try:
        # Create agent output provider function
        # In a real implementation, this would be more sophisticated
        async def agent_output_provider():
            # This is a placeholder - in reality, this would call the actual agent
            # with different random seeds or parameters to generate varied outputs
            return f"Generated output for determinism testing - run {datetime.now().microsecond}"
        
        pass_k_metrics = await eval_service.run_determinism_test(
            scenario_id=request.scenario_id,
            agent_output_provider=agent_output_provider,
            judge_config=request.judge_config,
            k_values=request.k_values,
            success_threshold=request.success_threshold
        )
        
        # Convert to response format
        metric_responses = [
            PassKMetricResponse(
                id=metric.id,
                scenario_id=metric.scenario_id,
                k_value=metric.k_value,
                total_runs=metric.total_runs,
                successful_runs=metric.successful_runs,
                pass_at_k=metric.pass_at_k,
                confidence_interval_lower=metric.confidence_interval_lower,
                confidence_interval_upper=metric.confidence_interval_upper,
                success_threshold=metric.success_threshold,
                score_variance=metric.score_variance,
                score_std_deviation=metric.score_std_deviation,
                score_range_min=metric.score_range_min,
                score_range_max=metric.score_range_max,
                consistency_score=metric.consistency_score,
                reliability_grade=metric.reliability_grade,
                created_at=metric.run_timestamp
            )
            for metric in pass_k_metrics
        ]
        
        # Determine overall reliability grade
        reliability_grades = [metric.reliability_grade for metric in pass_k_metrics if metric.reliability_grade]
        overall_grade = "F"  # Default
        if reliability_grades:
            grade_values = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
            avg_grade_value = sum(grade_values.get(g, 0) for g in reliability_grades) / len(reliability_grades)
            for grade, value in grade_values.items():
                if avg_grade_value >= value:
                    overall_grade = grade
                    break
        
        # Calculate consistency score
        consistency_scores = [metric.consistency_score for metric in pass_k_metrics if metric.consistency_score]
        avg_consistency = sum(consistency_scores) / len(consistency_scores) if consistency_scores else 0.0
        
        response = DeterminismTestResponse(
            test_id=f"det_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            scenario_id=request.scenario_id,
            pass_k_metrics=metric_responses,
            reliability_grade=overall_grade,
            consistency_score=avg_consistency,
            created_at=datetime.utcnow()
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to run determinism test: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to run determinism test: {str(e)}")


@router.get("/dashboard", response_model=EvaluationDashboardResponse)
async def get_dashboard(
    scenario_ids: Optional[str] = Query(None, description="Comma-separated list of scenario IDs"),
    time_range_days: int = Query(30, ge=1, le=365, description="Time range in days"),
    metrics: Optional[str] = Query(None, description="Comma-separated list of metrics"),
    eval_service: EvaluationService = Depends(get_evaluation_service)
):
    """Get evaluation dashboard data with trends and metrics."""
    try:
        # Parse scenario IDs
        scenario_id_list = None
        if scenario_ids:
            scenario_id_list = [sid.strip() for sid in scenario_ids.split(",")]
        
        # Parse metrics
        metrics_list = None
        if metrics:
            metrics_list = [m.strip() for m in metrics.split(",")]
        
        dashboard_data = await eval_service.get_evaluation_dashboard(
            scenario_ids=scenario_id_list,
            time_range_days=time_range_days,
            metrics=metrics_list
        )
        
        # Add generation timestamp
        dashboard_data["generated_at"] = datetime.utcnow()
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Failed to get dashboard data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {str(e)}")


@router.get("/results", response_model=List[EvaluationResultResponse])
async def list_evaluation_results(
    scenario_id: Optional[str] = Query(None, description="Filter by scenario ID"),
    status: Optional[str] = Query(None, description="Filter by evaluation status"),
    limit: int = Query(50, le=100, description="Maximum number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db=Depends(get_db)
):
    """List evaluation results."""
    try:
        query = db.query(EvaluationResult)
        
        if scenario_id:
            query = query.filter(EvaluationResult.scenario_id == scenario_id)
        
        if status:
            query = query.filter(EvaluationResult.status == status)
        
        results = query.order_by(
            EvaluationResult.completed_at.desc()
        ).offset(offset).limit(limit).all()
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to list evaluation results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list evaluation results: {str(e)}")


@router.get("/alerts", response_model=List[EvaluationAlertResponse])
async def list_alerts(
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    status: Optional[str] = Query("active", description="Filter by status"),
    limit: int = Query(50, le=100, description="Maximum number of alerts to return"),
    db=Depends(get_db)
):
    """List evaluation alerts."""
    try:
        query = db.query(EvaluationAlert)
        
        if alert_type:
            query = query.filter(EvaluationAlert.alert_type == alert_type)
        
        if severity:
            query = query.filter(EvaluationAlert.severity == severity)
        
        if status:
            query = query.filter(EvaluationAlert.status == status)
        
        alerts = query.order_by(
            EvaluationAlert.created_at.desc()
        ).limit(limit).all()
        
        return alerts
        
    except Exception as e:
        logger.error(f"Failed to list alerts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list alerts: {str(e)}")


@router.put("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str = Query(..., description="User who acknowledged the alert"),
    db=Depends(get_db)
):
    """Acknowledge an evaluation alert."""
    try:
        alert = db.query(EvaluationAlert).filter(
            EvaluationAlert.id == alert_id
        ).first()
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        alert.status = "acknowledged"
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.utcnow()
        
        db.commit()
        
        return {"message": "Alert acknowledged successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acknowledge alert {alert_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to acknowledge alert: {str(e)}")


@router.put("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    resolution_notes: str = Query(..., description="Notes about the resolution"),
    db=Depends(get_db)
):
    """Resolve an evaluation alert."""
    try:
        alert = db.query(EvaluationAlert).filter(
            EvaluationAlert.id == alert_id
        ).first()
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        alert.status = "resolved"
        alert.resolved_at = datetime.utcnow()
        alert.resolution_notes = resolution_notes
        
        db.commit()
        
        return {"message": "Alert resolved successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve alert {alert_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to resolve alert: {str(e)}")


@router.get("/baseline-scenarios")
async def get_baseline_scenarios(
    library: ScenarioLibrary = Depends(get_scenario_library)
):
    """Get baseline scenarios for testing."""
    try:
        baseline_scenarios = library.get_baseline_scenarios()
        return {
            "scenarios": baseline_scenarios,
            "total": len(baseline_scenarios),
            "categories": list(set(s["category"] for s in baseline_scenarios)),
            "complexity_distribution": {
                level.value: len([s for s in baseline_scenarios if s["complexity_level"] == level])
                for level in ComplexityLevel
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get baseline scenarios: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get baseline scenarios: {str(e)}")


@router.get("/regression-scenarios")
async def get_regression_scenarios(
    library: ScenarioLibrary = Depends(get_scenario_library)
):
    """Get scenarios specifically designed for regression testing."""
    try:
        regression_scenarios = library.get_regression_scenarios()
        return {
            "scenarios": regression_scenarios,
            "total": len(regression_scenarios),
            "purpose": "These scenarios are optimized for regression testing and monitoring performance changes"
        }
        
    except Exception as e:
        logger.error(f"Failed to get regression scenarios: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get regression scenarios: {str(e)}")


@router.get("/health")
async def evaluation_health():
    """Health check endpoint for evaluation service."""
    try:
        return {
            "status": "healthy",
            "service": "AI Evaluation Framework",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "AI Evaluation Framework",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )