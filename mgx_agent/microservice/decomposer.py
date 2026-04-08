# -*- coding: utf-8 -*-
"""
DecomposeTask Action

Mike rolünde LLM çağrısı yaparak yüksek seviye bir görevi bağımsız
mikroservislere ayırır. JSON parse başarısız olursa orijinal görevi
tek servis olarak saran bir fallback döndürür.
"""
from __future__ import annotations

import json
import re
from typing import List, Optional

from metagpt.actions import Action
from metagpt.logs import logger

from mgx_agent.microservice.models import ServiceSpec

_DECOMPOSE_PROMPT = """\
You are Mike, the senior software architect.

Your task is to decompose the following high-level project goal into independent microservices.

## Project goal
{task}

## Rules
- Return ONLY valid JSON — no prose, no markdown code fences.
- Return a JSON array with at most {max_services} items.
- Each item must have EXACTLY these fields:
  - "name": a lowercase, hyphenated service identifier (e.g. "user-service")
  - "description": a clear, self-contained task description for the team assigned to this service
  - "stack": one of [fastapi, express-ts, nestjs, laravel, nextjs, react-vite, vue-vite, go-fiber]
  - "port": a unique integer starting from 8001
  - "dependencies": a list of other service names this service directly calls (empty list if none)
- Each description must be fully self-contained so an independent team can implement it without
  knowing anything about other services; include REST endpoint expectations where relevant.
- Prefer cohesion: combine very small concerns into a single service.

## Output format (strict)
[
  {{
    "name": "...",
    "description": "...",
    "stack": "...",
    "port": 8001,
    "dependencies": []
  }}
]
"""

_BASE_PORTS = list(range(8001, 8020))


class DecomposeTask(Action):
    """Yüksek seviye bir görevi bağımsız mikroservis spec'lerine böler."""

    name: str = "DecomposeTask"

    async def run(self, task: str, max_services: int = 6) -> List[ServiceSpec]:  # type: ignore[override]
        """
        Parameters
        ----------
        task:         Kullanıcının orijinal yüksek seviye görevi.
        max_services: Üretilebilecek maksimum servis sayısı (varsayılan 6).

        Returns
        -------
        list[ServiceSpec] — parse başarısız olursa tek-elemanlı fallback liste.
        """
        prompt = _DECOMPOSE_PROMPT.format(task=task.strip(), max_services=max_services)

        try:
            raw = await self._aask(prompt)
        except Exception as exc:
            logger.warning(f"[DecomposeTask] LLM çağrısı başarısız: {exc} — fallback kullanılıyor")
            return _single_service_fallback(task)

        specs = _parse_llm_response(raw, task)
        if not specs:
            logger.warning("[DecomposeTask] JSON parse başarısız — fallback kullanılıyor")
            return _single_service_fallback(task)

        logger.info(f"[DecomposeTask] {len(specs)} servis üretildi: {[s.name for s in specs]}")
        return specs


def _parse_llm_response(raw: str, task: str) -> List[ServiceSpec]:
    """LLM çıktısından ServiceSpec listesi parse eder."""
    # JSON array'i bul (opsiyonel markdown code-fence içinde olabilir)
    match = re.search(r"\[[\s\S]*\]", raw)
    if not match:
        return []

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list) or not data:
        return []

    specs: List[ServiceSpec] = []
    used_ports: set[int] = set()
    port_iter = iter(_BASE_PORTS)

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        try:
            # Port çakışması önleme
            port = int(item.get("port") or 0)
            if port in used_ports or port < 1024:
                port = _next_free_port(port_iter, used_ports)
            used_ports.add(port)

            spec = ServiceSpec.from_dict({**item, "port": port})
            if not spec.name or not spec.description:
                continue
            specs.append(spec)
        except Exception as exc:
            logger.debug(f"[DecomposeTask] {idx}. item parse hatası: {exc}")

    return specs


def _next_free_port(port_iter, used: set) -> int:
    for p in port_iter:
        if p not in used:
            return p
    return 9000 + len(used)


def _single_service_fallback(task: str) -> List[ServiceSpec]:
    """Orijinal görevi tek bir FastAPI servisi olarak saran fallback."""
    return [
        ServiceSpec(
            name="main-service",
            description=task,
            stack="fastapi",
            port=8001,
            dependencies=[],
        )
    ]


__all__ = ["DecomposeTask"]
