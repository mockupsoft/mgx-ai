# -*- coding: utf-8 -*-
"""
DeepSite multi-step "agent" pipeline (Designer -> Coder -> optional Reviewer).
Uses LLMService (same stack as the rest of the API) instead of embedding full MetaGPT Team runtime.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator, Optional

from backend.services.llm.llm_service import get_llm_service
from backend.services.llm.provider import AllProvidersFailedError, ProviderError

from backend.services.deepsite import DEEPSITE_CONTEXT_MAX_CHARS

from .prompts import CODER_SYSTEM, DESIGNER_SYSTEM

logger = logging.getLogger(__name__)


async def _design_brief(user_prompt: str, context: Optional[str], provider, model, temperature, max_tokens) -> str:
    llm = get_llm_service()
    parts = [DESIGNER_SYSTEM, "\n\nUser request:\n", user_prompt]
    if context:
        parts.extend(["\n\nExisting HTML context (may be empty):\n", context[:8000]])
    prompt = "".join(parts)
    resp = await llm.generate(
        prompt=prompt,
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=min(max_tokens, 2048),
        task_type="code_generation",
        required_capability="code",
    )
    return (resp.content or "").strip()


async def stream_agent_html(
    *,
    user_prompt: str,
    context: Optional[str],
    provider: Optional[str],
    model: Optional[str],
    temperature: float,
    max_tokens: int,
) -> AsyncIterator[str]:
    """
    Stream final HTML: designer (sync) then coder stream (async).
    Optional reviewer pass on full buffered output would break streaming; reviewer runs only if stream fails.
    """
    llm = get_llm_service()
    try:
        brief = await _design_brief(user_prompt, context, provider, model, temperature, max_tokens)
    except (ProviderError, AllProvidersFailedError) as e:
        logger.warning("Designer step failed: %s", e)
        brief = ""

    full_prompt_parts = [
        CODER_SYSTEM,
        "\n\nDesign plan:\n",
        brief or "(no plan)",
        "\n\nUser request:\n",
        user_prompt,
    ]
    if context:
        full_prompt_parts.extend(
            ["\n\nRefine or replace this HTML:\n", context[:DEEPSITE_CONTEXT_MAX_CHARS]]
        )
    full_prompt = "".join(full_prompt_parts)

    try:
        async for chunk in llm.stream_generate(
            prompt=full_prompt,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            task_type="code_generation",
            required_capability="code",
        ):
            yield chunk
    except (ProviderError, AllProvidersFailedError) as e:
        logger.warning("Coder stream failed: %s", e)
        raise
