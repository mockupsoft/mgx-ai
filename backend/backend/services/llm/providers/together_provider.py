# -*- coding: utf-8 -*-
"""Together AI LLM provider implementation."""

import logging
import time
from typing import AsyncIterator, List, Optional
import httpx

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


class TogetherAIProvider(LLMProvider):
    """Together AI LLM provider implementation."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.together.xyz",
        default_model: str = "mistralai/Mistral-7B-Instruct-v0.2",
        **kwargs
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
            **kwargs
        )
        self._client = None
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(120.0),
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
        """Generate text completion using Together AI."""
        model = model or self.default_model
        client = self._get_client()
        
        start_time = time.time()
        
        try:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    **kwargs
                }
            )
            
            if response.status_code == 401:
                raise AuthenticationError("Together AI authentication failed. Check API key.")
            elif response.status_code == 429:
                raise RateLimitError("Together AI rate limit exceeded")
            elif response.status_code != 200:
                raise ProviderError(
                    f"Together AI request failed with status {response.status_code}: {response.text}"
                )
            
            data = response.json()
            latency_ms = int((time.time() - start_time) * 1000)
            
            content = data["choices"][0]["message"]["content"]
            tokens_prompt = data.get("usage", {}).get("prompt_tokens", 0)
            tokens_completion = data.get("usage", {}).get("completion_tokens", 0)
            tokens_total = data.get("usage", {}).get("total_tokens", tokens_prompt + tokens_completion)
            
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
                finish_reason=data["choices"][0].get("finish_reason"),
                metadata={
                    "model": data.get("model"),
                    "id": data.get("id"),
                }
            )
            
        except (AuthenticationError, RateLimitError, ProviderError):
            raise
        except Exception as e:
            error_msg = str(e)
            
            if "model" in error_msg.lower() and "not found" in error_msg.lower():
                raise ModelNotFoundError(f"Model not found: {model}")
            else:
                raise ProviderError(f"Together AI generation failed: {error_msg}")
    
    async def stream_generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream text completion using Together AI."""
        model = model or self.default_model
        client = self._get_client()
        
        try:
            async with client.stream(
                "POST",
                "/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                    **kwargs
                }
            ) as response:
                if response.status_code == 429:
                    raise RateLimitError("Together AI rate limit exceeded")
                elif response.status_code != 200:
                    raise ProviderError(f"Together AI streaming failed with status {response.status_code}")
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        line = line[6:]
                        if line.strip() == "[DONE]":
                            break
                        
                        try:
                            import json
                            data = json.loads(line)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            continue
                    
        except (RateLimitError, ProviderError):
            raise
        except Exception as e:
            raise ProviderError(f"Together AI streaming failed: {e}")
    
    async def get_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """Calculate cost for Together AI model."""
        config = ModelRegistry.get_model_config("together", model)
        
        if not config:
            logger.warning(f"Model config not found for together/{model}, using defaults")
            return 0.0
        
        prompt_cost = (prompt_tokens / 1000) * config.cost_per_1k_prompt
        completion_cost = (completion_tokens / 1000) * config.cost_per_1k_completion
        
        return prompt_cost + completion_cost
    
    async def get_latency_estimate(self, model: str) -> int:
        """Get estimated latency for Together AI model."""
        config = ModelRegistry.get_model_config("together", model)
        return config.latency_estimate_ms if config else 2000
    
    def get_model_capabilities(self, model: str) -> ModelCapabilities:
        """Get capabilities for Together AI model."""
        config = ModelRegistry.get_model_config("together", model)
        
        if not config:
            return ModelCapabilities(
                code_generation=True,
                reasoning=False,
                analysis=True,
                max_tokens=4096,
            )
        
        return ModelCapabilities(
            code_generation="code" in config.capabilities,
            reasoning="reasoning" in config.capabilities,
            analysis="analysis" in config.capabilities,
            long_context="long_context" in config.capabilities,
            function_calling=False,
            vision=False,
            streaming=True,
            max_tokens=config.max_tokens,
        )
    
    def list_models(self) -> List[str]:
        """List available Together AI models."""
        return [
            model.split("/")[1]
            for model in ModelRegistry.list_models("together")
        ]
    
    def is_available(self) -> bool:
        """Check if Together AI provider is available."""
        if not self.api_key:
            return False
        
        try:
            import httpx
            return True
        except ImportError:
            return False
    
    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "together"
