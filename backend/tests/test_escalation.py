# -*- coding: utf-8 -*-
"""
Tests for Escalation System

Comprehensive tests for:
- Escalation rules engine
- Priority scorer
- Escalation router
- Escalation notifier
- Escalation tracker
- Escalation service
- Multi-agent controller integration
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from backend.db.models import (
    EscalationRule,
    EscalationEvent,
    EscalationMetric,
    EscalationRuleType,
    EscalationSeverity,
    EscalationReason,
    EscalationStatus,
    AgentInstance,
    AgentDefinition,
    AgentStatus,
)

from backend.services.agents.escalation import (
    EscalationService,
    EscalationRulesEngine,
    RuleEvaluationContext,
    PriorityScorer,
    ComplexityMetrics,
    EscalationRouter,
    EscalationNotifier,
    EscalationTracker,
)


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def sample_rule():
    """Create a sample escalation rule."""
    return EscalationRule(
        id="rule-001",
        workspace_id="workspace-001",
        project_id="project-001",
        name="High Complexity Rule",
        description="Escalate highly complex tasks",
        rule_type=EscalationRuleType.THRESHOLD,
        condition={
            "complexity_threshold": 0.8,
            "error_rate_threshold": 0.5,
        },
        severity=EscalationSeverity.HIGH,
        reason=EscalationReason.COMPLEXITY,
        priority=10,
        is_enabled=True,
        auto_assign=True,
        notify_websocket=True,
        notify_email=False,
        notify_slack=False,
        notification_config={},
        meta_data={},
    )


@pytest.fixture
def sample_context():
    """Create a sample rule evaluation context."""
    return RuleEvaluationContext(
        workspace_id="workspace-001",
        project_id="project-001",
        complexity_score=0.85,
        error_count=5,
        error_rate=0.6,
        resource_usage={"memory_mb": 1024, "cpu_percent": 80},
        execution_duration_seconds=3600,
        retry_count=3,
        custom_metrics={"test_coverage": 60.0},
    )


@pytest.fixture
def sample_agent_definition():
    """Create a sample agent definition."""
    return AgentDefinition(
        id="def-001",
        slug="supervisor-agent",
        name="Supervisor Agent",
        agent_type="supervisor",
        capabilities=["review", "approve", "escalate"],
        is_enabled=True,
    )


@pytest.fixture
def sample_agent_instance():
    """Create a sample agent instance."""
    return AgentInstance(
        id="agent-001",
        workspace_id="workspace-001",
        project_id="project-001",
        definition_id="def-001",
        name="Supervisor 1",
        status=AgentStatus.IDLE,
        config={"max_concurrent_tasks": 5, "handles_escalations": True},
        meta_data={"escalation_success_rate": 0.9},
    )


# ============================================
# Rules Engine Tests
# ============================================

class TestEscalationRulesEngine:
    """Tests for the escalation rules engine."""
    
    @pytest.mark.asyncio
    async def test_threshold_rule_evaluation(self, mock_session, sample_rule, sample_context):
        """Test threshold-based rule evaluation."""
        engine = EscalationRulesEngine()
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_rule]
        mock_session.execute.return_value = mock_result
        
        # Evaluate rules
        matches = await engine.evaluate_rules(mock_session, sample_context)
        
        assert len(matches) > 0
        assert matches[0].rule.id == sample_rule.id
        assert "complexity >= 0.8" in matches[0].matched_conditions
        assert "error_rate >= 0.5" in matches[0].matched_conditions
    
    @pytest.mark.asyncio
    async def test_pattern_rule_evaluation(self, mock_session, sample_context):
        """Test pattern-based rule evaluation."""
        engine = EscalationRulesEngine()
        
        # Create pattern rule
        pattern_rule = EscalationRule(
            id="rule-002",
            workspace_id="workspace-001",
            rule_type=EscalationRuleType.PATTERN,
            condition={
                "error_patterns": ["OutOfMemoryError", "StackOverflowError"],
            },
            severity=EscalationSeverity.CRITICAL,
            reason=EscalationReason.ERROR_RATE,
            is_enabled=True,
            priority=20,
            name="Error Pattern Rule",
        )
        
        # Add error messages to context
        sample_context.custom_metrics["error_messages"] = [
            "OutOfMemoryError: heap space exceeded",
            "Some other error",
        ]
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pattern_rule]
        mock_session.execute.return_value = mock_result
        
        # Evaluate rules
        matches = await engine.evaluate_rules(mock_session, sample_context)
        
        assert len(matches) > 0
        assert matches[0].rule.id == pattern_rule.id
    
    @pytest.mark.asyncio
    async def test_time_based_rule_evaluation(self, mock_session, sample_context):
        """Test time-based rule evaluation."""
        engine = EscalationRulesEngine()
        
        # Create time-based rule
        time_rule = EscalationRule(
            id="rule-003",
            workspace_id="workspace-001",
            rule_type=EscalationRuleType.TIME_BASED,
            condition={
                "duration_threshold_seconds": 3000,
            },
            severity=EscalationSeverity.MEDIUM,
            reason=EscalationReason.TIMEOUT,
            is_enabled=True,
            priority=5,
            name="Timeout Rule",
        )
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [time_rule]
        mock_session.execute.return_value = mock_result
        
        # Evaluate rules
        matches = await engine.evaluate_rules(mock_session, sample_context)
        
        assert len(matches) > 0
        assert matches[0].rule.id == time_rule.id
    
    @pytest.mark.asyncio
    async def test_resource_based_rule_evaluation(self, mock_session, sample_context):
        """Test resource-based rule evaluation."""
        engine = EscalationRulesEngine()
        
        # Create resource-based rule
        resource_rule = EscalationRule(
            id="rule-004",
            workspace_id="workspace-001",
            rule_type=EscalationRuleType.RESOURCE_BASED,
            condition={
                "memory_threshold_mb": 512,
                "cpu_threshold_percent": 75,
            },
            severity=EscalationSeverity.HIGH,
            reason=EscalationReason.RESOURCE_LIMIT,
            is_enabled=True,
            priority=15,
            name="Resource Limit Rule",
        )
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [resource_rule]
        mock_session.execute.return_value = mock_result
        
        # Evaluate rules
        matches = await engine.evaluate_rules(mock_session, sample_context)
        
        assert len(matches) > 0
        assert matches[0].rule.id == resource_rule.id


# ============================================
# Priority Scorer Tests
# ============================================

class TestPriorityScorer:
    """Tests for the priority scorer."""
    
    def test_calculate_complexity_code(self):
        """Test code complexity calculation."""
        scorer = PriorityScorer()
        
        task_data = {
            "files": ["file1.py", "file2.py", "file3.py", "file4.py", "file5.py", "file6.py"],
            "estimated_lines": 500,
            "involves_refactoring": True,
        }
        
        metrics = scorer.calculate_complexity(task_data)
        
        assert metrics.code_complexity > 0
        assert metrics.overall_score > 0
    
    def test_calculate_complexity_dependencies(self):
        """Test dependencies complexity calculation."""
        scorer = PriorityScorer()
        
        task_data = {
            "dependencies": ["dep1", "dep2", "dep3"],
            "third_party_integrations": ["api1", "api2"],
            "involves_api_design": True,
        }
        
        metrics = scorer.calculate_complexity(task_data)
        
        assert metrics.dependencies_complexity > 0
    
    def test_calculate_complexity_data(self):
        """Test data complexity calculation."""
        scorer = PriorityScorer()
        
        task_data = {
            "involves_database_migration": True,
            "involves_schema_changes": True,
            "estimated_data_volume": "large",
            "involves_sensitive_data": True,
        }
        
        metrics = scorer.calculate_complexity(task_data)
        
        assert metrics.data_complexity > 0
    
    def test_calculate_complexity_business_logic(self):
        """Test business logic complexity calculation."""
        scorer = PriorityScorer()
        
        task_data = {
            "business_rules": ["rule1", "rule2", "rule3"],
            "edge_cases": ["case1", "case2", "case3"],
            "involves_security": True,
            "involves_compliance": True,
        }
        
        metrics = scorer.calculate_complexity(task_data)
        
        assert metrics.business_logic_complexity > 0
    
    def test_calculate_priority(self):
        """Test priority calculation."""
        scorer = PriorityScorer()
        
        complexity = ComplexityMetrics(
            overall_score=0.8,
            code_complexity=0.7,
            dependencies_complexity=0.6,
            data_complexity=0.9,
            business_logic_complexity=0.8,
        )
        
        priority = scorer.calculate_priority(
            complexity,
            error_rate=0.5,
            retry_count=4,
            execution_duration_seconds=4000,
        )
        
        assert priority > 0.5
        assert priority <= 1.0
    
    def test_should_escalate(self):
        """Test escalation decision."""
        scorer = PriorityScorer()
        
        assert scorer.should_escalate(0.8, threshold=0.7)
        assert not scorer.should_escalate(0.6, threshold=0.7)


# ============================================
# Router Tests
# ============================================

class TestEscalationRouter:
    """Tests for the escalation router."""
    
    @pytest.mark.asyncio
    async def test_route_escalation(
        self,
        mock_session,
        sample_rule,
        sample_agent_definition,
        sample_agent_instance,
    ):
        """Test escalation routing."""
        router = EscalationRouter()
        
        # Mock database queries
        instance_result = MagicMock()
        instance_result.scalars.return_value.all.return_value = [sample_agent_instance]
        
        def_result = MagicMock()
        def_result.scalar_one_or_none.return_value = sample_agent_definition
        
        event_result = MagicMock()
        event_result.scalars.return_value.all.return_value = []
        
        mock_session.execute.side_effect = [
            instance_result,
            def_result,
            event_result,
        ]
        
        # Route escalation
        selected_agent = await router.route_escalation(
            mock_session,
            "workspace-001",
            "project-001",
            sample_rule,
            {"complexity_score": 0.85},
        )
        
        assert selected_agent is not None
        assert selected_agent.id == sample_agent_instance.id
    
    @pytest.mark.asyncio
    async def test_route_escalation_no_candidates(self, mock_session, sample_rule):
        """Test routing when no candidates available."""
        router = EscalationRouter()
        
        # Mock empty results
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        # Route escalation
        selected_agent = await router.route_escalation(
            mock_session,
            "workspace-001",
            "project-001",
            sample_rule,
            {},
        )
        
        assert selected_agent is None


# ============================================
# Notifier Tests
# ============================================

class TestEscalationNotifier:
    """Tests for the escalation notifier."""
    
    @pytest.mark.asyncio
    async def test_notify_escalation_created(self, sample_rule):
        """Test escalation created notification."""
        notifier = EscalationNotifier()
        
        event = EscalationEvent(
            id="event-001",
            workspace_id="workspace-001",
            project_id="project-001",
            rule_id=sample_rule.id,
            severity=EscalationSeverity.HIGH,
            reason=EscalationReason.COMPLEXITY,
            status=EscalationStatus.PENDING,
            trigger_data={"complexity_score": 0.85},
            context_data={},
        )
        
        # Mock broadcaster
        with patch.object(notifier.broadcaster, 'publish', new_callable=AsyncMock) as mock_publish:
            await notifier.notify_escalation_created(event, sample_rule)
            
            assert mock_publish.called
    
    @pytest.mark.asyncio
    async def test_notify_escalation_assigned(self):
        """Test escalation assigned notification."""
        notifier = EscalationNotifier()
        
        event = EscalationEvent(
            id="event-001",
            workspace_id="workspace-001",
            severity=EscalationSeverity.HIGH,
            reason=EscalationReason.COMPLEXITY,
            status=EscalationStatus.ASSIGNED,
            trigger_data={},
            context_data={},
        )
        
        # Mock broadcaster
        with patch.object(notifier.broadcaster, 'publish', new_callable=AsyncMock) as mock_publish:
            await notifier.notify_escalation_assigned(event, "agent-001")
            
            assert mock_publish.called


# ============================================
# Tracker Tests
# ============================================

class TestEscalationTracker:
    """Tests for the escalation tracker."""
    
    @pytest.mark.asyncio
    async def test_record_metric(self, mock_session):
        """Test metric recording."""
        tracker = EscalationTracker()
        
        metric = await tracker.record_metric(
            mock_session,
            "event-001",
            "workspace-001",
            "complexity_score",
            0.85,
            "score",
            {"category": "complexity"},
        )
        
        assert metric.metric_name == "complexity_score"
        assert metric.metric_value == 0.85
        assert mock_session.add.called
    
    @pytest.mark.asyncio
    async def test_get_escalation_stats(self, mock_session):
        """Test escalation statistics."""
        tracker = EscalationTracker()
        
        # Create sample events
        events = [
            EscalationEvent(
                id=f"event-{i}",
                workspace_id="workspace-001",
                severity=EscalationSeverity.HIGH,
                reason=EscalationReason.COMPLEXITY,
                status=EscalationStatus.RESOLVED if i < 7 else EscalationStatus.PENDING,
                trigger_data={},
                context_data={},
                time_to_assign_seconds=60 if i < 7 else None,
                time_to_resolve_seconds=300 if i < 7 else None,
            )
            for i in range(10)
        ]
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = events
        mock_session.execute.return_value = mock_result
        
        stats = await tracker.get_escalation_stats(mock_session, "workspace-001")
        
        assert stats.total_escalations == 10
        assert stats.resolved == 7
        assert stats.pending == 3
        assert stats.resolution_rate == 0.7
        assert stats.avg_time_to_assign_seconds > 0
        assert stats.avg_time_to_resolve_seconds > 0
    
    @pytest.mark.asyncio
    async def test_detect_patterns(self, mock_session):
        """Test pattern detection."""
        tracker = EscalationTracker()
        
        # Create sample events
        events = [
            EscalationEvent(
                id=f"event-{i}",
                workspace_id="workspace-001",
                severity=EscalationSeverity.HIGH,
                reason=EscalationReason.COMPLEXITY,
                status=EscalationStatus.RESOLVED,
                trigger_data={},
                context_data={},
                source_agent_id="agent-001" if i < 5 else "agent-002",
                created_at=datetime.utcnow() - timedelta(days=i),
            )
            for i in range(10)
        ]
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = events
        mock_session.execute.return_value = mock_result
        
        patterns = await tracker.detect_patterns(mock_session, "workspace-001")
        
        assert "most_escalating_agent" in patterns
        assert "most_common_reason" in patterns
        assert "total_escalations" in patterns


# ============================================
# Escalation Service Tests
# ============================================

class TestEscalationService:
    """Tests for the escalation service."""
    
    @pytest.mark.asyncio
    async def test_check_escalation_triggered(self, mock_session, sample_context, sample_rule):
        """Test escalation check when rule matches."""
        service = EscalationService()
        
        # Mock rule evaluation
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_rule]
        mock_session.execute.return_value = mock_result
        
        event = await service.check_escalation(mock_session, sample_context)
        
        assert event is not None
        assert event.severity == sample_rule.severity
        assert event.reason == sample_rule.reason
    
    @pytest.mark.asyncio
    async def test_check_escalation_not_triggered(self, mock_session, sample_context):
        """Test escalation check when no rules match."""
        service = EscalationService()
        
        # Mock empty results
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        event = await service.check_escalation(mock_session, sample_context)
        
        assert event is None
    
    @pytest.mark.asyncio
    async def test_create_rule(self, mock_session):
        """Test rule creation."""
        service = EscalationService()
        
        rule = await service.create_rule(
            mock_session,
            workspace_id="workspace-001",
            name="Test Rule",
            rule_type="threshold",
            condition={"complexity_threshold": 0.7},
            severity="high",
            reason="complexity",
        )
        
        assert rule.name == "Test Rule"
        assert rule.rule_type == EscalationRuleType.THRESHOLD
        assert mock_session.add.called
    
    @pytest.mark.asyncio
    async def test_resolve_escalation(self, mock_session):
        """Test escalation resolution."""
        service = EscalationService()
        
        event = EscalationEvent(
            id="event-001",
            workspace_id="workspace-001",
            severity=EscalationSeverity.HIGH,
            reason=EscalationReason.COMPLEXITY,
            status=EscalationStatus.ASSIGNED,
            trigger_data={},
            context_data={},
            created_at=datetime.utcnow(),
        )
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_session.execute.return_value = mock_result
        
        with patch.object(service.notifier, 'notify_escalation_resolved', new_callable=AsyncMock):
            await service.resolve_escalation(
                mock_session,
                "event-001",
                {"resolution": "Fixed the issue"},
            )
        
        assert event.status == EscalationStatus.RESOLVED
        assert event.resolution_data is not None


# ============================================
# Integration Tests
# ============================================

class TestEscalationIntegration:
    """Integration tests for the escalation system."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_escalation(
        self,
        mock_session,
        sample_rule,
        sample_context,
        sample_agent_instance,
        sample_agent_definition,
    ):
        """Test end-to-end escalation workflow."""
        service = EscalationService()
        
        # Mock rule query
        rule_result = MagicMock()
        rule_result.scalars.return_value.all.return_value = [sample_rule]
        
        # Mock agent queries
        instance_result = MagicMock()
        instance_result.scalars.return_value.all.return_value = [sample_agent_instance]
        
        def_result = MagicMock()
        def_result.scalar_one_or_none.return_value = sample_agent_definition
        
        event_result = MagicMock()
        event_result.scalars.return_value.all.return_value = []
        
        mock_session.execute.side_effect = [
            rule_result,
            instance_result,
            def_result,
            event_result,
        ]
        
        # Check escalation
        event = await service.check_escalation(mock_session, sample_context)
        
        assert event is not None
        assert event.status in [EscalationStatus.PENDING, EscalationStatus.ASSIGNED]
        assert mock_session.add.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
