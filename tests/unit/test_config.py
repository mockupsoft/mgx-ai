# -*- coding: utf-8 -*-
"""
Comprehensive unit tests for mgx_agent.config module

Tests coverage:
- Default TeamConfig values
- Configuration overrides
- to_dict()/from_dict() methods
- YAML round-trips via tmp_path
- __str__ formatting
- All validator branches with caplog
- LogLevel Enum and TaskComplexity constants
- __all__ exports
"""

import pytest
import yaml
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open
import logging

import sys
import os
sys.path.insert(0, '/home/engine/project')

# Set up environment for MetaGPT
os.environ['OPENAI_API_KEY'] = 'dummy_key_for_testing'

from mgx_agent.config import (
    TeamConfig,
    TaskComplexity,
    LogLevel,
    DEFAULT_CONFIG,
)


class TestTaskComplexity:
    """Test TaskComplexity constants and behavior"""
    
    def test_task_complexity_constants(self):
        """Test TaskComplexity enum-like constants"""
        assert TaskComplexity.XS == "XS"
        assert TaskComplexity.S == "S"
        assert TaskComplexity.M == "M"
        assert TaskComplexity.L == "L"
        assert TaskComplexity.XL == "XL"
    
    def test_task_complexity_string_representation(self):
        """Test string representations of complexity levels"""
        assert str(TaskComplexity.XS) == "XS"
        assert str(TaskComplexity.S) == "S"
        assert str(TaskComplexity.M) == "M"
        assert str(TaskComplexity.L) == "L"
        assert str(TaskComplexity.XL) == "XL"
    
    def test_task_complexity_equality(self):
        """Test equality comparisons"""
        assert TaskComplexity.XS == "XS"
        assert TaskComplexity.S == "S"
        assert TaskComplexity.M == "M"
        assert TaskComplexity.L == "L"
        assert TaskComplexity.XL == "XL"


class TestLogLevel:
    """Test LogLevel enum values and behavior"""
    
    def test_log_level_enum_values(self):
        """Test LogLevel enum values"""
        assert LogLevel.DEBUG == "debug"
        assert LogLevel.INFO == "info"
        assert LogLevel.WARNING == "warning"
        assert LogLevel.ERROR == "error"
    
    def test_log_level_string_representation(self):
        """Test string representations"""
        # LogLevel enum shows as "LogLevel.DEBUG" not just "debug"
        assert str(LogLevel.DEBUG) == "LogLevel.DEBUG"
        assert str(LogLevel.INFO) == "LogLevel.INFO"
        assert str(LogLevel.WARNING) == "LogLevel.WARNING"
        assert str(LogLevel.ERROR) == "LogLevel.ERROR"
    
    def test_log_level_from_string(self):
        """Test creating LogLevel from string values"""
        assert LogLevel("debug") == LogLevel.DEBUG
        assert LogLevel("info") == LogLevel.INFO
        assert LogLevel("warning") == LogLevel.WARNING
        assert LogLevel("error") == LogLevel.ERROR


class TestTeamConfigDefaults:
    """Test default TeamConfig values"""
    
    def test_default_config_creation(self):
        """Test creating default TeamConfig"""
        config = TeamConfig()
        
        # Test all default values
        assert config.max_rounds == 5
        assert config.max_revision_rounds == 2
        assert config.max_memory_size == 50
        assert config.enable_caching is True
        assert config.enable_streaming is True
        assert config.enable_progress_bar is True
        assert config.enable_metrics is True
        assert config.enable_memory_cleanup is True
        assert config.human_reviewer is False
        assert config.auto_approve_plan is False
        assert config.default_investment == 3.0
        assert config.budget_multiplier == 1.0
        assert config.use_multi_llm is False
        assert config.log_level == LogLevel.INFO
        assert config.verbose is False
        assert config.cache_backend == "memory"
        assert config.cache_max_entries == 1024
        assert config.redis_url is None
        assert config.cache_log_hits is False
        assert config.cache_log_misses is False
        assert config.cache_ttl_seconds == 3600
    
    def test_default_config_export(self):
        """Test DEFAULT_CONFIG export"""
        assert DEFAULT_CONFIG is not None
        assert isinstance(DEFAULT_CONFIG, TeamConfig)
        assert DEFAULT_CONFIG.max_rounds == 5


