# -*- coding: utf-8 -*-
"""OpenAI LLM provider implementation."""

import logging
import time
from typing import AsyncIterator, List, Optional

from ..provider import (
    LLMProvider,
    LLMResponse,
    ModelCapabilities,
    ProviderError,
    RateLimitError,
    AuthenticationError,
    ModelNotFoundError,
)
from ..registry import ModelRegistry

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider implementation."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        organization: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: str = "gpt-3.5-turbo",
        **kwargs
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
            **kwargs
        )
        self.organization = organization
        self._client = None
    
    def _get_client(self):
        """Lazy initialize OpenAI client."""
        if self._client is None:
            try:
                import openai
                self._client = openai.AsyncOpenAI(
                    api_key=self.api_key,
                    organization=self.organization,
                    base_url=self.base_url,
                )
            except ImportError:
                raise ProviderError(
                    "OpenAI package not installed. Install with: pip install openai"
                )
        return self._client
    
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> LLMResponse:
        """Generate text completion using OpenAI."""
        model = model or self.default_model
        client = self._get_client()
        
        start_time = time.time()
        
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            content = response.choices[0].message.content
            tokens_prompt = response.usage.prompt_tokens
            tokens_completion = response.usage.completion_tokens
            tokens_total = response.usage.total_tokens
            
            cost_usd = await self.get_cost(model, tokens_prompt, tokens_completion)
            
            return LLMResponse(
                content=content,
                model=model,
                provider=self.provider_name,
                tokens_prompt=tokens_prompt,
                tokens_completion=tokens_completion,
                tokens_total=tokens_total,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                finish_reason=response.choices[0].finish_reason,
                metadata={
                    "model": response.model,
                    "created": response.created,
                }
            )
            
        except Exception as e:
            error_msg = str(e)
            
            if "rate_limit" in error_msg.lower():
                raise RateLimitError(f"OpenAI rate limit exceeded: {error_msg}")
            elif "authentication" in error_msg.lower() or "api_key" in error_msg.lower():
                raise AuthenticationError(f"OpenAI authentication failed: {error_msg}")
            elif "model" in error_msg.lower() and "not found" in error_msg.lower():
                raise ModelNotFoundError(f"Model not found: {model}")
            else:
                raise ProviderError(f"OpenAI generation failed: {error_msg}")
    
    async def stream_generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream text completion using OpenAI."""
        model = model or self.default_model
        client = self._get_client()
        
        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            error_msg = str(e)
            
            if "rate_limit" in error_msg.lower():
                raise RateLimitError(f"OpenAI rate limit exceeded: {error_msg}")
            else:
                raise ProviderError(f"OpenAI streaming failed: {error_msg}")
    
    async def get_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """Calculate cost for OpenAI model."""
        config = ModelRegistry.get_model_config("openai", model)
        
        if not config:
            logger.warning(f"Model config not found for openai/{model}, using defaults")
            return 0.0
        
        prompt_cost = (prompt_tokens / 1000) * config.cost_per_1k_prompt
        completion_cost = (completion_tokens / 1000) * config.cost_per_1k_completion
        
        return prompt_cost + completion_cost
    
    async def get_latency_estimate(self, model: str) -> int:
        """Get estimated latency for OpenAI model."""
        config = ModelRegistry.get_model_config("openai", model)
        return config.latency_estimate_ms if config else 1000
    
    def get_model_capabilities(self, model: str) -> ModelCapabilities:
        """Get capabilities for OpenAI model."""
        config = ModelRegistry.get_model_config("openai", model)
        
        if not config:
            return ModelCapabilities()
        
        return ModelCapabilities(
            code_generation="code" in config.capabilities,
            reasoning="reasoning" in config.capabilities,
            analysis="analysis" in config.capabilities,
            long_context="long_context" in config.capabilities,
            function_calling="function_calling" in config.capabilities,
            vision="vision" in config.capabilities,
            streaming=True,
            max_tokens=config.max_tokens,
        )
    
    def list_models(self) -> List[str]:
        """List available OpenAI models."""
        return [
            model.split("/")[1]
            for model in ModelRegistry.list_models("openai")
        ]
    
    def is_available(self) -> bool:
        """Check if OpenAI provider is available."""
        if not self.api_key:
            return False
        
        try:
            import openai
            return True
        except ImportError:
            return False
    
    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "openai"
