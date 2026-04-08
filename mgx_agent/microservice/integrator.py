# -*- coding: utf-8 -*-
"""
IntegrateServices Action

Tamamlanan servis çıktılarını alır ve Mike rolünde LLM çağrısı yaparak
aşağıdaki entegrasyon dosyalarını üretir:

  - docker-compose.yml
  - nginx/nginx.conf
  - service-contracts.md
  - README.md
"""
from __future__ import annotations

import re
from typing import Dict, List

from metagpt.actions import Action
from metagpt.logs import logger

from mgx_agent.microservice.models import ServiceResult

_INTEGRATE_PROMPT = """\
You are Mike, the senior software architect.
You have received the outputs of {n_services} independent microservice teams.
Your job is to produce the integration layer that ties all services together.

## Services summary
{services_summary}

## What to produce
Return ONLY the file contents below, each wrapped with start/end markers as shown.
Do NOT add any prose outside the markers.

### docker-compose.yml
<<<FILE:docker-compose.yml>>>
(full docker-compose v3 YAML here)
<<<END>>>

### nginx/nginx.conf
<<<FILE:nginx/nginx.conf>>>
(Nginx reverse-proxy config: upstream blocks + location rules for each service)
<<<END>>>

### service-contracts.md
<<<FILE:service-contracts.md>>>
(Markdown table: Service | Base URL | Key endpoints | Consumed by)
<<<END>>>

### README.md
<<<FILE:README.md>>>
(Markdown: project overview, how to start with docker-compose, environment variables, ports)
<<<END>>>
"""

_MARKER_RE = re.compile(
    r"<<<FILE:(?P<name>[^>]+)>>>\n(?P<content>.*?)<<<END>>>",
    re.DOTALL,
)


def _build_services_summary(results: List[ServiceResult]) -> str:
    lines: List[str] = []
    for r in results:
        status = "SUCCESS" if r.success else f"FAILED ({r.error or 'unknown'})"
        lines.append(
            f"- **{r.spec.name}** | stack={r.spec.stack} | port={r.spec.port} "
            f"| deps={r.spec.dependencies or []} | status={status}"
        )
        if r.success and r.output:
            snippet = r.output[:600].replace("\n", " ")
            lines.append(f"  output_snippet: {snippet}…")
    return "\n".join(lines)


def _fallback_files(results: List[ServiceResult]) -> Dict[str, str]:
    """LLM başarısız olursa minimal şablon dosyalar üretir."""
    services_yaml_blocks: List[str] = []
    upstream_blocks: List[str] = []
    location_blocks: List[str] = []

    for r in results:
        name = r.spec.name
        port = r.spec.port
        services_yaml_blocks.append(
            f"  {name}:\n"
            f"    build: ./{name}\n"
            f"    ports:\n"
            f'      - "{port}:{port}"\n'
            f"    environment:\n"
            f"      - PORT={port}\n"
        )
        upstream_blocks.append(
            f"  upstream {name} {{\n    server {name}:{port};\n  }}"
        )
        slug = name.replace("-", "_")
        location_blocks.append(
            f"  location /{slug}/ {{\n    proxy_pass http://{name}/;\n  }}"
        )

    compose = (
        "version: '3.8'\nservices:\n" + "\n".join(services_yaml_blocks)
    )
    nginx_upstreams = "\n".join(upstream_blocks)
    nginx_locations = "\n".join(location_blocks)
    nginx = (
        "http {\n"
        + nginx_upstreams
        + "\n\n  server {\n    listen 80;\n"
        + nginx_locations
        + "\n  }\n}"
    )

    rows = "\n".join(
        f"| {r.spec.name} | http://localhost:{r.spec.port} | — | {', '.join(r.spec.dependencies) or '—'} |"
        for r in results
    )
    contracts = (
        "# Service Contracts\n\n"
        "| Service | Base URL | Key Endpoints | Depends On |\n"
        "|---------|----------|---------------|------------|\n"
        + rows
    )
    readme = (
        "# Microservice Platform\n\n"
        "## Start\n```bash\ndocker compose up --build\n```\n\n"
        "## Services\n"
        + "\n".join(
            f"- **{r.spec.name}**: http://localhost:{r.spec.port}"
            for r in results
        )
    )

    return {
        "docker-compose.yml": compose,
        "nginx/nginx.conf": nginx,
        "service-contracts.md": contracts,
        "README.md": readme,
    }


class IntegrateServices(Action):
    """Tüm servis çıktılarından entegrasyon dosyaları üretir."""

    name: str = "IntegrateServices"

    async def run(self, services: List[ServiceResult]) -> Dict[str, str]:  # type: ignore[override]
        """
        Parameters
        ----------
        services: Tamamlanan (başarılı veya başarısız) servis sonuçları.

        Returns
        -------
        dict[str, str] — dosya adı → içerik.
        """
        if not services:
            return {}

        prompt = _INTEGRATE_PROMPT.format(
            n_services=len(services),
            services_summary=_build_services_summary(services),
        )

        try:
            raw = await self._aask(prompt)
        except Exception as exc:
            logger.warning(f"[IntegrateServices] LLM çağrısı başarısız: {exc} — fallback üretiliyor")
            return _fallback_files(services)

        files = _parse_files(raw)
        if not files:
            logger.warning("[IntegrateServices] LLM çıktısı parse edilemedi — fallback üretiliyor")
            return _fallback_files(services)

        logger.info(f"[IntegrateServices] {len(files)} entegrasyon dosyası üretildi: {list(files.keys())}")
        return files


def _parse_files(raw: str) -> Dict[str, str]:
    files: Dict[str, str] = {}
    for m in _MARKER_RE.finditer(raw):
        name = m.group("name").strip()
        content = m.group("content").strip()
        if name and content:
            files[name] = content
    return files


__all__ = ["IntegrateServices"]
