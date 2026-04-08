# -*- coding: utf-8 -*-
"""
ParallelOrchestrator

Yüksek seviye bir görevi şu adımlarda yürütür:

  1. DecomposeTask  — Mike LLM çağrısı → ServiceSpec listesi
  2. bounded_gather — Her servis için bağımsız MGXStyleTeam örneği, paralel
  3. IntegrateServices — Mike LLM çağrısı → docker-compose + nginx + README

Hata yönetimi: bir servis başarısız olursa diğerleri devam eder;
başarısız servisler de entegrasyon adımına aktarılır (mevcut çıktıyla çalışır).
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional, Union

from mgx_agent.microservice.models import ParallelRunResult, ServiceResult, ServiceSpec
from mgx_agent.microservice.decomposer import DecomposeTask
from mgx_agent.microservice.integrator import IntegrateServices
from mgx_agent.performance.async_tools import bounded_gather

logger = logging.getLogger(__name__)

# Lazy imports (MetaGPT/pydantic çözümü başlatma sırasında hata vermemesi için)
_MGXStyleTeam = None
_TeamConfig = None


def _get_team_classes():
    global _MGXStyleTeam, _TeamConfig
    if _MGXStyleTeam is None:
        from mgx_agent.team import MGXStyleTeam as T
        from mgx_agent.config import TeamConfig as C
        _MGXStyleTeam, _TeamConfig = T, C
    return _MGXStyleTeam, _TeamConfig


class ParallelOrchestrator:
    """
    Paralel mikroservis geliştirme orkestratörü.

    Parameters
    ----------
    base_config:
        Servis takımlarına aktarılacak temel TeamConfig.
        Her servis kendi ``target_stack`` ve ``auto_approve_plan=True``
        değerleriyle kopyasını oluşturur.
    max_concurrent:
        Aynı anda çalışabilecek maksimum MGXStyleTeam sayısı (1–6).
    output_dir_base:
        Üretilen dosyaların kaydedileceği kök dizin.
        Her servis kendi alt dizinini (``<output_dir_base>/<service_name>``) oluşturur.
    """

    def __init__(
        self,
        base_config=None,
        *,
        max_concurrent: int = 3,
        output_dir_base: str = "output/parallel",
    ):
        # base_config=None durumunda TeamConfig lazy import ile run() içinde çözülür
        self._base_config_raw = base_config
        self.max_concurrent = max(1, min(max_concurrent, 6))
        self.output_dir_base = output_dir_base

    @property
    def base_config(self):
        if self._base_config_raw is None:
            _, TeamConfig = _get_team_classes()
            self._base_config_raw = TeamConfig()
        return self._base_config_raw

    @base_config.setter
    def base_config(self, value):
        self._base_config_raw = value

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, task: str) -> ParallelRunResult:
        """
        Tam paralel mikroservis akışını çalıştırır.

        Parameters
        ----------
        task: Kullanıcının orijinal yüksek seviye görevi.

        Returns
        -------
        ParallelRunResult
        """
        t0 = time.perf_counter()
        logger.info(f"[ParallelOrchestrator] Görev başlıyor: {task[:80]!r}")

        # ── 1. Decompose ──────────────────────────────────────────────
        specs = await self._decompose(task)
        logger.info(
            f"[ParallelOrchestrator] {len(specs)} servis ayrıştırıldı: "
            f"{[s.name for s in specs]}"
        )

        # ── 2. Parallel execute ───────────────────────────────────────
        awaitables = [self._run_service(spec) for spec in specs]
        raw_results = await bounded_gather(
            *awaitables,
            max_concurrent=self.max_concurrent,
            return_exceptions=True,
        )

        service_results: List[ServiceResult] = []
        for spec, raw in zip(specs, raw_results):
            if isinstance(raw, Exception):
                logger.warning(
                    f"[ParallelOrchestrator] {spec.name} exception: {raw}"
                )
                service_results.append(
                    ServiceResult(
                        spec=spec,
                        success=False,
                        error=str(raw),
                    )
                )
            elif isinstance(raw, ServiceResult):
                service_results.append(raw)
            else:
                service_results.append(
                    ServiceResult(spec=spec, success=False, error="unexpected result type")
                )

        succeeded = sum(1 for r in service_results if r.success)
        logger.info(
            f"[ParallelOrchestrator] Paralel aşama tamamlandı: "
            f"{succeeded}/{len(service_results)} başarılı"
        )

        # ── 3. Integrate ─────────────────────────────────────────────
        integration_files = await self._integrate(service_results)

        duration = time.perf_counter() - t0
        logger.info(f"[ParallelOrchestrator] Toplam süre: {duration:.1f}s")

        return ParallelRunResult(
            task=task,
            services=service_results,
            integration_files=integration_files,
            success=succeeded > 0,
            duration=duration,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _decompose(self, task: str) -> List[ServiceSpec]:
        action = DecomposeTask(context=None)
        try:
            specs = await action.run(task)
        except Exception as exc:
            logger.warning(f"[ParallelOrchestrator] DecomposeTask hatası: {exc}")
            from mgx_agent.microservice.decomposer import _single_service_fallback
            specs = _single_service_fallback(task)
        return specs

    async def _run_service(self, spec: ServiceSpec) -> ServiceResult:
        MGXStyleTeam, TeamConfig = _get_team_classes()

        t0 = time.perf_counter()
        logger.info(
            f"[ParallelOrchestrator] Servis başlıyor: {spec.name} "
            f"(stack={spec.stack}, port={spec.port})"
        )

        # Her servis bağımsız config kopyası alır
        config_data = self.base_config.dict()
        config_data["target_stack"] = spec.stack
        config_data["auto_approve_plan"] = True
        config_data["enable_progress_bar"] = False  # paralel çıktı karışmasın

        try:
            config = TeamConfig(**config_data)
        except Exception:
            config = TeamConfig(
                target_stack=spec.stack,
                auto_approve_plan=True,
                enable_progress_bar=False,
            )

        output_dir = f"{self.output_dir_base}/{spec.name}"

        try:
            team = MGXStyleTeam(config=config, output_dir_base=output_dir)
            plan = await team.analyze_and_plan(spec.description)
            team.approve_plan()
            output = await team.execute()
            duration = time.perf_counter() - t0
            logger.info(
                f"[ParallelOrchestrator] {spec.name} tamamlandı ({duration:.1f}s)"
            )
            return ServiceResult(
                spec=spec,
                success=True,
                output=output or plan or "",
                output_dir=getattr(team, "_last_output_dir", output_dir),
                duration=duration,
            )
        except Exception as exc:
            duration = time.perf_counter() - t0
            logger.error(
                f"[ParallelOrchestrator] {spec.name} başarısız: {exc}",
                exc_info=True,
            )
            return ServiceResult(
                spec=spec,
                success=False,
                error=str(exc),
                duration=duration,
            )

    async def _integrate(
        self, results: List[ServiceResult]
    ) -> dict:
        action = IntegrateServices(context=None)
        try:
            files = await action.run(results)
        except Exception as exc:
            logger.warning(f"[ParallelOrchestrator] IntegrateServices hatası: {exc}")
            from mgx_agent.microservice.integrator import _fallback_files
            files = _fallback_files(results)
        return files


__all__ = ["ParallelOrchestrator"]
