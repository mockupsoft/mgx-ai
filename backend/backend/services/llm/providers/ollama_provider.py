# -*- coding: utf-8 -*-
"""Ollama local LLM provider implementation."""

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


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider implementation."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "http://localhost:11434",
        default_model: str = "mistral",
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
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(300.0),
            )
        return self._client
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation for local models."""
        return len(text.split()) + len(text) // 4
    
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> LLMResponse:
        """Generate text completion using Ollama."""
        model = model or self.default_model
        client = self._get_client()
        
        start_time = time.time()
        
        try:
            response = await client.post(
                "/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                        **kwargs
                    }
                }
            )
            
            if response.status_code != 200:
                raise ProviderError(
                    f"Ollama request failed with status {response.status_code}: {response.text}"
                )
            
            data = response.json()
            latency_ms = int((time.time() - start_time) * 1000)
            
            content = data.get("response", "")
            
            # Ollama doesn't always return token counts, estimate them
            tokens_prompt = data.get("prompt_eval_count", self._estimate_tokens(prompt))
            tokens_completion = data.get("eval_count", self._estimate_tokens(content))
            tokens_total = tokens_prompt + tokens_completion
            
            # Local models are free
            cost_usd = 0.0
            
            return LLMResponse(
                content=content,
                model=model,
                provider=self.provider_name,
                tokens_prompt=tokens_prompt,
                tokens_completion=tokens_completion,
                tokens_total=tokens_total,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                finish_reason=data.get("done_reason"),
                metadata={
                    "model": data.get("model"),
                    "total_duration": data.get("total_duration"),
                    "load_duration": data.get("load_duration"),
                }
            )
            
        except httpx.ConnectError as e:
            raise ProviderError(
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Make sure Ollama is running. Error: {e}"
            )
        except Exception as e:
            error_msg = str(e)
            
            if "model" in error_msg.lower() and "not found" in error_msg.lower():
                raise ModelNotFoundError(f"Model not found: {model}. Pull it with: ollama pull {model}")
            else:
                raise ProviderError(f"Ollama generation failed: {error_msg}")
    
    async def stream_generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream text completion using Ollama."""
        model = model or self.default_model
        client = self._get_client()
        
        try:
            async with client.stream(
                "POST",
                "/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": True,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                        **kwargs
                    }
                }
            ) as response:
                if response.status_code != 200:
                    raise ProviderError(f"Ollama streaming failed with status {response.status_code}")
                
                async for line in response.aiter_lines():
                    if line:
                        import json
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                        except json.JSONDecodeError:
                            continue
                    
        except httpx.ConnectError as e:
            raise ProviderError(
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Make sure Ollama is running. Error: {e}"
            )
        except Exception as e:
            raise ProviderError(f"Ollama streaming failed: {e}")
    
    async def get_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """Calculate cost for Ollama model (always 0 for local)."""
        return 0.0
    
    async def get_latency_estimate(self, model: str) -> int:
        """Get estimated latency for Ollama model."""
        config = ModelRegistry.get_model_config("ollama", model)
        return config.latency_estimate_ms if config else 5000
    
    def get_model_capabilities(self, model: str) -> ModelCapabilities:
        """Get capabilities for Ollama model."""
        config = ModelRegistry.get_model_config("ollama", model)
        
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
        """List available Ollama models."""
        return [
            model.split("/")[1]
            for model in ModelRegistry.list_models("ollama")
        ]
    
    async def list_installed_models(self) -> List[str]:
        """List models installed in Ollama."""
        client = self._get_client()
        
        try:
            response = await client.get("/api/tags")
            
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            else:
                return []
                
        except Exception as e:
            logger.warning(f"Failed to list Ollama models: {e}")
            return []
    
    def is_available(self) -> bool:
        """Check if Ollama provider is available."""
        try:
            import httpx
            return True
        except ImportError:
            return False
    
    async def check_connection(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            client = self._get_client()
            response = await client.get("/api/tags", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False
    
    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "ollama"
