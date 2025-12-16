# -*- coding: utf-8 -*-
"""backend.services.quality_gates.gate_manager

Quality Gate Manager for orchestrating gate evaluations and handling results.
"""

import asyncio
import yaml
import os
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import json
from dataclasses import asdict

from ..db.models.entities import QualityGate, GateExecution
from ..db.models.enums import QualityGateType, QualityGateStatus
from .gates.base_gate import GateResult, GateConfiguration, create_gate, gate_registry


class QualityGateManager:
    """Manager for quality gate evaluation and orchestration."""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "..", "configs", "quality_gates.yml")
        self.logger = logging.getLogger(__name__)
        self._config = None
        self._sandbox_runner = None
    
    @property
    def sandbox_runner(self):
        """Get sandbox runner instance."""
        if self._sandbox_runner is None:
            try:
                from ..sandbox.runner import SandboxRunner
                self._sandbox_runner = SandboxRunner()
            except ImportError:
                self.logger.warning("Sandbox runner not available")
                self._sandbox_runner = None
        return self._sandbox_runner
    
    async def initialize(self) -> None:
        """Initialize the gate manager."""
        await self._load_configuration()
        self.logger.info(f"Quality Gate Manager initialized with {len(gate_registry.get_all_gate_types())} gates")
    
    async def _load_configuration(self) -> None:
        """Load gate configuration from YAML file."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self._config = yaml.safe_load(f)
                self.logger.info(f"Loaded quality gate configuration from {self.config_path}")
            else:
                self.logger.warning(f"Configuration file not found: {self.config_path}")
                self._config = self._get_default_config()
                
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration when file not found."""
        return {
            "gates": {
                "lint": {"enabled": True, "blocking": True, "max_warnings": 10},
                "coverage": {"enabled": True, "blocking": True, "min_percentage": 80},
                "security": {"enabled": True, "blocking": True},
                "performance": {"enabled": True, "blocking": True},
                "contract": {"enabled": True, "blocking": True},
                "complexity": {"enabled": True, "blocking": True},
                "type_check": {"enabled": True, "blocking": True}
            },
            "global": {
                "default_timeout": 300,
                "parallel_execution": True,
                "max_parallel_gates": 4
            }
        }
    
    async def evaluate_gates(
        self,
        workspace_id: str,
        project_id: str,
        gate_types: List[str],
        task_id: Optional[str] = None,
        task_run_id: Optional[str] = None,
        sandbox_execution_id: Optional[str] = None,
        working_directory: Optional[str] = None,
        application_url: Optional[str] = None,
        openapi_spec: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Evaluate multiple quality gates."""
        
        start_time = datetime.utcnow()
        self.logger.info(f"Starting gate evaluation for workspace={workspace_id}, project={project_id}, gates={gate_types}")
        
        try:
            # Validate gate types
            valid_gate_types = []
            for gate_type_str in gate_types:
                try:
                    gate_type = QualityGateType(gate_type_str)
                    if gate_registry.is_gate_registered(gate_type):
                        valid_gate_types.append(gate_type)
                    else:
                        self.logger.warning(f"Gate type {gate_type_str} is not registered")
                except ValueError:
                    self.logger.warning(f"Invalid gate type: {gate_type_str}")
            
            if not valid_gate_types:
                return {
                    "success": False,
                    "error": "No valid gate types provided",
                    "passed": False,
                    "results": {},
                    "execution_time_ms": 0
                }
            
            # Execute gates
            parallel_execution = self._get_global_config("parallel_execution", True)
            max_parallel = self._get_global_config("max_parallel_gates", 4)
            
            if parallel_execution:
                results = await self._execute_gates_parallel(
                    valid_gate_types, workspace_id, project_id,
                    task_id, task_run_id, sandbox_execution_id,
                    working_directory, application_url, openapi_spec,
                    max_parallel, **kwargs
                )
            else:
                results = await self._execute_gates_sequential(
                    valid_gate_types, workspace_id, project_id,
                    task_id, task_run_id, sandbox_execution_id,
                    working_directory, application_url, openapi_spec,
                    **kwargs
                )
            
            # Calculate overall result
            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            overall_result = self._calculate_overall_result(results)
            
            # Persist results to database
            await self._persist_gate_results(
                workspace_id, project_id, task_id, task_run_id, sandbox_execution_id,
                results, overall_result, execution_time_ms
            )
            
            result_dict = {
                "success": True,
                "passed": overall_result["passed"],
                "passed_with_warnings": overall_result["passed_with_warnings"],
                "status": overall_result["status"],
                "results": {gt.value: asdict(result) for gt, result in results.items()},
                "summary": overall_result,
                "execution_time_ms": execution_time_ms,
                "gates_evaluated": len(valid_gate_types),
                "blocking_failures": overall_result["blocking_failures"],
                "recommendations": self._collect_all_recommendations(results)
            }
            
            self.logger.info(f"Gate evaluation completed. Overall result: {overall_result['status']}")
            return result_dict
            
        except Exception as e:
            self.logger.error(f"Gate evaluation failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "passed": False,
                "results": {},
                "execution_time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000)
            }
    
    async def _execute_gates_parallel(
        self,
        gate_types: List[QualityGateType],
        workspace_id: str,
        project_id: str,
        task_id: Optional[str],
        task_run_id: Optional[str],
        sandbox_execution_id: Optional[str],
        working_directory: Optional[str],
        application_url: Optional[str],
        openapi_spec: Optional[str],
        max_parallel: int,
        **kwargs
    ) -> Dict[QualityGateType, GateResult]:
        """Execute gates in parallel with a limit on concurrent execution."""
        
        results = {}
        
        # Split gates into batches
        for i in range(0, len(gate_types), max_parallel):
            batch = gate_types[i:i + max_parallel]
            
            # Execute batch in parallel
            batch_tasks = []
            for gate_type in batch:
                task = self._execute_single_gate(
                    gate_type, workspace_id, project_id,
                    task_id, task_run_id, sandbox_execution_id,
                    working_directory, application_url, openapi_spec,
                    **kwargs
                )
                batch_tasks.append((gate_type, task))
            
            # Wait for batch completion
            batch_results = await asyncio.gather(*[task for _, task in batch_tasks], return_exceptions=True)
            
            # Collect results
            for (gate_type, _), result in zip(batch_tasks, batch_results):
                if isinstance(result, Exception):
                    self.logger.error(f"Gate {gate_type.value} failed: {result}")
                    # Create error result
                    results[gate_type] = GateResult(
                        gate_type=gate_type,
                        status=QualityGateStatus.ERROR,
                        passed=False,
                        error_message=str(result)
                    )
                else:
                    results[gate_type] = result
        
        return results
    
    async def _execute_gates_sequential(
        self,
        gate_types: List[QualityGateType],
        workspace_id: str,
        project_id: str,
        task_id: Optional[str],
        task_run_id: Optional[str],
        sandbox_execution_id: Optional[str],
        working_directory: Optional[str],
        application_url: Optional[str],
        openapi_spec: Optional[str],
        **kwargs
    ) -> Dict[QualityGateType, GateResult]:
        """Execute gates sequentially."""
        
        results = {}
        
        for gate_type in gate_types:
            try:
                result = await self._execute_single_gate(
                    gate_type, workspace_id, project_id,
                    task_id, task_run_id, sandbox_execution_id,
                    working_directory, application_url, openapi_spec,
                    **kwargs
                )
                results[gate_type] = result
                
            except Exception as e:
                self.logger.error(f"Gate {gate_type.value} failed: {e}")
                results[gate_type] = GateResult(
                    gate_type=gate_type,
                    status=QualityGateStatus.ERROR,
                    passed=False,
                    error_message=str(e)
                )
        
        return results
    
    async def _execute_single_gate(
        self,
        gate_type: QualityGateType,
        workspace_id: str,
        project_id: str,
        task_id: Optional[str],
        task_run_id: Optional[str],
        sandbox_execution_id: Optional[str],
        working_directory: Optional[str],
        application_url: Optional[str],
        openapi_spec: Optional[str],
        **kwargs
    ) -> GateResult:
        """Execute a single quality gate."""
        
        try:
            # Get gate configuration
            gate_config = self._get_gate_config(gate_type.value)
            if not gate_config:
                return GateResult(
                    gate_type=gate_type,
                    status=QualityGateStatus.ERROR,
                    passed=False,
                    error_message=f"No configuration found for gate type: {gate_type.value}"
                )
            
            # Create gate instance
            config_obj = GateConfiguration(
                gate_type=gate_type,
                is_enabled=gate_config.get("enabled", True),
                is_blocking=gate_config.get("blocking", True),
                threshold_config=gate_config,
                timeout_seconds=self._get_global_config("default_timeout", 300)
            )
            
            gate_instance = create_gate(gate_type, config_obj)
            
            # Validate configuration
            config_errors = gate_instance.validate_configuration()
            if config_errors:
                return GateResult(
                    gate_type=gate_type,
                    status=QualityGateStatus.ERROR,
                    passed=False,
                    error_message=f"Configuration errors: {', '.join(config_errors)}"
                )
            
            # Execute gate
            result = await gate_instance.evaluate(
                workspace_id=workspace_id,
                project_id=project_id,
                task_id=task_id,
                task_run_id=task_run_id,
                sandbox_execution_id=sandbox_execution_id,
                working_directory=working_directory,
                application_url=application_url,
                openapi_spec=openapi_spec,
                **kwargs
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to execute gate {gate_type.value}: {str(e)}")
            return GateResult(
                gate_type=gate_type,
                status=QualityGateStatus.ERROR,
                passed=False,
                error_message=str(e)
            )
    
    def _calculate_overall_result(self, results: Dict[QualityGateType, GateResult]) -> Dict[str, Any]:
        """Calculate overall gate result from individual gate results."""
        
        passed_gates = []
        failed_gates = []
        warning_gates = []
        skipped_gates = []
        error_gates = []
        blocking_failures = []
        
        for gate_type, result in results.items():
            gate_config = self._get_gate_config(gate_type.value)
            is_blocking = gate_config.get("blocking", True) if gate_config else True
            
            if result.status == QualityGateStatus.PASSED:
                passed_gates.append(gate_type.value)
            elif result.status == QualityGateStatus.FAILED:
                failed_gates.append(gate_type.value)
                if is_blocking:
                    blocking_failures.append(gate_type.value)
            elif result.status == QualityGateStatus.WARNING:
                warning_gates.append(gate_type.value)
            elif result.status == QualityGateStatus.SKIPPED:
                skipped_gates.append(gate_type.value)
            elif result.status == QualityGateStatus.ERROR:
                error_gates.append(gate_type.value)
                if is_blocking:
                    blocking_failures.append(gate_type.value)
        
        # Determine overall status
        overall_passed = len(blocking_failures) == 0
        overall_passed_with_warnings = len(blocking_failures) == 0 and len(warning_gates) == 0
        
        if len(error_gates) > 0:
            if blocking_failures:
                status = QualityGateStatus.FAILED
            else:
                status = QualityGateStatus.WARNING
        elif len(blocking_failures) > 0:
            status = QualityGateStatus.FAILED
        elif len(warning_gates) > 0:
            status = QualityGateStatus.WARNING
        else:
            status = QualityGateStatus.PASSED
        
        return {
            "passed": overall_passed,
            "passed_with_warnings": overall_passed_with_warnings,
            "status": status,
            "passed_gates": passed_gates,
            "failed_gates": failed_gates,
            "warning_gates": warning_gates,
            "skipped_gates": skipped_gates,
            "error_gates": error_gates,
            "blocking_failures": blocking_failures,
            "total_gates": len(results),
            "successful_gates": len(passed_gates),
            "failed_gates_count": len(failed_gates),
            "warning_gates_count": len(warning_gates)
        }
    
    def _collect_all_recommendations(self, results: Dict[QualityGateType, GateResult]) -> List[str]:
        """Collect all recommendations from gate results."""
        
        all_recommendations = []
        
        for gate_type, result in results.items():
            if result.recommendations:
                all_recommendations.extend(result.recommendations)
        
        return all_recommendations
    
    async def _persist_gate_results(
        self,
        workspace_id: str,
        project_id: str,
        task_id: Optional[str],
        task_run_id: Optional[str],
        sandbox_execution_id: Optional[str],
        results: Dict[QualityGateType, GateResult],
        overall_result: Dict[str, Any],
        execution_time_ms: int
    ) -> None:
        """Persist gate results to database."""
        
        try:
            from ..db.database import get_db
            
            db = next(get_db())
            
            # Create or update gate configurations
            gate_configs = {}
            for gate_type in results.keys():
                gate_config = self._get_gate_config(gate_type.value)
                gate_configs[gate_type.value] = gate_config
            
            # Save individual gate executions
            for gate_type, result in results.items():
                try:
                    # Check if gate configuration exists
                    gate_name = gate_type.value.replace("_", " ").title()
                    gate_config_data = gate_configs.get(gate_type.value, {})
                    
                    # Create gate execution record
                    gate_execution = GateExecution(
                        gate_id=None,  # Will be set after creating gate config
                        task_id=task_id,
                        task_run_id=task_run_id,
                        sandbox_execution_id=sandbox_execution_id,
                        status=result.status,
                        started_at=datetime.utcnow(),
                        completed_at=datetime.utcnow(),
                        duration_ms=result.execution_time_ms or 0,
                        passed=result.passed,
                        passed_with_warnings=result.passed_with_warnings,
                        error_message=result.error_message,
                        result_details=result.details or {},
                        metrics=result.metrics or {},
                        recommendations=result.recommendations or [],
                        issues_found=result.total_issues,
                        critical_issues=result.critical_issues,
                        high_issues=result.high_issues,
                        medium_issues=result.medium_issues,
                        low_issues=result.low_issues,
                        config_used=gate_config_data
                    )
                    
                    db.add(gate_execution)
                    
                except Exception as e:
                    self.logger.error(f"Failed to persist gate execution for {gate_type.value}: {e}")
            
            db.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to persist gate results: {e}")
        finally:
            try:
                db.close()
            except:
                pass
    
    def _get_gate_config(self, gate_type: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific gate type."""
        
        if not self._config:
            return None
        
        gates_config = self._config.get("gates", {})
        return gates_config.get(gate_type)
    
    def _get_global_config(self, key: str, default: Any = None) -> Any:
        """Get global configuration value."""
        
        if not self._config:
            return default
        
        global_config = self._config.get("global", {})
        return global_config.get(key, default)
    
    async def get_gate_history(
        self,
        workspace_id: str,
        project_id: str,
        gate_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get gate execution history."""
        
        try:
            from ..db.database import get_db
            
            db = next(get_db())
            
            query = db.query(GateExecution).filter(
                GateExecution.workspace_id == workspace_id
            )
            
            if gate_type:
                # Join with QualityGate to filter by type
                query = query.join(QualityGate).filter(
                    QualityGate.gate_type == QualityGateType(gate_type)
                )
            
            # Order by creation time descending
            query = query.order_by(GateExecution.created_at.desc())
            
            # Apply pagination
            total_count = query.count()
            executions = query.offset(offset).limit(limit).all()
            
            history = []
            for execution in executions:
                history.append({
                    "id": execution.id,
                    "gate_type": execution.gate.gate_type.value if execution.gate else "unknown",
                    "status": execution.status.value,
                    "passed": execution.passed,
                    "passed_with_warnings": execution.passed_with_warnings,
                    "execution_time_ms": execution.duration_ms,
                    "issues_found": execution.issues_found,
                    "critical_issues": execution.critical_issues,
                    "high_issues": execution.high_issues,
                    "medium_issues": execution.medium_issues,
                    "low_issues": execution.low_issues,
                    "created_at": execution.created_at.isoformat(),
                    "task_run_id": execution.task_run_id,
                    "error_message": execution.error_message
                })
            
            return {
                "success": True,
                "total_count": total_count,
                "history": history,
                "limit": limit,
                "offset": offset
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get gate history: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "history": []
            }
        finally:
            try:
                db.close()
            except:
                pass
    
    async def get_gate_statistics(
        self,
        workspace_id: str,
        project_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get gate statistics for trending and analysis."""
        
        try:
            from ..db.database import get_db
            from datetime import datetime, timedelta
            
            db = next(get_db())
            
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get gate execution statistics
            query = db.query(GateExecution).filter(
                GateExecution.workspace_id == workspace_id,
                GateExecution.created_at >= start_date,
                GateExecution.created_at <= end_date
            )
            
            executions = query.all()
            
            # Calculate statistics
            stats = {
                "period_days": days,
                "total_executions": len(executions),
                "by_gate_type": {},
                "by_status": {},
                "success_rate": 0.0,
                "average_execution_time_ms": 0,
                "total_issues_found": 0,
                "trending": {}
            }
            
            if executions:
                # Group by gate type
                for execution in executions:
                    gate_type = execution.gate.gate_type.value if execution.gate else "unknown"
                    if gate_type not in stats["by_gate_type"]:
                        stats["by_gate_type"][gate_type] = {
                            "total": 0, "passed": 0, "failed": 0, "warnings": 0
                        }
                    
                    stats["by_gate_type"][gate_type]["total"] += 1
                    
                    if execution.passed:
                        stats["by_gate_type"][gate_type]["passed"] += 1
                    elif execution.passed_with_warnings:
                        stats["by_gate_type"][gate_type]["warnings"] += 1
                    else:
                        stats["by_gate_type"][gate_type]["failed"] += 1
                    
                    # Group by status
                    status = execution.status.value
                    stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
                    
                    # Accumulate metrics
                    stats["total_issues_found"] += execution.issues_found
                
                # Calculate success rate
                passed_executions = sum(1 for e in executions if e.passed)
                stats["success_rate"] = (passed_executions / len(executions)) * 100
                
                # Calculate average execution time
                execution_times = [e.duration_ms for e in executions if e.duration_ms]
                if execution_times:
                    stats["average_execution_time_ms"] = sum(execution_times) / len(execution_times)
                
                # Calculate trending (weekly breakdown)
                weekly_stats = {}
                for execution in executions:
                    week_start = execution.created_at - timedelta(days=execution.created_at.weekday())
                    week_key = week_start.strftime("%Y-%m-%d")
                    
                    if week_key not in weekly_stats:
                        weekly_stats[week_key] = {"total": 0, "passed": 0}
                    
                    weekly_stats[week_key]["total"] += 1
                    if execution.passed:
                        weekly_stats[week_key]["passed"] += 1
                
                stats["trending"] = weekly_stats
            
            return {
                "success": True,
                "statistics": stats
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get gate statistics: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "statistics": {}
            }
        finally:
            try:
                db.close()
            except:
                pass


# Global gate manager instance
_gate_manager: Optional[QualityGateManager] = None


async def get_gate_manager() -> QualityGateManager:
    """Get global gate manager instance."""
    global _gate_manager
    
    if _gate_manager is None:
        _gate_manager = QualityGateManager()
        await _gate_manager.initialize()
    
    return _gate_manager