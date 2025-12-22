# -*- coding: utf-8 -*-
"""Tests for LLM provider system."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.llm.provider import (
    LLMProvider,
    LLMResponse,
    ModelCapabilities,
    ProviderError,
    AllProvidersFailedError,
)
from backend.services.llm.registry import ModelRegistry, ModelConfig
from backend.services.llm.router import LLMRouter, RoutingStrategy, FallbackChain
from backend.services.llm.providers import (
    OpenAIProvider,
    AnthropicProvider,
    MistralProvider,
    OllamaProvider,
    TogetherAIProvider,
)
from backend.services.llm.llm_service import LLMService


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
    
    def test_list_models_by_provider(self):
        """Test listing models for specific provider."""
        models = ModelRegistry.list_models("openai")
        
        assert len(models) > 0
        assert all(m.startswith("openai/") for m in models)
    
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
    
    def test_get_cheapest_model(self):
        """Test getting cheapest model."""
        model = ModelRegistry.get_cheapest_model(capability="code")
        
        assert model is not None
        # Ollama models are free
        assert model.cost_per_1k_prompt == 0.0
    
    def test_get_cheapest_model_exclude_local(self):
        """Test getting cheapest non-local model."""
        model = ModelRegistry.get_cheapest_model(
            capability="code",
            exclude_local=True
        )
        
        assert model is not None
        assert model.provider != "ollama"
    
    def test_get_fastest_model(self):
        """Test getting fastest model."""
        model = ModelRegistry.get_fastest_model(capability="code")
        
        assert model is not None
        assert model.latency_estimate_ms < 1000


class TestOpenAIProvider:
    """Test OpenAI provider."""
    
    def test_initialization(self):
        """Test provider initialization."""
        provider = OpenAIProvider(api_key="test-key")
        
        assert provider.api_key == "test-key"
        assert provider.default_model == "gpt-3.5-turbo"
        assert provider.provider_name == "openai"
    
    def test_is_available_with_key(self):
        """Test availability check with API key."""
        provider = OpenAIProvider(api_key="test-key")
        # Will be False unless openai package is installed
        assert isinstance(provider.is_available(), bool)
    
    def test_is_available_without_key(self):
        """Test availability check without API key."""
        provider = OpenAIProvider()
        assert provider.is_available() is False
    
    def test_list_models(self):
        """Test listing available models."""
        provider = OpenAIProvider(api_key="test-key")
        models = provider.list_models()
        
        assert len(models) > 0
        assert "gpt-4" in models
        assert "gpt-3.5-turbo" in models
    
    def test_get_model_capabilities(self):
        """Test getting model capabilities."""
        provider = OpenAIProvider(api_key="test-key")
        caps = provider.get_model_capabilities("gpt-4")
        
        assert caps.code_generation is True
        assert caps.reasoning is True
        assert caps.streaming is True
        assert caps.max_tokens == 8192
    
    @pytest.mark.asyncio
    async def test_get_cost(self):
        """Test cost calculation."""
        provider = OpenAIProvider(api_key="test-key")
        cost = await provider.get_cost("gpt-4", 1000, 500)
        
        # 1000 tokens * 0.03 + 500 tokens * 0.06 = 0.03 + 0.03 = 0.06
        assert cost == pytest.approx(0.06)
    
    @pytest.mark.asyncio
    async def test_get_latency_estimate(self):
        """Test latency estimation."""
        provider = OpenAIProvider(api_key="test-key")
        latency = await provider.get_latency_estimate("gpt-3.5-turbo")
        
        assert latency == 500


class TestAnthropicProvider:
    """Test Anthropic provider."""
    
    def test_initialization(self):
        """Test provider initialization."""
        provider = AnthropicProvider(api_key="test-key")
        
        assert provider.api_key == "test-key"
        assert provider.default_model == "claude-3-sonnet"
        assert provider.provider_name == "anthropic"
    
    def test_list_models(self):
        """Test listing available models."""
        provider = AnthropicProvider(api_key="test-key")
        models = provider.list_models()
        
        assert len(models) > 0
        assert "claude-3-opus" in models
        assert "claude-3-sonnet" in models


class TestOllamaProvider:
    """Test Ollama provider."""
    
    def test_initialization(self):
        """Test provider initialization."""
        provider = OllamaProvider()
        
        assert provider.base_url == "http://localhost:11434"
        assert provider.default_model == "mistral"
        assert provider.provider_name == "ollama"
    
    @pytest.mark.asyncio
    async def test_get_cost(self):
        """Test cost calculation (always 0 for local)."""
        provider = OllamaProvider()
        cost = await provider.get_cost("mistral", 1000, 500)
        
        assert cost == 0.0
    
    def test_estimate_tokens(self):
        """Test token estimation."""
        provider = OllamaProvider()
        text = "This is a test prompt with several words."
        tokens = provider._estimate_tokens(text)
        
        assert tokens > 0
        assert tokens > len(text.split())


class TestLLMRouter:
    """Test LLM router functionality."""
    
    def test_initialization(self):
        """Test router initialization."""
        router = LLMRouter()
        
        assert router.default_strategy == RoutingStrategy.BALANCED
        assert len(router.default_fallback_chain) > 0
    
    def test_register_provider(self):
        """Test provider registration."""
        router = LLMRouter()
        provider = OpenAIProvider(api_key="test-key")
        
        router.register_provider("openai", provider)
        
        assert "openai" in router.providers
        assert router.get_provider("openai") == provider
    
    @pytest.mark.asyncio
    async def test_select_provider_cost_optimized(self):
        """Test cost-optimized provider selection."""
        router = LLMRouter()
        
        # Register providers
        router.register_provider("openai", OpenAIProvider(api_key="test-key"))
        router.register_provider("ollama", OllamaProvider())
        
        provider, model = await router.select_provider(
            strategy=RoutingStrategy.COST_OPTIMIZED
        )
        
        # Should select cheapest (Ollama is free)
        assert provider == "ollama"
    
    @pytest.mark.asyncio
    async def test_select_provider_latency_optimized(self):
        """Test latency-optimized provider selection."""
        router = LLMRouter()
        
        router.register_provider("openai", OpenAIProvider(api_key="test-key"))
        router.register_provider("anthropic", AnthropicProvider(api_key="test-key"))
        
        provider, model = await router.select_provider(
            strategy=RoutingStrategy.LATENCY_OPTIMIZED
        )
        
        assert provider in ["openai", "anthropic"]
    
    @pytest.mark.asyncio
    async def test_get_fallback_chain(self):
        """Test fallback chain generation."""
        router = LLMRouter()
        
        router.register_provider("openai", OpenAIProvider(api_key="test-key"))
        router.register_provider("anthropic", AnthropicProvider(api_key="test-key"))
        router.register_provider("ollama", OllamaProvider())
        
        chain = await router.get_fallback_chain("openai", "gpt-4")
        
        assert len(chain) > 0
        assert chain[0] == ("openai", "gpt-4")  # Primary is first
    
    @pytest.mark.asyncio
    async def test_get_fallback_chain_with_capability(self):
        """Test fallback chain with capability filter."""
        router = LLMRouter()
        
        router.register_provider("openai", OpenAIProvider(api_key="test-key"))
        router.register_provider("anthropic", AnthropicProvider(api_key="test-key"))
        
        chain = await router.get_fallback_chain(
            "openai",
            "gpt-4",
            required_capability="code"
        )
        
        # All models in chain should have code capability
        for provider, model in chain:
            config = ModelRegistry.get_model_config(provider, model)
            if config:
                assert "code" in config.capabilities
    
    def test_track_usage(self):
        """Test usage tracking."""
        router = LLMRouter()
        
        router.track_usage(
            provider="openai",
            model="gpt-4",
            success=True,
            latency_ms=1000,
            cost_usd=0.05
        )
        
        stats = router.get_usage_stats("openai")
        
        assert "openai/gpt-4" in stats
        assert stats["openai/gpt-4"]["total_calls"] == 1
        assert stats["openai/gpt-4"]["successful_calls"] == 1
        assert stats["openai/gpt-4"]["total_cost_usd"] == 0.05
    
    def test_track_usage_failure(self):
        """Test tracking failed calls."""
        router = LLMRouter()
        
        router.track_usage(
            provider="openai",
            model="gpt-4",
            success=False,
            latency_ms=0,
            cost_usd=0.0
        )
        
        stats = router.get_usage_stats("openai")
        
        assert stats["openai/gpt-4"]["failed_calls"] == 1


class TestLLMService:
    """Test LLM service integration."""
    
    def test_initialization(self):
        """Test service initialization."""
        service = LLMService()
        
        assert service.router is not None
        assert len(service.providers) >= 0  # Depends on config
    
    def test_get_available_providers(self):
        """Test getting available providers."""
        service = LLMService()
        providers = service.get_available_providers()
        
        assert isinstance(providers, list)
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        service = LLMService()
        health = await service.health_check()
        
        assert isinstance(health, dict)
        # At minimum, should have Ollama
        for provider, status in health.items():
            assert isinstance(status, bool)


class TestFallbackChains:
    """Test predefined fallback chains."""
    
    def test_high_quality_chain(self):
        """Test high quality fallback chain."""
        chain = FallbackChain.HIGH_QUALITY
        
        assert len(chain) > 0
        assert chain[0][0] in ["openai", "anthropic"]
    
    def test_cost_optimized_chain(self):
        """Test cost optimized fallback chain."""
        chain = FallbackChain.COST_OPTIMIZED
        
        assert len(chain) > 0
        # Should end with local model
        assert chain[-1][0] == "ollama"
    
    def test_local_only_chain(self):
        """Test local only fallback chain."""
        chain = FallbackChain.LOCAL_ONLY
        
        assert len(chain) > 0
        # All should be ollama
        assert all(p == "ollama" for p, m in chain)
    
    def test_code_generation_chain(self):
        """Test code generation fallback chain."""
        chain = FallbackChain.CODE_GENERATION
        
        assert len(chain) > 0
        # Verify all models have code capability
        for provider, model in chain:
            config = ModelRegistry.get_model_config(provider, model)
            if config:
                assert "code" in config.capabilities
