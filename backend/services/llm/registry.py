# -*- coding: utf-8 -*-
"""Model registry for LLM provider configurations and capabilities."""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    
    provider: str
    model: str
    max_tokens: int
    cost_per_1k_prompt: float
    cost_per_1k_completion: float
    latency_estimate_ms: int
    capabilities: List[str]
    context_window: int = None
    
    def __post_init__(self):
        if self.context_window is None:
            self.context_window = self.max_tokens


class ModelRegistry:
    """
    Central registry for all LLM models and their configurations.
    
    Provides:
    - Model metadata (pricing, capabilities, limits)
    - Model lookup and search
    - Capability-based model selection
    """
    
    # Model configurations by provider
    MODELS: Dict[str, Dict[str, Dict]] = {
        "openai": {
            "gpt-4": {
                "max_tokens": 8192,
                "context_window": 8192,
                "cost_per_1k_prompt": 0.03,
                "cost_per_1k_completion": 0.06,
                "latency_estimate_ms": 1000,
                "capabilities": ["code", "reasoning", "analysis", "function_calling"],
            },
            "gpt-4-turbo": {
                "max_tokens": 4096,
                "context_window": 128000,
                "cost_per_1k_prompt": 0.01,
                "cost_per_1k_completion": 0.03,
                "latency_estimate_ms": 800,
                "capabilities": ["code", "reasoning", "analysis", "function_calling", "vision"],
            },
            "gpt-4-32k": {
                "max_tokens": 32768,
                "context_window": 32768,
                "cost_per_1k_prompt": 0.06,
                "cost_per_1k_completion": 0.12,
                "latency_estimate_ms": 1500,
                "capabilities": ["code", "reasoning", "analysis", "long_context"],
            },
            "gpt-3.5-turbo": {
                "max_tokens": 4096,
                "context_window": 16385,
                "cost_per_1k_prompt": 0.0005,
                "cost_per_1k_completion": 0.0015,
                "latency_estimate_ms": 500,
                "capabilities": ["code", "simple_analysis", "function_calling"],
            },
            "gpt-3.5-turbo-16k": {
                "max_tokens": 16384,
                "context_window": 16384,
                "cost_per_1k_prompt": 0.001,
                "cost_per_1k_completion": 0.002,
                "latency_estimate_ms": 600,
                "capabilities": ["code", "simple_analysis", "long_context"],
            },
        },
        "anthropic": {
            "claude-3-opus": {
                "max_tokens": 4096,
                "context_window": 200000,
                "cost_per_1k_prompt": 0.015,
                "cost_per_1k_completion": 0.075,
                "latency_estimate_ms": 1500,
                "capabilities": ["code", "reasoning", "analysis", "long_context", "vision"],
            },
            "claude-3-sonnet": {
                "max_tokens": 4096,
                "context_window": 200000,
                "cost_per_1k_prompt": 0.003,
                "cost_per_1k_completion": 0.015,
                "latency_estimate_ms": 800,
                "capabilities": ["code", "reasoning", "analysis", "long_context"],
            },
            "claude-3-haiku": {
                "max_tokens": 4096,
                "context_window": 200000,
                "cost_per_1k_prompt": 0.00025,
                "cost_per_1k_completion": 0.00125,
                "latency_estimate_ms": 500,
                "capabilities": ["code", "simple_analysis", "long_context"],
            },
            "claude-2.1": {
                "max_tokens": 4096,
                "context_window": 200000,
                "cost_per_1k_prompt": 0.008,
                "cost_per_1k_completion": 0.024,
                "latency_estimate_ms": 1000,
                "capabilities": ["code", "reasoning", "analysis", "long_context"],
            },
        },
        "mistral": {
            "mistral-large": {
                "max_tokens": 4096,
                "context_window": 32768,
                "cost_per_1k_prompt": 0.008,
                "cost_per_1k_completion": 0.024,
                "latency_estimate_ms": 1200,
                "capabilities": ["code", "reasoning", "analysis"],
            },
            "mistral-medium": {
                "max_tokens": 4096,
                "context_window": 32768,
                "cost_per_1k_prompt": 0.0027,
                "cost_per_1k_completion": 0.0081,
                "latency_estimate_ms": 1000,
                "capabilities": ["code", "analysis"],
            },
            "mistral-small": {
                "max_tokens": 4096,
                "context_window": 32768,
                "cost_per_1k_prompt": 0.002,
                "cost_per_1k_completion": 0.006,
                "latency_estimate_ms": 800,
                "capabilities": ["code", "simple_analysis"],
            },
            "mistral-tiny": {
                "max_tokens": 4096,
                "context_window": 32768,
                "cost_per_1k_prompt": 0.00025,
                "cost_per_1k_completion": 0.00075,
                "latency_estimate_ms": 600,
                "capabilities": ["code"],
            },
        },
        "ollama": {
            "llama2": {
                "max_tokens": 4096,
                "context_window": 4096,
                "cost_per_1k_prompt": 0.0,
                "cost_per_1k_completion": 0.0,
                "latency_estimate_ms": 5000,
                "capabilities": ["code", "simple_analysis"],
            },
            "llama2:13b": {
                "max_tokens": 4096,
                "context_window": 4096,
                "cost_per_1k_prompt": 0.0,
                "cost_per_1k_completion": 0.0,
                "latency_estimate_ms": 8000,
                "capabilities": ["code", "analysis"],
            },
            "llama2:70b": {
                "max_tokens": 4096,
                "context_window": 4096,
                "cost_per_1k_prompt": 0.0,
                "cost_per_1k_completion": 0.0,
                "latency_estimate_ms": 15000,
                "capabilities": ["code", "reasoning", "analysis"],
            },
            "mistral": {
                "max_tokens": 8192,
                "context_window": 32768,
                "cost_per_1k_prompt": 0.0,
                "cost_per_1k_completion": 0.0,
                "latency_estimate_ms": 4000,
                "capabilities": ["code", "analysis"],
            },
            "codellama": {
                "max_tokens": 4096,
                "context_window": 16384,
                "cost_per_1k_prompt": 0.0,
                "cost_per_1k_completion": 0.0,
                "latency_estimate_ms": 6000,
                "capabilities": ["code"],
            },
            "codellama:13b": {
                "max_tokens": 4096,
                "context_window": 16384,
                "cost_per_1k_prompt": 0.0,
                "cost_per_1k_completion": 0.0,
                "latency_estimate_ms": 9000,
                "capabilities": ["code"],
            },
            "qwen3-coder:30b": {
                "max_tokens": 8192,
                "context_window": 32768,
                "cost_per_1k_prompt": 0.0,
                "cost_per_1k_completion": 0.0,
                "latency_estimate_ms": 12000,
                "capabilities": ["code", "analysis", "reasoning"],
            },
        },
        "together": {
            "mistralai/Mistral-7B-Instruct-v0.2": {
                "max_tokens": 8192,
                "context_window": 32768,
                "cost_per_1k_prompt": 0.0002,
                "cost_per_1k_completion": 0.0002,
                "latency_estimate_ms": 1500,
                "capabilities": ["code", "analysis"],
            },
            "codellama/CodeLlama-34b-Instruct-hf": {
                "max_tokens": 4096,
                "context_window": 16384,
                "cost_per_1k_prompt": 0.000776,
                "cost_per_1k_completion": 0.000776,
                "latency_estimate_ms": 2000,
                "capabilities": ["code"],
            },
            "meta-llama/Llama-2-70b-chat-hf": {
                "max_tokens": 4096,
                "context_window": 4096,
                "cost_per_1k_prompt": 0.0009,
                "cost_per_1k_completion": 0.0009,
                "latency_estimate_ms": 2500,
                "capabilities": ["code", "reasoning", "analysis"],
            },
        },
    }
    
    @classmethod
    def get_model_config(cls, provider: str, model: str) -> Optional[ModelConfig]:
        """
        Get configuration for a specific model.
        
        Args:
            provider: Provider name
            model: Model name
        
        Returns:
            ModelConfig if found, None otherwise
        """
        provider_lower = provider.lower()
        model_lower = model.lower()
        
        if provider_lower not in cls.MODELS:
            return None
        
        model_data = cls.MODELS[provider_lower].get(model_lower)
        if not model_data:
            return None
        
        return ModelConfig(
            provider=provider_lower,
            model=model_lower,
            **model_data
        )
    
    @classmethod
    def list_models(cls, provider: Optional[str] = None) -> List[str]:
        """
        List available models.
        
        Args:
            provider: Optional provider filter
        
        Returns:
            List of model identifiers (provider/model)
        """
        models = []
        
        if provider:
            provider_lower = provider.lower()
            if provider_lower in cls.MODELS:
                models.extend([
                    f"{provider_lower}/{model}"
                    for model in cls.MODELS[provider_lower].keys()
                ])
        else:
            for prov, prov_models in cls.MODELS.items():
                models.extend([
                    f"{prov}/{model}"
                    for model in prov_models.keys()
                ])
        
        return models
    
    @classmethod
    def find_models_by_capability(
        cls,
        capability: str,
        max_cost_per_1k: Optional[float] = None,
        max_latency_ms: Optional[int] = None
    ) -> List[ModelConfig]:
        """
        Find models that have a specific capability.
        
        Args:
            capability: Required capability
            max_cost_per_1k: Maximum cost per 1K tokens (prompt + completion)
            max_latency_ms: Maximum latency in milliseconds
        
        Returns:
            List of matching ModelConfig objects
        """
        matching_models = []
        
        for provider, models in cls.MODELS.items():
            for model, config in models.items():
                if capability not in config["capabilities"]:
                    continue
                
                total_cost = config["cost_per_1k_prompt"] + config["cost_per_1k_completion"]
                
                if max_cost_per_1k and total_cost > max_cost_per_1k:
                    continue
                
                if max_latency_ms and config["latency_estimate_ms"] > max_latency_ms:
                    continue
                
                matching_models.append(ModelConfig(
                    provider=provider,
                    model=model,
                    **config
                ))
        
        return matching_models
    
    @classmethod
    def get_cheapest_model(
        cls,
        capability: Optional[str] = None,
        exclude_local: bool = False
    ) -> Optional[ModelConfig]:
        """
        Get the cheapest model, optionally filtered by capability.
        
        Args:
            capability: Required capability filter
            exclude_local: Exclude local/free models
        
        Returns:
            ModelConfig for cheapest model, None if no match
        """
        candidates = []
        
        for provider, models in cls.MODELS.items():
            if exclude_local and provider in ["ollama"]:
                continue
            
            for model, config in models.items():
                if capability and capability not in config["capabilities"]:
                    continue
                
                total_cost = config["cost_per_1k_prompt"] + config["cost_per_1k_completion"]
                candidates.append((total_cost, provider, model, config))
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda x: x[0])
        _, provider, model, config = candidates[0]
        
        return ModelConfig(provider=provider, model=model, **config)
    
    @classmethod
    def get_fastest_model(
        cls,
        capability: Optional[str] = None,
        max_cost_per_1k: Optional[float] = None
    ) -> Optional[ModelConfig]:
        """
        Get the fastest model, optionally filtered by capability and cost.
        
        Args:
            capability: Required capability filter
            max_cost_per_1k: Maximum cost per 1K tokens
        
        Returns:
            ModelConfig for fastest model, None if no match
        """
        candidates = []
        
        for provider, models in cls.MODELS.items():
            for model, config in models.items():
                if capability and capability not in config["capabilities"]:
                    continue
                
                total_cost = config["cost_per_1k_prompt"] + config["cost_per_1k_completion"]
                
                if max_cost_per_1k and total_cost > max_cost_per_1k:
                    continue
                
                candidates.append((
                    config["latency_estimate_ms"],
                    provider,
                    model,
                    config
                ))
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda x: x[0])
        _, provider, model, config = candidates[0]
        
        return ModelConfig(provider=provider, model=model, **config)
