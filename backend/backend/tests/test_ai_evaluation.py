# -*- coding: utf-8 -*-
"""backend.tests.test_ai_evaluation

Comprehensive test suite for the AI evaluation framework.
Tests LLM-as-a-Judge evaluation, regression testing, determinism testing, and dashboard functionality.
"""

import pytest
import asyncio
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from backend.services.evaluation.judge import LLMJudgeService
from backend.services.evaluation.scenarios import ScenarioLibrary
from backend.services.evaluation.evaluation_service import EvaluationService
from backend.db.models.entities_evaluation import (
    EvaluationScenario,
    EvaluationResult,
    RegressionTest,
    PassKMetric,
    EvaluationAlert
)
from backend.db.models.enums import (
    EvaluationType,
    EvaluationStatus,
    ComplexityLevel,
    RegressionAlertType,
    LLMProvider
)


class TestScenarioLibrary:
    """Test the scenario library functionality."""
    
    def test_scenario_library_initialization(self):
        """Test that scenario library initializes with correct scenarios."""
        library = ScenarioLibrary()
        scenarios = library.scenarios
        
        assert len(scenarios) > 0
        assert "create_simple_endpoint" in scenarios
        assert "microservice" in scenarios
        
        # Check scenario structure
        simple_endpoint = scenarios["create_simple_endpoint"]
        assert "name" in simple_endpoint
        assert "description" in simple_endpoint
        assert "category" in simple_endpoint
        assert "complexity_level" in simple_endpoint
        assert "prompt" in simple_endpoint
        assert "evaluation_criteria" in simple_endpoint
        
        # Check complexity distribution
        easy_scenarios = library.get_scenarios(complexity=ComplexityLevel.EASY)
        hard_scenarios = library.get_scenarios(complexity=ComplexityLevel.HARD)
        
        assert len(easy_scenarios) > 0
        assert len(hard_scenarios) > 0
    
    def test_scenario_filtering(self):
        """Test scenario filtering by category and complexity."""
        library = ScenarioLibrary()
        
        # Filter by category
        api_scenarios = library.get_scenarios(category="api_development")
        assert len(api_scenarios) > 0
        for scenario in api_scenarios:
            assert scenario["category"] == "api_development"
        
        # Filter by complexity
        easy_scenarios = library.get_scenarios(complexity=ComplexityLevel.EASY)
        assert len(easy_scenarios) > 0
        for scenario in easy_scenarios:
            assert scenario["complexity_level"] == ComplexityLevel.EASY
    
    def test_baseline_scenarios(self):
        """Test baseline scenarios selection."""
        library = ScenarioLibrary()
        baseline_scenarios = library.get_baseline_scenarios()
        
        assert len(baseline_scenarios) > 0
        
        # Check complexity distribution
        complexity_counts = {}
        for scenario in baseline_scenarios:
            level = scenario["complexity_level"]
            complexity_counts[level] = complexity_counts.get(level, 0) + 1
        
        # Should have scenarios from different complexity levels
        assert ComplexityLevel.EASY in complexity_counts
        assert ComplexityLevel.MEDIUM in complexity_counts
    
    def test_regression_scenarios(self):
        """Test regression scenarios selection."""
        library = ScenarioLibrary()
        regression_scenarios = library.get_regression_scenarios()
        
        assert len(regression_scenarios) > 0
        
        # Should include key development scenarios
        expected_scenarios = [
            "create_simple_endpoint",
            "simple_component", 
            "database_model",
            "restful_api",
            "react_app",
            "microservice"
        ]
        
        scenario_names = [s["name"] for s in regression_scenarios if s]
        for expected in expected_scenarios:
            assert any(expected in name for name in scenario_names)


