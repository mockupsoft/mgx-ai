# -*- coding: utf-8 -*-
"""MGX takım görev geçmişi (mgx_runs) ve çok adımlı pipeline."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services import get_task_runner
from backend.services.mgx_history import delete_mgx_run, get_mgx_run, list_mgx_runs
from backend.services.mgx_pipeline import build_pipeline_runner, get_pipeline_registry

router = APIRouter(prefix="/api/mgx", tags=["mgx"])


class PipelineCreateBody(BaseModel):
    """Sıralı MGX görev listesi."""

    tasks: List[str] = Field(..., min_length=1, description="Sırayla çalıştırılacak görev metinleri")
    stop_on_error: bool = Field(True, description="True ise ilk hatada kalan adımlar atlanır")


@router.post("/pipeline")
async def create_mgx_pipeline(body: PipelineCreateBody) -> Dict[str, Any]:
    """Birden fazla görevi sıraya alır; BackgroundTaskRunner ile arka planda çalıştırır."""
    reg = get_pipeline_registry()
    rec = reg.create(
        tasks=[t.strip() for t in body.tasks if t and str(t).strip()],
        stop_on_error=body.stop_on_error,
    )
    if not rec.steps:
        raise HTTPException(status_code=400, detail="En az bir geçerli görev gerekli")

    runner = get_task_runner()
    coro = build_pipeline_runner(rec.pipeline_id)
    background_task_id = await runner.submit(
        coro,
        name=f"mgx_pipeline:{rec.pipeline_id}",
    )
    reg.set_background_task_id(rec.pipeline_id, background_task_id)
    return {
        "pipeline_id": rec.pipeline_id,
        "background_task_id": background_task_id,
        "step_count": len(rec.steps),
    }


@router.get("/pipeline")
async def list_mgx_pipelines() -> Dict[str, Any]:
    """Bellekteki pipeline özetleri (yeniden eskiye)."""
    reg = get_pipeline_registry()
    return {"items": reg.list_summaries()}


@router.get("/pipeline/{pipeline_id}")
async def get_mgx_pipeline(pipeline_id: str) -> Dict[str, Any]:
    """Tek pipeline durumu ve adım detayları."""
    reg = get_pipeline_registry()
    rec = reg.get(pipeline_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return rec.to_dict()


def _run_to_dict(row: Any) -> Dict[str, Any]:
    if hasattr(row, "to_dict"):
        return row.to_dict()
    return {
        "id": row.id,
        "task": row.task,
        "status": row.status,
        "complexity": row.complexity,
        "output_dir": row.output_dir,
        "plan_summary": row.plan_summary,
        "results_summary": row.results_summary,
        "duration": row.duration,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/history")
async def list_mgx_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, description="success | error"),
) -> Dict[str, Any]:
    """Üretilen MGX görev kayıtlarını listele (yeniden eskiye)."""
    rows = await list_mgx_runs(skip=skip, limit=limit, status=status)
    return {
        "items": [_run_to_dict(r) for r in rows],
        "skip": skip,
        "limit": limit,
        "count": len(rows),
    }


@router.get("/history/{run_id}")
async def get_mgx_history_detail(run_id: str) -> Dict[str, Any]:
    """Tek bir MGX görev kaydının detayı."""
    row = await get_mgx_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_to_dict(row)


@router.delete("/history/{run_id}")
async def remove_mgx_history(run_id: str) -> Dict[str, bool]:
    """MGX görev kaydını sil."""
    ok = await delete_mgx_run(run_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"deleted": True}
