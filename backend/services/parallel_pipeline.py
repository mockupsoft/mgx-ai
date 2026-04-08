# -*- coding: utf-8 -*-
"""
Paralel Mikroservis Pipeline Servisi

ParallelOrchestrator'u FastAPI arka planında çalıştıran ince servis katmanı.
Sonuçları MgxRun tablosuna gömülü JSON olarak kaydeder — yeni migration gerekmez.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def run_parallel_task(
    task: str,
    *,
    max_concurrent: int = 3,
    output_dir_base: str = "output/parallel",
) -> Dict[str, Any]:
    """
    Paralel mikroservis görevini çalıştırır ve DB'ye kaydeder.

    Parameters
    ----------
    task:            Kullanıcının yüksek seviye görevi.
    max_concurrent:  Aynı anda çalışacak maksimum servis sayısı.
    output_dir_base: Üretilen dosyaların kök dizini.

    Returns
    -------
    dict — serialise edilmiş ParallelRunResult + ``run_id``.
    """
    started_at = datetime.now(timezone.utc)

    # Lazy import — MetaGPT/Pydantic hataları startup sırasında oluşmasın
    try:
        from mgx_agent.microservice import ParallelOrchestrator
        from mgx_agent.config import TeamConfig

        config = TeamConfig(auto_approve_plan=True, enable_progress_bar=False)
        orchestrator = ParallelOrchestrator(
            base_config=config,
            max_concurrent=max_concurrent,
            output_dir_base=output_dir_base,
        )
        result = await orchestrator.run(task)
    except Exception as exc:
        logger.error(f"[parallel_pipeline] Orchestrator hatası: {exc}", exc_info=True)
        completed_at = datetime.now(timezone.utc)
        run_id = await _persist(
            task=task,
            status="failed",
            started_at=started_at,
            completed_at=completed_at,
            results_summary={"error": str(exc)},
            duration=(completed_at - started_at).total_seconds(),
        )
        return {
            "run_id": run_id,
            "status": "failed",
            "error": str(exc),
            "task": task,
        }

    completed_at = datetime.now(timezone.utc)
    duration = (completed_at - started_at).total_seconds()
    result_dict = result.to_dict()

    status = "success" if result.success else "partial"

    run_id = await _persist(
        task=task,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        results_summary=result_dict,
        duration=duration,
    )

    return {
        "run_id": run_id,
        "status": status,
        "task": task,
        **result_dict,
    }


async def _persist(
    *,
    task: str,
    status: str,
    started_at: datetime,
    completed_at: datetime,
    results_summary: Optional[Dict[str, Any]] = None,
    duration: Optional[float] = None,
) -> Optional[str]:
    """mgx_runs tablosuna sessiz kayıt yapar."""
    try:
        from backend.services.mgx_history import persist_mgx_run

        return await persist_mgx_run(
            task=task,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            results_summary=results_summary,
            duration=duration,
        )
    except Exception as exc:
        logger.warning(f"[parallel_pipeline] DB kayıt hatası: {exc}")
        return None
