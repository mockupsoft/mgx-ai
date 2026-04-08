# -*- coding: utf-8 -*-
"""Persist MGXStyleTeam run metadata to PostgreSQL (mgx_runs)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import delete, select

from backend.db.engine import get_session_factory
from backend.db.models import MgxRun

logger = logging.getLogger(__name__)


async def persist_mgx_run(
    *,
    task: str,
    status: str,
    complexity: Optional[str] = None,
    output_dir: Optional[str] = None,
    plan_summary: Optional[Dict[str, Any]] = None,
    results_summary: Optional[Dict[str, Any]] = None,
    duration: Optional[float] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
) -> Optional[str]:
    """
    Insert a row into mgx_runs. Fails silently (logs warning) if DB unavailable.
    """
    try:
        factory = await get_session_factory()
        async with factory() as session:
            row = MgxRun(
                task=task[:50000] if task else "",
                status=status[:20] if status else "unknown",
                complexity=(complexity[:8] if complexity else None),
                output_dir=(output_dir[:1024] if output_dir else None),
                plan_summary=plan_summary,
                results_summary=results_summary,
                duration=duration,
                started_at=started_at,
                completed_at=completed_at or datetime.now(timezone.utc),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            logger.info("MGX run history saved: id=%s", row.id)
            return row.id
    except Exception as e:
        logger.warning("Could not persist MGX run history: %s", e, exc_info=True)
        return None


async def list_mgx_runs(
    *,
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
) -> list[MgxRun]:
    factory = await get_session_factory()
    async with factory() as session:
        q = select(MgxRun).order_by(MgxRun.created_at.desc())
        if status:
            q = q.where(MgxRun.status == status)
        q = q.offset(skip).limit(min(limit, 200))
        res = await session.execute(q)
        return list(res.scalars().all())


async def get_mgx_run(run_id: str) -> Optional[MgxRun]:
    factory = await get_session_factory()
    async with factory() as session:
        res = await session.execute(select(MgxRun).where(MgxRun.id == run_id))
        return res.scalar_one_or_none()


async def delete_mgx_run(run_id: str) -> bool:
    factory = await get_session_factory()
    async with factory() as session:
        res = await session.execute(delete(MgxRun).where(MgxRun.id == run_id))
        await session.commit()
        return bool(getattr(res, "rowcount", 0) or 0)
