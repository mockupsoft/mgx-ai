# -*- coding: utf-8 -*-
"""
Paralel Mikroservis Router

POST /api/mgx/parallel   — Görevi ayrıştır, servisleri paralel geliştir, entegre et.
GET  /api/mgx/parallel/{task_id} — Arka plan görev durumunu sorgula.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services import get_task_runner

router = APIRouter(prefix="/api/mgx/parallel", tags=["mgx-parallel"])


class ParallelTaskBody(BaseModel):
    """Paralel mikroservis görevi isteği."""

    task: str = Field(
        ...,
        min_length=10,
        max_length=8000,
        description="Yüksek seviye proje açıklaması (Mike bunu servislere böler).",
    )
    max_concurrent: int = Field(
        default=3,
        ge=1,
        le=6,
        description="Aynı anda çalışan maksimum servis takımı sayısı (1–6).",
    )
    output_dir_base: str = Field(
        default="output/parallel",
        description="Üretilen dosyaların kaydedileceği kök dizin.",
    )


@router.post("")
async def create_parallel_task(body: ParallelTaskBody) -> Dict[str, Any]:
    """
    Yüksek seviye bir görevi paralel mikroservislere böler ve geliştirmeyi başlatır.

    Akış:
      1. Mike LLM çağrısıyla görevi bağımsız servislere ayırır.
      2. Her servis için ayrı MGXStyleTeam ``max_concurrent`` eşzamanlılıkla paralel çalışır.
      3. Tamamlanınca Mike entegrasyon dosyalarını (docker-compose, nginx, README) üretir.
      4. Sonuç ``mgx_runs`` tablosuna kaydedilir.

    ``task_id`` ile ``GET /api/mgx/parallel/{task_id}`` üzerinden durumu takip edebilirsiniz.
    """
    task_text = body.task.strip()

    async def _run():
        from backend.services.parallel_pipeline import run_parallel_task

        return await run_parallel_task(
            task_text,
            max_concurrent=body.max_concurrent,
            output_dir_base=body.output_dir_base,
        )

    runner = get_task_runner()
    task_id = await runner.submit(
        _run,
        name=f"mgx_parallel:{task_text[:40]}",
    )

    return {
        "task_id": task_id,
        "status": "pending",
        "message": (
            "Paralel mikroservis görevi sıraya alındı. "
            f"GET /api/mgx/parallel/{task_id} ile durumu sorgulayın."
        ),
        "task": task_text,
        "max_concurrent": body.max_concurrent,
    }


@router.get("/{task_id}")
async def get_parallel_task_status(task_id: str) -> Dict[str, Any]:
    """
    Paralel mikroservis arka plan görevinin durumunu döndürür.

    - ``status``: pending | running | completed | failed
    - ``result``: tamamlandıysa ``ParallelRunResult.to_dict()`` çıktısı
    """
    runner = get_task_runner()
    info = runner.get_status(task_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Görev bulunamadı.")

    response: Dict[str, Any] = {
        "task_id": task_id,
        "status": info.get("status"),
        "created_at": info.get("created_at"),
        "started_at": info.get("started_at"),
        "completed_at": info.get("completed_at"),
    }

    if info.get("error"):
        response["error"] = info["error"]

    if info.get("result") is not None:
        response["result"] = info["result"]

    return response
