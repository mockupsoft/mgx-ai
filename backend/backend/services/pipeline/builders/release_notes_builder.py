# -*- coding: utf-8 -*-

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class ReleaseNotesResult:
    file_path: str
    content: str


class ReleaseNotesBuilder:
    async def generate_notes(
        self,
        *,
        project_name: str,
        version: str,
        changes: List[str],
        breaking_changes: List[str],
        migration_steps: Optional[List[str]] = None,
        security_alerts: Optional[List[str]] = None,
        performance_improvements: Optional[List[str]] = None,
        image_ref: Optional[str] = None,
        output_dir: str,
    ) -> ReleaseNotesResult:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        migration_steps = migration_steps or []
        security_alerts = security_alerts or ["None"]
        performance_improvements = performance_improvements or []

        file_path = out_dir / f"release_{version}.md"

        features = [c for c in changes if c.lower().startswith("feat") or c.lower().startswith("feature")]
        bugfixes = [c for c in changes if c.lower().startswith("fix") or c.lower().startswith("bug")]
        others = [c for c in changes if c not in features and c not in bugfixes]

        content = """# Release {version}

## Features
{features}

## Bug Fixes
{bugfixes}

## Breaking Changes
{breaking}

## Migration Guide
{migration}

## Security Alerts
{security}

## Performance Improvements
{perf}

## Deployment Instructions
1. Pull image: docker pull {image}
2. Update compose
3. Run migrations
4. Restart services
""".format(
            version=version,
            features=_as_md_list(features) or "- None",
            bugfixes=_as_md_list(bugfixes) or "- None",
            breaking=_as_md_list(breaking_changes) or "- None",
            migration=_as_md_numbered_list(migration_steps) or "1. None",
            security=_as_md_list(security_alerts) or "- None",
            perf=_as_md_list(performance_improvements) or "- None",
            image=image_ref or f"{project_name}:{version}",
        )

        file_path.write_text(content, encoding="utf-8")
        return ReleaseNotesResult(file_path=str(file_path), content=content)


def _as_md_list(items: List[str]) -> str:
    return "\n".join(f"- {i}" for i in items)


def _as_md_numbered_list(items: List[str]) -> str:
    return "\n".join(f"{idx}. {i}" for idx, i in enumerate(items, start=1))
