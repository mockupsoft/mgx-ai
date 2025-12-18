# -*- coding: utf-8 -*-
"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Dict, List, Optional


class ProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class RateLimitError(ProviderError):
    """Exception raised when rate limit is exceeded."""
    pass


class AuthenticationError(ProviderError):
    """Exception raised when authentication fails."""
    pass


class ModelNotFoundError(ProviderError):
    """Exception raised when model is not available."""
    pass


class AllProvidersFailedError(Exception):
    """Exception raised when all providers in fallback chain fail."""
    pass


@dataclass
class ModelCapabilities:
    """Model capabilities and features."""
    
    code_generation: bool = False
    reasoning: bool = False
    analysis: bool = False
    long_context: bool = False
    function_calling: bool = False
    vision: bool = False
    streaming: bool = False
    max_tokens: int = 4096
    supported_languages: List[str] = None
    
    def __post_init__(self):
        if self.supported_languages is None:
            self.supported_languages = []


@dataclass
class LLMResponse:
    """Response from LLM provider."""
    
    content: str
    model: str
    provider: str
    tokens_prompt: int
    tokens_completion: int
    tokens_total: int
    cost_usd: float
    latency_ms: int
    finish_reason: Optional[str] = None
    metadata: Optional[Dict] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    Implementations should provide:
    - Text generation
    - Streaming generation
    - Cost calculation
    - Latency estimation
    - Model capabilities
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the provider.
        
        Args:
            api_key: API key for authentication
            base_url: Base URL for API endpoint
            default_model: Default model to use
            **kwargs: Additional provider-specific configuration
        """
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self.config = kwargs
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> LLMResponse:
        """
        Generate text completion.
        
        Args:
            prompt: Input prompt
            model: Model name (uses default if not specified)
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model-specific parameters
        
        Returns:
            LLMResponse with generated text and metadata
        
        Raises:
            ProviderError: If generation fails
            RateLimitError: If rate limit is exceeded
            AuthenticationError: If authentication fails
            ModelNotFoundError: If model is not available
        """
        pass
    
    @abstractmethod
    async def stream_generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream text completion.
        
        Args:
            prompt: Input prompt
            model: Model name (uses default if not specified)
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model-specific parameters
        
        Yields:
            Text chunks as they are generated
        
        Raises:
            ProviderError: If streaming fails
            RateLimitError: If rate limit is exceeded
        """
        pass
    
    @abstractmethod
    async def get_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """
        Calculate cost for token usage.
        
        Args:
            model: Model name
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
        
        Returns:
            Cost in USD
        """
        pass
    
    @abstractmethod
    async def get_latency_estimate(self, model: str) -> int:
        """
        Get estimated latency for model.
        
        Args:
            model: Model name
        
        Returns:
            Estimated latency in milliseconds
        """
        pass
    
    @abstractmethod
    def get_model_capabilities(self, model: str) -> ModelCapabilities:
        """
        Get capabilities for a specific model.
        
        Args:
            model: Model name
        
        Returns:
            ModelCapabilities object
        """
        pass
    
    @abstractmethod
    def list_models(self) -> List[str]:
        """
        List available models for this provider.
        
        Returns:
            List of model names
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if provider is available and configured.
        
        Returns:
            True if provider can be used, False otherwise
        """
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get provider name."""
        pass
