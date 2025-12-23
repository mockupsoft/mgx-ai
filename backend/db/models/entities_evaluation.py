# -*- coding: utf-8 -*-
"""backend.db.models.entities_evaluation

AI Evaluation Framework database models for measuring code quality, safety, and agent performance.
"""

from datetime import datetime
from uuid import uuid4
from typing import Optional, Dict, Any, List
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from .base import Base, SerializationMixin, TimestampMixin
from .enums import (
    LLMProvider,
    EvaluationType,
    EvaluationStatus,
    ComplexityLevel,
    RegressionAlertType,
)


class EvaluationScenario(Base, TimestampMixin, SerializationMixin):
    """Test scenarios for AI evaluation framework."""
    
    __tablename__ = "evaluation_scenarios"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    
    # Scenario categorization
    category = Column(String(100), nullable=False, index=True)  # e.g., "api_development", "frontend_ui"
    complexity_level = Column(SQLEnum(ComplexityLevel), nullable=False, index=True)
    language = Column(String(50), nullable=True)  # Python, JavaScript, etc.
    framework = Column(String(100), nullable=True)  # FastAPI, React, etc.
    
    # Task definition
    prompt = Column(Text, nullable=False)
    expected_output = Column(Text, nullable=True)
    evaluation_criteria = Column(JSON, nullable=False)  # Scoring criteria
    
    # Versioning for regression testing
    version = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Metadata
    estimated_duration_minutes = Column(Integer, nullable=True)
    tags = Column(JSON, nullable=True)  # List of tags for categorization
    created_by = Column(String(100), nullable=True)
    
    # Relationships
    evaluations = relationship("EvaluationResult", back_populates="scenario", cascade="all, delete-orphan")
    regression_tests = relationship("RegressionTest", back_populates="scenario", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<EvaluationScenario(name='{self.name}', complexity='{self.complexity_level}', version={self.version})>"


class EvaluationResult(Base, TimestampMixin, SerializationMixin):
    """Results from LLM-as-a-Judge evaluations."""
    
    __tablename__ = "evaluation_results"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    
    # Links to scenario and execution context
    scenario_id = Column(String(36), ForeignKey("evaluation_scenarios.id"), nullable=False, index=True)
    task_id = Column(String(36), nullable=True, index=True)
    task_run_id = Column(String(36), nullable=True, index=True)
    commit_hash = Column(String(40), nullable=True, index=True)
    branch_name = Column(String(255), nullable=True, index=True)
    
    # Evaluation execution details
    evaluation_type = Column(SQLEnum(EvaluationType), nullable=False, index=True)
    status = Column(SQLEnum(EvaluationStatus), nullable=False, index=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    
    # Judge configuration
    judge_model = Column(String(100), nullable=False)  # "gpt-4o", "claude-3-opus", etc.
    judge_provider = Column(SQLEnum(LLMProvider), nullable=False)
    judge_version = Column(String(50), nullable=True)
    judge_temperature = Column(Float, default=0.1, nullable=False)
    
    # LLM-as-a-Judge scores (0-10 scale)
    code_safety_score = Column(Float, nullable=True)
    code_quality_score = Column(Float, nullable=True)
    best_practices_score = Column(Float, nullable=True)
    performance_score = Column(Float, nullable=True)
    readability_score = Column(Float, nullable=True)
    functionality_score = Column(Float, nullable=True)
    security_score = Column(Float, nullable=True)
    maintainability_score = Column(Float, nullable=True)
    
    # Overall metrics
    overall_score = Column(Float, nullable=False, index=True)
    weighted_score = Column(Float, nullable=True)
    percentile_rank = Column(Float, nullable=True)
    
    # Detailed evaluation feedback
    judge_feedback = Column(Text, nullable=True)
    improvement_suggestions = Column(JSON, nullable=True)
    code_violations = Column(JSON, nullable=True)
    best_practices_mentioned = Column(JSON, nullable=True)
    
    # Output and comparison
    agent_output = Column(Text, nullable=True)
    expected_output = Column(Text, nullable=True)
    similarity_score = Column(Float, nullable=True)
    semantic_similarity = Column(Float, nullable=True)
    
    # Cost tracking
    judge_tokens_used = Column(Integer, nullable=True)
    judge_cost_usd = Column(Float, nullable=True)
    total_cost_usd = Column(Float, nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    
    # Relationships
    scenario = relationship("EvaluationScenario", back_populates="evaluations")
    regression_metrics = relationship("RegressionMetric", back_populates="evaluation_result", uselist=False)
    pass_k_metrics = relationship("PassKMetric", back_populates="evaluation_result", uselist=False)
    
    __table_args__ = (
        Index('idx_evaluation_scenario_status', 'scenario_id', 'status'),
        Index('idx_evaluation_commit_branch', 'commit_hash', 'branch_name'),
        Index('idx_evaluation_overall_score', 'overall_score'),
        Index('idx_evaluation_completed_at', 'completed_at'),
    )
    
    def __repr__(self):
        return f"<EvaluationResult(scenario='{self.scenario_id}', score={self.overall_score}, status='{self.status}')>"


class RegressionTest(Base, TimestampMixin, SerializationMixin):
    """Regression test tracking for prompt/model changes."""
    
    __tablename__ = "regression_tests"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    
    # Links
    scenario_id = Column(String(36), ForeignKey("evaluation_scenarios.id"), nullable=False, index=True)
    baseline_evaluation_id = Column(String(36), ForeignKey("evaluation_results.id"), nullable=True, index=True)
    current_evaluation_id = Column(String(36), ForeignKey("evaluation_results.id"), nullable=True, index=True)
    
    # Test context
    commit_hash = Column(String(40), nullable=False, index=True)
    branch_name = Column(String(255), nullable=False, index=True)
    trigger_type = Column(String(50), nullable=False)  # "commit", "pr", "manual", "scheduled"
    trigger_reason = Column(Text, nullable=True)
    
    # Regression analysis
    baseline_score = Column(Float, nullable=True)
    current_score = Column(Float, nullable=True)
    score_change = Column(Float, nullable=True)
    score_change_percentage = Column(Float, nullable=True)
    
    # Alert configuration
    degradation_threshold_percentage = Column(Float, default=5.0, nullable=False)
    alert_triggered = Column(Boolean, default=False, nullable=False)
    alert_type = Column(SQLEnum(RegressionAlertType), nullable=True)
    alert_message = Column(Text, nullable=True)
    
    # Status
    status = Column(String(50), default="pending", nullable=False)
    is_blocking = Column(Boolean, default=False, nullable=False)
    
    # Analysis details
    detailed_analysis = Column(JSON, nullable=True)
    recommendations = Column(JSON, nullable=True)
    
    # Relationships
    scenario = relationship("EvaluationScenario", back_populates="regression_tests")
    baseline_evaluation = relationship("EvaluationResult", foreign_keys=[baseline_evaluation_id])
    current_evaluation = relationship("EvaluationResult", foreign_keys=[current_evaluation_id])
    
    __table_args__ = (
        Index('idx_regression_commit_branch', 'commit_hash', 'branch_name'),
        Index('idx_regression_status', 'status'),
        Index('idx_regression_alert_triggered', 'alert_triggered'),
        Index('idx_regression_score_change', 'score_change_percentage'),
    )
    
    def __repr__(self):
        return f"<RegressionTest(scenario='{self.scenario_id}', change={self.score_change_percentage}%, alert={self.alert_triggered})>"


class PassKMetric(Base, TimestampMixin, SerializationMixin):
    """Pass@k determinism and reliability metrics."""
    
    __tablename__ = "pass_k_metrics"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    
    # Links
    scenario_id = Column(String(36), ForeignKey("evaluation_scenarios.id"), nullable=False, index=True)
    evaluation_result_id = Column(String(36), ForeignKey("evaluation_results.id"), nullable=False, index=True)
    
    # Test configuration
    k_value = Column(Integer, nullable=False, index=True)  # k in Pass@k (1, 5, 10, 20)
    total_runs = Column(Integer, nullable=False)
    successful_runs = Column(Integer, nullable=False)
    
    # Pass@k calculation
    pass_at_k = Column(Float, nullable=False, index=True)
    confidence_interval_lower = Column(Float, nullable=True)
    confidence_interval_upper = Column(Float, nullable=True)
    confidence_level = Column(Float, default=0.95, nullable=False)
    
    # Success criteria for this test
    success_threshold = Column(Float, default=7.0, nullable=False)  # Minimum score to count as success
    success_criteria = Column(JSON, nullable=False)  # Detailed success criteria
    
    # Output variance analysis
    score_variance = Column(Float, nullable=True)
    score_std_deviation = Column(Float, nullable=True)
    score_range_min = Column(Float, nullable=True)
    score_range_max = Column(Float, nullable=True)
    
    # Failure pattern analysis
    failure_patterns = Column(JSON, nullable=True)
    common_failures = Column(JSON, nullable=True)
    error_categories = Column(JSON, nullable=True)
    
    # Reliability metrics
    consistency_score = Column(Float, nullable=True)
    reliability_grade = Column(String(10), nullable=True)  # A, B, C, D, F
    
    # Context
    run_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    run_duration_ms = Column(Integer, nullable=True)
    
    # Relationships
    scenario = relationship("EvaluationScenario")
    evaluation_result = relationship("EvaluationResult", back_populates="pass_k_metrics")
    
    __table_args__ = (
        Index('idx_pass_k_scenario_k', 'scenario_id', 'k_value'),
        Index('idx_pass_k_pass_rate', 'pass_at_k'),
        Index('idx_pass_k_reliability', 'reliability_grade'),
    )
    
    def __repr__(self):
        return f"<PassKMetric(scenario='{self.scenario_id}', k={self.k_value}, pass_rate={self.pass_at_k:.2f})>"


class RegressionMetric(Base, TimestampMixin, SerializationMixin):
    """Historical metrics for regression detection."""
    
    __tablename__ = "regression_metrics"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    
    # Links
    evaluation_result_id = Column(String(36), ForeignKey("evaluation_results.id"), nullable=False, unique=True, index=True)
    
    # Historical comparison
    historical_avg_score = Column(Float, nullable=True)
    historical_std_deviation = Column(Float, nullable=True)
    historical_median_score = Column(Float, nullable=True)
    historical_percentile_25 = Column(Float, nullable=True)
    historical_percentile_75 = Column(Float, nullable=True)
    historical_percentile_90 = Column(Float, nullable=True)
    
    # Trend analysis
    trend_direction = Column(String(20), nullable=True)  # "improving", "declining", "stable"
    trend_strength = Column(Float, nullable=True)  # Correlation coefficient
    last_significant_change = Column(DateTime, nullable=True)
    improvement_count = Column(Integer, default=0, nullable=False)
    degradation_count = Column(Integer, default=0, nullable=False)
    
    # Benchmarking
    vs_best_score = Column(Float, nullable=True)
    vs_worst_score = Column(Float, nullable=True)
    vs_median_score = Column(Float, nullable=True)
    
    # Quality gates
    quality_gate_threshold = Column(Float, default=7.0, nullable=False)
    quality_gate_status = Column(String(20), nullable=True)  # "pass", "fail", "warning"
    
    # Relationships
    evaluation_result = relationship("EvaluationResult", back_populates="regression_metrics")
    
    def __repr__(self):
        return f"<RegressionMetric(eval='{self.evaluation_result_id}', trend='{self.trend_direction}', status='{self.quality_gate_status}')>"


class EvaluationDashboard(Base, TimestampMixin, SerializationMixin):
    """Dashboard configuration and cached metrics."""
    
    __tablename__ = "evaluation_dashboard"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    
    # Dashboard configuration
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    dashboard_type = Column(String(50), nullable=False)  # "overview", "regression", "reliability", "cost"
    
    # Metrics configuration
    time_range_days = Column(Integer, default=30, nullable=False)
    scenarios_filter = Column(JSON, nullable=True)
    metrics_to_display = Column(JSON, nullable=False)
    
    # Cached metrics (updated periodically)
    cached_metrics = Column(JSON, nullable=True)
    last_cache_update = Column(DateTime, nullable=True)
    cache_ttl_minutes = Column(Integer, default=60, nullable=False)
    
    # Alert configuration
    alert_thresholds = Column(JSON, nullable=True)
    notification_channels = Column(JSON, nullable=True)
    
    # Access control
    is_public = Column(Boolean, default=False, nullable=False)
    workspace_id = Column(String(36), nullable=True, index=True)
    
    def __repr__(self):
        return f"<EvaluationDashboard(name='{self.name}', type='{self.dashboard_type}')>"


class EvaluationAlert(Base, TimestampMixin, SerializationMixin):
    """Alerts for evaluation degradation and quality issues."""
    
    __tablename__ = "evaluation_alerts"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    
    # Alert context
    alert_type = Column(SQLEnum(RegressionAlertType), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)  # "low", "medium", "high", "critical"
    
    # Links
    scenario_id = Column(String(36), nullable=True, index=True)
    regression_test_id = Column(String(36), nullable=True, index=True)
    evaluation_result_id = Column(String(36), nullable=True, index=True)
    
    # Alert details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    metric_name = Column(String(100), nullable=True)
    metric_value = Column(Float, nullable=True)
    threshold_value = Column(Float, nullable=True)
    
    # Status tracking
    status = Column(String(50), default="active", nullable=False, index=True)  # "active", "acknowledged", "resolved"
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    # Context
    commit_hash = Column(String(40), nullable=True, index=True)
    branch_name = Column(String(255), nullable=True, index=True)
    triggered_by = Column(String(100), nullable=True)
    extra_metadata = Column("metadata", JSON, nullable=True)
    
    def __repr__(self):
        return f"<EvaluationAlert(type='{self.alert_type}', severity='{self.severity}', status='{self.status}')>"