# -*- coding: utf-8 -*-
"""
Comprehensive unit tests for mgx_agent.metrics module

Test coverage:
- TaskMetrics.duration_seconds for different time scenarios
- TaskMetrics.duration_formatted for seconds/minutes/hours cases
- Success/failure toggle behavior
- Token usage aggregation
- to_dict() formatting with currency precision
- Error message omission when empty
- Edge cases and boundary conditions
"""

import pytest
import time
from unittest.mock import patch, Mock

import sys
import os
sys.path.insert(0, '/home/engine/project')

# Set up environment for MetaGPT
os.environ['OPENAI_API_KEY'] = 'dummy_key_for_testing'

from mgx_agent.metrics import TaskMetrics
from mgx_agent.config import TaskComplexity


class TestTaskMetricsBasic:
    """Test basic TaskMetrics creation and properties"""
    
    def test_minimal_task_metrics(self):
        """Test creating minimal TaskMetrics with required fields"""
        start_time = time.time()
        
        metrics = TaskMetrics(task_name="minimal_test", start_time=start_time)
        
        assert metrics.task_name == "minimal_test"
        assert metrics.start_time == start_time
        assert metrics.end_time == 0.0
        assert metrics.success is False
        assert metrics.complexity == "XS"  # Default value
        assert metrics.token_usage == 0
        assert metrics.estimated_cost == 0.0
        assert metrics.revision_rounds == 0
        assert metrics.error_message == ""
    
    def test_complete_task_metrics(self):
        """Test creating TaskMetrics with all fields"""
        start_time = time.time()
        end_time = start_time + 120.0  # 2 minutes
        
        metrics = TaskMetrics(
            task_name="complete_test",
            start_time=start_time,
            end_time=end_time,
            success=True,
            complexity=TaskComplexity.M,
            token_usage=1500,
            estimated_cost=3.75,
            revision_rounds=2,
            error_message="Test error"
        )
        
        assert metrics.task_name == "complete_test"
        assert metrics.start_time == start_time
        assert metrics.end_time == end_time
        assert metrics.success is True
        assert metrics.complexity == "M"
        assert metrics.token_usage == 1500
        assert metrics.estimated_cost == 3.75
        assert metrics.revision_rounds == 2
        assert metrics.error_message == "Test error"


class TestDurationSeconds:
    """Test duration_seconds property for various scenarios"""
    
    def test_duration_seconds_when_in_progress(self):
        """Test duration_seconds when task is still in progress"""
        start_time = time.time()
        metrics = TaskMetrics(task_name="in_progress", start_time=start_time)
        
        # end_time is 0.0 (default), so duration should be 0.0
        assert metrics.duration_seconds == 0.0
    
    def test_duration_seconds_when_completed(self):
        """Test duration_seconds when task is completed"""
        start_time = 1000.0
        end_time = 1165.5  # 165.5 seconds later
        metrics = TaskMetrics(
            task_name="completed",
            start_time=start_time,
            end_time=end_time
        )
        
        assert metrics.duration_seconds == 165.5
    
    def test_duration_seconds_zero_duration(self):
        """Test duration_seconds for zero duration task"""
        start_time = 1000.0
        end_time = 1000.0  # Same time
        metrics = TaskMetrics(
            task_name="zero_duration",
            start_time=start_time,
            end_time=end_time
        )
        
        assert metrics.duration_seconds == 0.0
    
    def test_duration_seconds_fractional_seconds(self):
        """Test duration_seconds with fractional seconds"""
        start_time = 1000.0
        end_time = 1000.123456789  # Fractional seconds
        metrics = TaskMetrics(
            task_name="fractional",
            start_time=start_time,
            end_time=end_time
        )
        
        assert abs(metrics.duration_seconds - 0.123456789) < 1e-6
    
    def test_duration_seconds_negative_end_time(self):
        """Test duration_seconds with negative end_time"""
        start_time = 1000.0
        end_time = 500.0  # Before start_time (edge case)
        metrics = TaskMetrics(
            task_name="negative_duration",
            start_time=start_time,
            end_time=end_time
        )
        
        # Should handle negative duration gracefully
        assert metrics.duration_seconds == -500.0
    
    def test_duration_seconds_very_long_duration(self):
        """Test duration_seconds with very long duration"""
        start_time = 1000.0
        end_time = 1000.0 + 365*24*3600  # One year in seconds
        metrics = TaskMetrics(
            task_name="year_duration",
            start_time=start_time,
            end_time=end_time
        )
        
        expected_duration = 365 * 24 * 3600
        assert metrics.duration_seconds == expected_duration


