# -*- coding: utf-8 -*-
"""
mgx_agent.microservice

Paralel mikroservis geliştirme ve orkestrasyon paketi.

Ana sınıflar:
  ParallelOrchestrator  — tam akış (decompose → parallel teams → integrate)
  DecomposeTask         — LLM tabanlı servis ayrıştırma action'ı
  IntegrateServices     — LLM tabanlı entegrasyon dosyası üretim action'ı
  ServiceSpec           — tek bir servisi tanımlayan değer nesnesi
  ServiceResult         — tek servis çalışmasının sonucu
  ParallelRunResult     — tüm paralel akışın sonucu
"""

from mgx_agent.microservice.models import ServiceSpec, ServiceResult, ParallelRunResult
from mgx_agent.microservice.decomposer import DecomposeTask
from mgx_agent.microservice.integrator import IntegrateServices
from mgx_agent.microservice.orchestrator import ParallelOrchestrator

__all__ = [
    "ParallelOrchestrator",
    "DecomposeTask",
    "IntegrateServices",
    "ServiceSpec",
    "ServiceResult",
    "ParallelRunResult",
]
