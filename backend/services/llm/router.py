# -*- coding: utf-8 -*-
"""LLM provider router for intelligent provider selection and fallback."""

import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum

from .provider import LLMProvider, AllProvidersFailedError
from .registry import ModelRegistry, ModelConfig
from .providers import (
    OpenAIProvider,
    AnthropicProvider,
    MistralProvider,
    OllamaProvider,
    TogetherAIProvider,
)

logger = logging.getLogger(__name__)


class RoutingStrategy(str, Enum):
    """Strategy for selecting LLM provider."""
    
    COST_OPTIMIZED = "cost_optimized"
    LATENCY_OPTIMIZED = "latency_optimized"
    QUALITY_OPTIMIZED = "quality_optimized"
    LOCAL_FIRST = "local_first"
    CAPABILITY_MATCH = "capability_match"
    BALANCED = "balanced"


class FallbackChain:
    """Predefined fallback chains for different scenarios."""
    
    HIGH_QUALITY = [
        ("openai", "gpt-4"),
        ("anthropic", "claude-3-opus"),
        ("mistral", "mistral-large"),
        ("together", "meta-llama/Llama-2-70b-chat-hf"),
    ]
    
    COST_OPTIMIZED = [
        ("openai", "gpt-3.5-turbo"),
        ("anthropic", "claude-3-haiku"),
        ("mistral", "mistral-tiny"),
        ("together", "mistralai/Mistral-7B-Instruct-v0.2"),
        ("ollama", "mistral"),
    ]
    
    FAST_LATENCY = [
        ("openai", "gpt-3.5-turbo"),
        ("anthropic", "claude-3-haiku"),
        ("mistral", "mistral-small"),
        ("ollama", "mistral"),
    ]
    
    LOCAL_ONLY = [
        ("ollama", "mistral"),
        ("ollama", "llama2"),
        ("ollama", "codellama"),
    ]
    
    CODE_GENERATION = [
        ("openai", "gpt-4"),
        ("anthropic", "claude-3-sonnet"),
        ("together", "codellama/CodeLlama-34b-Instruct-hf"),
        ("ollama", "codellama"),
    ]
    
    LONG_CONTEXT = [
        ("anthropic", "claude-3-sonnet"),
        ("anthropic", "claude-3-haiku"),
        ("openai", "gpt-4-turbo"),
        ("mistral", "mistral-medium"),
    ]
    
    BALANCED = [
        ("openai", "gpt-3.5-turbo"),
        ("anthropic", "claude-3-sonnet"),
        ("mistral", "mistral-medium"),
        ("together", "mistralai/Mistral-7B-Instruct-v0.2"),
        ("ollama", "mistral"),
    ]


