# -*- coding: utf-8 -*-
"""LLM provider utilities router.

This router exposes lightweight endpoints to inspect configured LLM providers and
to exercise the model registry/routing logic without making outbound calls.

It intentionally does not import provider SDKs (openai/anthropic/etc.) so it can
run in minimal test environments.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import settings
from backend.services.llm.registry import ModelConfig, ModelRegistry


router = APIRouter(prefix="/api/llm", tags=["llm"])


def _provider_configured(provider: str) -> bool:
    provider = provider.lower()
    if provider == "openai":
        return bool(settings.openai_api_key)
    if provider == "anthropic":
        return bool(settings.anthropic_api_key)
    if provider == "mistral":
        return bool(settings.mistral_api_key)
    if provider == "together":
        return bool(settings.together_api_key)
    if provider == "ollama":
        return bool(settings.ollama_base_url)
    return False


def _iter_model_configs() -> List[ModelConfig]:
    configs: List[ModelConfig] = []
    for provider, models in ModelRegistry.MODELS.items():
        for model_name in models:
            config = ModelRegistry.get_model_config(provider, model_name)
            if config:
                configs.append(config)
    return configs


class ProviderHealth(BaseModel):
    provider: str
    configured: bool
    model_count: int
    models: List[str]


class LLMHealthResponse(BaseModel):
    routing_strategy: str
    fallback_enabled: bool
    prefer_local: bool
    providers: List[ProviderHealth]


@router.get("/health", response_model=LLMHealthResponse)
async def llm_health() -> LLMHealthResponse:
    providers = []

    for provider in sorted(ModelRegistry.MODELS.keys()):
        models = sorted(ModelRegistry.MODELS[provider].keys())
        providers.append(
            ProviderHealth(
                provider=provider,
                configured=_provider_configured(provider),
                model_count=len(models),
                models=models,
            )
        )

    return LLMHealthResponse(
        routing_strategy=settings.llm_routing_strategy,
        fallback_enabled=settings.llm_enable_fallback,
        prefer_local=settings.llm_prefer_local,
        providers=providers,
    )


class RouteRequest(BaseModel):
    required_capability: Optional[str] = Field(
        default=None,
        description="Capability to match (e.g. code, reasoning, long_context)",
    )
    strategy: str = Field(
        default="balanced",
        description="Routing strategy (balanced, cost_optimized, latency_optimized, quality_optimized, local_first)",
    )
    budget_remaining: Optional[float] = Field(
        default=None,
        ge=0,
        description="Optional budget remaining in USD. When provided, will try to avoid very expensive models.",
    )
    prefer_local: bool = False


class RouteResponse(BaseModel):
    provider: str
    model: str
    reason: str


def _select_model(req: RouteRequest) -> RouteResponse:
    strategy = req.strategy.lower()
    capability = req.required_capability

    candidates = [
        c
        for c in _iter_model_configs()
        if _provider_configured(c.provider)
        and (capability is None or capability in (c.capabilities or []))
    ]

    if not candidates:
        # Fall back to any known model even if not configured; useful for local dev.
        fallback = ModelRegistry.get_cheapest_model(capability=capability, exclude_local=False)
        if fallback is None:
            raise HTTPException(status_code=503, detail="No models available")
        return RouteResponse(provider=fallback.provider, model=fallback.model, reason="no_configured_providers")

    def total_cost(c: ModelConfig) -> float:
        return (c.cost_per_1k_prompt or 0.0) + (c.cost_per_1k_completion or 0.0)

    if strategy in {"local_first", "local-first"} or req.prefer_local:
        local = [c for c in candidates if c.provider == "ollama"]
        if local:
            local.sort(key=lambda c: (c.latency_estimate_ms or 0, total_cost(c)))
            chosen = local[0]
            return RouteResponse(provider=chosen.provider, model=chosen.model, reason="local_first")

    if strategy in {"cost_optimized", "cost"}:
        candidates.sort(key=lambda c: (total_cost(c), c.latency_estimate_ms or 0))
        chosen = candidates[0]
        return RouteResponse(provider=chosen.provider, model=chosen.model, reason="cost_optimized")

    if strategy in {"latency_optimized", "latency"}:
        candidates.sort(key=lambda c: (c.latency_estimate_ms or 0, total_cost(c)))
        chosen = candidates[0]
        return RouteResponse(provider=chosen.provider, model=chosen.model, reason="latency_optimized")

    if strategy in {"quality_optimized", "quality"}:
        # Heuristic: pick the most expensive among configured candidates.
        candidates.sort(key=lambda c: (-(total_cost(c)), c.latency_estimate_ms or 0))
        chosen = candidates[0]
        return RouteResponse(provider=chosen.provider, model=chosen.model, reason="quality_optimized")

    if strategy not in {"balanced", "default"}:
        raise HTTPException(status_code=400, detail=f"Unsupported strategy: {req.strategy}")

    # Balanced: avoid extreme cost when budget is set, otherwise choose moderate cost+latency.
    if req.budget_remaining is not None:
        max_cost = max(req.budget_remaining / 1000.0, 0.0)
        filtered = [c for c in candidates if total_cost(c) <= max_cost] or candidates
        filtered.sort(key=lambda c: (total_cost(c), c.latency_estimate_ms or 0))
        chosen = filtered[0]
        return RouteResponse(provider=chosen.provider, model=chosen.model, reason="balanced_with_budget")

    candidates.sort(key=lambda c: (total_cost(c), c.latency_estimate_ms or 0))
    chosen = candidates[0]
    return RouteResponse(provider=chosen.provider, model=chosen.model, reason="balanced")


@router.post("/route", response_model=RouteResponse)
async def test_route(req: RouteRequest) -> RouteResponse:
    return _select_model(req)


@router.get("/models", response_model=Dict[str, Any])
async def list_models(provider: Optional[str] = None) -> Dict[str, Any]:
    return {
        "provider": provider,
        "models": ModelRegistry.list_models(provider),
    }


__all__ = ["router"]
