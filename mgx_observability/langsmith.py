# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .config import ObservabilityConfig
from .spans import get_current_span_ids

logger = logging.getLogger(__name__)


@dataclass
class LangSmithLogger:
    api_key: str
    project: str
    endpoint: Optional[str] = None

    def _client(self):
        from langsmith import Client

        kwargs: Dict[str, Any] = {}
        if self.endpoint:
            kwargs["api_url"] = self.endpoint
        if self.api_key:
            kwargs["api_key"] = self.api_key
        return Client(**kwargs)

    async def log_llm_call(
        self,
        *,
        name: str,
        provider: str,
        model: str,
        prompt: str,
        output: str,
        metadata: Optional[Dict[str, Any]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        error: Optional[str] = None,
    ) -> Optional[str]:
        """Create a LangSmith run for an LLM call.

        This uses a background thread to avoid blocking the event loop.
        """

        trace_id, span_id = get_current_span_ids()
        merged_meta: Dict[str, Any] = {
            "provider": provider,
            "model": model,
            "otel_trace_id": trace_id,
            "otel_span_id": span_id,
        }
        if metadata:
            merged_meta.update(metadata)

        start_time = start_time or datetime.now(timezone.utc)
        end_time = end_time or datetime.now(timezone.utc)

        def _send() -> str:
            client = self._client()

            payload: Dict[str, Any] = {
                "name": name,
                "run_type": "llm",
                "inputs": {"prompt": prompt},
                "outputs": {"output": output} if error is None else None,
                "extra": {"metadata": merged_meta},
                "start_time": start_time,
                "end_time": end_time,
            }
            if error is not None:
                payload["error"] = error

            try:
                run = client.create_run(**payload, project_name=self.project)
            except TypeError:
                run = client.create_run(**payload, session_name=self.project)

            if isinstance(run, dict) and "id" in run:
                return str(run["id"])
            return str(run)

        try:
            return await asyncio.to_thread(_send)
        except Exception as e:
            logger.debug("LangSmith logging failed: %s", e)
            return None


_LOGGER: Optional[LangSmithLogger] = None


def get_langsmith_logger(config: Optional[ObservabilityConfig] = None) -> Optional[LangSmithLogger]:
    global _LOGGER

    if _LOGGER is not None:
        return _LOGGER

    if config is None:
        return None

    cfg = config.normalized()
    if not cfg.langsmith_enabled:
        return None

    api_key = cfg.langsmith_api_key or os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        logger.warning("LangSmith enabled but API key missing")
        return None

    project = cfg.langsmith_project or os.getenv("LANGSMITH_PROJECT") or "mgx-agent"
    endpoint = cfg.langsmith_endpoint or os.getenv("LANGSMITH_ENDPOINT")

    _LOGGER = LangSmithLogger(api_key=api_key, project=project, endpoint=endpoint)

    os.environ.setdefault("LANGSMITH_API_KEY", api_key)
    os.environ.setdefault("LANGSMITH_PROJECT", project)
    if endpoint:
        os.environ.setdefault("LANGSMITH_ENDPOINT", endpoint)

    return _LOGGER