class TestDurationFormatted:
    """Test duration_formatted property for different time scales"""
    
    def test_duration_formatted_seconds(self):
        """Test duration_formatted for seconds (< 60s)"""
        start_time = 1000.0
        end_time = 1045.2  # 45.2 seconds
        metrics = TaskMetrics(
            task_name="seconds_test",
            start_time=start_time,
            end_time=end_time
        )
        
        formatted = metrics.duration_formatted
        assert formatted == "45.2s"
        assert "s" in formatted
    
    def test_duration_formatted_minutes(self):
        """Test duration_formatted for minutes (1-59 minutes)"""
        start_time = 1000.0
        end_time = 1000.0 + (25 * 60) + 30.5  # 25 minutes 30.5 seconds
        metrics = TaskMetrics(
            task_name="minutes_test",
            start_time=start_time,
            end_time=end_time
        )
        
        formatted = metrics.duration_formatted
        assert formatted == "25.5m"
        assert "m" in formatted
    
    def test_duration_formatted_hours(self):
        """Test duration_formatted for hours (>= 60 minutes)"""
        start_time = 1000.0
        end_time = 1000.0 + (2 * 3600) + (15 * 60) + 45.2  # 2h 15m 45.2s
        metrics = TaskMetrics(
            task_name="hours_test",
            start_time=start_time,
            end_time=end_time
        )
        
        formatted = metrics.duration_formatted
        assert formatted == "2.3h"
        assert "h" in formatted
    
    def test_duration_formatted_very_long_duration(self):
        """Test duration_formatted for very long durations"""
        start_time = 1000.0
        end_time = 1000.0 + (24 * 3600)  # 24 hours
        metrics = TaskMetrics(
            task_name="day_duration",
            start_time=start_time,
            end_time=end_time
        )
        
        formatted = metrics.duration_formatted
        assert formatted == "24.0h"
        assert "h" in formatted
    
    def test_duration_formatted_fractional_minutes(self):
        """Test duration_formatted with fractional minute precision"""
        start_time = 1000.0
        end_time = 1000.0 + (10 * 60) + 12.345  # 10 minutes 12.345 seconds
        metrics = TaskMetrics(
            task_name="fractional_minutes",
            start_time=start_time,
            end_time=end_time
        )
        
        formatted = metrics.duration_formatted
        assert formatted == "10.2m"  # Should round to 10.2m
        assert "m" in formatted
    
    def test_duration_formatted_fractional_hours(self):
        """Test duration_formatted with fractional hour precision"""
        start_time = 1000.0
        end_time = 1000.0 + (1.5 * 3600)  # 1.5 hours
        metrics = TaskMetrics(
            task_name="fractional_hours",
            start_time=start_time,
            end_time=end_time
        )
        
        formatted = metrics.duration_formatted
        assert formatted == "1.5h"
        assert "h" in formatted
    
    def test_duration_formatted_zero_duration(self):
        """Test duration_formatted for zero duration"""
        start_time = 1000.0
        end_time = 1000.0
        metrics = TaskMetrics(
            task_name="zero_duration_formatted",
            start_time=start_time,
            end_time=end_time
        )
        
        formatted = metrics.duration_formatted
        assert formatted == "0.0s"
        assert "s" in formatted
    
    def test_duration_formatted_in_progress(self):
        """Test duration_formatted when task is in progress"""
        start_time = time.time()
        metrics = TaskMetrics(task_name="in_progress_formatted", start_time=start_time)
        
        formatted = metrics.duration_formatted
        assert formatted == "0.0s"
        assert "s" in formatted


