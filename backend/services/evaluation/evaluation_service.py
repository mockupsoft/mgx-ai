# -*- coding: utf-8 -*-
"""backend.services.evaluation.evaluation_service

Core evaluation service orchestrating LLM-as-a-Judge, regression testing, and determinism testing.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from .judge import LLMJudgeService
from .scenarios import ScenarioLibrary
from ..db.models.entities_evaluation import (
    EvaluationScenario,
    EvaluationResult,
    RegressionTest,
    PassKMetric,
    RegressionMetric,
    EvaluationDashboard,
    EvaluationAlert
)
from ..db.models.enums import (
    EvaluationType,
    EvaluationStatus,
    ComplexityLevel,
    RegressionAlertType
)
from ...db.database import get_db


class EvaluationService:
    """Core service for AI evaluation framework."""
    
    def __init__(self, judge_service: LLMJudgeService = None):
        self.judge_service = judge_service or LLMJudgeService()
        self.scenario_library = ScenarioLibrary()
        self.logger = logging.getLogger(__name__)
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def run_evaluation(
        self,
        scenario_id: str,
        agent_output: str,
        judge_config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        commit_hash: Optional[str] = None,
        branch_name: Optional[str] = None
    ) -> EvaluationResult:
        """
        Run a single evaluation using LLM-as-a-Judge.
        
        Args:
            scenario_id: ID of the evaluation scenario
            agent_output: Code/content produced by the agent
            judge_config: Configuration for the judge LLM
            context: Additional context for evaluation
            commit_hash: Git commit hash for tracking
            branch_name: Git branch name for tracking
            
        Returns:
            EvaluationResult with detailed scoring
        """
        
        try:
            # Get scenario from database
            scenario = await self._get_scenario(scenario_id)
            if not scenario:
                raise ValueError(f"Scenario {scenario_id} not found")
            
            # Run LLM-as-a-Judge evaluation
            result = await self.judge_service.evaluate_code(
                agent_output=agent_output,
                scenario=scenario,
                judge_config=judge_config,
                context=context
            )
            
            # Add Git context
            result.commit_hash = commit_hash
            result.branch_name = branch_name
            
            # Save to database
            await self._save_evaluation_result(result)
            
            # Update regression metrics if this is a regression test
            if commit_hash and branch_name:
                await self._update_regression_metrics(result)
            
            # Check for alerts
            await self._check_alerts(result)
            
            self.logger.info(f"Evaluation completed: {scenario_id} -> {result.overall_score:.2f}")
            return result
            
        except Exception as e:
            self.logger.error(f"Evaluation failed: {str(e)}", exc_info=True)
            raise
    
    async def run_regression_test(
        self,
        scenario_id: str,
        current_agent_output: str,
        judge_config: Dict[str, Any],
        commit_hash: str,
        branch_name: str,
        threshold_degradation: float = 5.0
    ) -> RegressionTest:
        """
        Run regression test comparing current vs baseline performance.
        
        Args:
            scenario_id: Scenario to test
            current_agent_output: Current agent output
            judge_config: Judge configuration
            commit_hash: Current commit hash
            branch_name: Current branch name
            threshold_degradation: Threshold for triggering regression alert
            
        Returns:
            RegressionTest result
        """
        
        try:
            # Get scenario
            scenario = await self._get_scenario(scenario_id)
            if not scenario:
                raise ValueError(f"Scenario {scenario_id} not found")
            
            # Get baseline evaluation for this scenario
            baseline_result = await self._get_baseline_evaluation(scenario_id)
            if not baseline_result:
                self.logger.warning(f"No baseline found for scenario {scenario_id}")
                # Create baseline from current evaluation
                baseline_result = await self.judge_service.evaluate_code(
                    agent_output=current_agent_output,
                    scenario=scenario,
                    judge_config=judge_config
                )
                await self._save_evaluation_result(baseline_result)
            
            # Evaluate current output
            current_result = await self.judge_service.evaluate_code(
                agent_output=current_agent_output,
                scenario=scenario,
                judge_config=judge_config
            )
            
            # Create regression test record
            regression_test = RegressionTest(
                scenario_id=scenario_id,
                baseline_evaluation_id=baseline_result.id if baseline_result else None,
                current_evaluation_id=current_result.id,
                commit_hash=commit_hash,
                branch_name=branch_name,
                trigger_type="commit",
                trigger_reason=f"Automated regression test for commit {commit_hash}",
                baseline_score=baseline_result.overall_score if baseline_result else None,
                current_score=current_result.overall_score,
                degradation_threshold_percentage=threshold_degradation
            )
            
            # Calculate score change
            if baseline_result and current_result.overall_score is not None:
                score_change = current_result.overall_score - baseline_result.overall_score
                score_change_pct = (score_change / baseline_result.overall_score) * 100
                
                regression_test.score_change = score_change
                regression_test.score_change_percentage = score_change_pct
                
                # Check if regression alert should be triggered
                if score_change_pct < -threshold_degradation:
                    regression_test.alert_triggered = True
                    regression_test.alert_type = RegressionAlertType.SCORE_DEGRADATION
                    regression_test.alert_message = (
                        f"Score degradation of {abs(score_change_pct):.1f}% "
                        f"(threshold: {threshold_degradation}%)"
                    )
            
            # Save regression test
            await self._save_regression_test(regression_test)
            
            # Create alert if triggered
            if regression_test.alert_triggered:
                await self._create_regression_alert(regression_test, current_result)
            
            self.logger.info(
                f"Regression test completed: {scenario_id} "
                f"(change: {regression_test.score_change_percentage:.1f}%)"
            )
            
            return regression_test
            
        except Exception as e:
            self.logger.error(f"Regression test failed: {str(e)}", exc_info=True)
            raise
    
    async def run_determinism_test(
        self,
        scenario_id: str,
        agent_output_provider,
        judge_config: Dict[str, Any],
        k_values: List[int] = None,
        success_threshold: float = 7.0
    ) -> List[PassKMetric]:
        """
        Run determinism test (Pass@k) for reliability measurement.
        
        Args:
            scenario_id: Scenario to test
            agent_output_provider: Function that provides agent outputs
            judge_config: Judge configuration
            k_values: List of k values to test (default: [1, 5, 10, 20])
            success_threshold: Minimum score to count as success
            
        Returns:
            List of PassKMetric results for different k values
        """
        
        if k_values is None:
            k_values = [1, 5, 10, 20]
        
        try:
            # Get scenario
            scenario = await self._get_scenario(scenario_id)
            if not scenario:
                raise ValueError(f"Scenario {scenario_id} not found")
            
            # Run multiple evaluations
            self.logger.info(f"Starting determinism test for {scenario_id} with k={max(k_values)}")
            
            evaluation_results = []
            scores = []
            
            for run_id in range(max(k_values)):
                try:
                    # Get agent output (could be different each time for testing determinism)
                    agent_output = await agent_output_provider()
                    
                    # Evaluate output
                    result = await self.judge_service.evaluate_code(
                        agent_output=agent_output,
                        scenario=scenario,
                        judge_config=judge_config
                    )
                    
                    evaluation_results.append(result)
                    scores.append(result.overall_score or 0.0)
                    
                    # Save evaluation result
                    await self._save_evaluation_result(result)
                    
                    self.logger.debug(f"Determinism run {run_id + 1}: score = {result.overall_score:.2f}")
                    
                except Exception as e:
                    self.logger.error(f"Determinism run {run_id + 1} failed: {e}")
                    scores.append(0.0)  # Treat failures as 0 score
            
            # Calculate Pass@k metrics for each k value
            pass_k_metrics = []
            
            for k in k_values:
                if k <= len(scores):
                    # Calculate pass@k
                    successful_runs = sum(1 for score in scores[:k] if score >= success_threshold)
                    pass_at_k = successful_runs / k if k > 0 else 0.0
                    
                    # Calculate confidence interval (simplified binomial CI)
                    n = k
                    p = pass_at_k
                    confidence_level = 0.95
                    
                    if n > 0 and p >= 0 and p <= 1:
                        # Wilson score interval (simplified)
                        z = 1.96  # For 95% confidence
                        center = (p + z*z/(2*n)) / (1 + z*z/n)
                        margin = z * ((p*(1-p) + z*z/(4*n))/n)**0.5 / (1 + z*z/n)
                        
                        ci_lower = max(0, center - margin)
                        ci_upper = min(1, center + margin)
                    else:
                        ci_lower = ci_upper = p
                    
                    # Calculate variance and reliability metrics
                    score_variance = self._calculate_variance(scores[:k])
                    score_std = score_variance ** 0.5 if score_variance else 0
                    score_range_min = min(scores[:k]) if scores[:k] else 0
                    score_range_max = max(scores[:k]) if scores[:k] else 0
                    
                    # Determine reliability grade
                    reliability_grade = self._get_reliability_grade(pass_at_k)
                    consistency_score = self._calculate_consistency_score(scores[:k])
                    
                    # Create PassKMetric record
                    pass_k_metric = PassKMetric(
                        scenario_id=scenario_id,
                        evaluation_result_id=evaluation_results[0].id if evaluation_results else None,
                        k_value=k,
                        total_runs=k,
                        successful_runs=successful_runs,
                        pass_at_k=pass_at_k,
                        confidence_interval_lower=ci_lower,
                        confidence_interval_upper=ci_upper,
                        success_threshold=success_threshold,
                        success_criteria={
                            "minimum_score": success_threshold,
                            "scoring_dimensions": list(scenario.evaluation_criteria.keys())
                        },
                        score_variance=score_variance,
                        score_std_deviation=score_std,
                        score_range_min=score_range_min,
                        score_range_max=score_range_max,
                        consistency_score=consistency_score,
                        reliability_grade=reliability_grade,
                        run_duration_ms=sum(getattr(r, 'execution_time_ms', 0) for r in evaluation_results[:k])
                    )
                    
                    pass_k_metrics.append(pass_k_metric)
            
            # Save PassKMetric results
            for metric in pass_k_metrics:
                await self._save_pass_k_metric(metric)
            
            # Create alert for poor reliability
            worst_pass_k = min(pass_k_metrics, key=lambda x: x.pass_at_k) if pass_k_metrics else None
            if worst_pass_k and worst_pass_k.pass_at_k < 0.5:
                await self._create_reliability_alert(scenario_id, worst_pass_k)
            
            self.logger.info(
                f"Determinism test completed: {scenario_id} "
                f"(Pass@10: {pass_k_metrics[2].pass_at_k:.2f} if len >= 3 else 'N/A')"
            )
            
            return pass_k_metrics
            
        except Exception as e:
            self.logger.error(f"Determinism test failed: {str(e)}", exc_info=True)
            raise
    
    async def run_evaluation_batch(
        self,
        evaluations: List[Dict[str, Any]],
        judge_config: Dict[str, Any],
        parallel: bool = True
    ) -> List[EvaluationResult]:
        """
        Run multiple evaluations in batch.
        
        Args:
            evaluations: List of evaluation configurations
            judge_config: Shared judge configuration
            parallel: Whether to run evaluations in parallel
            
        Returns:
            List of EvaluationResult objects
        """
        
        try:
            self.logger.info(f"Starting batch evaluation of {len(evaluations)} scenarios")
            
            if parallel:
                # Run in parallel with semaphore to limit concurrency
                semaphore = asyncio.Semaphore(4)  # Limit to 4 concurrent evaluations
                
                async def run_with_semaphore(eval_config):
                    async with semaphore:
                        return await self.run_evaluation(**eval_config)
                
                tasks = [
                    run_with_semaphore(eval_config) 
                    for eval_config in evaluations
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Filter out exceptions and log them
                evaluation_results = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        self.logger.error(f"Batch evaluation {i} failed: {result}")
                    else:
                        evaluation_results.append(result)
                
            else:
                # Run sequentially
                evaluation_results = []
                for i, eval_config in enumerate(evaluations):
                    try:
                        result = await self.run_evaluation(**eval_config)
                        evaluation_results.append(result)
                    except Exception as e:
                        self.logger.error(f"Batch evaluation {i} failed: {e}")
            
            self.logger.info(f"Batch evaluation completed: {len(evaluation_results)}/{len(evaluations)} successful")
            return evaluation_results
            
        except Exception as e:
            self.logger.error(f"Batch evaluation failed: {str(e)}", exc_info=True)
            raise
    
    async def get_evaluation_dashboard(
        self,
        scenario_ids: List[str] = None,
        time_range_days: int = 30,
        metrics: List[str] = None
    ) -> Dict[str, Any]:
        """
        Get evaluation dashboard data with trends and metrics.
        
        Args:
            scenario_ids: Specific scenarios to include
            time_range_days: How many days of history to include
            metrics: Specific metrics to include
            
        Returns:
            Dashboard data with trends and insights
        """
        
        try:
            # Default metrics to include
            if metrics is None:
                metrics = [
                    "overall_score",
                    "code_safety_score",
                    "code_quality_score",
                    "best_practices_score",
                    "pass_at_10",
                    "reliability_grade"
                ]
            
            # Get database connection
            db = next(get_db())
            
            # Calculate time range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=time_range_days)
            
            # Query evaluation results
            query = db.query(EvaluationResult).filter(
                EvaluationResult.completed_at >= start_date,
                EvaluationResult.completed_at <= end_date,
                EvaluationResult.status == EvaluationStatus.COMPLETED
            )
            
            if scenario_ids:
                query = query.filter(EvaluationResult.scenario_id.in_(scenario_ids))
            
            results = query.order_by(EvaluationResult.completed_at.desc()).all()
            
            # Process results into dashboard data
            dashboard_data = {
                "summary": {
                    "total_evaluations": len(results),
                    "avg_overall_score": sum(r.overall_score or 0 for r in results) / len(results) if results else 0,
                    "pass_rate": len([r for r in results if (r.overall_score or 0) >= 7.0]) / len(results) if results else 0,
                    "time_range_days": time_range_days
                },
                "score_trends": self._calculate_score_trends(results),
                "dimension_breakdown": self._calculate_dimension_breakdown(results),
                "regression_alerts": await self._get_recent_regression_alerts(time_range_days),
                "reliability_metrics": await self._get_reliability_metrics(scenario_ids),
                "cost_analysis": self._calculate_cost_analysis(results),
                "scenario_performance": self._calculate_scenario_performance(results)
            }
            
            db.close()
            return dashboard_data
            
        except Exception as e:
            self.logger.error(f"Dashboard generation failed: {str(e)}", exc_info=True)
            raise
    
    # ==================== Private Methods ====================
    
    async def _get_scenario(self, scenario_id: str) -> Optional[EvaluationScenario]:
        """Get evaluation scenario by ID."""
        try:
            db = next(get_db())
            scenario = db.query(EvaluationScenario).filter(
                EvaluationScenario.id == scenario_id,
                EvaluationScenario.is_active == True
            ).first()
            db.close()
            return scenario
        except Exception as e:
            self.logger.error(f"Failed to get scenario {scenario_id}: {e}")
            return None
    
    async def _get_baseline_evaluation(self, scenario_id: str) -> Optional[EvaluationResult]:
        """Get baseline evaluation for a scenario."""
        try:
            db = next(get_db())
            baseline = db.query(EvaluationResult).filter(
                EvaluationResult.scenario_id == scenario_id,
                EvaluationResult.status == EvaluationStatus.COMPLETED
            ).order_by(EvaluationResult.completed_at.asc()).first()
            db.close()
            return baseline
        except Exception as e:
            self.logger.error(f"Failed to get baseline for {scenario_id}: {e}")
            return None
    
    async def _save_evaluation_result(self, result: EvaluationResult):
        """Save evaluation result to database."""
        try:
            db = next(get_db())
            db.add(result)
            db.commit()
            db.close()
        except Exception as e:
            self.logger.error(f"Failed to save evaluation result: {e}")
            db.rollback()
            db.close()
            raise
    
    async def _save_regression_test(self, regression_test: RegressionTest):
        """Save regression test to database."""
        try:
            db = next(get_db())
            db.add(regression_test)
            db.commit()
            db.close()
        except Exception as e:
            self.logger.error(f"Failed to save regression test: {e}")
            db.rollback()
            db.close()
            raise
    
    async def _save_pass_k_metric(self, metric: PassKMetric):
        """Save Pass@k metric to database."""
        try:
            db = next(get_db())
            db.add(metric)
            db.commit()
            db.close()
        except Exception as e:
            self.logger.error(f"Failed to save Pass@k metric: {e}")
            db.rollback()
            db.close()
            raise
    
    async def _update_regression_metrics(self, result: EvaluationResult):
        """Update regression metrics for a scenario."""
        try:
            db = next(get_db())
            
            # Get historical scores for this scenario
            historical_scores = [
                r.overall_score for r in db.query(EvaluationResult).filter(
                    EvaluationResult.scenario_id == result.scenario_id,
                    EvaluationResult.id != result.id,
                    EvaluationResult.overall_score.isnot(None)
                ).all()
            ]
            
            if historical_scores:
                # Calculate regression metrics
                regression_metric = RegressionMetric(
                    evaluation_result_id=result.id,
                    historical_avg_score=sum(historical_scores) / len(historical_scores),
                    historical_median_score=sorted(historical_scores)[len(historical_scores)//2],
                    historical_percentile_25=sorted(historical_scores)[len(historical_scores)//4] if len(historical_scores) > 3 else None,
                    historical_percentile_75=sorted(historical_scores)[3*len(historical_scores)//4] if len(historical_scores) > 3 else None,
                    historical_percentile_90=sorted(historical_scores)[9*len(historical_scores)//10] if len(historical_scores) > 9 else None,
                    quality_gate_threshold=7.0,
                    quality_gate_status="pass" if (result.overall_score or 0) >= 7.0 else "fail"
                )
                
                db.add(regression_metric)
                db.commit()
            
            db.close()
        except Exception as e:
            self.logger.error(f"Failed to update regression metrics: {e}")
            db.rollback()
            db.close()
    
    async def _check_alerts(self, result: EvaluationResult):
        """Check if any alerts should be triggered for this evaluation."""
        try:
            # Check for poor performance
            if (result.overall_score or 0) < 5.0:
                await self._create_performance_alert(result)
            
            # Check for high error rate in evaluation
            if result.status == EvaluationStatus.ERROR:
                await self._create_evaluation_error_alert(result)
                
        except Exception as e:
            self.logger.error(f"Failed to check alerts: {e}")
    
    async def _create_regression_alert(self, regression_test: RegressionTest, current_result: EvaluationResult):
        """Create regression alert."""
        try:
            alert = EvaluationAlert(
                alert_type=RegressionAlertType.SCORE_DEGRADATION,
                severity="high",
                scenario_id=regression_test.scenario_id,
                regression_test_id=regression_test.id,
                evaluation_result_id=current_result.id,
                title=f"Score Degradation Detected",
                description=regression_test.alert_message,
                metric_name="overall_score",
                metric_value=current_result.overall_score,
                threshold_value=regression_test.baseline_score,
                commit_hash=regression_test.commit_hash,
                branch_name=regression_test.branch_name,
                triggered_by="automated_regression_test"
            )
            
            db = next(get_db())
            db.add(alert)
            db.commit()
            db.close()
            
            self.logger.warning(f"Regression alert created: {regression_test.alert_message}")
            
        except Exception as e:
            self.logger.error(f"Failed to create regression alert: {e}")
    
    async def _create_reliability_alert(self, scenario_id: str, pass_k_metric: PassKMetric):
        """Create reliability alert."""
        try:
            alert = EvaluationAlert(
                alert_type=RegressionAlertType.CONSISTENCY_DROP,
                severity="medium",
                scenario_id=scenario_id,
                title=f"Low Reliability Detected",
                description=f"Pass@{pass_k_metric.k_value} = {pass_k_metric.pass_at_k:.2f} (below 0.5 threshold)",
                metric_name=f"pass_at_{pass_k_metric.k_value}",
                metric_value=pass_k_metric.pass_at_k,
                threshold_value=0.5,
                triggered_by="automated_reliability_test"
            )
            
            db = next(get_db())
            db.add(alert)
            db.commit()
            db.close()
            
            self.logger.warning(f"Reliability alert created for scenario {scenario_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to create reliability alert: {e}")
    
    async def _create_performance_alert(self, result: EvaluationResult):
        """Create performance alert."""
        try:
            alert = EvaluationAlert(
                alert_type=RegressionAlertType.SCORE_DEGRADATION,
                severity="medium",
                scenario_id=result.scenario_id,
                evaluation_result_id=result.id,
                title=f"Poor Performance Detected",
                description=f"Overall score {result.overall_score:.2f} below 5.0 threshold",
                metric_name="overall_score",
                metric_value=result.overall_score,
                threshold_value=5.0,
                triggered_by="automated_quality_check"
            )
            
            db = next(get_db())
            db.add(alert)
            db.commit()
            db.close()
            
            self.logger.warning(f"Performance alert created for evaluation {result.id}")
            
        except Exception as e:
            self.logger.error(f"Failed to create performance alert: {e}")
    
    async def _create_evaluation_error_alert(self, result: EvaluationResult):
        """Create evaluation error alert."""
        try:
            alert = EvaluationAlert(
                alert_type=RegressionAlertType.FUNCTIONALITY_BREAK,
                severity="high",
                scenario_id=result.scenario_id,
                evaluation_result_id=result.id,
                title=f"Evaluation System Error",
                description=result.error_message or "Unknown evaluation error",
                triggered_by="automated_system_check"
            )
            
            db = next(get_db())
            db.add(alert)
            db.commit()
            db.close()
            
            self.logger.warning(f"Evaluation error alert created for {result.id}")
            
        except Exception as e:
            self.logger.error(f"Failed to create evaluation error alert: {e}")
    
    def _calculate_variance(self, scores: List[float]) -> float:
        """Calculate variance of a list of scores."""
        if len(scores) < 2:
            return 0.0
        
        mean = sum(scores) / len(scores)
        variance = sum((score - mean) ** 2 for score in scores) / len(scores)
        return variance
    
    def _get_reliability_grade(self, pass_rate: float) -> str:
        """Get reliability grade based on pass rate."""
        if pass_rate >= 0.9:
            return "A"
        elif pass_rate >= 0.8:
            return "B"
        elif pass_rate >= 0.7:
            return "C"
        elif pass_rate >= 0.6:
            return "D"
        else:
            return "F"
    
    def _calculate_consistency_score(self, scores: List[float]) -> float:
        """Calculate consistency score (inverse of coefficient of variation)."""
        if len(scores) < 2:
            return 1.0
        
        mean = sum(scores) / len(scores)
        if mean == 0:
            return 1.0
        
        variance = self._calculate_variance(scores)
        std_dev = variance ** 0.5
        cv = std_dev / mean  # Coefficient of variation
        
        # Convert to 0-1 score (1 = perfectly consistent)
        consistency_score = max(0.0, min(1.0, 1.0 / (1.0 + cv)))
        return consistency_score
    
    def _calculate_score_trends(self, results: List[EvaluationResult]) -> List[Dict[str, Any]]:
        """Calculate score trends over time."""
        # Group by day and calculate averages
        daily_scores = {}
        for result in results:
            date_key = result.completed_at.date().isoformat()
            if date_key not in daily_scores:
                daily_scores[date_key] = []
            daily_scores[date_key].append(result.overall_score or 0)
        
        trends = []
        for date, scores in sorted(daily_scores.items()):
            trends.append({
                "date": date,
                "avg_score": sum(scores) / len(scores),
                "min_score": min(scores),
                "max_score": max(scores),
                "count": len(scores)
            })
        
        return trends
    
    def _calculate_dimension_breakdown(self, results: List[EvaluationResult]) -> Dict[str, float]:
        """Calculate average scores by dimension."""
        dimensions = [
            "code_safety_score", "code_quality_score", "best_practices_score",
            "performance_score", "readability_score", "functionality_score",
            "security_score", "maintainability_score"
        ]
        
        breakdown = {}
        for dimension in dimensions:
            scores = [getattr(r, dimension) for r in results if getattr(r, dimension) is not None]
            breakdown[dimension] = sum(scores) / len(scores) if scores else 0.0
        
        return breakdown
    
    async def _get_recent_regression_alerts(self, time_range_days: int) -> List[Dict[str, Any]]:
        """Get recent regression alerts."""
        try:
            db = next(get_db())
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=time_range_days)
            
            alerts = db.query(EvaluationAlert).filter(
                EvaluationAlert.created_at >= start_date,
                EvaluationAlert.alert_type == RegressionAlertType.SCORE_DEGRADATION
            ).order_by(EvaluationAlert.created_at.desc()).limit(10).all()
            
            db.close()
            return [self._alert_to_dict(alert) for alert in alerts]
            
        except Exception as e:
            self.logger.error(f"Failed to get regression alerts: {e}")
            return []
    
    async def _get_reliability_metrics(self, scenario_ids: List[str] = None) -> Dict[str, Any]:
        """Get reliability metrics across scenarios."""
        try:
            db = next(get_db())
            
            query = db.query(PassKMetric)
            if scenario_ids:
                query = query.filter(PassKMetric.scenario_id.in_(scenario_ids))
            
            metrics = query.filter(PassKMetric.k_value == 10).all()  # Focus on Pass@10
            
            if not metrics:
                return {"avg_pass_at_10": 0.0, "reliability_distribution": {}}
            
            pass_rates = [m.pass_at_k for m in metrics]
            reliability_grades = [m.reliability_grade for m in metrics]
            
            # Count grades
            grade_distribution = {}
            for grade in reliability_grades:
                grade_distribution[grade] = grade_distribution.get(grade, 0) + 1
            
            db.close()
            
            return {
                "avg_pass_at_10": sum(pass_rates) / len(pass_rates),
                "reliability_distribution": grade_distribution,
                "total_scenarios": len(metrics)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get reliability metrics: {e}")
            return {"avg_pass_at_10": 0.0, "reliability_distribution": {}}
    
    def _calculate_cost_analysis(self, results: List[EvaluationResult]) -> Dict[str, Any]:
        """Calculate cost analysis of evaluations."""
        total_cost = sum(r.judge_cost_usd or 0 for r in results)
        total_tokens = sum(r.judge_tokens_used or 0 for r in results)
        
        return {
            "total_cost_usd": total_cost,
            "total_tokens": total_tokens,
            "avg_cost_per_evaluation": total_cost / len(results) if results else 0,
            "avg_tokens_per_evaluation": total_tokens / len(results) if results else 0
        }
    
    def _calculate_scenario_performance(self, results: List[EvaluationResult]) -> List[Dict[str, Any]]:
        """Calculate performance by scenario."""
        scenario_performance = {}
        
        for result in results:
            scenario_id = result.scenario_id
            if scenario_id not in scenario_performance:
                scenario_performance[scenario_id] = []
            scenario_performance[scenario_id].append(result.overall_score or 0)
        
        performance = []
        for scenario_id, scores in scenario_performance.items():
            performance.append({
                "scenario_id": scenario_id,
                "avg_score": sum(scores) / len(scores),
                "min_score": min(scores),
                "max_score": max(scores),
                "evaluation_count": len(scores),
                "reliability_grade": self._get_reliability_grade(len([s for s in scores if s >= 7.0]) / len(scores))
            })
        
        return sorted(performance, key=lambda x: x["avg_score"], reverse=True)
    
    def _alert_to_dict(self, alert: EvaluationAlert) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "id": alert.id,
            "type": alert.alert_type.value,
            "severity": alert.severity,
            "title": alert.title,
            "description": alert.description,
            "created_at": alert.created_at.isoformat(),
            "status": alert.status
        }