class TestLLMJudgeService:
    """Test the LLM-as-a-Judge service."""
    
    @pytest.fixture
    def judge_service(self):
        """Create judge service instance."""
        return LLMJudgeService()
    
    @pytest.fixture
    def sample_scenario(self):
        """Create sample evaluation scenario."""
        return EvaluationScenario(
            name="Test Scenario",
            description="A test scenario for evaluation",
            category="test",
            complexity_level=ComplexityLevel.EASY,
            language="Python",
            framework="FastAPI",
            prompt="Create a simple function that adds two numbers",
            evaluation_criteria={
                "code_quality": {
                    "weight": 1.0,
                    "requirements": ["Clear function name", "Type hints", "Error handling"]
                }
            }
        )
    
    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM response for testing."""
        return {
            "content": json.dumps({
                "scores": {
                    "code_safety": 8.0,
                    "code_quality": 7.5,
                    "best_practices": 8.5,
                    "performance": 7.0,
                    "readability": 8.0,
                    "functionality": 9.0,
                    "security": 8.5,
                    "maintainability": 7.5
                },
                "overall_feedback": "Good implementation with minor areas for improvement.",
                "improvement_suggestions": [
                    "Add more comprehensive error handling",
                    "Improve variable naming consistency"
                ],
                "code_violations": [
                    {
                        "type": "best_practice",
                        "description": "Missing input validation",
                        "severity": "medium",
                        "line_number": 42
                    }
                ],
                "best_practices_mentioned": [
                    "DRY principle",
                    "Error handling",
                    "Type hints"
                ]
            }),
            "total_tokens": 1500,
            "estimated_cost": 0.0075
        }
    
    @pytest.mark.asyncio
    async def test_construct_evaluation_prompt(self, judge_service, sample_scenario):
        """Test evaluation prompt construction."""
        agent_output = "def add(a, b): return a + b"
        context = {"additional_info": "test"}
        
        prompt = judge_service._construct_evaluation_prompt(agent_output, sample_scenario, context)
        
        assert "You are an expert code reviewer" in prompt
        assert sample_scenario.name in prompt
        assert agent_output in prompt
        assert "EVALUATION DIMENSIONS" in prompt
        assert "Code Safety" in prompt
        assert "Code Quality" in prompt
    
    @pytest.mark.asyncio
    async def test_parse_judge_response(self, judge_service, mock_llm_response):
        """Test parsing of judge LLM response."""
        scores, feedback = judge_service._parse_judge_response(mock_llm_response)
        
        assert "code_safety" in scores
        assert "code_quality" in scores
        assert scores["code_safety"] == 8.0
        assert scores["code_quality"] == 7.5
        
        assert "overall_feedback" in feedback
        assert "improvement_suggestions" in feedback
        assert "code_violations" in feedback
        assert "best_practices_mentioned" in feedback
    
    def test_calculate_weighted_score(self, judge_service):
        """Test weighted score calculation."""
        scores = {
            "code_safety": 8.0,
            "code_quality": 7.5,
            "best_practices": 8.5,
            "performance": 7.0,
            "readability": 8.0,
            "functionality": 9.0,
            "security": 8.5,
            "maintainability": 7.5
        }
        
        weighted_score = judge_service._calculate_weighted_score(scores)
        
        # Should be between 0 and 10
        assert 0 <= weighted_score <= 10
        
        # Should be reasonable (around 8 for these scores)
        assert 7.5 <= weighted_score <= 9.0
    
    def test_exact_similarity_calculation(self, judge_service):
        """Test exact similarity calculation."""
        text1 = "def add(a, b): return a + b"
        text2 = "def add_numbers(x, y): return x + y"
        
        similarity = judge_service._calculate_exact_similarity(text1, text2)
        
        assert 0 <= similarity <= 1
        # Should have some similarity due to common words
        assert similarity > 0
        
        # Different texts should have lower similarity
        text3 = "class Calculator: pass"
        similarity2 = judge_service._calculate_exact_similarity(text1, text3)
        assert similarity2 < similarity
    
    @pytest.mark.asyncio
    async def test_semantic_similarity_calculation(self, judge_service):
        """Test semantic similarity calculation."""
        # Mock the LLM service to avoid actual API calls
        with patch.object(judge_service.llm_service, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_response = Mock()
            mock_response.content = "0.85"
            mock_generate.return_value = mock_response
            
            text1 = "def add(a, b): return a + b"
            text2 = "function sum(x, y) { return x + y; }"
            
            similarity = await judge_service._calculate_semantic_similarity(
                text1, text2, {"model": "gpt-4o"}
            )
            
            assert 0 <= similarity <= 1
            assert similarity > 0.8  # Should recognize semantic similarity


class TestEvaluationService:
    """Test the core evaluation service."""
    
    @pytest.fixture
    def evaluation_service(self):
        """Create evaluation service instance."""
        return EvaluationService()
    
    @pytest.fixture
    def mock_scenario(self):
        """Create mock evaluation scenario."""
        scenario = Mock(spec=EvaluationScenario)
        scenario.id = "test-scenario-123"
        scenario.name = "Test Scenario"
        scenario.description = "A test scenario"
        scenario.category = "test"
        scenario.complexity_level = ComplexityLevel.EASY
        scenario.prompt = "Create a simple function"
        scenario.expected_output = "Expected output"
        scenario.evaluation_criteria = {"test": {"weight": 1.0, "requirements": []}}
        return scenario
    
    @pytest.fixture
    def mock_judge_config(self):
        """Mock judge configuration."""
        return {
            "model": "gpt-4o",
            "provider": "openai",
            "temperature": 0.1,
            "max_tokens": 2000
        }
    
    def test_evaluation_service_initialization(self, evaluation_service):
        """Test evaluation service initialization."""
        assert evaluation_service.judge_service is not None
        assert evaluation_service.scenario_library is not None
        assert evaluation_service.executor is not None
    
    @pytest.mark.asyncio
    async def test_get_scenario(self, evaluation_service, mock_scenario):
        """Test getting scenario by ID."""
        with patch('backend.services.evaluation.evaluation_service.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = Mock(return_value=False)
            
            mock_db.query.return_value.filter.return_value.first.return_value = mock_scenario
            
            result = await evaluation_service._get_scenario("test-scenario-123")
            
            assert result == mock_scenario
            mock_db.query.assert_called_once()
    
    def test_calculate_variance(self, evaluation_service):
        """Test variance calculation."""
        scores = [8.0, 7.5, 8.5, 7.0, 8.2]
        variance = evaluation_service._calculate_variance(scores)
        
        assert variance >= 0
        assert isinstance(variance, float)
        
        # Test with single score
        single_variance = evaluation_service._calculate_variance([8.0])
        assert single_variance == 0.0
    
    def test_get_reliability_grade(self, evaluation_service):
        """Test reliability grade calculation."""
        # Test different pass rates
        assert evaluation_service._get_reliability_grade(0.95) == "A"
        assert evaluation_service._get_reliability_grade(0.85) == "B"
        assert evaluation_service._get_reliability_grade(0.75) == "C"
        assert evaluation_service._get_reliability_grade(0.65) == "D"
        assert evaluation_service._get_reliability_grade(0.50) == "F"
        assert evaluation_service._get_reliability_grade(0.30) == "F"
    
    def test_calculate_consistency_score(self, evaluation_service):
        """Test consistency score calculation."""
        # Perfect consistency
        consistent_scores = [8.0, 8.0, 8.0, 8.0, 8.0]
        consistency = evaluation_service._calculate_consistency_score(consistent_scores)
        assert abs(consistency - 1.0) < 0.01  # Should be close to 1
        
        # High variance
        inconsistent_scores = [2.0, 9.0, 3.0, 8.0, 1.0]
        consistency = evaluation_service._calculate_consistency_score(inconsistent_scores)
        assert consistency < 0.5  # Should be low
        
        # Single score
        single_consistency = evaluation_service._calculate_consistency_score([8.0])
        assert single_consistency == 1.0
    
    def test_calculate_score_trends(self, evaluation_service):
        """Test score trends calculation."""
        # Create mock evaluation results
        results = []
        for i in range(5):
            result = Mock()
            result.completed_at = datetime.now() - timedelta(days=i)
            result.overall_score = 8.0 - i * 0.2  # Declining scores
            results.append(result)
        
        trends = evaluation_service._calculate_score_trends(results)
        
        assert len(trends) > 0
        for trend in trends:
            assert "date" in trend
            assert "avg_score" in trend
            assert "count" in trend
        
        # Should show declining trend
        assert trends[0]["avg_score"] > trends[-1]["avg_score"]
    
    def test_calculate_dimension_breakdown(self, evaluation_service):
        """Test dimension breakdown calculation."""
        # Create mock results with different scores
        results = []
        dimensions = [
            "code_safety_score", "code_quality_score", "best_practices_score",
            "performance_score", "readability_score", "functionality_score",
            "security_score", "maintainability_score"
        ]
        
        for i in range(3):
            result = Mock()
            for dim in dimensions:
                setattr(result, dim, 7.0 + i)  # Different scores for each result
            results.append(result)
        
        breakdown = evaluation_service._calculate_dimension_breakdown(results)
        
        assert len(breakdown) == len(dimensions)
        for dim in dimensions:
            assert dim in breakdown
            assert 0 <= breakdown[dim] <= 10
            # Should be average of scores
            assert breakdown[dim] == 8.0  # (7+8+9)/3


class TestRegressionTesting:
    """Test regression testing functionality."""
    
    @pytest.fixture
    def evaluation_service(self):
        """Create evaluation service instance."""
        return EvaluationService()
    
    @pytest.fixture
    def mock_baseline_result(self):
        """Create mock baseline evaluation result."""
        result = Mock(spec=EvaluationResult)
        result.id = "baseline-123"
        result.overall_score = 8.5
        result.status = EvaluationStatus.COMPLETED
        return result
    
    @pytest.fixture
    def mock_current_result(self):
        """Create mock current evaluation result."""
        result = Mock(spec=EvaluationResult)
        result.id = "current-456"
        result.overall_score = 8.0  # Lower than baseline
        result.status = EvaluationStatus.COMPLETED
        result.started_at = datetime.utcnow()
        result.completed_at = datetime.utcnow()
        result.execution_time_ms = 1000
        result.judge_model = "gpt-4o"
        result.judge_provider = LLMProvider.OPENAI
        return result
    
    @pytest.mark.asyncio
    async def test_run_regression_test_no_regression(self, evaluation_service, mock_baseline_result, mock_current_result):
        """Test regression test with no significant regression."""
        with patch.object(evaluation_service, '_get_scenario') as mock_get_scenario, \
             patch.object(evaluation_service, '_get_baseline_evaluation') as mock_get_baseline, \
             patch.object(evaluation_service.judge_service, 'evaluate_code') as mock_evaluate, \
             patch.object(evaluation_service, '_save_regression_test') as mock_save_regression, \
             patch.object(evaluation_service, '_create_regression_alert') as mock_create_alert:
            
            # Setup mocks
            mock_scenario = Mock()
            mock_get_scenario.return_value = mock_scenario
            mock_get_baseline.return_value = mock_baseline_result
            mock_evaluate.return_value = mock_current_result
            
            # Run regression test
            result = await evaluation_service.run_regression_test(
                scenario_id="test-scenario",
                current_agent_output="test output",
                judge_config={"model": "gpt-4o"},
                commit_hash="abc123",
                branch_name="main",
                threshold_degradation=5.0
            )
            
            # Verify results
            assert isinstance(result, RegressionTest)
            assert result.scenario_id == "test-scenario"
            assert result.commit_hash == "abc123"
            assert result.branch_name == "main"
            assert result.score_change == -0.5  # 8.0 - 8.5
            assert result.score_change_percentage == pytest.approx(-5.88)  # -0.5/8.5 * 100
            assert not result.alert_triggered  # Should not trigger alert for small regression
            
            # Verify calls
            mock_evaluate.assert_called_once()
            mock_save_regression.assert_called_once()
            mock_create_alert.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_run_regression_test_with_regression(self, evaluation_service, mock_baseline_result):
        """Test regression test with significant regression."""
        mock_current_result = Mock(spec=EvaluationResult)
        mock_current_result.id = "current-456"
        mock_current_result.overall_score = 7.0  # Much lower than baseline (8.5)
        mock_current_result.status = EvaluationStatus.COMPLETED
        mock_current_result.started_at = datetime.utcnow()
        mock_current_result.completed_at = datetime.utcnow()
        mock_current_result.execution_time_ms = 1000
        mock_current_result.judge_model = "gpt-4o"
        mock_current_result.judge_provider = LLMProvider.OPENAI
        
        with patch.object(evaluation_service, '_get_scenario') as mock_get_scenario, \
             patch.object(evaluation_service, '_get_baseline_evaluation') as mock_get_baseline, \
             patch.object(evaluation_service.judge_service, 'evaluate_code') as mock_evaluate, \
             patch.object(evaluation_service, '_save_regression_test') as mock_save_regression, \
             patch.object(evaluation_service, '_create_regression_alert') as mock_create_alert:
            
            # Setup mocks
            mock_scenario = Mock()
            mock_get_scenario.return_value = mock_scenario
            mock_get_baseline.return_value = mock_baseline_result
            mock_evaluate.return_value = mock_current_result
            
            # Run regression test
            result = await evaluation_service.run_regression_test(
                scenario_id="test-scenario",
                current_agent_output="test output",
                judge_config={"model": "gpt-4o"},
                commit_hash="abc123",
                branch_name="main",
                threshold_degradation=5.0
            )
            
            # Verify regression detected
            assert result.score_change == -1.5  # 7.0 - 8.5
            assert result.score_change_percentage == pytest.approx(-17.65)  # -1.5/8.5 * 100
            assert result.alert_triggered  # Should trigger alert
            assert result.alert_type == RegressionAlertType.SCORE_DEGRADATION
            
            # Verify alert creation
            mock_create_alert.assert_called_once()


class TestDeterminismTesting:
    """Test determinism and Pass@k testing."""
    
    @pytest.fixture
    def evaluation_service(self):
        """Create evaluation service instance."""
        return EvaluationService()
    
    @pytest.fixture
    def mock_scenario(self):
        """Create mock evaluation scenario."""
        scenario = Mock(spec=EvaluationScenario)
        scenario.id = "test-scenario-123"
        scenario.name = "Test Determinism Scenario"
        scenario.evaluation_criteria = {"test": {"weight": 1.0, "requirements": []}}
        return scenario
    
    @pytest.mark.asyncio
    async def test_run_determinism_test(self, evaluation_service, mock_scenario):
        """Test determinism test with Pass@k calculation."""
        with patch.object(evaluation_service, '_get_scenario') as mock_get_scenario, \
             patch.object(evaluation_service.judge_service, 'evaluate_code') as mock_evaluate, \
             patch.object(evaluation_service, '_save_pass_k_metric') as mock_save_metric, \
             patch.object(evaluation_service, '_create_reliability_alert') as mock_create_alert:
            
            # Setup mocks
            mock_get_scenario.return_value = mock_scenario
            
            # Create mock evaluation results with varying scores
            mock_results = []
            for i in range(20):  # 20 runs for Pass@20
                result = Mock()
                result.id = f"eval-{i}"
                result.overall_score = 7.5 + (i % 3) * 0.5  # Varying scores
                result.execution_time_ms = 1000 + i * 10
                mock_results.append(result)
            
            # Mock evaluate_code to return different results
            mock_evaluate.side_effect = mock_results
            
            # Create agent output provider
            async def agent_output_provider():
                return f"Generated output {time.time()}"
            
            # Run determinism test
            pass_k_metrics = await evaluation_service.run_determinism_test(
                scenario_id="test-scenario-123",
                agent_output_provider=agent_output_provider,
                judge_config={"model": "gpt-4o"},
                k_values=[1, 5, 10, 20],
                success_threshold=7.0
            )
            
            # Verify results
            assert len(pass_k_metrics) == 4  # For k=1,5,10,20
            
            # Check Pass@10 specifically
            pass_at_10 = next(m for m in pass_k_metrics if m.k_value == 10)
            assert pass_at_10.k_value == 10
            assert pass_at_10.total_runs == 10
            assert 0 <= pass_at_10.pass_at_k <= 1
            assert pass_at_10.reliability_grade in ["A", "B", "C", "D", "F"]
            
            # Verify metrics were saved
            assert mock_save_metric.call_count == 4
            
            # Verify calls
            assert mock_evaluate.call_count == 20  # Should run 20 times
    
    @pytest.mark.asyncio
    async def test_run_determinism_test_low_reliability(self, evaluation_service, mock_scenario):
        """Test determinism test with low reliability triggering alert."""
        with patch.object(evaluation_service, '_get_scenario') as mock_get_scenario, \
             patch.object(evaluation_service.judge_service, 'evaluate_code') as mock_evaluate, \
             patch.object(evaluation_service, '_save_pass_k_metric') as mock_save_metric, \
             patch.object(evaluation_service, '_create_reliability_alert') as mock_create_alert:
            
            # Setup mocks
            mock_get_scenario.return_value = mock_scenario
            
            # Create mock evaluation results with mostly failures
            mock_results = []
            for i in range(10):
                result = Mock()
                result.id = f"eval-{i}"
                # Most scores below threshold (7.0)
                result.overall_score = 6.0 if i < 8 else 8.0
                result.execution_time_ms = 1000
                mock_results.append(result)
            
            mock_evaluate.side_effect = mock_results
            
            async def agent_output_provider():
                return f"Generated output {i}"
            
            pass_k_metrics = await evaluation_service.run_determinism_test(
                scenario_id="test-scenario-123",
                agent_output_provider=agent_output_provider,
                judge_config={"model": "gpt-4o"},
                k_values=[10],
                success_threshold=7.0
            )
            
            # Should trigger reliability alert for low pass rate
            pass_at_10 = pass_k_metrics[0]
            assert pass_at_10.pass_at_k < 0.5  # Low reliability
            
            # Alert should be created
            mock_create_alert.assert_called_once()


class TestEvaluationDashboard:
    """Test evaluation dashboard functionality."""
    
    @pytest.fixture
    def evaluation_service(self):
        """Create evaluation service instance."""
        return EvaluationService()
    
    @pytest.fixture
    def mock_evaluation_results(self):
        """Create mock evaluation results for dashboard testing."""
        results = []
        base_date = datetime.utcnow() - timedelta(days=30)
        
        for i in range(50):  # 50 results over 30 days
            result = Mock(spec=EvaluationResult)
            result.id = f"eval-{i}"
            result.scenario_id = f"scenario-{i % 5}"  # 5 different scenarios
            result.status = EvaluationStatus.COMPLETED
            result.completed_at = base_date + timedelta(days=i % 30)
            result.overall_score = 7.0 + (i % 20) * 0.1  # Varying scores
            result.code_safety_score = result.overall_score - 0.5
            result.code_quality_score = result.overall_score - 0.3
            result.best_practices_score = result.overall_score - 0.2
            result.performance_score = result.overall_score - 0.4
            result.readability_score = result.overall_score - 0.1
            result.functionality_score = result.overall_score
            result.security_score = result.overall_score - 0.3
            result.maintainability_score = result.overall_score - 0.2
            result.judge_cost_usd = 0.005 + i * 0.001
            result.judge_tokens_used = 1000 + i * 50
            results.append(result)
        
        return results
    
    @pytest.mark.asyncio
    async def test_get_evaluation_dashboard(self, evaluation_service, mock_evaluation_results):
        """Test dashboard data generation."""
        with patch('backend.services.evaluation.evaluation_service.get_db') as mock_get_db, \
             patch.object(evaluation_service, '_get_recent_regression_alerts') as mock_alerts, \
             patch.object(evaluation_service, '_get_reliability_metrics') as mock_reliability:
            
            # Setup mocks
            mock_db = Mock()
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = Mock(return_value=False)
            
            mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_evaluation_results
            mock_alerts.return_value = []
            mock_reliability.return_value = {"avg_pass_at_10": 0.75}
            
            # Get dashboard data
            dashboard_data = await evaluation_service.get_evaluation_dashboard(
                time_range_days=30
            )
            
            # Verify dashboard structure
            assert "summary" in dashboard_data
            assert "score_trends" in dashboard_data
            assert "dimension_breakdown" in dashboard_data
            assert "regression_alerts" in dashboard_data
            assert "reliability_metrics" in dashboard_data
            assert "cost_analysis" in dashboard_data
            assert "scenario_performance" in dashboard_data
            
            # Verify summary statistics
            summary = dashboard_data["summary"]
            assert summary["total_evaluations"] == 50
            assert "avg_overall_score" in summary
            assert "pass_rate" in summary
            assert summary["time_range_days"] == 30
            
            # Verify score trends
            trends = dashboard_data["score_trends"]
            assert len(trends) > 0
            for trend in trends:
                assert "date" in trend
                assert "avg_score" in trend
                assert "count" in trend
            
            # Verify dimension breakdown
            breakdown = dashboard_data["dimension_breakdown"]
            expected_dimensions = [
                "code_safety_score", "code_quality_score", "best_practices_score",
                "performance_score", "readability_score", "functionality_score",
                "security_score", "maintainability_score"
            ]
            for dim in expected_dimensions:
                assert dim in breakdown
                assert 0 <= breakdown[dim] <= 10
            
            # Verify cost analysis
            cost_analysis = dashboard_data["cost_analysis"]
            assert "total_cost_usd" in cost_analysis
            assert "total_tokens" in cost_analysis
            assert "avg_cost_per_evaluation" in cost_analysis
    
    def test_calculate_scenario_performance(self, evaluation_service, mock_evaluation_results):
        """Test scenario performance calculation."""
        performance = evaluation_service._calculate_scenario_performance(mock_evaluation_results)
        
        assert len(performance) == 5  # 5 different scenarios
        
        for perf in performance:
            assert "scenario_id" in perf
            assert "avg_score" in perf
            assert "min_score" in perf
            assert "max_score" in perf
            assert "evaluation_count" in perf
            assert "reliability_grade" in perf
            
            # Verify scores are within range
            assert 0 <= perf["avg_score"] <= 10
            assert 0 <= perf["min_score"] <= 10
            assert 0 <= perf["max_score"] <= 10
            assert perf["evaluation_count"] > 0
            assert perf["reliability_grade"] in ["A", "B", "C", "D", "F"]
    
    def test_calculate_cost_analysis(self, evaluation_service, mock_evaluation_results):
        """Test cost analysis calculation."""
        cost_analysis = evaluation_service._calculate_cost_analysis(mock_evaluation_results)
        
        assert "total_cost_usd" in cost_analysis
        assert "total_tokens" in cost_analysis
        assert "avg_cost_per_evaluation" in cost_analysis
        assert "avg_tokens_per_evaluation" in cost_analysis
        
        # Verify calculations
        expected_total_cost = sum(r.judge_cost_usd for r in mock_evaluation_results)
        expected_total_tokens = sum(r.judge_tokens_used for r in mock_evaluation_results)
        
        assert cost_analysis["total_cost_usd"] == expected_total_cost
        assert cost_analysis["total_tokens"] == expected_total_tokens
        assert cost_analysis["avg_cost_per_evaluation"] == expected_total_cost / len(mock_evaluation_results)
        assert cost_analysis["avg_tokens_per_evaluation"] == expected_total_tokens / len(mock_evaluation_results)


class TestAlerting:
    """Test alert creation and management."""
    
    @pytest.fixture
    def evaluation_service(self):
        """Create evaluation service instance."""
        return EvaluationService()
    
    @pytest.fixture
    def mock_evaluation_result(self):
        """Create mock evaluation result for alert testing."""
        result = Mock(spec=EvaluationResult)
        result.id = "test-eval-123"
        result.scenario_id = "test-scenario-456"
        result.overall_score = 4.5  # Low score to trigger alert
        result.status = EvaluationStatus.COMPLETED
        result.error_message = None
        return result
    
    @pytest.mark.asyncio
    async def test_create_regression_alert(self, evaluation_service):
        """Test regression alert creation."""
        regression_test = Mock(spec=RegressionTest)
        regression_test.id = "regression-123"
        regression_test.scenario_id = "scenario-456"
        regression_test.commit_hash = "abc123"
        regression_test.branch_name = "main"
        regression_test.alert_message = "Score degradation of 10.5% detected"
        regression_test.alert_type = RegressionAlertType.SCORE_DEGRADATION
        
        current_result = Mock()
        current_result.overall_score = 7.6
        
        with patch('backend.services.evaluation.evaluation_service.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = Mock(return_value=False)
            
            # Mock alert query
            mock_db.query.return_value.filter.return_value.first.return_value = None
            
            await evaluation_service._create_regression_alert(regression_test, current_result)
            
            # Verify alert was created
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            
            # Check the alert that was created
            created_alert = mock_db.add.call_args[0][0]
            assert created_alert.alert_type == RegressionAlertType.SCORE_DEGRADATION
            assert created_alert.severity == "high"
            assert created_alert.scenario_id == regression_test.scenario_id
            assert created_alert.regression_test_id == regression_test.id
            assert created_alert.title == "Score Degradation Detected"
            assert created_alert.description == regression_test.alert_message
            assert created_alert.commit_hash == regression_test.commit_hash
            assert created_alert.branch_name == regression_test.branch_name
    
    @pytest.mark.asyncio
    async def test_create_performance_alert(self, evaluation_service, mock_evaluation_result):
        """Test performance alert creation for low scores."""
        with patch('backend.services.evaluation.evaluation_service.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = Mock(return_value=False)
            
            mock_db.query.return_value.filter.return_value.first.return_value = None
            
            await evaluation_service._create_performance_alert(mock_evaluation_result)
            
            # Verify alert was created
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            
            created_alert = mock_db.add.call_args[0][0]
            assert created_alert.alert_type == RegressionAlertType.SCORE_DEGRADATION
            assert created_alert.severity == "medium"
            assert created_alert.scenario_id == mock_evaluation_result.scenario_id
            assert created_alert.evaluation_result_id == mock_evaluation_result.id
            assert created_alert.title == "Poor Performance Detected"
            assert "Overall score 4.50 below 5.0 threshold" in created_alert.description
            assert created_alert.metric_value == 4.5
            assert created_alert.threshold_value == 5.0
    
    @pytest.mark.asyncio
    async def test_create_evaluation_error_alert(self, evaluation_service):
        """Test evaluation error alert creation."""
        error_result = Mock(spec=EvaluationResult)
        error_result.id = "error-eval-123"
        error_result.scenario_id = "test-scenario-456"
        error_result.status = EvaluationStatus.ERROR
        error_result.error_message = "LLM service timeout"
        
        with patch('backend.services.evaluation.evaluation_service.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = Mock(return_value=False)
            
            mock_db.query.return_value.filter.return_value.first.return_value = None
            
            await evaluation_service._create_evaluation_error_alert(error_result)
            
            # Verify alert was created
            mock_db.add.assert_called_once()
            
            created_alert = mock_db.add.call_args[0][0]
            assert created_alert.alert_type == RegressionAlertType.FUNCTIONALITY_BREAK
            assert created_alert.severity == "high"
            assert created_alert.title == "Evaluation System Error"
            assert created_alert.description == "LLM service timeout"


# Integration tests
class TestEvaluationIntegration:
    """Integration tests for the complete evaluation workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_evaluation_workflow(self):
        """Test complete evaluation workflow from scenario to results."""
        # This is a high-level integration test
        # In a real implementation, this would test the full flow
        
        # 1. Create evaluation service
        eval_service = EvaluationService()
        
        # 2. Get scenarios from library
        library = ScenarioLibrary()
        baseline_scenarios = library.get_baseline_scenarios()
        
        assert len(baseline_scenarios) > 0
        
        # 3. Verify scenario structure
        for scenario in baseline_scenarios[:3]:  # Test first 3 scenarios
            assert "name" in scenario
            assert "description" in scenario
            assert "category" in scenario
            assert "complexity_level" in scenario
            assert "prompt" in scenario
            assert "evaluation_criteria" in scenario
            assert "estimated_duration_minutes" in scenario
        
        # 4. Test judge service configuration
        judge_service = LLMJudgeService()
        
        # Verify evaluation dimensions are properly configured
        expected_dimensions = [
            "code_safety", "code_quality", "best_practices", "performance",
            "readability", "functionality", "security", "maintainability"
        ]
        
        for dimension in expected_dimensions:
            assert dimension in judge_service.evaluation_dimensions
            assert "weight" in judge_service.evaluation_dimensions[dimension]
            assert "description" in judge_service.evaluation_dimensions[dimension]
        
        # 5. Test service initialization
        assert eval_service.judge_service is not None
        assert eval_service.scenario_library is not None
        assert eval_service.executor is not None
    
    def test_data_model_relationships(self):
        """Test database model relationships and constraints."""
        # Test evaluation scenario relationships
        scenario = EvaluationScenario(
            name="Test Integration Scenario",
            description="Integration test scenario",
            category="integration_test",
            complexity_level=ComplexityLevel.EASY,
            prompt="Test prompt",
            evaluation_criteria={"test": {"weight": 1.0, "requirements": []}}
        )
        
        # Test evaluation result relationships
        result = EvaluationResult(
            scenario_id=scenario.id,
            evaluation_type=EvaluationType.LLM_AS_JUDGE,
            status=EvaluationStatus.COMPLETED,
            overall_score=8.5,
            judge_model="gpt-4o",
            judge_provider=LLMProvider.OPENAI,
            started_at=datetime.utcnow()
        )
        
        # Test regression test relationships
        regression_test = RegressionTest(
            scenario_id=scenario.id,
            commit_hash="abc123",
            branch_name="main",
            trigger_type="manual",
            baseline_score=8.0,
            current_score=7.5,
            score_change=-0.5,
            score_change_percentage=-6.25,
            status="completed"
        )
        
        # Test Pass@k metric relationships
        pass_k_metric = PassKMetric(
            scenario_id=scenario.id,
            evaluation_result_id=result.id,
            k_value=10,
            total_runs=10,
            successful_runs=8,
            pass_at_k=0.8,
            success_threshold=7.0,
            success_criteria={"minimum_score": 7.0},
            run_timestamp=datetime.utcnow()
        )
        
        # Test evaluation alert relationships
        alert = EvaluationAlert(
            alert_type=RegressionAlertType.SCORE_DEGRADATION,
            severity="medium",
            scenario_id=scenario.id,
            title="Test Alert",
            description="Test alert description",
            status="active"
        )
        
        # Verify all objects can be created and have expected attributes
        assert scenario.name == "Test Integration Scenario"
        assert result.overall_score == 8.5
        assert regression_test.score_change_percentage == -6.25
        assert pass_k_metric.pass_at_k == 0.8
        assert alert.severity == "medium"


if __name__ == "__main__":
    pytest.main([__file__])