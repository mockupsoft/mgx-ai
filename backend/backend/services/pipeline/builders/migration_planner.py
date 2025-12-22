# -*- coding: utf-8 -*-

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class MigrationPlanResult:
    file_path: str
    content: str


class MigrationPlanner:
    async def generate_plan(
        self,
        *,
        from_version: str,
        to_version: str,
        changes: Dict[str, Any],
        output_dir: str,
    ) -> MigrationPlanResult:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        file_path = out_dir / f"migration_{from_version}_to_{to_version}.md"

        sql = changes.get("db_migrations_sql") or "-- No database migration SQL provided"
        rollback_sql = changes.get("rollback_sql") or "-- No rollback SQL provided"
        estimated_downtime = changes.get("estimated_downtime") or "0-5 minutes (estimate)"
        preflight = changes.get("preflight_checks") or [
            "Verify database connectivity",
            "Verify current version is installed",
            "Backup database",
        ]
        post = changes.get("post_deploy_validation") or [
            "Run smoke tests",
            "Verify /health endpoint",
            "Validate key user flows",
        ]

        content = f"""# Migration Plan: {from_version} → {to_version}

## Summary
- Estimated downtime: {estimated_downtime}

## Pre-flight Checks
{_as_md_numbered(preflight)}

## Database Migration SQL
```sql
{sql}
```

## Rollback Procedures
```sql
{rollback_sql}
```

## Deployment Steps
1. Deploy new container image(s)
2. Apply database migration
3. Verify application health checks
4. Monitor logs and metrics

## Post-deployment Validation
{_as_md_numbered(post)}

## Rollback Steps
1. Roll back application deployment to previous image
2. Apply rollback SQL (if required)
3. Re-run post-deployment validation
"""

        file_path.write_text(content, encoding="utf-8")
        return MigrationPlanResult(file_path=str(file_path), content=content)


def _as_md_numbered(items: list[str]) -> str:
    return "\n".join(f"{idx}. {item}" for idx, item in enumerate(items, start=1))
