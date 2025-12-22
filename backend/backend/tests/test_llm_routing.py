# -*- coding: utf-8 -*-
"""LLM routing & fallback tests.

This file complements the existing provider/registry tests by focusing on:
- routing strategy selection with deterministic provider availability
- fallback execution via ``LLMService.generate``
- ensuring cost tracking is only recorded for successful calls (no double-charge)
"""

from __future__ import annotations

from typing import AsyncIterator, List, Optional
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.llm.provider import (
    AllProvidersFailedError,
    LLMProvider,
    LLMResponse,
    ProviderError,
    RateLimitError,
)
from backend.services.llm.router import LLMRouter, RoutingStrategy
from backend.services.llm.llm_service import LLMService


class DummyProvider(LLMProvider):
    def __init__(
        self,
        *,
        provider_name: str,
        available: bool = True,
        fail_with: Optional[Exception] = None,
        content: str = "ok",
    ):
        super().__init__(api_key="test", default_model="default")
        self.provider_name = provider_name
        self._available = available
        self._fail_with = fail_with
        self._content = content

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> LLMResponse:
        if self._fail_with is not None:
            raise self._fail_with
        used_model = model or self.default_model or "default"
        return LLMResponse(
            content=f"{self.provider_name}:{used_model}:{self._content}",
            model=used_model,
            provider=self.provider_name,
            tokens_prompt=10,
            tokens_completion=5,
            tokens_total=15,
            cost_usd=0.01,
            latency_ms=123,
            metadata={"prompt_len": len(prompt)},
        )

    async def stream_generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> AsyncIterator[str]:
        yield "chunk"

    async def get_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        return 0.0

    async def get_latency_estimate(self, model: str) -> int:
        return 1

    def get_model_capabilities(self, model: str):
        raise NotImplementedError

    def list_models(self) -> List[str]:
        return ["gpt-4", "gpt-3.5-turbo", "claude-3-sonnet", "mistral"]

    def is_available(self) -> bool:
        return self._available


class TestLLMRouterStrategies:
    @pytest.mark.asyncio
    async def test_select_provider_respects_availability(self):
        openai = DummyProvider(provider_name="openai", available=False)
        anthropic = DummyProvider(provider_name="anthropic", available=True)

        router = LLMRouter(providers={"openai": openai, "anthropic": anthropic})

        provider, model = await router.select_provider(strategy=RoutingStrategy.QUALITY_OPTIMIZED)

        assert provider == "anthropic"
        assert model.startswith("claude")

    @pytest.mark.asyncio
    async def test_select_provider_local_first_prefers_ollama_when_available(self):
        ollama = DummyProvider(provider_name="ollama", available=True)
        openai = DummyProvider(provider_name="openai", available=True)

        router = LLMRouter(providers={"ollama": ollama, "openai": openai})

        provider, _model = await router.select_provider(strategy=RoutingStrategy.LOCAL_FIRST)
        assert provider == "ollama"


class TestLLMServiceFallback:
    @pytest.mark.asyncio
    async def test_fallback_chain_executes_and_logs_cost_only_once(self):
        # Primary provider fails; fallback succeeds.
        openai = DummyProvider(
            provider_name="openai",
            available=True,
            fail_with=RateLimitError("rl"),
        )
        anthropic = DummyProvider(
            provider_name="anthropic",
            available=True,
            content="fallback",
        )

        router = LLMRouter(providers={"openai": openai, "anthropic": anthropic})

        with patch.object(
            LLMService,
            "_initialize_providers",
            return_value={"openai": openai, "anthropic": anthropic},
        ):
            service = LLMService(db_session=None, router=router)

        service.cost_tracker = AsyncMock()

        resp = await service.generate(
            prompt="hello",
            workspace_id="ws-1",
            execution_id="exec-1",
            required_capability="code",
            enable_fallback=True,
        )

        assert resp.provider == "anthropic"
        assert "fallback" in resp.content

        # log_llm_call should be called exactly once for the successful call.
        assert service.cost_tracker.log_llm_call.await_count == 1
        call_kwargs = service.cost_tracker.log_llm_call.await_args.kwargs
        assert call_kwargs["provider"] == "anthropic"

        stats = router.get_usage_stats()
        openai_failed = any(k.startswith("openai/") and v["failed_calls"] >= 1 for k, v in stats.items())
        anthropic_success = any(
            k.startswith("anthropic/") and v["successful_calls"] >= 1 for k, v in stats.items()
        )

        assert openai_failed
        assert anthropic_success

    @pytest.mark.asyncio
    async def test_all_fallbacks_exhausted_raises(self):
        openai = DummyProvider(
            provider_name="openai",
            available=True,
            fail_with=ProviderError("down"),
        )
        anthropic = DummyProvider(
            provider_name="anthropic",
            available=True,
            fail_with=ProviderError("down"),
        )

        router = LLMRouter(providers={"openai": openai, "anthropic": anthropic})

        with patch.object(
            LLMService,
            "_initialize_providers",
            return_value={"openai": openai, "anthropic": anthropic},
        ):
            service = LLMService(db_session=None, router=router)

        with pytest.raises(AllProvidersFailedError):
            await service.generate(prompt="hello", enable_fallback=True)
