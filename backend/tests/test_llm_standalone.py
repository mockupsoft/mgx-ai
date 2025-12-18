# -*- coding: utf-8 -*-
"""Standalone tests for LLM provider system - no external dependencies."""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Direct imports without backend.services dependencies
from backend.services.llm.registry import ModelRegistry, ModelConfig
from backend.services.llm.router import RoutingStrategy, FallbackChain


class TestModelRegistry:
    """Test model registry functionality."""
    
    def test_get_model_config(self):
        """Test getting model configuration."""
        config = ModelRegistry.get_model_config("openai", "gpt-4")
        
        assert config is not None
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.max_tokens == 8192
        assert config.cost_per_1k_prompt == 0.03
        assert "code" in config.capabilities
    
    def test_get_model_config_not_found(self):
        """Test getting non-existent model."""
        config = ModelRegistry.get_model_config("unknown", "model")
        assert config is None
    
    def test_list_models(self):
        """Test listing all models."""
        models = ModelRegistry.list_models()
        
        assert len(models) > 0
        assert "openai/gpt-4" in models
        assert "anthropic/claude-3-opus" in models
        assert "mistral/mistral-medium" in models
        assert "ollama/mistral" in models
    
    def test_list_models_by_provider(self):
        """Test listing models for specific provider."""
        models = ModelRegistry.list_models("openai")
        
        assert len(models) > 0
        assert all(m.startswith("openai/") for m in models)
        assert "openai/gpt-4" in models
        assert "openai/gpt-3.5-turbo" in models
    
    def test_find_models_by_capability(self):
        """Test finding models by capability."""
        models = ModelRegistry.find_models_by_capability("code")
        
        assert len(models) > 0
        assert all("code" in m.capabilities for m in models)
    
    def test_find_models_by_capability_with_cost_filter(self):
        """Test finding models with cost constraint."""
        models = ModelRegistry.find_models_by_capability(
            "code",
            max_cost_per_1k=0.01
        )
        
        assert len(models) > 0
        for model in models:
            total_cost = model.cost_per_1k_prompt + model.cost_per_1k_completion
            assert total_cost <= 0.01
    
    def test_find_models_with_latency_filter(self):
        """Test finding models with latency constraint."""
        models = ModelRegistry.find_models_by_capability(
            "code",
            max_latency_ms=1000
        )
        
        assert len(models) > 0
        assert all(m.latency_estimate_ms <= 1000 for m in models)
    
    def test_get_cheapest_model(self):
        """Test getting cheapest model."""
        model = ModelRegistry.get_cheapest_model(capability="code")
        
        assert model is not None
        # Ollama models are free
        assert model.cost_per_1k_prompt == 0.0
        assert model.cost_per_1k_completion == 0.0
        assert model.provider == "ollama"
    
    def test_get_cheapest_model_exclude_local(self):
        """Test getting cheapest non-local model."""
        model = ModelRegistry.get_cheapest_model(
            capability="code",
            exclude_local=True
        )
        
        assert model is not None
        assert model.provider != "ollama"
        # Should be a cheap cloud model
        total_cost = model.cost_per_1k_prompt + model.cost_per_1k_completion
        assert total_cost < 0.01
    
    def test_get_fastest_model(self):
        """Test getting fastest model."""
        model = ModelRegistry.get_fastest_model(capability="code")
        
        assert model is not None
        # Should be under 1000ms
        assert model.latency_estimate_ms < 1000
    
    def test_get_fastest_model_with_cost_limit(self):
        """Test getting fastest model with cost constraint."""
        model = ModelRegistry.get_fastest_model(
            capability="code",
            max_cost_per_1k=0.01
        )
        
        assert model is not None
        total_cost = model.cost_per_1k_prompt + model.cost_per_1k_completion
        assert total_cost <= 0.01
    
    def test_model_config_dataclass(self):
        """Test ModelConfig dataclass."""
        config = ModelConfig(
            provider="test",
            model="test-model",
            max_tokens=4096,
            cost_per_1k_prompt=0.01,
            cost_per_1k_completion=0.02,
            latency_estimate_ms=500,
            capabilities=["code", "reasoning"],
        )
        
        assert config.provider == "test"
        assert config.model == "test-model"
        assert config.max_tokens == 4096
        assert config.context_window == 4096  # Default equals max_tokens
        assert "code" in config.capabilities