class TestSuccessFailureToggles:
    """Test success/failure toggle behavior"""
    
    def test_success_false_by_default(self):
        """Test success is False by default"""
        metrics = TaskMetrics(task_name="default_success", start_time=1000.0)
        assert metrics.success is False
    
    def test_success_true_when_set(self):
        """Test success can be set to True"""
        metrics = TaskMetrics(task_name="successful_task", success=True, start_time=1000.0)
        assert metrics.success is True
    
    def test_success_false_explicitly_set(self):
        """Test success can be explicitly set to False"""
        metrics = TaskMetrics(task_name="failed_task", success=False, start_time=1000.0)
        assert metrics.success is False
    
    def test_success_toggle(self):
        """Test toggling success value"""
        metrics = TaskMetrics(task_name="toggle_test", start_time=1000.0)
        assert metrics.success is False
        
        metrics.success = True
        assert metrics.success is True
        
        metrics.success = False
        assert metrics.success is False
    
    def test_success_with_duration(self):
        """Test success with various duration scenarios"""
        # Successful short task
        metrics_success = TaskMetrics(
            task_name="success_short",
            success=True,
            start_time=1000.0,
            end_time=1005.0
        )
        assert metrics_success.success is True
        
        # Failed long task
        metrics_failure = TaskMetrics(
            task_name="failure_long",
            success=False,
            start_time=1000.0,
            end_time=2000.0
        )
        assert metrics_failure.success is False
        
        # In-progress task that hasn't completed yet
        metrics_incomplete = TaskMetrics(
            task_name="incomplete",
            success=False,
            start_time=time.time()
        )
        assert metrics_incomplete.success is False


class TestTokenUsage:
    """Test token usage aggregation and handling"""
    
    def test_token_usage_default_zero(self):
        """Test token_usage is 0 by default"""
        metrics = TaskMetrics(task_name="default_tokens", start_time=1000.0)
        assert metrics.token_usage == 0
    
    def test_token_usage_positive_value(self):
        """Test token_usage with positive value"""
        metrics = TaskMetrics(task_name="positive_tokens", token_usage=1234, start_time=1000.0)
        assert metrics.token_usage == 1234
    
    def test_token_usage_aggregation_scenario(self):
        """Test token usage for aggregation scenario"""
        # Simulate multiple subtasks aggregated
        metrics = TaskMetrics(
            task_name="aggregated_task",
            token_usage=5000  # Sum of all subtasks
        , start_time=1000.0)
        assert metrics.token_usage == 5000
    
    def test_token_usage_very_large(self):
        """Test token_usage with very large values"""
        metrics = TaskMetrics(task_name="large_tokens", token_usage=1000000, start_time=1000.0)
        assert metrics.token_usage == 1000000
    
    def test_token_usage_in_dict_output(self):
        """Test token_usage appears correctly in dict output"""
        metrics = TaskMetrics(
            task_name="token_dict_test",
            token_usage=2500,
            start_time=1000.0,
            end_time=1005.0
        )
        
        metrics_dict = metrics.to_dict()
        assert "token_usage" in metrics_dict
        assert metrics_dict["token_usage"] == 2500
    
    def test_token_usage_zero_in_dict_output(self):
        """Test token_usage=0 appears in dict output"""
        metrics = TaskMetrics(
            task_name="zero_token_test",
            token_usage=0,
            start_time=1000.0,
            end_time=1005.0
        )
        
        metrics_dict = metrics.to_dict()
        assert "token_usage" in metrics_dict
        assert metrics_dict["token_usage"] == 0


