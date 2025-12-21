# -*- coding: utf-8 -*-

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.entities import LLMCall
from backend.db.session import get_session
from mgx_observability import get_span_store


router = APIRouter(prefix="/api/observability", tags=["observability"])


class SpanRecordResponse(BaseModel):
    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    kind: str
    start_time: str
    end_time: str
    duration_ms: float
    attributes: Dict[str, Any]
    status_code: Optional[str] = None
    status_description: Optional[str] = None
    resource: Dict[str, Any]


class SpansResponse(BaseModel):
    items: List[SpanRecordResponse]
    total: int


@router.get("/spans", response_model=SpansResponse)
async def list_spans(
    limit: int = Query(100, ge=1, le=1000),
    trace_id: Optional[str] = Query(None, description="Filter by trace_id (hex)")
) -> SpansResponse:
    store = get_span_store()
    spans = store.list(limit=limit, trace_id=trace_id)
    return SpansResponse(
        items=[SpanRecordResponse.model_validate(s.__dict__) for s in spans],
        total=len(spans),
    )


def _percentile(values: List[int], p: float) -> Optional[float]:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return float(xs[0])

    k = (len(xs) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(xs[int(k)])

    d0 = xs[f] * (c - k)
    d1 = xs[c] * (k - f)
    return float(d0 + d1)


class LatencyStats(BaseModel):
    provider: str
    model: str
    call_count: int
    p50_ms: Optional[float] = None
    p95_ms: Optional[float] = None
    p99_ms: Optional[float] = None


class WorkspaceLLMLatencyResponse(BaseModel):
    workspace_id: str
    days: int
    stats: List[LatencyStats]


@router.get("/workspaces/{workspace_id}/llm/latency", response_model=WorkspaceLLMLatencyResponse)
async def get_llm_latency_stats(
    workspace_id: str,
    days: int = Query(30, ge=1, le=365),
    provider: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
) -> WorkspaceLLMLatencyResponse:
    since = datetime.utcnow() - timedelta(days=days)

    stmt = select(LLMCall).where(
        LLMCall.workspace_id == workspace_id,
        LLMCall.timestamp >= since,
    )
    if provider:
        stmt = stmt.where(LLMCall.provider == provider)
    if model:
        stmt = stmt.where(LLMCall.model == model)

    rows = (await db.execute(stmt)).scalars().all()

    by_key: Dict[tuple[str, str], List[int]] = {}
    for row in rows:
        if row.latency_ms is None:
            continue
        by_key.setdefault((row.provider, row.model), []).append(int(row.latency_ms))

    stats: List[LatencyStats] = []
    for (prov, mdl), latencies in sorted(by_key.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        stats.append(
            LatencyStats(
                provider=prov,
                model=mdl,
                call_count=len(latencies),
                p50_ms=_percentile(latencies, 50),
                p95_ms=_percentile(latencies, 95),
                p99_ms=_percentile(latencies, 99),
            )
        )

    return WorkspaceLLMLatencyResponse(workspace_id=workspace_id, days=days, stats=stats)


class CostBreakdownRow(BaseModel):
    provider: str
    model: str
    agent_id: Optional[str] = None
    execution_id: Optional[str] = None
    total_cost: float
    total_tokens: int
    call_count: int


class WorkspaceLLMCostBreakdownResponse(BaseModel):
    workspace_id: str
    days: int
    breakdown: List[CostBreakdownRow]


@router.get("/workspaces/{workspace_id}/llm/costs", response_model=WorkspaceLLMCostBreakdownResponse)
async def get_llm_cost_breakdown(
    workspace_id: str,
    days: int = Query(30, ge=1, le=365),
    group_by_execution: bool = Query(False),
    group_by_agent: bool = Query(True),
    db: AsyncSession = Depends(get_session),
) -> WorkspaceLLMCostBreakdownResponse:
    since = datetime.utcnow() - timedelta(days=days)
    stmt = select(LLMCall).where(
        LLMCall.workspace_id == workspace_id,
        LLMCall.timestamp >= since,
    )
    rows = (await db.execute(stmt)).scalars().all()

    totals: Dict[tuple, Dict[str, Any]] = {}

    for row in rows:
        agent_id = None
        meta = row.call_metadata or {}
        if isinstance(meta, dict):
            agent_id = meta.get("agent_id") or meta.get("agent")

        key = [row.provider, row.model]
        if group_by_agent:
            key.append(agent_id)
        if group_by_execution:
            key.append(row.execution_id)
        key_tuple = tuple(key)

        bucket = totals.setdefault(
            key_tuple,
            {
                "provider": row.provider,
                "model": row.model,
                "agent_id": agent_id if group_by_agent else None,
                "execution_id": row.execution_id if group_by_execution else None,
                "total_cost": 0.0,
                "total_tokens": 0,
                "call_count": 0,
            },
        )
        bucket["total_cost"] += float(row.cost_usd or 0.0)
        bucket["total_tokens"] += int(row.tokens_total or 0)
        bucket["call_count"] += 1

    breakdown = [CostBreakdownRow(**b) for b in totals.values()]
    breakdown.sort(key=lambda b: (-b.total_cost, b.provider, b.model))

    return WorkspaceLLMCostBreakdownResponse(workspace_id=workspace_id, days=days, breakdown=breakdown)


__all__ = ["router"]
