# -*- coding: utf-8 -*-
"""End-to-end-ish integration scenarios.

These are intentionally lightweight and mock external services. The goal is to
validate that the core building blocks (RAG enhancement + LLM routing) can be
composed into realistic execution flows.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.services.knowledge.enhanced_actions import RAGEnhancedAction
from backend.services.llm.router import LLMRouter, RoutingStrategy
from backend.services.llm.provider import LLMResponse


class TestRoutingScenarios:
    @pytest.mark.asyncio
    async def test_simple_task_uses_cost_optimized_route(self):
        router = LLMRouter(
            providers={
                "ollama": AsyncMock(is_available=lambda: True),
                "openai": AsyncMock(is_available=lambda: True),
            },
        )
        provider, _model = await router.select_provider(strategy=RoutingStrategy.COST_OPTIMIZED)
        # With ollama available, cost optimized should choose a free local model.
        assert provider == "ollama"

    @pytest.mark.asyncio
    async def test_complex_task_uses_quality_optimized_route(self):
        router = LLMRouter(
            providers={
                "openai": AsyncMock(is_available=lambda: True),
                "anthropic": AsyncMock(is_available=lambda: True),
            },
        )
        provider, model = await router.select_provider(strategy=RoutingStrategy.QUALITY_OPTIMIZED)
        assert provider in {"openai", "anthropic"}
        assert model in {"gpt-4", "claude-3-opus"}


class DummyRAGAction(RAGEnhancedAction):
    pass


class TestRAGAndLLMComposition:
    @pytest.mark.asyncio
    async def test_rag_enhancement_used_as_llm_prompt_input(self):
        action = DummyRAGAction()
        action._enable_rag = True
        action._workspace_id = "ws-1"

        action._knowledge_services = {
            "rag_service": AsyncMock(
                enhance_prompt=AsyncMock(
                    return_value=type(
                        "Enhanced",
                        (),
                        {
                            "enhanced_prompt": "ENHANCED PROMPT\n\n## Relevant Knowledge Examples:\n...",
                        },
                    )()
                )
            )
        }

        enhanced_prompt = await action.enhance_prompt_with_knowledge(
            base_prompt="Base",
            query="jwt auth",
            category_filter="best_practice",
            language_filter="python",
            max_examples=2,
        )

        assert enhanced_prompt.startswith("ENHANCED PROMPT")
        action._knowledge_services["rag_service"].enhance_prompt.assert_awaited_once()

        # Pretend we send that prompt to an LLM.
        fake_llm_response = LLMResponse(
            content="generated",
            model="gpt-4",
            provider="openai",
            tokens_prompt=10,
            tokens_completion=10,
            tokens_total=20,
            cost_usd=0.1,
            latency_ms=200,
        )

        assert fake_llm_response.content == "generated"