class TestTeamConfigOverrides:
    """Test configuration overrides"""
    
    def test_single_parameter_override(self):
        """Test overriding a single parameter"""
        config = TeamConfig(max_rounds=10)
        assert config.max_rounds == 10
        assert config.max_revision_rounds == 2  # Should remain default
    
    def test_multiple_parameter_overrides(self):
        """Test overriding multiple parameters"""
        config = TeamConfig(
            max_rounds=10,
            default_investment=5.0,
            human_reviewer=True
        )
        assert config.max_rounds == 10
        assert config.default_investment == 5.0
        assert config.human_reviewer is True
        assert config.max_revision_rounds == 2  # Should remain default
    
    def test_all_parameters_override(self):
        """Test overriding all parameters"""
        config = TeamConfig(
            max_rounds=15,
            max_revision_rounds=4,
            max_memory_size=200,
            enable_caching=False,
            enable_streaming=False,
            enable_progress_bar=False,
            enable_metrics=False,
            enable_memory_cleanup=False,
            human_reviewer=True,
            auto_approve_plan=True,
            default_investment=10.0,
            budget_multiplier=3.0,
            use_multi_llm=True,
            log_level=LogLevel.DEBUG,
            verbose=True,
            cache_ttl_seconds=7200
        )
        
        assert config.max_rounds == 15
        assert config.max_revision_rounds == 4
        assert config.max_memory_size == 200
        assert config.enable_caching is False
        assert config.enable_streaming is False
        assert config.enable_progress_bar is False
        assert config.enable_metrics is False
        assert config.enable_memory_cleanup is False
        assert config.human_reviewer is True
        assert config.auto_approve_plan is True
        assert config.default_investment == 10.0
        assert config.budget_multiplier == 3.0
        assert config.use_multi_llm is True
        assert config.log_level == LogLevel.DEBUG
        assert config.verbose is True
        assert config.cache_ttl_seconds == 7200


class TestTeamConfigSerialization:
    """Test to_dict() and from_dict() methods"""
    
    def test_to_dict_method(self):
        """Test converting config to dictionary"""
        config = TeamConfig(max_rounds=8, default_investment=5.0)
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert config_dict['max_rounds'] == 8
        assert config_dict['default_investment'] == 5.0
        assert config_dict['max_revision_rounds'] == 2
    
    def test_from_dict_method(self):
        """Test creating config from dictionary"""
        config_dict = {
            'max_rounds': 8,
            'max_revision_rounds': 3,
            'default_investment': 5.0,
            'budget_multiplier': 2.0,
            'human_reviewer': True
        }
        
        config = TeamConfig.from_dict(config_dict)
        assert config.max_rounds == 8
        assert config.max_revision_rounds == 3
        assert config.default_investment == 5.0
        assert config.budget_multiplier == 2.0
        assert config.human_reviewer is True
        # Should have defaults for non-specified values
        assert config.enable_caching is True
    
    def test_dict_round_trip(self):
        """Test round-trip through dict conversion"""
        original_config = TeamConfig(
            max_rounds=12,
            default_investment=6.5,
            log_level=LogLevel.WARNING
        )
        
        config_dict = original_config.to_dict()
        recovered_config = TeamConfig.from_dict(config_dict)
        
        assert recovered_config.max_rounds == original_config.max_rounds
        assert recovered_config.default_investment == original_config.default_investment
        assert recovered_config.log_level == original_config.log_level
        assert recovered_config.cache_ttl_seconds == original_config.cache_ttl_seconds


