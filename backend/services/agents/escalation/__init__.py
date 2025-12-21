# -*- coding: utf-8 -*-
"""
Escalation Service Package

Provides escalation logic for multi-agent controller system.
"""

from .escalation_service import EscalationService
from .rules_engine import EscalationRulesEngine, RuleEvaluationContext
from .priority_scorer import PriorityScorer
from .router import EscalationRouter
from .notifier import EscalationNotifier
from .tracker import EscalationTracker

__all__ = [
    "EscalationService",
    "EscalationRulesEngine",
    "RuleEvaluationContext",
    "PriorityScorer",
    "EscalationRouter",
    "EscalationNotifier",
    "EscalationTracker",
]