class LLMRouter:
    """
    Intelligent router for LLM provider selection and fallback.
    
    Features:
    - Multiple routing strategies (cost, latency, quality)
    - Automatic fallback on failure
    - Budget-aware selection
    - Capability matching
    - Provider availability checking
    """
    
    def __init__(
        self,
        providers: Optional[Dict[str, LLMProvider]] = None,
        default_strategy: RoutingStrategy = RoutingStrategy.BALANCED,
        default_fallback_chain: Optional[List[Tuple[str, str]]] = None,
    ):
        """
        Initialize the LLM router.
        
        Args:
            providers: Dictionary of provider name -> provider instance
            default_strategy: Default routing strategy
            default_fallback_chain: Default fallback chain
        """
        self.providers = providers or {}
        self.default_strategy = default_strategy
        self.default_fallback_chain = default_fallback_chain or FallbackChain.BALANCED
        self.usage_stats: Dict[str, Dict] = {}
    
    def register_provider(self, name: str, provider: LLMProvider):
        """Register a provider."""
        self.providers[name] = provider
        logger.info(f"Registered LLM provider: {name}")
    
    def get_provider(self, name: str) -> Optional[LLMProvider]:
        """Get a provider by name."""
        return self.providers.get(name)
    
    async def select_provider(
        self,
        task: Optional[str] = None,
        budget_remaining: Optional[float] = None,
        latency_sensitive: bool = False,
        prefer_local: bool = False,
        required_capability: Optional[str] = None,
        strategy: Optional[RoutingStrategy] = None,
        task_complexity: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Select best provider and model based on criteria.
        
        Args:
            task: Task description for logging
            budget_remaining: Remaining budget in USD
            latency_sensitive: Whether to prioritize low latency
            prefer_local: Prefer local models
            required_capability: Required model capability
            strategy: Routing strategy to use
            task_complexity: Task complexity level (XS, S, M, L, XL)
            task_type: Task type for optimization (e.g., "code", "analysis", "simple")
        
        Returns:
            Tuple of (provider_name, model_name)
        """
        strategy = strategy or self.default_strategy
        
        # Auto-select strategy based on task complexity if not specified
        if not strategy and task_complexity:
            strategy = self._select_strategy_by_complexity(task_complexity, task_type)
        
        logger.info(
            f"Selecting LLM provider - task={task}, strategy={strategy}, "
            f"budget={budget_remaining}, latency_sensitive={latency_sensitive}, "
            f"prefer_local={prefer_local}, capability={required_capability}, "
            f"complexity={task_complexity}, task_type={task_type}"
        )
        
        # Get available providers
        available_providers = {
            name: provider
            for name, provider in self.providers.items()
            if provider.is_available()
        }
        
        if not available_providers:
            raise AllProvidersFailedError("No providers are available")
        
        # Apply strategy
        if strategy == RoutingStrategy.LOCAL_FIRST or prefer_local:
            return await self._select_local_first(required_capability)
        
        elif strategy == RoutingStrategy.COST_OPTIMIZED:
            return await self._select_cost_optimized(
                budget_remaining,
                required_capability,
                exclude_local=not prefer_local
            )
        
        elif strategy == RoutingStrategy.LATENCY_OPTIMIZED or latency_sensitive:
            return await self._select_latency_optimized(
                required_capability,
                budget_remaining
            )
        
        elif strategy == RoutingStrategy.QUALITY_OPTIMIZED:
            return await self._select_quality_optimized(
                required_capability,
                budget_remaining
            )
        
        elif strategy == RoutingStrategy.CAPABILITY_MATCH:
            return await self._select_capability_match(required_capability)
        
        else:  # BALANCED
            return await self._select_balanced(
                required_capability,
                budget_remaining,
                prefer_local
            )
    
    def _select_strategy_by_complexity(
        self,
        complexity: str,
        task_type: Optional[str] = None
    ) -> RoutingStrategy:
        """
        Select routing strategy based on task complexity.
        
        Args:
            complexity: Task complexity (XS, S, M, L, XL)
            task_type: Optional task type
        
        Returns:
            Appropriate routing strategy
        """
        # Simple tasks -> cost optimized
        if complexity in ("XS", "S"):
            return RoutingStrategy.COST_OPTIMIZED
        
        # Medium tasks -> balanced
        if complexity == "M":
            return RoutingStrategy.BALANCED
        
        # Complex tasks -> quality optimized
        if complexity in ("L", "XL"):
            return RoutingStrategy.QUALITY_OPTIMIZED
        
        # Default to balanced
        return RoutingStrategy.BALANCED
    
    async def _select_local_first(
        self,
        required_capability: Optional[str] = None
    ) -> Tuple[str, str]:
        """Select local provider first."""
        if "ollama" in self.providers and self.providers["ollama"].is_available():
            models = ModelRegistry.find_models_by_capability(
                required_capability or "code"
            )
            
            for model_config in models:
                if model_config.provider == "ollama":
                    return ("ollama", model_config.model)
        
        return await self._select_cost_optimized(None, required_capability, exclude_local=False)
    
    async def _select_cost_optimized(
        self,
        budget_remaining: Optional[float],
        required_capability: Optional[str],
        exclude_local: bool = False
    ) -> Tuple[str, str]:
        """Select cheapest available provider."""
        max_cost = budget_remaining / 1000 if budget_remaining else None
        
        model_config = ModelRegistry.get_cheapest_model(
            capability=required_capability,
            exclude_local=exclude_local
        )
        
        if model_config and model_config.provider in self.providers:
            return (model_config.provider, model_config.model)
        
        return ("openai", "gpt-3.5-turbo")
    
    async def _select_latency_optimized(
        self,
        required_capability: Optional[str],
        budget_remaining: Optional[float]
    ) -> Tuple[str, str]:
        """Select fastest available provider."""
        max_cost = budget_remaining / 1000 if budget_remaining else None
        
        model_config = ModelRegistry.get_fastest_model(
            capability=required_capability,
            max_cost_per_1k=max_cost
        )
        
        if model_config and model_config.provider in self.providers:
            return (model_config.provider, model_config.model)
        
        return ("openai", "gpt-3.5-turbo")
    
    async def _select_quality_optimized(
        self,
        required_capability: Optional[str],
        budget_remaining: Optional[float]
    ) -> Tuple[str, str]:
        """Select highest quality provider."""
        for provider, model in FallbackChain.HIGH_QUALITY:
            if provider in self.providers and self.providers[provider].is_available():
                if required_capability:
                    config = ModelRegistry.get_model_config(provider, model)
                    if config and required_capability in config.capabilities:
                        return (provider, model)
                else:
                    return (provider, model)
        
        return ("openai", "gpt-4")
    
    async def _select_capability_match(
        self,
        required_capability: Optional[str]
    ) -> Tuple[str, str]:
        """Select provider based on capability match."""
        if not required_capability:
            return ("openai", "gpt-3.5-turbo")
        
        models = ModelRegistry.find_models_by_capability(required_capability)
        
        for model_config in models:
            if model_config.provider in self.providers:
                return (model_config.provider, model_config.model)
        
        return ("openai", "gpt-3.5-turbo")
    
    async def _select_balanced(
        self,
        required_capability: Optional[str],
        budget_remaining: Optional[float],
        prefer_local: bool
    ) -> Tuple[str, str]:
        """Select provider with balanced cost/quality/latency."""
        for provider, model in FallbackChain.BALANCED:
            if provider in self.providers and self.providers[provider].is_available():
                if required_capability:
                    config = ModelRegistry.get_model_config(provider, model)
                    if config and required_capability in config.capabilities:
                        return (provider, model)
                else:
                    return (provider, model)
        
        return ("openai", "gpt-3.5-turbo")
    
    async def get_fallback_chain(
        self,
        primary_provider: str,
        primary_model: str,
        strategy: Optional[RoutingStrategy] = None,
        required_capability: Optional[str] = None,
    ) -> List[Tuple[str, str]]:
        """
        Get fallback chain for a primary provider/model.
        
        Args:
            primary_provider: Primary provider name
            primary_model: Primary model name
            strategy: Routing strategy
            required_capability: Required capability filter
        
        Returns:
            List of (provider, model) tuples in fallback order
        """
        strategy = strategy or self.default_strategy
        
        # Select base fallback chain
        if strategy == RoutingStrategy.COST_OPTIMIZED:
            base_chain = FallbackChain.COST_OPTIMIZED
        elif strategy == RoutingStrategy.LATENCY_OPTIMIZED:
            base_chain = FallbackChain.FAST_LATENCY
        elif strategy == RoutingStrategy.QUALITY_OPTIMIZED:
            base_chain = FallbackChain.HIGH_QUALITY
        elif strategy == RoutingStrategy.LOCAL_FIRST:
            base_chain = FallbackChain.LOCAL_ONLY
        else:
            base_chain = FallbackChain.BALANCED
        
        # Filter by capability if needed
        if required_capability:
            filtered_chain = []
            for provider, model in base_chain:
                config = ModelRegistry.get_model_config(provider, model)
                if config and required_capability in config.capabilities:
                    filtered_chain.append((provider, model))
            
            if filtered_chain:
                base_chain = filtered_chain
        
        # Filter by availability
        available_chain = [
            (provider, model)
            for provider, model in base_chain
            if provider in self.providers and self.providers[provider].is_available()
        ]
        
        # Ensure primary is first
        primary_tuple = (primary_provider, primary_model)
        if primary_tuple in available_chain:
            available_chain.remove(primary_tuple)
        available_chain.insert(0, primary_tuple)
        
        return available_chain
    
    def track_usage(
        self,
        provider: str,
        model: str,
        success: bool,
        latency_ms: int,
        cost_usd: float,
    ):
        """
        Track usage statistics for provider/model.
        
        Args:
            provider: Provider name
            model: Model name
            success: Whether the call succeeded
            latency_ms: Call latency in milliseconds
            cost_usd: Call cost in USD
        """
        key = f"{provider}/{model}"
        
        if key not in self.usage_stats:
            self.usage_stats[key] = {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_latency_ms": 0,
                "total_cost_usd": 0.0,
            }
        
        stats = self.usage_stats[key]
        stats["total_calls"] += 1
        
        if success:
            stats["successful_calls"] += 1
        else:
            stats["failed_calls"] += 1
        
        stats["total_latency_ms"] += latency_ms
        stats["total_cost_usd"] += cost_usd
    
    def get_usage_stats(self, provider: Optional[str] = None) -> Dict:
        """
        Get usage statistics.
        
        Args:
            provider: Optional provider filter
        
        Returns:
            Dictionary of usage statistics
        """
        if provider:
            return {
                key: stats
                for key, stats in self.usage_stats.items()
                if key.startswith(f"{provider}/")
            }
        
        return self.usage_stats