class TestFallbackChains:
    """Test predefined fallback chains."""
    
    def test_high_quality_chain(self):
        """Test high quality fallback chain."""
        chain = FallbackChain.HIGH_QUALITY
        
        assert len(chain) > 0
        assert chain[0][0] in ["openai", "anthropic"]
        # Should start with premium models
        assert chain[0][1] in ["gpt-4", "claude-3-opus"]
    
    def test_cost_optimized_chain(self):
        """Test cost optimized fallback chain."""
        chain = FallbackChain.COST_OPTIMIZED
        
        assert len(chain) > 0
        # Should end with local model
        assert chain[-1][0] == "ollama"
        # Should start with cheap cloud models
        assert chain[0][1] in ["gpt-3.5-turbo", "claude-3-haiku"]
    
    def test_fast_latency_chain(self):
        """Test fast latency fallback chain."""
        chain = FallbackChain.FAST_LATENCY
        
        assert len(chain) > 0
        # All models should be relatively fast
        for provider, model in chain:
            config = ModelRegistry.get_model_config(provider, model)
            if config:
                # Allow up to 5000ms for local models
                assert config.latency_estimate_ms <= 5000
    
    def test_local_only_chain(self):
        """Test local only fallback chain."""
        chain = FallbackChain.LOCAL_ONLY
        
        assert len(chain) > 0
        # All should be ollama
        assert all(p == "ollama" for p, m in chain)
        # Should include common local models
        models = [m for p, m in chain]
        assert "mistral" in models or "llama2" in models
    
    def test_code_generation_chain(self):
        """Test code generation fallback chain."""
        chain = FallbackChain.CODE_GENERATION
        
        assert len(chain) > 0
        # Verify all models have code capability
        for provider, model in chain:
            config = ModelRegistry.get_model_config(provider, model)
            if config:
                assert "code" in config.capabilities
    
    def test_long_context_chain(self):
        """Test long context fallback chain."""
        chain = FallbackChain.LONG_CONTEXT
        
        assert len(chain) > 0
        # Should prioritize models with large context windows
        for provider, model in chain:
            config = ModelRegistry.get_model_config(provider, model)
            if config:
                # Long context models should have at least 32K tokens
                assert config.context_window >= 32000
    
    def test_balanced_chain(self):
        """Test balanced fallback chain."""
        chain = FallbackChain.BALANCED
        
        assert len(chain) > 0
        # Should have variety of providers
        providers = set(p for p, m in chain)
        assert len(providers) >= 3
        # Should include both cloud and local
        assert "ollama" in providers
    
    def test_analysis_chain(self):
        """Test analysis chain."""
        chain = FallbackChain.HIGH_QUALITY  # Analysis uses high quality
        
        assert len(chain) > 0
        # Should include models with reasoning capability
        for provider, model in chain:
            config = ModelRegistry.get_model_config(provider, model)
            if config:
                assert "reasoning" in config.capabilities or "analysis" in config.capabilities


class TestRoutingStrategy:
    """Test routing strategy enum."""
    
    def test_strategy_values(self):
        """Test all strategy values are defined."""
        assert RoutingStrategy.COST_OPTIMIZED == "cost_optimized"
        assert RoutingStrategy.LATENCY_OPTIMIZED == "latency_optimized"
        assert RoutingStrategy.QUALITY_OPTIMIZED == "quality_optimized"
        assert RoutingStrategy.LOCAL_FIRST == "local_first"
        assert RoutingStrategy.CAPABILITY_MATCH == "capability_match"
        assert RoutingStrategy.BALANCED == "balanced"
    
    def test_strategy_enum_members(self):
        """Test all strategies are enum members."""
        strategies = list(RoutingStrategy)
        assert len(strategies) == 6


