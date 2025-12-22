# -*- coding: utf-8 -*-
"""backend.services.evaluation

AI Evaluation Framework services package.

This package provides services for evaluating code quality, safety, and agent performance
using LLM-as-a-Judge, regression testing, and determinism testing.
"""

from .judge import LLMJudgeService
from .scenarios import ScenarioLibrary
from .evaluation_service import EvaluationService

__all__ = [
    "LLMJudgeService",
    "ScenarioLibrary", 
    "EvaluationService"
]