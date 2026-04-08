# -*- coding: utf-8 -*-
"""Google Gemini LLM provider (google-genai SDK)."""

from __future__ import annotations

import asyncio
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
)
from ..registry import ModelRegistry

logger = logging.getLogger(__name__)


def _extract_text(response) -> str:
    """Best-effort text extraction (handles safety blocks / empty candidates)."""
    try:
        t = getattr(response, "text", None)
        if t:
            return t
    except Exception:
        pass
    parts: List[str] = []
    cands = getattr(response, "candidates", None) or []
    for cand in cands:
        content = getattr(cand, "content", None)
        if not content:
            continue
        for p in getattr(content, "parts", None) or []:
            txt = getattr(p, "text", None)
            if txt:
                parts.append(txt)
    return "".join(parts)


class GeminiProvider(LLMProvider):
    """Google Gemini via google-genai (resmi yeni SDK)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "gemini-2.0-flash",
        **kwargs,
    ):
        super().__init__(
            api_key=api_key,
            default_model=default_model,
            **kwargs,
        )
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            return None
        try:
            from google import genai
        except ImportError as e:
            raise ProviderError(
                "google-genai not installed. pip install google-genai"
            ) from e
        self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _ensure_configured(self) -> None:
        if not self.api_key:
            return
        self._get_client()

    def _build_config(self, temperature: float, max_tokens: int):
        from google.genai import types

        return types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> LLMResponse:
        self._ensure_configured()
        client = self._get_client()
        if client is None:
            raise ProviderError("Gemini API key not configured")

        model_name = model or self.default_model
        config = self._build_config(temperature, max_tokens)
        start = time.time()

        def _sync():
            return client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )

        try:
            response = await asyncio.to_thread(_sync)
        except Exception as e:
            msg = str(e).lower()
            if "api key" in msg or "permission" in msg or "401" in msg:
                raise AuthenticationError(f"Gemini authentication failed: {e}") from e
            if "429" in msg or "resource exhausted" in msg or "quota" in msg:
                raise RateLimitError(f"Gemini rate limit: {e}") from e
            raise ProviderError(f"Gemini generation failed: {e}") from e

        latency_ms = int((time.time() - start) * 1000)
        text = _extract_text(response)
        usage = getattr(response, "usage_metadata", None)
        prompt_tok = int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
        completion_tok = int(getattr(usage, "candidates_token_count", 0) or 0) if usage else 0
        total_tok = prompt_tok + completion_tok

        cost_usd = await self.get_cost(model_name, prompt_tok, completion_tok)

        return LLMResponse(
            content=text,
            model=model_name,
            provider=self.provider_name,
            tokens_prompt=prompt_tok,
            tokens_completion=completion_tok,
            tokens_total=total_tok or max(len(prompt) // 4, 0) + max(len(text) // 4, 0),
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            finish_reason=None,
            metadata={"provider": "gemini"},
        )

    async def stream_generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> AsyncIterator[str]:
        self._ensure_configured()
        client = self._get_client()
        if client is None:
            raise ProviderError("Gemini API key not configured")

        model_name = model or self.default_model
        config = self._build_config(temperature, max_tokens)

        def _iter_chunks():
            stream = client.models.generate_content_stream(
                model=model_name,
                contents=prompt,
                config=config,
            )
            for chunk in stream:
                t = getattr(chunk, "text", None)
                if t:
                    yield t

        it = _iter_chunks()
        _SENTINEL = object()

        def _next_chunk():
            try:
                return next(it)
            except StopIteration:
                return _SENTINEL

        try:
            while True:
                piece = await asyncio.to_thread(_next_chunk)
                if piece is _SENTINEL:
                    break
                yield piece
        except Exception as e:
            msg = str(e).lower()
            if "api key" in msg or "401" in msg:
                raise AuthenticationError(f"Gemini authentication failed: {e}") from e
            if "429" in msg or "quota" in msg:
                raise RateLimitError(f"Gemini rate limit: {e}") from e
            raise ProviderError(f"Gemini streaming failed: {e}") from e

    async def get_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        config = ModelRegistry.get_model_config("gemini", model)
        if not config:
            return 0.0
        prompt_cost = (prompt_tokens / 1000) * config.cost_per_1k_prompt
        completion_cost = (completion_tokens / 1000) * config.cost_per_1k_completion
        return prompt_cost + completion_cost

    async def get_latency_estimate(self, model: str) -> int:
        config = ModelRegistry.get_model_config("gemini", model)
        return config.latency_estimate_ms if config else 1200

    def get_model_capabilities(self, model: str) -> ModelCapabilities:
        config = ModelRegistry.get_model_config("gemini", model)
        if not config:
            return ModelCapabilities(
                code_generation=True,
                streaming=True,
                long_context=True,
            )
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
        return [self.default_model]

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            import google.genai  # noqa: F401

            return True
        except ImportError:
            return False

    @property
    def provider_name(self) -> str:
        return "gemini"
