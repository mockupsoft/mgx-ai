# -*- coding: utf-8 -*-
"""Birden fazla MGX görevini sırayla arka planda çalıştırma (bellek içi durum)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PipelineStep:
    """Tek bir pipeline adımı."""

    task: str
    status: str = "pending"  # pending | running | success | error | skipped
    run_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class PipelineRecord:
    """Tüm pipeline durumu (uygulama yeniden başlayınca sıfırlanır)."""

    pipeline_id: str
    steps: List[PipelineStep]
    status: str = "pending"  # pending | running | completed | failed
    background_task_id: Optional[str] = None
    stop_on_error: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "status": self.status,
            "background_task_id": self.background_task_id,
            "stop_on_error": self.stop_on_error,
            "created_at": self.created_at.isoformat(),
            "steps": [
                {
                    "task": s.task,
                    "status": s.status,
                    "run_id": s.run_id,
                    "error": s.error,
                }
                for s in self.steps
            ],
        }


class PipelineRegistry:
    """In-memory pipeline kayıtları."""

    def __init__(self) -> None:
        self._pipelines: Dict[str, PipelineRecord] = {}

    def create(
        self,
        tasks: List[str],
        stop_on_error: bool = True,
        pipeline_id: Optional[str] = None,
    ) -> PipelineRecord:
        pid = pipeline_id or str(uuid.uuid4())
        steps = [PipelineStep(task=t) for t in tasks]
        rec = PipelineRecord(
            pipeline_id=pid,
            steps=steps,
            status="pending",
            stop_on_error=stop_on_error,
        )
        self._pipelines[pid] = rec
        return rec

    def get(self, pipeline_id: str) -> Optional[PipelineRecord]:
        return self._pipelines.get(pipeline_id)

    def set_background_task_id(self, pipeline_id: str, background_task_id: str) -> None:
        rec = self._pipelines.get(pipeline_id)
        if rec:
            rec.background_task_id = background_task_id

    def list_summaries(self) -> List[Dict[str, Any]]:
        return [
            {
                "pipeline_id": r.pipeline_id,
                "status": r.status,
                "background_task_id": r.background_task_id,
                "step_count": len(r.steps),
                "created_at": r.created_at.isoformat(),
            }
            for r in sorted(
                self._pipelines.values(),
                key=lambda x: x.created_at,
                reverse=True,
            )
        ]


_registry: Optional[PipelineRegistry] = None


def get_pipeline_registry() -> PipelineRegistry:
    global _registry
    if _registry is None:
        _registry = PipelineRegistry()
    return _registry


async def run_sequential(pipeline_id: str) -> None:
    """Arka plan worker: adımları sırayla MGXTeamProvider.run_task ile çalıştır."""
    from backend.services import get_team_provider

    reg = get_pipeline_registry()
    rec = reg.get(pipeline_id)
    if not rec:
        logger.warning("Pipeline not found: %s", pipeline_id)
        return

    try:
        provider = get_team_provider()
    except Exception as e:
        logger.error("get_team_provider failed: %s", e)
        rec.status = "failed"
        for s in rec.steps:
            s.status = "error"
            s.error = f"Team provider unavailable: {e}"
        return

    rec.status = "running"

    for i, step in enumerate(rec.steps):
        step.status = "running"
        try:
            result = await provider.run_task(step.task)
            step.run_id = result.get("run_id")
            if result.get("status") == "success":
                step.status = "success"
                step.error = None
            else:
                step.status = "error"
                step.error = result.get("error")
                if rec.stop_on_error:
                    for s in rec.steps[i + 1 :]:
                        s.status = "skipped"
                    rec.status = "failed"
                    return
        except Exception as e:
            logger.exception("Pipeline step %s failed", i)
            step.status = "error"
            step.error = str(e)
            if rec.stop_on_error:
                for s in rec.steps[i + 1 :]:
                    s.status = "skipped"
                rec.status = "failed"
                return

    if any(s.status == "error" for s in rec.steps):
        rec.status = "failed"
    else:
        rec.status = "completed"
    logger.info("Pipeline %s finished: %s", pipeline_id, rec.status)


def build_pipeline_runner(pipeline_id: str) -> Callable:
    """BackgroundTaskRunner.submit için uygun async callable döner."""

    async def _runner() -> None:
        await run_sequential(pipeline_id)

    return _runner


__all__ = [
    "PipelineStep",
    "PipelineRecord",
    "PipelineRegistry",
    "get_pipeline_registry",
    "run_sequential",
    "build_pipeline_runner",
]
