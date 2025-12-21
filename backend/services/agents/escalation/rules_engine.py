# -*- coding: utf-8 -*-
"""
Escalation Rules Engine

Evaluates escalation rules and determines when tasks should be escalated.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.models import (
    EscalationRule,
    EscalationRuleType,
    EscalationSeverity,
    EscalationReason,
)

logger = logging.getLogger(__name__)


class RuleEvaluationContext:
    """Context for rule evaluation."""
    
    def __init__(
        self,
        workspace_id: str,
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
        task_run_id: Optional[str] = None,
        workflow_execution_id: Optional[str] = None,
        workflow_step_execution_id: Optional[str] = None,
        complexity_score: float = 0.0,
        error_count: int = 0,
        error_rate: float = 0.0,
        resource_usage: Optional[Dict[str, Any]] = None,
        execution_duration_seconds: int = 0,
        retry_count: int = 0,
        custom_metrics: Optional[Dict[str, Any]] = None,
    ):
        self.workspace_id = workspace_id
        self.project_id = project_id
        self.task_id = task_id
        self.task_run_id = task_run_id
        self.workflow_execution_id = workflow_execution_id
        self.workflow_step_execution_id = workflow_step_execution_id
        self.complexity_score = complexity_score
        self.error_count = error_count
        self.error_rate = error_rate
        self.resource_usage = resource_usage or {}
        self.execution_duration_seconds = execution_duration_seconds
        self.retry_count = retry_count
        self.custom_metrics = custom_metrics or {}
        self.timestamp = datetime.utcnow()


class RuleMatch:
    """Represents a matched escalation rule."""
    
    def __init__(
        self,
        rule: EscalationRule,
        matched_conditions: List[str],
        trigger_data: Dict[str, Any],
    ):
        self.rule = rule
        self.matched_conditions = matched_conditions
        self.trigger_data = trigger_data


class EscalationRulesEngine:
    """
    Engine for evaluating escalation rules.
    
    Supports:
    - Threshold-based rules
    - Pattern matching rules
    - Time-based rules
    - Resource-based rules
    - Composite rules
    """
    
    def __init__(self):
        """Initialize the rules engine."""
        self._rule_cache: Dict[str, List[EscalationRule]] = {}
        self._cache_timestamp: Dict[str, datetime] = {}
        logger.info("EscalationRulesEngine initialized")
    
    async def evaluate_rules(
        self,
        session: AsyncSession,
        context: RuleEvaluationContext,
    ) -> List[RuleMatch]:
        """
        Evaluate all applicable rules for the given context.
        
        Args:
            session: Database session
            context: Evaluation context
            
        Returns:
            List of matched rules
        """
        # Load applicable rules
        rules = await self._load_rules(session, context)
        
        if not rules:
            return []
        
        # Evaluate each rule
        matches = []
        for rule in rules:
            match = await self._evaluate_rule(rule, context)
            if match:
                matches.append(match)
        
        # Sort by priority (higher priority first)
        matches.sort(key=lambda m: m.rule.priority, reverse=True)
        
        logger.info(f"Evaluated {len(rules)} rules, found {len(matches)} matches")
        return matches
    
    async def _load_rules(
        self,
        session: AsyncSession,
        context: RuleEvaluationContext,
    ) -> List[EscalationRule]:
        """
        Load applicable escalation rules.
        
        Args:
            session: Database session
            context: Evaluation context
            
        Returns:
            List of applicable rules
        """
        # Build query for workspace and project rules
        query = select(EscalationRule).where(
            EscalationRule.workspace_id == context.workspace_id,
            EscalationRule.is_enabled == True,
        )
        
        # Include both workspace-level and project-specific rules
        if context.project_id:
            from sqlalchemy import or_
            query = query.where(
                or_(
                    EscalationRule.project_id == context.project_id,
                    EscalationRule.project_id.is_(None),
                )
            )
        else:
            query = query.where(EscalationRule.project_id.is_(None))
        
        # Order by priority
        query = query.order_by(EscalationRule.priority.desc())
        
        result = await session.execute(query)
        rules = result.scalars().all()
        
        return rules
    
    async def _evaluate_rule(
        self,
        rule: EscalationRule,
        context: RuleEvaluationContext,
    ) -> Optional[RuleMatch]:
        """
        Evaluate a single rule against the context.
        
        Args:
            rule: Rule to evaluate
            context: Evaluation context
            
        Returns:
            RuleMatch if rule matches, None otherwise
        """
        try:
            if rule.rule_type == EscalationRuleType.THRESHOLD:
                return await self._evaluate_threshold_rule(rule, context)
            elif rule.rule_type == EscalationRuleType.PATTERN:
                return await self._evaluate_pattern_rule(rule, context)
            elif rule.rule_type == EscalationRuleType.TIME_BASED:
                return await self._evaluate_time_based_rule(rule, context)
            elif rule.rule_type == EscalationRuleType.RESOURCE_BASED:
                return await self._evaluate_resource_based_rule(rule, context)
            elif rule.rule_type == EscalationRuleType.COMPOSITE:
                return await self._evaluate_composite_rule(rule, context)
            else:
                logger.warning(f"Unknown rule type: {rule.rule_type}")
                return None
                
        except Exception as e:
            logger.error(f"Error evaluating rule {rule.id}: {str(e)}")
            return None
    
    async def _evaluate_threshold_rule(
        self,
        rule: EscalationRule,
        context: RuleEvaluationContext,
    ) -> Optional[RuleMatch]:
        """Evaluate threshold-based rule."""
        condition = rule.condition
        matched_conditions = []
        trigger_data = {}
        
        # Check complexity threshold
        if "complexity_threshold" in condition:
            threshold = float(condition["complexity_threshold"])
            if context.complexity_score >= threshold:
                matched_conditions.append(f"complexity >= {threshold}")
                trigger_data["complexity_score"] = context.complexity_score
        
        # Check error rate threshold
        if "error_rate_threshold" in condition:
            threshold = float(condition["error_rate_threshold"])
            if context.error_rate >= threshold:
                matched_conditions.append(f"error_rate >= {threshold}")
                trigger_data["error_rate"] = context.error_rate
        
        # Check retry count threshold
        if "retry_threshold" in condition:
            threshold = int(condition["retry_threshold"])
            if context.retry_count >= threshold:
                matched_conditions.append(f"retry_count >= {threshold}")
                trigger_data["retry_count"] = context.retry_count
        
        # Check custom metrics
        if "custom_metrics" in condition:
            for metric_name, threshold_value in condition["custom_metrics"].items():
                actual_value = context.custom_metrics.get(metric_name, 0)
                if actual_value >= threshold_value:
                    matched_conditions.append(f"{metric_name} >= {threshold_value}")
                    trigger_data[metric_name] = actual_value
        
        # Rule matches if all conditions are met
        require_all = condition.get("require_all", True)
        expected_matches = len([k for k in condition.keys() if k not in ["require_all"]])
        
        if require_all and len(matched_conditions) == expected_matches:
            return RuleMatch(rule, matched_conditions, trigger_data)
        elif not require_all and len(matched_conditions) > 0:
            return RuleMatch(rule, matched_conditions, trigger_data)
        
        return None
    
    async def _evaluate_pattern_rule(
        self,
        rule: EscalationRule,
        context: RuleEvaluationContext,
    ) -> Optional[RuleMatch]:
        """Evaluate pattern matching rule."""
        condition = rule.condition
        matched_conditions = []
        trigger_data = {}
        
        # Check error patterns
        if "error_patterns" in condition:
            patterns = condition["error_patterns"]
            error_messages = context.custom_metrics.get("error_messages", [])
            
            for pattern in patterns:
                regex = re.compile(pattern, re.IGNORECASE)
                for error_msg in error_messages:
                    if regex.search(str(error_msg)):
                        matched_conditions.append(f"error_pattern: {pattern}")
                        trigger_data["matched_error"] = error_msg
                        break
        
        # Check log patterns
        if "log_patterns" in condition:
            patterns = condition["log_patterns"]
            logs = context.custom_metrics.get("logs", [])
            
            for pattern in patterns:
                regex = re.compile(pattern, re.IGNORECASE)
                for log_entry in logs:
                    if regex.search(str(log_entry)):
                        matched_conditions.append(f"log_pattern: {pattern}")
                        trigger_data["matched_log"] = log_entry
                        break
        
        if matched_conditions:
            return RuleMatch(rule, matched_conditions, trigger_data)
        
        return None
    
    async def _evaluate_time_based_rule(
        self,
        rule: EscalationRule,
        context: RuleEvaluationContext,
    ) -> Optional[RuleMatch]:
        """Evaluate time-based rule."""
        condition = rule.condition
        matched_conditions = []
        trigger_data = {}
        
        # Check execution duration
        if "duration_threshold_seconds" in condition:
            threshold = int(condition["duration_threshold_seconds"])
            if context.execution_duration_seconds >= threshold:
                matched_conditions.append(f"duration >= {threshold}s")
                trigger_data["duration_seconds"] = context.execution_duration_seconds
        
        # Check time window (e.g., business hours)
        if "time_window" in condition:
            window = condition["time_window"]
            current_hour = context.timestamp.hour
            
            if "start_hour" in window and "end_hour" in window:
                start = window["start_hour"]
                end = window["end_hour"]
                
                if start <= current_hour < end:
                    matched_conditions.append(f"time_window: {start}-{end}")
                    trigger_data["current_hour"] = current_hour
        
        if matched_conditions:
            return RuleMatch(rule, matched_conditions, trigger_data)
        
        return None
    
    async def _evaluate_resource_based_rule(
        self,
        rule: EscalationRule,
        context: RuleEvaluationContext,
    ) -> Optional[RuleMatch]:
        """Evaluate resource-based rule."""
        condition = rule.condition
        matched_conditions = []
        trigger_data = {}
        
        # Check memory usage
        if "memory_threshold_mb" in condition:
            threshold = float(condition["memory_threshold_mb"])
            memory_usage = context.resource_usage.get("memory_mb", 0)
            if memory_usage >= threshold:
                matched_conditions.append(f"memory >= {threshold}MB")
                trigger_data["memory_mb"] = memory_usage
        
        # Check CPU usage
        if "cpu_threshold_percent" in condition:
            threshold = float(condition["cpu_threshold_percent"])
            cpu_usage = context.resource_usage.get("cpu_percent", 0)
            if cpu_usage >= threshold:
                matched_conditions.append(f"cpu >= {threshold}%")
                trigger_data["cpu_percent"] = cpu_usage
        
        # Check storage usage
        if "storage_threshold_gb" in condition:
            threshold = float(condition["storage_threshold_gb"])
            storage_usage = context.resource_usage.get("storage_gb", 0)
            if storage_usage >= threshold:
                matched_conditions.append(f"storage >= {threshold}GB")
                trigger_data["storage_gb"] = storage_usage
        
        if matched_conditions:
            return RuleMatch(rule, matched_conditions, trigger_data)
        
        return None
    
    async def _evaluate_composite_rule(
        self,
        rule: EscalationRule,
        context: RuleEvaluationContext,
    ) -> Optional[RuleMatch]:
        """Evaluate composite rule (combination of multiple rules)."""
        condition = rule.condition
        matched_conditions = []
        trigger_data = {}
        
        # Evaluate sub-rules
        sub_rules = condition.get("sub_rules", [])
        operator = condition.get("operator", "AND")  # AND or OR
        
        for sub_rule_condition in sub_rules:
            # Create temporary rule for evaluation
            temp_rule = EscalationRule(
                id=rule.id,
                workspace_id=rule.workspace_id,
                project_id=rule.project_id,
                name=f"{rule.name}_sub",
                rule_type=EscalationRuleType(sub_rule_condition.get("type", "threshold")),
                condition=sub_rule_condition,
                severity=rule.severity,
                reason=rule.reason,
                is_enabled=True,
                priority=rule.priority,
            )
            
            # Evaluate sub-rule
            sub_match = await self._evaluate_rule(temp_rule, context)
            if sub_match:
                matched_conditions.extend(sub_match.matched_conditions)
                trigger_data.update(sub_match.trigger_data)
        
        # Check operator logic
        if operator == "AND" and len(matched_conditions) == len(sub_rules):
            return RuleMatch(rule, matched_conditions, trigger_data)
        elif operator == "OR" and len(matched_conditions) > 0:
            return RuleMatch(rule, matched_conditions, trigger_data)
        
        return None
    
    def clear_cache(self):
        """Clear the rule cache."""
        self._rule_cache.clear()
        self._cache_timestamp.clear()


__all__ = ["EscalationRulesEngine", "RuleEvaluationContext", "RuleMatch"]