class TestToDictFormatting:
    """Test to_dict() formatting and currency precision"""
    
    def test_to_dict_currency_precision(self):
        """Test currency formatting with proper precision"""
        metrics = TaskMetrics(
            task_name="currency_test",
            estimated_cost=2.75,
            start_time=1000.0,
            end_time=1005.0
        )
        
        metrics_dict = metrics.to_dict()
        
        # Should format as $X.XXXX with 4 decimal places
        assert "estimated_cost" in metrics_dict
        assert metrics_dict["estimated_cost"] == "$2.7500"
    
    def test_to_dict_currency_rounding(self):
        """Test currency rounding behavior"""
        metrics = TaskMetrics(
            task_name="rounding_test",
            estimated_cost=2.123456789,  # Should round to 2.1235
            start_time=1000.0,
            end_time=1005.0
        )
        
        metrics_dict = metrics.to_dict()
        assert metrics_dict["estimated_cost"] == "$2.1235"
    
    def test_to_dict_currency_zero(self):
        """Test currency formatting for zero cost"""
        metrics = TaskMetrics(
            task_name="zero_cost_test",
            estimated_cost=0.0,
            start_time=1000.0,
            end_time=1005.0
        )
        
        metrics_dict = metrics.to_dict()
        assert metrics_dict["estimated_cost"] == "$0.0000"
    
    def test_to_dict_error_message_empty(self):
        """Test error message omission when empty"""
        metrics = TaskMetrics(
            task_name="no_error_test",
            error_message="",  # Empty error
            start_time=1000.0,
            end_time=1005.0
        )
        
        metrics_dict = metrics.to_dict()
        
        # Empty error message should be None
        assert "error" in metrics_dict
        assert metrics_dict["error"] is None
    
    def test_to_dict_error_message_present(self):
        """Test error message when present"""
        metrics = TaskMetrics(
            task_name="error_test",
            error_message="Connection timeout",
            start_time=1000.0,
            end_time=1005.0
        )
        
        metrics_dict = metrics.to_dict()
        
        # Non-empty error message should be included
        assert "error" in metrics_dict
        assert metrics_dict["error"] == "Connection timeout"
    
    def test_to_dict_all_fields_present(self):
        """Test that to_dict includes all expected fields"""
        metrics = TaskMetrics(
            task_name="complete_dict_test",
            start_time=1000.0,
            end_time=1165.5,
            success=True,
            complexity="L",
            token_usage=3000,
            estimated_cost=7.25,
            revision_rounds=3,
            error_message="Minor warning"
        )
        
        expected_keys = [
            "task_name",
            "duration",
            "success", 
            "complexity",
            "token_usage",
            "estimated_cost",
            "revision_rounds",
            "error"
        ]
        
        metrics_dict = metrics.to_dict()
        
        for key in expected_keys:
            assert key in metrics_dict, f"Missing key: {key}"
        
        # Verify specific values
        assert metrics_dict["task_name"] == "complete_dict_test"
        assert metrics_dict["duration"] == "2.8m"  # 165.5 seconds = 2.8 minutes
        assert metrics_dict["success"] is True
        assert metrics_dict["complexity"] == "L"
        assert metrics_dict["token_usage"] == 3000
        assert metrics_dict["estimated_cost"] == "$7.2500"
        assert metrics_dict["revision_rounds"] == 3
        assert metrics_dict["error"] == "Minor warning"
    
    def test_to_dict_duration_format_in_dict(self):
        """Test that duration_formatted appears as 'duration' in dict"""
        start_time = 1000.0
        end_time = 1000.0 + (15 * 60) + 45.2  # 15 minutes
        metrics = TaskMetrics(
            task_name="duration_dict_test",
            start_time=start_time,
            end_time=end_time
        )
        
        metrics_dict = metrics.to_dict()
        
        # Should use formatted duration, not raw seconds
        assert "duration" in metrics_dict
        assert metrics_dict["duration"] == "15.8m"
        assert isinstance(metrics_dict["duration"], str)


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_complexity_values(self):
        """Test various complexity values"""
        complexities = ["XS", "S", "M", "L", "XL"]
        
        for complexity in complexities:
            metrics = TaskMetrics(task_name=f"test_{complexity}", complexity=complexity, start_time=1000.0)
            assert metrics.complexity == complexity
    
    def test_revision_rounds_edge_cases(self):
        """Test revision_rounds edge cases"""
        # Zero revisions
        metrics = TaskMetrics(task_name="zero_revisions", revision_rounds=0, start_time=1000.0)
        assert metrics.revision_rounds == 0
        
        # Many revisions
        metrics = TaskMetrics(task_name="many_revisions", revision_rounds=100, start_time=1000.0)
        assert metrics.revision_rounds == 100
    
    def test_negative_estimated_cost(self):
        """Test negative estimated cost (edge case)"""
        metrics = TaskMetrics(
            task_name="negative_cost",
            estimated_cost=-5.0,
            start_time=1000.0,
            end_time=1005.0
        )
        
        metrics_dict = metrics.to_dict()
        # Should still format as negative currency
        assert metrics_dict["estimated_cost"] == "$-5.0000"
    
    def test_very_small_positive_cost(self):
        """Test very small positive estimated cost"""
        metrics = TaskMetrics(
            task_name="small_cost",
            estimated_cost=0.0001,
            start_time=1000.0,
            end_time=1005.0
        )
        
        metrics_dict = metrics.to_dict()
        assert metrics_dict["estimated_cost"] == "$0.0001"
    
    def test_special_characters_in_task_name(self):
        """Test task names with special characters"""
        special_names = [
            "task_with_émojis_🚀",
            "task-with-dashes_and_underscores",
            "task with spaces",
            "task.with.dots",
            "task/with/slashes",
            "task@with#symbols$and%percents"
        ]
        
        for name in special_names:
            metrics = TaskMetrics(task_name=name, start_time=1000.0)
            assert metrics.task_name == name
    
    def test_very_long_task_name(self):
        """Test very long task names"""
        long_name = "a" * 1000  # 1000 character name
        metrics = TaskMetrics(task_name=long_name, start_time=1000.0)
        assert metrics.task_name == long_name
        
        # Should still work in dict output
        metrics_dict = metrics.to_dict()
        assert metrics_dict["task_name"] == long_name
    
    def test_empty_task_name(self):
        """Test empty task name (edge case)"""
        metrics = TaskMetrics(task_name="", start_time=1000.0)
        assert metrics.task_name == ""
        
        metrics_dict = metrics.to_dict()
        assert metrics_dict["task_name"] == ""