class TestModelCapabilities:
    """Test model capability queries."""
    
    def test_code_capability_models(self):
        """Test finding code generation models."""
        models = ModelRegistry.find_models_by_capability("code")
        
        assert len(models) > 10  # Should have many code models
        # Check specific models
        gpt4 = next((m for m in models if m.model == "gpt-4"), None)
        assert gpt4 is not None
        assert "code" in gpt4.capabilities
    
    def test_reasoning_capability_models(self):
        """Test finding reasoning models."""
        models = ModelRegistry.find_models_by_capability("reasoning")
        
        assert len(models) > 0
        # High-end models should have reasoning
        for model in models:
            if model.model in ["gpt-4", "claude-3-opus"]:
                assert "reasoning" in model.capabilities
    
    def test_long_context_capability_models(self):
        """Test finding long context models."""
        models = ModelRegistry.find_models_by_capability("long_context")
        
        assert len(models) > 0
        # Claude and GPT-4 variants should support long context
        for model in models:
            assert model.context_window >= 16384
    
    def test_simple_analysis_models(self):
        """Test finding simple analysis models."""
        models = ModelRegistry.find_models_by_capability("simple_analysis")
        
        assert len(models) > 0
        # Should include cheaper models
        for model in models:
            total_cost = model.cost_per_1k_prompt + model.cost_per_1k_completion
            # Simple analysis models should be relatively cheap
            assert total_cost < 0.05


class TestModelPricing:
    """Test model pricing information."""
    
    def test_openai_pricing(self):
        """Test OpenAI model pricing."""
        gpt4 = ModelRegistry.get_model_config("openai", "gpt-4")
        gpt35 = ModelRegistry.get_model_config("openai", "gpt-3.5-turbo")
        
        # GPT-4 should be more expensive than GPT-3.5
        assert gpt4.cost_per_1k_prompt > gpt35.cost_per_1k_prompt
        assert gpt4.cost_per_1k_completion > gpt35.cost_per_1k_completion
    
    def test_anthropic_pricing(self):
        """Test Anthropic model pricing."""
        opus = ModelRegistry.get_model_config("anthropic", "claude-3-opus")
        haiku = ModelRegistry.get_model_config("anthropic", "claude-3-haiku")
        
        # Opus should be more expensive than Haiku
        assert opus.cost_per_1k_prompt > haiku.cost_per_1k_prompt
        assert opus.cost_per_1k_completion > haiku.cost_per_1k_completion
    
    def test_ollama_pricing(self):
        """Test Ollama model pricing (should be free)."""
        models = ModelRegistry.list_models("ollama")
        
        for model_id in models:
            provider, model = model_id.split("/")
            config = ModelRegistry.get_model_config(provider, model)
            assert config.cost_per_1k_prompt == 0.0
            assert config.cost_per_1k_completion == 0.0


class TestModelPerformance:
    """Test model performance characteristics."""
    
    def test_latency_estimates(self):
        """Test latency estimates are reasonable."""
        models = ModelRegistry.list_models()
        
        for model_id in models:
            provider, model = model_id.split("/")
            config = ModelRegistry.get_model_config(provider, model)
            
            # All latencies should be positive and reasonable
            assert config.latency_estimate_ms > 0
            assert config.latency_estimate_ms < 30000  # Max 30 seconds
            
            # Cloud models should be faster than local
            if provider in ["openai", "anthropic", "mistral"]:
                assert config.latency_estimate_ms < 3000
            elif provider == "ollama":
                # Local models can be slower
                assert config.latency_estimate_ms >= 1000
    
    def test_context_windows(self):
        """Test context window sizes."""
        models = ModelRegistry.list_models()
        
        for model_id in models:
            provider, model = model_id.split("/")
            config = ModelRegistry.get_model_config(provider, model)
            
            # Context window should be at least as large as max_tokens
            assert config.context_window >= config.max_tokens
            
            # All models should have reasonable context windows
            assert config.context_window >= 4096
            assert config.context_window <= 200000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
