# -*- coding: utf-8 -*-
"""
Priority Scorer

Calculates task complexity and priority scores for escalation decisions.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ComplexityMetrics:
    """Container for complexity metrics."""
    
    def __init__(
        self,
        overall_score: float = 0.0,
        code_complexity: float = 0.0,
        dependencies_complexity: float = 0.0,
        data_complexity: float = 0.0,
        business_logic_complexity: float = 0.0,
    ):
        self.overall_score = overall_score
        self.code_complexity = code_complexity
        self.dependencies_complexity = dependencies_complexity
        self.data_complexity = data_complexity
        self.business_logic_complexity = business_logic_complexity


class PriorityScorer:
    """
    Calculates task complexity and priority scores.
    
    Uses multiple factors to determine if a task is complex enough
    to warrant escalation to a supervisor agent.
    """
    
    def __init__(
        self,
        complexity_weights: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize the priority scorer.
        
        Args:
            complexity_weights: Custom weights for complexity factors
        """
        self.complexity_weights = complexity_weights or {
            "code_complexity": 0.3,
            "dependencies_complexity": 0.2,
            "data_complexity": 0.2,
            "business_logic_complexity": 0.3,
        }
        logger.info("PriorityScorer initialized")
    
    def calculate_complexity(
        self,
        task_data: Dict[str, Any],
    ) -> ComplexityMetrics:
        """
        Calculate task complexity score.
        
        Args:
            task_data: Task data and metadata
            
        Returns:
            ComplexityMetrics with detailed scores
        """
        code_score = self._calculate_code_complexity(task_data)
        deps_score = self._calculate_dependencies_complexity(task_data)
        data_score = self._calculate_data_complexity(task_data)
        logic_score = self._calculate_business_logic_complexity(task_data)
        
        # Calculate weighted overall score
        overall = (
            code_score * self.complexity_weights["code_complexity"] +
            deps_score * self.complexity_weights["dependencies_complexity"] +
            data_score * self.complexity_weights["data_complexity"] +
            logic_score * self.complexity_weights["business_logic_complexity"]
        )
        
        metrics = ComplexityMetrics(
            overall_score=min(overall, 1.0),  # Cap at 1.0
            code_complexity=code_score,
            dependencies_complexity=deps_score,
            data_complexity=data_score,
            business_logic_complexity=logic_score,
        )
        
        logger.debug(f"Calculated complexity: overall={metrics.overall_score:.2f}")
        return metrics
    
    def _calculate_code_complexity(
        self,
        task_data: Dict[str, Any],
    ) -> float:
        """Calculate code complexity score (0.0 - 1.0)."""
        score = 0.0
        
        # Number of files to modify
        files_count = len(task_data.get("files", []))
        if files_count > 20:
            score += 0.4
        elif files_count > 10:
            score += 0.3
        elif files_count > 5:
            score += 0.2
        elif files_count > 0:
            score += 0.1
        
        # Lines of code to modify
        lines_count = task_data.get("estimated_lines", 0)
        if lines_count > 1000:
            score += 0.3
        elif lines_count > 500:
            score += 0.2
        elif lines_count > 100:
            score += 0.1
        
        # Code structure complexity
        if task_data.get("involves_refactoring", False):
            score += 0.2
        
        if task_data.get("involves_architecture_change", False):
            score += 0.3
        
        return min(score, 1.0)
    
    def _calculate_dependencies_complexity(
        self,
        task_data: Dict[str, Any],
    ) -> float:
        """Calculate dependencies complexity score (0.0 - 1.0)."""
        score = 0.0
        
        # Number of external dependencies
        deps_count = len(task_data.get("dependencies", []))
        if deps_count > 10:
            score += 0.4
        elif deps_count > 5:
            score += 0.3
        elif deps_count > 2:
            score += 0.2
        elif deps_count > 0:
            score += 0.1
        
        # Third-party integrations
        integrations_count = len(task_data.get("third_party_integrations", []))
        if integrations_count > 3:
            score += 0.3
        elif integrations_count > 1:
            score += 0.2
        elif integrations_count > 0:
            score += 0.1
        
        # API complexity
        if task_data.get("involves_api_design", False):
            score += 0.2
        
        if task_data.get("involves_breaking_changes", False):
            score += 0.3
        
        return min(score, 1.0)
    
    def _calculate_data_complexity(
        self,
        task_data: Dict[str, Any],
    ) -> float:
        """Calculate data complexity score (0.0 - 1.0)."""
        score = 0.0
        
        # Database operations
        if task_data.get("involves_database_migration", False):
            score += 0.4
        
        if task_data.get("involves_schema_changes", False):
            score += 0.3
        
        if task_data.get("involves_data_migration", False):
            score += 0.3
        
        # Data volume
        data_volume = task_data.get("estimated_data_volume", "small")
        if data_volume == "large":
            score += 0.3
        elif data_volume == "medium":
            score += 0.2
        
        # Data sensitivity
        if task_data.get("involves_sensitive_data", False):
            score += 0.2
        
        return min(score, 1.0)
    
    def _calculate_business_logic_complexity(
        self,
        task_data: Dict[str, Any],
    ) -> float:
        """Calculate business logic complexity score (0.0 - 1.0)."""
        score = 0.0
        
        # Business rules
        rules_count = len(task_data.get("business_rules", []))
        if rules_count > 10:
            score += 0.3
        elif rules_count > 5:
            score += 0.2
        elif rules_count > 2:
            score += 0.1
        
        # Edge cases
        edge_cases_count = len(task_data.get("edge_cases", []))
        if edge_cases_count > 10:
            score += 0.3
        elif edge_cases_count > 5:
            score += 0.2
        elif edge_cases_count > 2:
            score += 0.1
        
        # Security implications
        if task_data.get("involves_security", False):
            score += 0.3
        
        # Compliance requirements
        if task_data.get("involves_compliance", False):
            score += 0.3
        
        # Cross-functional impact
        if task_data.get("cross_functional_impact", False):
            score += 0.2
        
        return min(score, 1.0)
    
    def calculate_priority(
        self,
        complexity_metrics: ComplexityMetrics,
        error_rate: float = 0.0,
        retry_count: int = 0,
        execution_duration_seconds: int = 0,
    ) -> float:
        """
        Calculate escalation priority score.
        
        Args:
            complexity_metrics: Complexity metrics
            error_rate: Current error rate (0.0 - 1.0)
            retry_count: Number of retries
            execution_duration_seconds: Execution duration
            
        Returns:
            Priority score (0.0 - 1.0), higher means higher priority
        """
        # Base priority from complexity
        priority = complexity_metrics.overall_score * 0.5
        
        # Factor in error rate
        priority += error_rate * 0.3
        
        # Factor in retries
        if retry_count > 5:
            priority += 0.15
        elif retry_count > 3:
            priority += 0.10
        elif retry_count > 0:
            priority += 0.05
        
        # Factor in execution time
        if execution_duration_seconds > 3600:  # > 1 hour
            priority += 0.05
        
        return min(priority, 1.0)
    
    def should_escalate(
        self,
        priority: float,
        threshold: float = 0.7,
    ) -> bool:
        """
        Determine if a task should be escalated based on priority.
        
        Args:
            priority: Priority score
            threshold: Escalation threshold (default: 0.7)
            
        Returns:
            True if task should be escalated
        """
        return priority >= threshold


__all__ = ["PriorityScorer", "ComplexityMetrics"]
