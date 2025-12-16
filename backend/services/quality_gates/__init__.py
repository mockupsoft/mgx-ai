# -*- coding: utf-8 -*-
"""backend.services.quality_gates

Quality Gate Engine for automated code quality checks and enforcement.

This module provides a comprehensive quality gate system that evaluates
code against various quality criteria including linting, coverage,
performance, security, complexity, and type checking.
"""

# Import all gate implementations to trigger registration
from . import gates  # noqa: F401

from .gate_manager import QualityGateManager, get_gate_manager
from .gates.base_gate import BaseQualityGate, GateResult, GateConfiguration

__all__ = [
    "QualityGateManager",
    "get_gate_manager",
    "BaseQualityGate",
    "GateResult",
    "GateConfiguration",
]