# Multiple assertions test to reach target of ~30 assertions
class TestMultipleAssertions:
    """Multiple assertion tests to reach target coverage"""
    
    def test_complex_scenario_assertions(self):
        """Test complex scenario with multiple assertions"""
        start_time = time.time()
        end_time = start_time + 3725.5  # 1 hour, 2 minutes, 5.5 seconds
        
        metrics = TaskMetrics(
            task_name="complex_scenario_test",
            start_time=start_time,
            end_time=end_time,
            success=True,
            complexity=TaskComplexity.L,
            token_usage=8750,
            estimated_cost=12.3456,
            revision_rounds=5,
            error_message="Partial success with warnings"
        )
        
        # Assert 1-10: Basic properties
        assert metrics.task_name == "complex_scenario_test"
        assert metrics.start_time == start_time
        assert metrics.end_time == end_time
        assert metrics.success is True
        assert metrics.complexity == "L"
        assert metrics.token_usage == 8750
        assert metrics.estimated_cost == 12.3456
        assert metrics.revision_rounds == 5
        assert metrics.error_message == "Partial success with warnings"
        assert isinstance(metrics.start_time, float)
        
        # Assert 11-20: Duration calculations
        assert abs(metrics.duration_seconds - 3725.5) < 1e-6
        assert "h" in metrics.duration_formatted
        assert metrics.duration_formatted == "1.0h"  # Should round to hours
        
        # Assert 21-30: Dictionary output
        metrics_dict = metrics.to_dict()
        assert "task_name" in metrics_dict
        assert "duration" in metrics_dict
        assert "success" in metrics_dict
        assert "complexity" in metrics_dict
        assert "token_usage" in metrics_dict
        assert "estimated_cost" in metrics_dict
        assert "revision_rounds" in metrics_dict
        assert "error" in metrics_dict
        
        # Verify specific dict values
        assert metrics_dict["task_name"] == "complex_scenario_test"
        assert metrics_dict["duration"] == "1.0h"
        assert metrics_dict["success"] is True
        assert metrics_dict["complexity"] == "L"
        assert metrics_dict["token_usage"] == 8750
        assert metrics_dict["estimated_cost"] == "$12.3456"
        assert metrics_dict["revision_rounds"] == 5
        assert metrics_dict["error"] == "Partial success with warnings"
    
    def test_multiple_quick_assertions(self):
        """Multiple quick assertions for coverage"""
        # Test 1: Multiple task creations
        metrics1 = TaskMetrics(task_name="test1", start_time=1000.0)
        metrics2 = TaskMetrics(task_name="test2", success=True, start_time=1000.0)
        metrics3 = TaskMetrics(task_name="test3", token_usage=100, start_time=1000.0)
        
        assert metrics1.task_name == "test1"
        assert metrics2.task_name == "test2"
        assert metrics3.task_name == "test3"
        
        # Test 2: Multiple complexity levels
        for complexity in ["XS", "S", "M", "L", "XL"]:
            m = TaskMetrics(task_name=f"comp_test", complexity=complexity, start_time=1000.0)
            assert m.complexity == complexity
        
        # Test 3: Multiple time ranges
        test_times = [(1000, 1001), (2000, 2200), (3000, 3600)]
        for start, end in test_times:
            m = TaskMetrics(task_name="time_test", start_time=start, end_time=end)
            assert m.duration_seconds == (end - start)
        
        # Test 4: Multiple cost formats
        costs = [0.0, 0.5, 1.0, 10.5, 100.1234]
        for cost in costs:
            m = TaskMetrics(task_name="cost_test", estimated_cost=cost, start_time=1000.0)
            assert m.estimated_cost == cost
            assert m.to_dict()["estimated_cost"] == f"${cost:.4f}"
        
        # Test 5: Multiple revision scenarios
        revisions = [0, 1, 5, 10, 50]
        for rev in revisions:
            m = TaskMetrics(task_name="rev_test", revision_rounds=rev, start_time=1000.0)
            assert m.revision_rounds == rev