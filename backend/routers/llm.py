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

import logging

from backend.config import settings
from backend.services.llm.registry import ModelConfig, ModelRegistry

logger = logging.getLogger(__name__)


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
    if provider == "openrouter":
        return bool(settings.openrouter_api_key)
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


# Ollama-specific endpoints
class OllamaModelInfo(BaseModel):
    name: str
    size: Optional[int] = None
    modified_at: Optional[str] = None


class OllamaListResponse(BaseModel):
    models: List[OllamaModelInfo]
    connected: bool
    base_url: str


class OllamaPullRequest(BaseModel):
    model: str = Field(..., description="Model name to pull (e.g., 'mistral', 'llama2')")


class OllamaPullResponse(BaseModel):
    success: bool
    message: str
    model: str


class OllamaDeleteRequest(BaseModel):
    model: str = Field(..., description="Model name to delete")


class OllamaDeleteResponse(BaseModel):
    success: bool
    message: str
    model: str


@router.get("/ollama/models", response_model=OllamaListResponse)
async def list_ollama_models() -> OllamaListResponse:
    """List models installed in Ollama."""
    from backend.services.llm.providers.ollama_provider import OllamaProvider
    
    base_url = settings.ollama_base_url
    provider = OllamaProvider(base_url=base_url)
    
    try:
        models = await provider.list_installed_models()
        connected = await provider.check_connection()
        
        # Get detailed model info
        import httpx
        client = httpx.AsyncClient(base_url=base_url, timeout=10.0)
        model_details = []
        
        if connected:
            try:
                response = await client.get("/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    for model in data.get("models", []):
                        model_details.append(OllamaModelInfo(
                            name=model.get("name", ""),
                            size=model.get("size"),
                            modified_at=model.get("modified_at"),
                        ))
            except Exception:
                # Fallback to simple list
                model_details = [OllamaModelInfo(name=m) for m in models]
        else:
            model_details = [OllamaModelInfo(name=m) for m in models]
        
        await client.aclose()
        
        return OllamaListResponse(
            models=model_details,
            connected=connected,
            base_url=base_url,
        )
    except Exception as e:
        return OllamaListResponse(
            models=[],
            connected=False,
            base_url=base_url,
        )


@router.post("/ollama/pull", response_model=OllamaPullResponse)
async def pull_ollama_model(req: OllamaPullRequest) -> OllamaPullResponse:
    """Pull a model from Ollama."""
    import httpx
    
    base_url = settings.ollama_base_url
    model = req.model
    
    try:
        client = httpx.AsyncClient(base_url=base_url, timeout=300.0)  # Long timeout for pulling
        
        # Start pull request
        async with client.stream(
            "POST",
            "/api/pull",
            json={"name": model},
        ) as response:
            if response.status_code != 200:
                await client.aclose()
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to pull model: {response.text}"
                )
            
            # Stream the response (Ollama sends progress updates)
            async for line in response.aiter_lines():
                if line:
                    import json
                    try:
                        data = json.loads(line)
                        # Log progress if needed
                        if "status" in data:
                            logger.info(f"Ollama pull progress: {data.get('status')}")
                    except json.JSONDecodeError:
                        continue
        
        await client.aclose()
        
        return OllamaPullResponse(
            success=True,
            message=f"Model '{model}' pulled successfully",
            model=model,
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Ollama at {base_url}. Make sure Ollama is running."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to pull model: {str(e)}"
        )


@router.post("/ollama/delete", response_model=OllamaDeleteResponse)
async def delete_ollama_model(req: OllamaDeleteRequest) -> OllamaDeleteResponse:
    """Delete a model from Ollama."""
    import httpx
    
    base_url = settings.ollama_base_url
    model = req.model
    
    try:
        client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
        
        response = await client.delete(
            "/api/delete",
            json={"name": model},
        )
        
        await client.aclose()
        
        if response.status_code == 200:
            return OllamaDeleteResponse(
                success=True,
                message=f"Model '{model}' deleted successfully",
                model=model,
            )
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to delete model: {response.text}"
            )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Ollama at {base_url}. Make sure Ollama is running."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete model: {str(e)}"
        )


@router.get("/ollama/health")
async def ollama_health() -> Dict[str, Any]:
    """Check Ollama connection health."""
    from backend.services.llm.providers.ollama_provider import OllamaProvider
    
    base_url = settings.ollama_base_url
    provider = OllamaProvider(base_url=base_url)
    
    connected = await provider.check_connection()
    models = await provider.list_installed_models()
    
    return {
        "connected": connected,
        "base_url": base_url,
        "model_count": len(models),
        "models": models,
    }


__all__ = ["router"]
