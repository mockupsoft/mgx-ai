# -*- coding: utf-8 -*-
"""Anthropic (Claude) LLM provider implementation."""

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


class AnthropicProvider(LLMProvider):
    """Anthropic (Claude) LLM provider implementation."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: str = "claude-3-sonnet",
        **kwargs
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
            **kwargs
        )
        self._client = None
    
    def _get_client(self):
        """Lazy initialize Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.AsyncAnthropic(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except ImportError:
                raise ProviderError(
                    "Anthropic package not installed. Install with: pip install anthropic"
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
        """Generate text completion using Anthropic."""
        model = model or self.default_model
        client = self._get_client()
        
        start_time = time.time()
        
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            content = response.content[0].text
            tokens_prompt = response.usage.input_tokens
            tokens_completion = response.usage.output_tokens
            tokens_total = tokens_prompt + tokens_completion
            
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
                finish_reason=response.stop_reason,
                metadata={
                    "model": response.model,
                    "id": response.id,
                    "type": response.type,
                }
            )
            
        except Exception as e:
            error_msg = str(e)
            
            if "rate_limit" in error_msg.lower() or "429" in error_msg:
                raise RateLimitError(f"Anthropic rate limit exceeded: {error_msg}")
            elif "authentication" in error_msg.lower() or "401" in error_msg:
                raise AuthenticationError(f"Anthropic authentication failed: {error_msg}")
            elif "model" in error_msg.lower() and "not found" in error_msg.lower():
                raise ModelNotFoundError(f"Model not found: {model}")
            else:
                raise ProviderError(f"Anthropic generation failed: {error_msg}")
    
    async def stream_generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream text completion using Anthropic."""
        model = model or self.default_model
        client = self._get_client()
        
        try:
            async with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                    
        except Exception as e:
            error_msg = str(e)
            
            if "rate_limit" in error_msg.lower() or "429" in error_msg:
                raise RateLimitError(f"Anthropic rate limit exceeded: {error_msg}")
            else:
                raise ProviderError(f"Anthropic streaming failed: {error_msg}")
    
    async def get_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """Calculate cost for Anthropic model."""
        config = ModelRegistry.get_model_config("anthropic", model)
        
        if not config:
            logger.warning(f"Model config not found for anthropic/{model}, using defaults")
            return 0.0
        
        prompt_cost = (prompt_tokens / 1000) * config.cost_per_1k_prompt
        completion_cost = (completion_tokens / 1000) * config.cost_per_1k_completion
        
        return prompt_cost + completion_cost
    
    async def get_latency_estimate(self, model: str) -> int:
        """Get estimated latency for Anthropic model."""
        config = ModelRegistry.get_model_config("anthropic", model)
        return config.latency_estimate_ms if config else 1000
    
    def get_model_capabilities(self, model: str) -> ModelCapabilities:
        """Get capabilities for Anthropic model."""
        config = ModelRegistry.get_model_config("anthropic", model)
        
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
        """List available Anthropic models."""
        return [
            model.split("/")[1]
            for model in ModelRegistry.list_models("anthropic")
        ]
    
    def is_available(self) -> bool:
        """Check if Anthropic provider is available."""
        if not self.api_key:
            return False
        
        try:
            import anthropic
            return True
        except ImportError:
            return False
    
    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "anthropic"