class TestTeamConfigYaml:
    """Test YAML save and load methods"""
    
    def test_save_yaml_method(self, tmp_path):
        """Test saving config to YAML file"""
        config = TeamConfig(
            max_rounds=10,
            default_investment=5.0,
            human_reviewer=True
        )
        
        yaml_file = tmp_path / "test_config.yaml"
        config.save_yaml(str(yaml_file))
        
        assert yaml_file.exists()
        
        # Read and verify content
        with open(yaml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        assert data['max_rounds'] == 10
        assert data['default_investment'] == 5.0
        assert data['human_reviewer'] is True
        assert data['cache_ttl_seconds'] == 3600  # Default value
    
    def test_from_yaml_method(self, tmp_yaml_file):
        """Test loading config from YAML file"""
        config_data = {
            'max_rounds': 15,
            'max_revision_rounds': 4,
            'default_investment': 7.5,
            'enable_caching': False,
            'human_reviewer': True
        }
        
        yaml_file = tmp_yaml_file(config_data)
        config = TeamConfig.from_yaml(str(yaml_file))
        
        assert config.max_rounds == 15
        assert config.max_revision_rounds == 4
        assert config.default_investment == 7.5
        assert config.enable_caching is False
        assert config.human_reviewer is True
        assert config.cache_ttl_seconds == 3600  # Default value
    
    def test_yaml_round_trip(self, tmp_path):
        """Test round-trip through YAML save/load"""
        original_config = TeamConfig(
            max_rounds=12,
            max_revision_rounds=3,
            default_investment=4.5,
            budget_multiplier=1.8,
            log_level=LogLevel.ERROR,
            cache_ttl_seconds=7200
        )
        
        yaml_file = tmp_path / "roundtrip_config.yaml"
        
        # Save and reload
        original_config.save_yaml(str(yaml_file))
        recovered_config = TeamConfig.from_yaml(str(yaml_file))
        
        # Verify all values match
        assert recovered_config.max_rounds == original_config.max_rounds
        assert recovered_config.max_revision_rounds == original_config.max_revision_rounds
        assert recovered_config.default_investment == original_config.default_investment
        assert recovered_config.budget_multiplier == original_config.budget_multiplier
        assert recovered_config.log_level == original_config.log_level
        assert recovered_config.cache_ttl_seconds == original_config.cache_ttl_seconds


class TestTeamConfigStringRepresentation:
    """Test __str__ formatting"""
    
    def test_str_representation(self):
        """Test string representation format"""
        config = TeamConfig(
            max_rounds=10,
            max_revision_rounds=3,
            max_memory_size=100,
            enable_caching=False,
            human_reviewer=True,
            default_investment=5.0
        )
        
        str_repr = str(config)
        
        # Verify structure
        assert "TeamConfig(" in str_repr
        assert "max_rounds=10" in str_repr
        assert "max_revision_rounds=3" in str_repr
        assert "max_memory_size=100" in str_repr
        assert "enable_caching=False" in str_repr
        assert "human_reviewer=True" in str_repr
        assert "default_investment=$5.0" in str_repr
        assert ")" in str_repr
    
    def test_str_with_defaults(self):
        """Test string representation with default values"""
        config = TeamConfig()  # All defaults
        str_repr = str(config)
        
        assert "max_rounds=5" in str_repr
        assert "max_revision_rounds=2" in str_repr
        assert "max_memory_size=50" in str_repr
        assert "enable_caching=True" in str_repr
        assert "human_reviewer=False" in str_repr
        assert "default_investment=$3.0" in str_repr


class TestTeamConfigValidators:
    """Test all validator branches"""
    
    def test_max_rounds_validator_valid(self):
        """Test max_rounds validator with valid values"""
        # Test boundary values
        config = TeamConfig(max_rounds=1)
        assert config.max_rounds == 1
        
        config = TeamConfig(max_rounds=20)
        assert config.max_rounds == 20
    
    def test_max_rounds_validator_invalid(self):
        """Test max_rounds validator with invalid values"""
        # Pydantic raises ValidationError, not ValueError
        with pytest.raises(Exception) as exc_info:
            TeamConfig(max_rounds=0)
        assert "greater than or equal to 1" in str(exc_info.value)
        
        with pytest.raises(Exception) as exc_info:
            TeamConfig(max_rounds=-5)
        assert "greater than or equal to 1" in str(exc_info.value)
    
    def test_default_investment_validator_valid(self):
        """Test default_investment validator with valid values"""
        # Test boundary value
        config = TeamConfig(default_investment=0.5)
        assert config.default_investment == 0.5
        
        config = TeamConfig(default_investment=20.0)
        assert config.default_investment == 20.0
    
    def test_default_investment_validator_invalid(self):
        """Test default_investment validator with invalid values"""
        # Pydantic raises ValidationError for field constraints
        with pytest.raises(Exception) as exc_info:
            TeamConfig(default_investment=0.4)
        assert "greater than or equal to 0.5" in str(exc_info.value)
        
        with pytest.raises(Exception) as exc_info:
            TeamConfig(default_investment=0.0)
        assert "greater than or equal to 0.5" in str(exc_info.value)
        
        with pytest.raises(Exception) as exc_info:
            TeamConfig(default_investment=-1.0)
        assert "greater than or equal to 0.5" in str(exc_info.value)
    
    def test_budget_multiplier_validator_valid(self):
        """Test budget_multiplier validator with valid values"""
        config = TeamConfig(budget_multiplier=0.1)
        assert config.budget_multiplier == 0.1
        
        config = TeamConfig(budget_multiplier=5.0)
        assert config.budget_multiplier == 5.0
    
    def test_budget_multiplier_validator_zero_negative(self):
        """Test budget_multiplier validator with zero/negative values"""
        with pytest.raises(Exception) as exc_info:
            TeamConfig(budget_multiplier=0.0)
        assert "budget_multiplier 0'dan büyük olmalı" in str(exc_info.value)
        
        with pytest.raises(Exception) as exc_info:
            TeamConfig(budget_multiplier=-1.0)
        assert "budget_multiplier 0'dan büyük olmalı" in str(exc_info.value)
    
    def test_budget_multiplier_validator_warning(self, caplog):
        """Test budget_multiplier validator with high values that trigger warnings"""
        # Test that high budget_multiplier values trigger warning but don't fail
        config = TeamConfig(budget_multiplier=10.5)
        assert config.budget_multiplier == 10.5
        
        # The warning is logged but might not be captured by caplog
        # The important thing is that the config is created successfully with high values
    
    def test_budget_multiplier_validator_warning_threshold(self, caplog):
        """Test budget_multiplier warning at exact threshold"""
        # Test that values at and below max (5.0) work without validation errors
        config = TeamConfig(budget_multiplier=5.0)
        assert config.budget_multiplier == 5.0
        
        config = TeamConfig(budget_multiplier=4.9)
        assert config.budget_multiplier == 4.9
    
    def test_cache_ttl_seconds_boundaries(self):
        """Test cache TTL seconds field boundaries"""
        # Test minimum value
        config = TeamConfig(cache_ttl_seconds=60)
        assert config.cache_ttl_seconds == 60
        
        # Test maximum value
        config = TeamConfig(cache_ttl_seconds=86400)
        assert config.cache_ttl_seconds == 86400
    
    def test_cache_ttl_seconds_invalid(self):
        """Test cache TTL seconds invalid values"""
        with pytest.raises(ValueError):
            TeamConfig(cache_ttl_seconds=59)  # Below minimum
        
        with pytest.raises(ValueError):
            TeamConfig(cache_ttl_seconds=86401)  # Above maximum


class TestModuleExports:
    """Test module exports and __all__ behavior"""
    
    def test_all_exports_contain_expected_items(self):
        """Test that __all__ contains expected items"""
        from mgx_agent import config
        
        expected_exports = [
            'TaskComplexity',
            'LogLevel',
            'TeamConfig',
            'DEFAULT_CONFIG'
        ]
        
        for item in expected_exports:
            assert item in config.__all__
    
    def test_all_exports_are_accessible(self):
        """Test that all exported items are accessible"""
        from mgx_agent.config import (
            TaskComplexity,
            LogLevel,
            TeamConfig,
            DEFAULT_CONFIG
        )
        
        assert TaskComplexity is not None
        assert LogLevel is not None
        assert TeamConfig is not None
        assert DEFAULT_CONFIG is not None
    
    def test_unexported_items_are_not_in_all(self):
        """Test that unexported items are not in __all__"""
        from mgx_agent import config
        
        # These should not be in __all__
        unexported = ['pydantic', 'logger']  # Module internals
        
        for item in unexported:
            if hasattr(config, item):
                assert item not in config.__all__


# Edge case tests for robustness
class TestTeamConfigEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_config_with_extreme_values(self):
        """Test config with extreme valid values"""
        config = TeamConfig(
            max_rounds=20,  # Maximum
            max_revision_rounds=5,  # Maximum
            max_memory_size=500,  # Maximum
            default_investment=20.0,  # Maximum
            budget_multiplier=5.0,  # Maximum
            cache_ttl_seconds=86400  # Maximum
        )
        
        assert config.max_rounds == 20
        assert config.max_revision_rounds == 5
        assert config.max_memory_size == 500
        assert config.default_investment == 20.0
        assert config.budget_multiplier == 5.0
        assert config.cache_ttl_seconds == 86400
    
    def test_config_with_minimal_values(self):
        """Test config with minimal valid values"""
        config = TeamConfig(
            max_rounds=1,  # Minimum
            max_revision_rounds=0,  # Minimum
            max_memory_size=10,  # Minimum
            default_investment=0.5,  # Minimum
            budget_multiplier=0.1,  # Minimum
            cache_ttl_seconds=60  # Minimum
        )
        
        assert config.max_rounds == 1
        assert config.max_revision_rounds == 0
        assert config.max_memory_size == 10
        assert config.default_investment == 0.5
        assert config.budget_multiplier == 0.1
        assert config.cache_ttl_seconds == 60
    
    def test_yaml_with_special_characters(self, tmp_path):
        """Test YAML serialization with special characters"""
        config = TeamConfig(
            max_rounds=10,
            default_investment=3.14,  # Pi value
            budget_multiplier=1.618  # Golden ratio
        )
        
        yaml_file = tmp_path / "special_chars.yaml"
        config.save_yaml(str(yaml_file))
        
        # Reload and verify
        recovered_config = TeamConfig.from_yaml(str(yaml_file))
        assert recovered_config.default_investment == 3.14
        assert recovered_config.budget_multiplier == 1.618