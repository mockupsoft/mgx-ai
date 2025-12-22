# -*- coding: utf-8 -*-
"""backend.services.quality_gates.gates.base_gate

Base class for all quality gates.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import logging
import asyncio
from dataclasses import dataclass, asdict

from ....db.models.entities import QualityGate, GateExecution
from ....db.models.enums import QualityGateType, QualityGateStatus, GateSeverity


@dataclass
class GateResult:
    """Result of a gate evaluation."""
    
    gate_type: QualityGateType
    status: QualityGateStatus
    passed: bool
    passed_with_warnings: bool = False
    execution_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    
    # Detailed results
    details: Dict[str, Any] = None
    metrics: Dict[str, Union[int, float]] = None
    recommendations: List[str] = None
    
    # Issue tracking
    total_issues: int = 0
    critical_issues: int = 0
    high_issues: int = 0
    medium_issues: int = 0
    low_issues: int = 0
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.metrics is None:
            self.metrics = {}
        if self.recommendations is None:
            self.recommendations = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return asdict(self)


@dataclass
class GateConfiguration:
    """Configuration for a quality gate."""
    
    gate_type: QualityGateType
    is_enabled: bool = True
    is_blocking: bool = True
    threshold_config: Dict[str, Any] = None
    timeout_seconds: int = 300
    
    def __post_init__(self):
        if self.threshold_config is None:
            self.threshold_config = {}


class BaseQualityGate(ABC):
    """Abstract base class for all quality gates."""
    
    def __init__(self, gate_type: QualityGateType, config: GateConfiguration):
        self.gate_type = gate_type
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._execution_context: Dict[str, Any] = {}
    
    @abstractmethod
    async def evaluate(
        self,
        workspace_id: str,
        project_id: str,
        task_id: Optional[str] = None,
        task_run_id: Optional[str] = None,
        sandbox_execution_id: Optional[str] = None,
        **kwargs
    ) -> GateResult:
        """Evaluate the gate with given parameters."""
        pass
    
    def validate_configuration(self) -> List[str]:
        """Validate gate configuration and return list of validation errors."""
        errors = []
        
        if not self.config.gate_type:
            errors.append("Gate type is required")
        
        if self.config.timeout_seconds <= 0:
            errors.append("Timeout must be positive")
        
        return errors
    
    async def run_with_timeout(
        self,
        evaluation_func,
        timeout_seconds: Optional[int] = None
    ) -> GateResult:
        """Run evaluation function with timeout."""
        timeout = timeout_seconds or self.config.timeout_seconds
        
        try:
            result = await asyncio.wait_for(
                evaluation_func(),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            self.logger.error(f"Gate evaluation timed out after {timeout} seconds")
            return GateResult(
                gate_type=self.gate_type,
                status=QualityGateStatus.TIMEOUT,
                passed=False,
                execution_time_ms=timeout * 1000,
                error_message=f"Evaluation timed out after {timeout} seconds"
            )
        except Exception as e:
            self.logger.error(f"Gate evaluation failed with error: {str(e)}")
            return GateResult(
                gate_type=self.gate_type,
                status=QualityGateStatus.ERROR,
                passed=False,
                error_message=f"Evaluation failed: {str(e)}"
            )
    
    def set_execution_context(self, context: Dict[str, Any]) -> None:
        """Set execution context for this evaluation."""
        self._execution_context.update(context)
    
    def get_execution_context(self) -> Dict[str, Any]:
        """Get current execution context."""
        return self._execution_context.copy()
    
    def add_issue(
        self,
        severity: GateSeverity,
        message: str,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        column_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """Add an issue to the current evaluation."""
        issue = {
            "severity": severity,
            "message": message,
            "file_path": file_path,
            "line_number": line_number,
            "column_number": column_number,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        context = self.get_execution_context()
        issues = context.get("issues", [])
        issues.append(issue)
        context["issues"] = issues
        
        return issue
    
    def get_threshold_value(self, key: str, default: Any = None) -> Any:
        """Get threshold configuration value with default."""
        return self.config.threshold_config.get(key, default)
    
    def is_threshold_exceeded(
        self,
        actual_value: Union[int, float],
        threshold_key: str,
        threshold_type: str = "max"
    ) -> bool:
        """Check if a value exceeds the configured threshold."""
        threshold = self.get_threshold_value(threshold_key)
        if threshold is None:
            return False
        
        if threshold_type == "max":
            return actual_value > threshold
        elif threshold_type == "min":
            return actual_value < threshold
        else:
            self.logger.warning(f"Unknown threshold type: {threshold_type}")
            return False
    
    def create_recommendation(
        self,
        issue_type: str,
        suggestion: str,
        priority: GateSeverity = GateSeverity.MEDIUM
    ) -> str:
        """Create a recommendation based on an issue."""
        return f"[{priority.value.upper()}] {issue_type}: {suggestion}"
    
    def classify_issues_by_severity(self, issues: List[Dict[str, Any]]) -> Dict[str, int]:
        """Classify issues by severity and return counts."""
        counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0
        }
        
        for issue in issues:
            severity = issue.get("severity", GateSeverity.LOW)
            if isinstance(severity, str):
                severity = GateSeverity(severity)
            
            counts[severity.value] += 1
        
        return counts
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported programming languages for this gate."""
        return ["javascript", "python", "php", "typescript"]
    
    def is_language_supported(self, language: str) -> bool:
        """Check if a programming language is supported."""
        return language.lower() in [lang.lower() for lang in self.get_supported_languages()]
    
    async def cleanup(self) -> None:
        """Cleanup resources after evaluation."""
        self._execution_context.clear()
        self.logger.debug(f"Cleaned up execution context for {self.gate_type.value} gate")


class GateRegistry:
    """Registry for all quality gate implementations."""
    
    def __init__(self):
        self._gates: Dict[QualityGateType, type] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_gate(self, gate_type: QualityGateType, gate_class: type) -> None:
        """Register a gate implementation."""
        if not issubclass(gate_class, BaseQualityGate):
            raise ValueError(f"Gate class must inherit from BaseQualityGate")
        
        self._gates[gate_type] = gate_class
        self.logger.info(f"Registered gate implementation: {gate_type.value}")
    
    def get_gate_class(self, gate_type: QualityGateType) -> Optional[type]:
        """Get gate implementation class."""
        return self._gates.get(gate_type)
    
    def get_all_gate_types(self) -> List[QualityGateType]:
        """Get list of all registered gate types."""
        return list(self._gates.keys())
    
    def is_gate_registered(self, gate_type: QualityGateType) -> bool:
        """Check if a gate type is registered."""
        return gate_type in self._gates


# Global gate registry instance
gate_registry = GateRegistry()


def register_gate(gate_type: QualityGateType):
    """Decorator to register a gate implementation."""
    def decorator(gate_class: type):
        gate_registry.register_gate(gate_type, gate_class)
        return gate_class
    return decorator


def create_gate(
    gate_type: QualityGateType,
    config: GateConfiguration
) -> BaseQualityGate:
    """Create a gate instance from configuration."""
    gate_class = gate_registry.get_gate_class(gate_type)
    if not gate_class:
        raise ValueError(f"No implementation found for gate type: {gate_type.value}")
    
    return gate_class(config)