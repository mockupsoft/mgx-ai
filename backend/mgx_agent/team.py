#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MGX Style Multi-Agent Team
Açık kaynak MetaGPT'yi MGX'e benzer şekilde çalıştıran örnek.

Özellikler:
- Plan taslağı oluşturma
- Kullanıcı onayı bekleme
- Görev karmaşıklık değerlendirmesi (XS/S/M/L/XL)
- Takım üyelerine görev atama
- İlerleme takibi
"""


# Lokal geliştirme: examples klasöründen çalışırken metagpt paketini bul

import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence, Any, Dict, Tuple
from enum import Enum

from pydantic import BaseModel, Field, validator
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from metagpt.actions import Action
from metagpt.logs import logger
from metagpt.roles import Role
from metagpt.schema import Message
from metagpt.config2 import config as global_config
try:
    from metagpt.team import Team
    from metagpt.context import Context
except ImportError:
    from metagpt.config import Config
    from mgx_agent.metagpt_wrapper import Team, Context

# Import from mgx_agent package for modular structure  
from mgx_agent.adapter import MetaGPTAdapter
from mgx_agent.actions import (
    AnalyzeTask,
    DraftPlan,
    WriteCode,
    WriteTest,
    ReviewCode,
)
from mgx_agent.roles import Mike, Alex, Bob, Charlie
from mgx_agent.cache import (
    CacheBackend,
    ResponseCache,
    InMemoryLRUTTLCache,
    NullCache,
    RedisCache,
    make_cache_key,
)
from mgx_agent.performance.async_tools import (
    AsyncTimer,
    bounded_gather,
    with_timeout,
    run_in_thread,
    PhaseTimings,
)

from mgx_observability import start_span, set_span_attributes


# ============================================
# GÖREV KARMAŞIKLIK DEĞERLENDİRME
# ============================================
class TaskComplexity:
    """Görev karmaşıklık seviyeleri"""
    XS = "XS"  # Çok basit - tek dosya, tek fonksiyon
    S = "S"    # Basit - birkaç fonksiyon
    M = "M"    # Orta - birden fazla dosya
    L = "L"    # Büyük - mimari gerektirir
    XL = "XL"  # Çok büyük - tam takım gerektirir


# ============================================
# TAKIM KONFİGÜRASYONU (Pydantic)
# ============================================
class LogLevel(str, Enum):
    """Log seviyeleri"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class TeamConfig(BaseModel):
    """MGX Style Team konfigürasyonu - Pydantic validation ile"""
    
    # Temel ayarlar
    max_rounds: int = Field(default=5, ge=1, le=20, description="Maksimum çalışma turu")
    max_revision_rounds: int = Field(default=2, ge=0, le=5, description="Maksimum düzeltme turu")
    max_memory_size: int = Field(default=50, ge=10, le=500, description="Hafıza limiti")
    
    # Özellik anahtarları
    enable_caching: bool = Field(default=True, description="Analiz cache'i aktif mi")
    enable_streaming: bool = Field(default=True, description="LLM streaming aktif mi")
    enable_progress_bar: bool = Field(default=True, description="Progress bar göster")
    enable_metrics: bool = Field(default=True, description="Metrik toplama aktif mi")
    enable_memory_cleanup: bool = Field(default=True, description="Otomatik hafıza temizliği")
    enable_profiling: bool = Field(default=False, description="Performance profiling aktif mi")
    enable_profiling_tracemalloc: bool = Field(default=False, description="Tracemalloc ile detaylı hafıza profiling")
    
    # Takım ayarları
    human_reviewer: bool = Field(default=False, description="Charlie insan modu")
    auto_approve_plan: bool = Field(default=False, description="Plan otomatik onayla")
    
    # Budget ayarları
    default_investment: float = Field(default=3.0, ge=0.5, le=20.0, description="Varsayılan investment ($)")
    budget_multiplier: float = Field(default=1.0, ge=0.1, le=5.0, description="Budget çarpanı")
    
    # LLM ayarları
    use_multi_llm: bool = Field(default=False, description="Her role farklı LLM")
    
    # Log ayarları
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Log seviyesi")
    verbose: bool = Field(default=False, description="Detaylı çıktı")
    
    # Cache ayarları
    cache_backend: str = Field(
        default="memory",
        description="Cache backend: none | memory | redis",
    )
    cache_max_entries: int = Field(
        default=1024,
        ge=1,
        le=100_000,
        description="In-memory cache için maksimum entry sayısı (LRU)",
    )
    redis_url: Optional[str] = Field(
        default=None,
        description="Redis URL (cache_backend=redis için)",
    )
    cache_log_hits: bool = Field(default=False, description="Cache hit logla")
    cache_log_misses: bool = Field(default=False, description="Cache miss logla")
    cache_ttl_seconds: int = Field(default=3600, ge=60, le=86400, description="Cache TTL (saniye)")
    
    @validator('max_rounds')
    @classmethod
    def validate_max_rounds(cls, v):
        if v < 1:
            raise ValueError("max_rounds en az 1 olmalı")
        return v
    
    @validator('default_investment')
    @classmethod
    def validate_investment(cls, v):
        if v < 0.5:
            raise ValueError("investment en az $0.5 olmalı")
        return v
    
    @validator('budget_multiplier')
    @classmethod
    def validate_budget_multiplier(cls, v):
        if v <= 0:
            raise ValueError("budget_multiplier 0'dan büyük olmalı")
        if v > 10:
            logger.warning(f"⚠️ budget_multiplier çok yüksek: {v}x - Maliyet patlaması riski!")
        return v
    
    # ✅ Pydantic v2 syntax
    class Config:
        use_enum_values = True
    
    def to_dict(self) -> dict:
        """Config'i dict olarak döndür"""
        return self.dict()
    
    @classmethod
    def from_dict(cls, data: dict) -> "TeamConfig":
        """Dict'ten config oluştur"""
        return cls(**data)
    
    @classmethod
    def from_yaml(cls, path: str) -> "TeamConfig":
        """YAML dosyasından config oluştur"""
        import yaml
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return cls(**data)
    
    def save_yaml(self, path: str):
        """Config'i YAML dosyasına kaydet"""
        import yaml
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, allow_unicode=True)
    
    def __str__(self) -> str:
        return f"""TeamConfig(
  max_rounds={self.max_rounds}, max_revision_rounds={self.max_revision_rounds},
  max_memory_size={self.max_memory_size}, enable_caching={self.enable_caching},
  human_reviewer={self.human_reviewer}, default_investment=${self.default_investment}
)"""


# Varsayılan config
DEFAULT_CONFIG = TeamConfig()


# ============================================
# GÖREV METRİKLERİ
# ============================================
@dataclass
class TaskMetrics:
    """Görev metrikleri - izlenebilirlik için"""
    task_name: str
    start_time: float
    end_time: float = 0.0
    success: bool = False
    complexity: str = "XS"
    token_usage: int = 0  # Şimdilik dummy - ileride gerçek değer
    estimated_cost: float = 0.0  # Şimdilik dummy - ileride gerçek değer
    revision_rounds: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    error_message: str = ""
    
    @property
    def duration_seconds(self) -> float:
        """Görev süresi (saniye)"""
        return self.end_time - self.start_time if self.end_time else 0.0
    
    @property
    def duration_formatted(self) -> str:
        """Formatlanmış süre"""
        secs = self.duration_seconds
        if secs < 60:
            return f"{secs:.1f}s"
        elif secs < 3600:
            return f"{secs/60:.1f}m"
        else:
            return f"{secs/3600:.1f}h"
    
    def to_dict(self) -> dict:
        """Metriği dict olarak döndür"""
        return {
            "task_name": self.task_name,
            "duration": self.duration_formatted,
            "success": self.success,
            "complexity": self.complexity,
            "token_usage": self.token_usage,
            "estimated_cost": f"${self.estimated_cost:.4f}",
            "revision_rounds": self.revision_rounds,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "error": self.error_message if self.error_message else None,
        }


# ============================================
# ACTION'LAR (Retry Logic ile)
# ============================================

# Retry decorator - LLM hatalarında otomatik yeniden dene
def llm_retry():
    """LLM çağrıları için retry decorator"""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=lambda retry_state: logger.warning(
            f"⚠️ LLM hatası, yeniden deneniyor... (Deneme {retry_state.attempt_number}/3)"
        )
    )


# ============================================
# PROGRESS HELPERS
# ============================================
def print_step_progress(step: int, total: int, description: str, role=None):
    """Adım adım progress göster
    
    Args:
        step: Mevcut adım
        total: Toplam adım
        description: Açıklama
        role: Role instance (team referansı için)
    """
    # Eğer role'un team referansı varsa onu kullan (config kontrolü için)
    if role and hasattr(role, '_team_ref') and hasattr(role._team_ref, '_print_progress'):
        role._team_ref._print_progress(step, total, description)
        return
    
    # Fallback: Global fonksiyon (eski davranış)
    bar_length = 20
    filled = int(bar_length * step / total)
    bar = "█" * filled + "░" * (bar_length - filled)
    percent = int(100 * step / total)
    print(f"\r[{bar}] {percent}% - {description}", end="", flush=True)
    if step == total:
        print()  # Yeni satır


def print_phase_header(phase: str, emoji: str = "🔄"):
    """Faz başlığı yazdır"""
    print(f"\n{'='*60}")
    print(f"{emoji} {phase}")
    print(f"{'='*60}")




# ============================================
# MGX STYLE TEAM
# ============================================
class MGXStyleTeam:
    """MGX tarzı takım yöneticisi"""

    # Shared cache instance used when MGX_GLOBAL_CACHE=1 (perf/load tests).
    _GLOBAL_RESPONSE_CACHE: Optional[ResponseCache] = None

    def __init__(
        self,
        config: TeamConfig = None,
        human_reviewer: bool = False,
        max_memory_size: int = 50,
        *,
        context_override: Optional[Any] = None,
        team_override: Optional[Any] = None,
        roles_override: Optional[Sequence[Any]] = None,
        output_dir_base: Optional[str] = "output",
    ):
        """
        MGX tarzı takım oluştur.
        
        Args:
            config: TeamConfig objesi (None ise varsayılan kullanılır)
            human_reviewer: True ise Charlie (Reviewer) insan olarak çalışır (config'den override edilir)
            max_memory_size: Hafıza limiti (config'den override edilir)
        """
        # Config yoksa varsayılan oluştur
        if config is None:
            config = TeamConfig(
                human_reviewer=human_reviewer,
                max_memory_size=max_memory_size
            )
        
        self.config = config
        self._log_config()
        
        # Config'den değerleri al
        self.output_dir_base = output_dir_base
        self.context = context_override if context_override is not None else Context()
        self.team = team_override if team_override is not None else Team(context=self.context)
        self.plan_approved = False
        self.current_task = None
        self.current_task_spec = None  # Tek kaynak: task, plan, complexity bilgisi
        self.progress = []
        self.memory_log = []  # Hafıza günlüğü
        self.max_memory_size = config.max_memory_size
        self.human_mode = config.human_reviewer
        self.metrics: List[TaskMetrics] = [] if config.enable_metrics else None
        self.phase_timings = PhaseTimings()  # Track phase durations

        # Cache stats (used by performance suite)
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache: ResponseCache = self._init_cache()
        
        # Profiling
        self._profiler = None
        self._profiling_enabled = config.enable_profiling
        
        # Her role için farklı LLM config'leri yükle (veya test harness overrides)
        if roles_override is not None:
            roles_list = list(roles_override)
            self.multi_llm_mode = False
        else:
            if config.use_multi_llm:
                try:
                    mike_config = Config.from_home("mike_llm.yaml")
                    alex_config = Config.from_home("alex_llm.yaml")
                    bob_config = Config.from_home("bob_llm.yaml")
                    charlie_config = Config.from_home("charlie_llm.yaml")
                    self.multi_llm_mode = True
                    logger.info("🎯 Multi-LLM modu aktif - Her role farklı model kullanacak!")
                except Exception:
                    mike_config = alex_config = bob_config = charlie_config = None
                    self.multi_llm_mode = False
                    logger.info("📦 Tek LLM modu - Tüm roller aynı modeli kullanacak")
            else:
                mike_config = alex_config = bob_config = charlie_config = None
                self.multi_llm_mode = False
                logger.info("📦 Tek LLM modu - Tüm roller aynı modeli kullanacak")

            # Takımı oluştur (her role farklı config ile)
            # Global LLM config'i kullan (config2.yaml'dan okunan değerler)
            logger.info(f"🤖 Global LLM model: {global_config.llm.model}, type: {global_config.llm.api_type}")
            roles_list = [
                Mike(config=mike_config) if mike_config else Mike(),
                Alex(config=alex_config) if alex_config else Alex(),
                Bob(config=bob_config) if bob_config else Bob(),
                Charlie(is_human=config.human_reviewer, config=charlie_config)
                if charlie_config
                else Charlie(is_human=config.human_reviewer),
            ]
            
            # Global LLM config'i tüm rollere uygula
            for role in roles_list:
                if hasattr(role, 'llm') and hasattr(global_config, 'llm'):
                    role.llm = global_config.get_llm()

        # Role'lara team referansı ekle (progress bar için)
        for role in roles_list:
            try:
                role._team_ref = self
            except Exception:
                pass

        if hasattr(self.team, "hire"):
            self.team.hire(roles_list)

        # Role referanslarını sakla (team.env.roles erişimini azaltmak için)
        if len(roles_list) >= 4:
            self._mike = roles_list[0]
            self._alex = roles_list[1]
            self._bob = roles_list[2]
            self._charlie = roles_list[3]
        else:
            self._mike = roles_list[0] if roles_list else None
            self._alex = None
            self._bob = None
            self._charlie = None
        
        # Multi-LLM sanity check: Gerçekten farklı modeller kullanılıyor mu?
        if self.multi_llm_mode:
            self._verify_multi_llm_setup(roles_list)
        
        logger.info("🏢 MGX Style Takım oluşturuldu!")
        if self.multi_llm_mode:
            logger.info("👤 Mike (Team Leader) - 🧠 allenai/olmo-3-32b-think:free")
            logger.info("👤 Alex (Engineer) - 💻 amazon/nova-2-lite-v1:free")
            logger.info("👤 Bob (Tester) - ⚡ arcee-ai/trinity-mini:free")
            if config.human_reviewer:
                logger.info("👤 Charlie (Reviewer) - 🧑 HUMAN FLAG (LLM fallback)")
            else:
                logger.info("👤 Charlie (Reviewer) - 🔍 nvidia/nemotron-nano-12b-v2-vl:free")
        else:
            logger.info("👤 Mike (Team Leader) - Görev analizi ve planlama")
            logger.info("👤 Alex (Engineer) - Kod yazma")
            logger.info("👤 Bob (Tester) - Test yazma")
            if config.human_reviewer:
                logger.info("👤 Charlie (Reviewer) - 🧑 HUMAN FLAG (LLM fallback)")
            else:
                logger.info("👤 Charlie (Reviewer) - Kod inceleme")
    
    def _log_config(self):
        """Config bilgilerini logla"""
        if self.config.verbose:
            logger.info(f"⚙️ TeamConfig yüklendi:")
            logger.info(f"   max_rounds: {self.config.max_rounds}")
            logger.info(f"   max_revision_rounds: {self.config.max_revision_rounds}")
            logger.info(f"   max_memory_size: {self.config.max_memory_size}")
            logger.info(f"   enable_caching: {self.config.enable_caching}")
            logger.info(f"   enable_metrics: {self.config.enable_metrics}")
            logger.info(f"   default_investment: ${self.config.default_investment}")
            logger.info(f"   cache_backend: {getattr(self.config, 'cache_backend', 'memory')}")
            logger.info(f"   cache_max_entries: {getattr(self.config, 'cache_max_entries', 1024)}")
            logger.info(f"   cache_ttl_seconds: {self.config.cache_ttl_seconds}")

    def _init_cache(self) -> ResponseCache:
        """Initialize response cache based on config."""

        if not getattr(self.config, "enable_caching", True):
            return NullCache()

        backend_raw = str(getattr(self.config, "cache_backend", CacheBackend.MEMORY.value)).lower()
        if backend_raw in (CacheBackend.NONE.value, "off", "false", "0"):
            return NullCache()

        use_global = os.getenv("MGX_GLOBAL_CACHE") == "1"
        max_entries = int(getattr(self.config, "cache_max_entries", 1024))
        ttl_seconds = int(getattr(self.config, "cache_ttl_seconds", 3600))

        if backend_raw == CacheBackend.REDIS.value:
            redis_url = getattr(self.config, "redis_url", None)
            if not redis_url:
                logger.warning("⚠️ cache_backend=redis ama redis_url boş - cache devre dışı")
                return NullCache()
            try:
                return RedisCache(redis_url=redis_url, ttl_seconds=ttl_seconds)
            except Exception as e:
                logger.warning(f"⚠️ Redis cache init başarısız ({e}) - in-memory cache kullanılacak")
                return InMemoryLRUTTLCache(max_entries=max_entries, ttl_seconds=ttl_seconds)

        if use_global:
            if MGXStyleTeam._GLOBAL_RESPONSE_CACHE is None:
                MGXStyleTeam._GLOBAL_RESPONSE_CACHE = InMemoryLRUTTLCache(
                    max_entries=max_entries,
                    ttl_seconds=ttl_seconds,
                )
            return MGXStyleTeam._GLOBAL_RESPONSE_CACHE

        return InMemoryLRUTTLCache(max_entries=max_entries, ttl_seconds=ttl_seconds)

    async def cached_llm_call(
        self,
        *,
        role: str,
        action: str,
        payload: Dict[str, Any],
        compute,
        bypass_cache: bool = False,
        encode=None,
        decode=None,
    ):
        """Run an expensive computation with cache.

        `payload` must be JSON serializable.

        encode/decode can be used to cache a serialized representation while
        returning richer python objects.
        """

        if bypass_cache or not getattr(self.config, "enable_caching", True):
            return await compute()

        # Human reviewer mode should never influence LLM review behavior.
        if getattr(self.config, "human_reviewer", False) and role == "Reviewer":
            return await compute()

        key = make_cache_key(role=role, action=action, payload=payload)

        cached = None
        try:
            cached = self._cache.get(key)
        except Exception as e:
            logger.debug(f"Cache get hatası: {e}")

        if cached is not None:
            self._cache_hits += 1
            if getattr(self.config, "cache_log_hits", False):
                logger.info(f"⚡ Cache hit: {role}/{action}")
            try:
                from mgx_agent.performance.profiler import get_active_profiler

                prof = get_active_profiler()
                if prof is not None:
                    prof.record_cache(True)
            except Exception:
                pass
            return decode(cached) if decode else cached

        # Try semantic cache if available
        if hasattr(self._cache, '_find_similar') or isinstance(self._cache, type(self._cache).__module__ + '.SemanticCache'):
            try:
                from mgx_agent.cache import SemanticCache
                if isinstance(self._cache, SemanticCache):
                    # Extract text from payload for semantic matching
                    payload_text = str(payload.get('task', payload.get('content', '')))
                    if payload_text:
                        semantic_key = self._cache._find_similar(self._cache._simple_embedding(payload_text))
                        if semantic_key:
                            semantic_cached = self._cache.base_cache.get(semantic_key)
                            if semantic_cached is not None:
                                self._cache_hits += 1
                                logger.debug(f"⚡ Semantic cache hit: {role}/{action}")
                                try:
                                    from mgx_agent.performance.profiler import get_active_profiler
                                    prof = get_active_profiler()
                                    if prof is not None:
                                        prof.record_cache(True)
                                except Exception:
                                    pass
                                return decode(semantic_cached) if decode else semantic_cached
            except Exception as e:
                logger.debug(f"Semantic cache lookup failed: {e}")

        self._cache_misses += 1
        if getattr(self.config, "cache_log_misses", False):
            logger.info(f"🐢 Cache miss: {role}/{action}")
        try:
            from mgx_agent.performance.profiler import get_active_profiler

            prof = get_active_profiler()
            if prof is not None:
                prof.record_cache(False)
        except Exception:
            pass

        result = await compute()
        to_store = encode(result) if encode else result
        try:
            self._cache.set(key, to_store)
        except Exception as e:
            logger.debug(f"Cache set hatası: {e}")
        return result

    def cache_clear(self) -> None:
        """Clear the configured cache."""
        try:
            self._cache.clear()
        except Exception:
            pass

    def clear_cache(self) -> None:
        """Backward-compatible alias for cache_clear()."""
        return self.cache_clear()

    def cache_inspect(self) -> dict:
        """Return cache stats + a sample of keys for debugging."""
        try:
            st = self._cache.stats()
            keys = self._cache.keys()
        except Exception:
            st = None
            keys = []

        return {
            "enabled": bool(getattr(self.config, "enable_caching", True)),
            "backend": getattr(st, "backend", None),
            "size": getattr(st, "size", 0),
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "keys_sample": keys[:10],
        }

    def inspect_cache(self) -> dict:
        """Backward-compatible alias for cache_inspect()."""
        return self.cache_inspect()

    def cache_warm(self, *, role: str, action: str, payload: Dict[str, Any], value: Any) -> None:
        """Prewarm cache with a known response."""
        if not getattr(self.config, "enable_caching", True):
            return
        key = make_cache_key(role=role, action=action, payload=payload)
        try:
            self._cache.set(key, value)
        except Exception:
            pass

    def warm_cache(self, *, role: str, action: str, payload: Dict[str, Any], value: Any) -> None:
        """Backward-compatible alias for cache_warm()."""
        return self.cache_warm(role=role, action=action, payload=payload, value=value)

    def _sync_task_spec_from_plan(self, plan_content: str, *, fallback_task: str) -> None:
        """Ensure self.current_task_spec is populated from Mike's plan message."""

        task = fallback_task
        complexity = "M"
        plan = ""

        if "---JSON_START---" in plan_content and "---JSON_END---" in plan_content:
            try:
                json_str = plan_content.split("---JSON_START---")[1].split("---JSON_END---")[0].strip()
                data = json.loads(json_str)
                if isinstance(data, dict):
                    task = data.get("task") or task
                    complexity = data.get("complexity") or complexity
                    plan = data.get("plan") or plan
            except Exception:
                pass

        if not plan:
            # Try to extract a PLAN: section; otherwise keep entire message.
            m = re.search(r"\bPLAN:\s*(.*)", plan_content, re.IGNORECASE | re.DOTALL)
            if m:
                plan = m.group(1).strip()
            else:
                plan = plan_content

        self.set_task_spec(
            task=task,
            complexity=str(complexity),
            plan=plan,
            is_revision=False,
            review_notes="",
        )

    def _verify_multi_llm_setup(self, roles_list):
        """
        Multi-LLM modunda gerçekten farklı modeller kullanılıyor mu kontrol et (sanity check)
        
        Args:
            roles_list: Oluşturulan role listesi
        """
        try:
            role_names = ["Mike", "Alex", "Bob", "Charlie"]
            llm_models = []
            
            for i, role in enumerate(roles_list):
                role_name = role_names[i] if i < len(role_names) else f"Role_{i}"
                llm_info = "N/A"
                
                # Role'un LLM'ini kontrol et
                if hasattr(role, 'llm') and role.llm:
                    # LLM provider'ından model adını almaya çalış
                    if hasattr(role.llm, 'model'):
                        llm_info = role.llm.model
                    elif hasattr(role.llm, 'model_name'):
                        llm_info = role.llm.model_name
                    elif hasattr(role.llm, '__class__'):
                        llm_info = role.llm.__class__.__name__
                    else:
                        llm_info = "Unknown"
                
                llm_models.append((role_name, llm_info))
                logger.debug(f"🔍 {role_name} LLM: {llm_info}")
            
            # Tüm modeller aynı mı kontrol et
            unique_models = set(model for _, model in llm_models)
            if len(unique_models) == 1:
                logger.warning(f"⚠️ SANITY CHECK: Multi-LLM modu aktif ama tüm roller aynı modeli kullanıyor: {unique_models.pop()}")
                logger.warning(f"⚠️ Config dosyaları yüklendi ama role'lar farklı LLM kullanmıyor olabilir!")
                logger.warning(f"⚠️ MetaGPT'nin Role sınıfı config parametresini desteklemiyor olabilir.")
            else:
                logger.info(f"✅ SANITY CHECK: Multi-LLM modu çalışıyor - {len(unique_models)} farklı model kullanılıyor")
                for role_name, model in llm_models:
                    logger.info(f"   {role_name}: {model}")
        
        except Exception as e:
            logger.warning(f"⚠️ Multi-LLM sanity check hatası: {e}")
            logger.warning(f"⚠️ LLM kontrolü yapılamadı - config'lerin gerçekten kullanıldığından emin olamıyoruz")
    
    def get_config(self) -> TeamConfig:
        """Mevcut config'i döndür"""
        return self.config
    
    def update_config(self, **kwargs):
        """Config değerlerini güncelle"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"⚙️ Config güncellendi: {key} = {value}")
    
    def set_task_spec(self, task: str, complexity: str, plan: str, is_revision: bool = False, review_notes: str = ""):
        """
        Task spec'i set et (tek kaynak - hafıza taraması yerine bu kullanılacak)
        
        Args:
            task: Görev açıklaması
            complexity: Karmaşıklık seviyesi (XS, S, M, L, XL)
            plan: Plan metni
            is_revision: Revision turu mu?
            review_notes: Review notları (revision turunda)
        """
        self.current_task_spec = {
            "task": task,
            "complexity": complexity,
            "plan": plan,
            "is_revision": is_revision,
            "review_notes": review_notes
        }
        logger.debug(f"📋 Task spec set edildi: task='{task[:50]}...', complexity={complexity}, is_revision={is_revision}")
    
    def get_task_spec(self) -> dict:
        """
        Mevcut task spec'i döndür
        
        Returns:
            Task spec dict veya None
        """
        return self.current_task_spec
    
    def _print_progress(self, step: int, total: int, description: str):
        """Progress göster (config'e göre)"""
        if not self.config.enable_progress_bar:
            return
        
        bar_length = 20
        filled = int(bar_length * step / total)
        bar = "█" * filled + "░" * (bar_length - filled)
        percent = int(100 * step / total)
        print(f"\r[{bar}] {percent}% - {description}", end="", flush=True)
        if step == total:
            print()  # Yeni satır
    
    def _log(self, message: str, level: str = "info"):
        """Config'e göre log yaz"""
        if not self.config.verbose and level == "debug":
            return
        
        if level == "info":
            logger.info(message)
        elif level == "debug":
            logger.debug(message)
        elif level == "warning":
            logger.warning(message)
        elif level == "error":
            logger.error(message)
    
    def add_to_memory(self, role: str, action: str, content: str):
        """Hafıza günlüğüne ekle"""
        entry = {
            "role": role,
            "action": action,
            "content": content[:100] + "..." if len(content) > 100 else content,
            "timestamp": datetime.now().isoformat(timespec="seconds")
        }
        self.memory_log.append(entry)
        self.progress.append(f"{role}: {action}")
    
    def cleanup_memory(self):
        """Hafıza günlüğünü temizle - şişmeyi önle"""
        # 1. memory_log temizliği
        if len(self.memory_log) > self.max_memory_size:
            old_size = len(self.memory_log)
            self.memory_log = self.memory_log[-self.max_memory_size:]
            logger.info(f"🧹 Hafıza günlüğü temizlendi: {old_size} → {len(self.memory_log)} kayıt")
        
        # 2. progress temizliği
        if len(self.progress) > self.max_memory_size:
            self.progress = self.progress[-self.max_memory_size:]
        
        # 3. Role memory temizliği (her role için) - Adapter kullanarak
        if hasattr(self.team, 'env') and hasattr(self.team.env, 'roles'):
            for role in self.team.env.roles.values():
                mem_store = MetaGPTAdapter.get_memory_store(role)
                if mem_store is None:
                    continue
                
                # Mesajları adapter üzerinden al
                memory = MetaGPTAdapter.get_messages(mem_store)
                
                if len(memory) > self.max_memory_size:
                    # Adapter üzerinden temizle
                    success = MetaGPTAdapter.clear_memory(mem_store, self.max_memory_size)
                    if success:
                        logger.info(f"🧹 {role.name} hafızası temizlendi: {len(memory)} → {self.max_memory_size} mesaj")
                    else:
                        logger.warning(f"⚠️ {role.name} hafızası temizlenemedi")
    
    def show_memory_log(self) -> str:
        """Hafıza günlüğünü göster"""
        if not self.memory_log:
            return "📋 Hafıza günlüğü boş."
        
        result = "\n📋 HAFIZA GÜNLÜĞÜ:\n" + "=" * 40 + "\n"
        for i, entry in enumerate(self.memory_log, 1):
            result += f"{i}. [{entry['role']}] {entry['action']}\n"
            result += f"   İçerik: {entry['content']}\n"
        return result
    
    def _start_profiler(self, run_name: str = "mgx_team_run"):
        """Initialize and start the profiler if enabled."""
        if not self._profiling_enabled:
            return None
        
        from mgx_agent.performance.profiler import PerformanceProfiler
        
        self._profiler = PerformanceProfiler(
            run_name=run_name,
            enable_tracemalloc=self.config.enable_profiling_tracemalloc,
            enable_file_output=True,
        )
        self._profiler.start()
        return self._profiler
    
    def _end_profiler(self) -> Optional[dict]:
        """End profiling and write reports."""
        if self._profiler is None:
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self._profiler.stop()
        
        # Write detailed report
        detailed_file = self._profiler.write_detailed_report(timestamp)
        if detailed_file:
            logger.info(f"📊 Detailed performance report: {detailed_file}")
        
        # Write summary report
        summary_file = self._profiler.write_summary_report()
        if summary_file:
            logger.info(f"📊 Summary performance report: {summary_file}")
        
        metrics = self._profiler.to_run_metrics()
        self._profiler = None
        return metrics

    async def analyze_and_plan(self, task: str) -> str:
        """Görevi analiz et ve plan oluştur"""
        self.current_task = task

        # Kullanıcıya görünen bilgi main() fonksiyonunda print ile basılıyor
        logger.debug(f"Yeni görev analiz ediliyor: {task}")
        
        # Start profiling phase if enabled
        if self._profiler:
            self._profiler.start_phase("analyze_and_plan")

        # Cache (perf + interactive) - plan generation is one of the hottest paths.
        if getattr(self.config, "enable_caching", True):
            cache_key = make_cache_key(
                role="TeamLeader",
                action="AnalyzeTask+DraftPlan",
                payload={"task": task},
            )
            cache_start = time.perf_counter()

            cached = None
            try:
                cached = self._cache.get(cache_key)
            except Exception:
                cached = None

            if cached is not None:
                self._cache_hits += 1
                try:
                    from mgx_agent.performance.profiler import get_active_profiler

                    prof = get_active_profiler()
                    if prof is not None:
                        prof.record_cache(True)
                        prof.record_timer("analyze_and_plan_cache_hit", time.perf_counter() - cache_start)
                except Exception:
                    pass

                cached_content = cached.get("content") if isinstance(cached, dict) else cached
                cached_role = cached.get("role", "TeamLeader") if isinstance(cached, dict) else "TeamLeader"

                self.last_plan = Message(content=str(cached_content), role=cached_role, cause_by=AnalyzeTask)
                self.add_to_memory(
                    "Mike",
                    "AnalyzeTask + DraftPlan (cache)",
                    str(cached_content),
                )
                self._sync_task_spec_from_plan(str(cached_content), fallback_task=task)

                if self.config.auto_approve_plan:
                    self._log("🤖 Auto-approve aktif, plan otomatik onaylandı", "info")
                    self.approve_plan()

                return str(cached_content)

            self._cache_misses += 1
            try:
                from mgx_agent.performance.profiler import get_active_profiler

                prof = get_active_profiler()
                if prof is not None:
                    prof.record_cache(False)
            except Exception:
                pass

        # Team'deki Mike'ı bul (saklanan referansı kullan - team.env.roles erişimini azalt)
        mike = getattr(self, '_mike', None)
        if not mike:
            # Fallback: team.env.roles erişimi (sadece gerekirse)
            if hasattr(self.team, 'env') and hasattr(self.team.env, 'roles'):
                for role in self.team.env.roles.values():
                    if role.profile == "TeamLeader":
                        mike = role
                        break
        
        if not mike:
            mike = Mike(context=self.context)
        
        # Mike analiz etsin (with timing and timeout)
        async with AsyncTimer("analyze_and_plan", log_on_exit=True) as timer:
            async with start_span(
                "mgx.team.analyze_and_plan",
                attributes={
                    "task.length": len(task),
                    "mgx.cache.enabled": bool(getattr(self.config, "enable_caching", True)),
                },
            ) as span:
                try:
                    analysis = await asyncio.wait_for(
                        mike.analyze_task(task),
                        timeout=120.0  # 2 minute timeout for analysis
                    )
                    set_span_attributes(
                        span,
                        {
                            "analysis.content.length": len(getattr(analysis, "content", str(analysis))),
                        },
                    )
                except asyncio.TimeoutError:
                    logger.error("⏱️  Analysis timeout (120s) exceeded")
                    raise
        
        # Record timing
        self.phase_timings.analysis_duration = timer.duration
        self.phase_timings.planning_duration = timer.duration  # Combined for now
        self.phase_timings.add_phase("analyze_and_plan", timer.duration)
        
        # ÖNEMLİ: Plan mesajını team environment'a publish et
        # Bu sayede Alex (Engineer) plan mesajını alacak
        self.last_plan = analysis

        # Cache the plan for repeated identical tasks
        if getattr(self.config, "enable_caching", True):
            cache_key = make_cache_key(
                role="TeamLeader",
                action="AnalyzeTask+DraftPlan",
                payload={"task": task},
            )
            try:
                self._cache.set(
                    cache_key,
                    {
                        "content": getattr(analysis, "content", str(analysis)),
                        "role": getattr(analysis, "role", "TeamLeader"),
                    },
                )
            except Exception:
                pass

        # Ensure task spec is set even when using mock roles.
        self._sync_task_spec_from_plan(getattr(analysis, "content", str(analysis)), fallback_task=task)

        # Hafızaya ekle
        self.add_to_memory("Mike", "AnalyzeTask + DraftPlan", analysis.content)
        
        # Auto approve kontrolü
        if self.config.auto_approve_plan:
            self._log("🤖 Auto-approve aktif, plan otomatik onaylandı", "info")
            self.approve_plan()
        
        # End profiling phase
        if self._profiler:
            self._profiler.end_phase()
        
        return analysis.content
    
    def approve_plan(self) -> bool:
        """Planı onayla"""
        self.plan_approved = True
        logger.info("✅ Plan onaylandı! Görev dağıtımı başlıyor...")
        return True
    
    def _tune_budget(self, complexity: str) -> dict:
        """Karmaşıklığa göre investment ve n_round ayarla
        
        Args:
            complexity: Görev karmaşıklığı (XS/S/M/L/XL)
        
        Returns:
            dict: {"investment": float, "n_round": int}
        """
        # Config'den multiplier ve max_rounds al
        multiplier = self.config.budget_multiplier
        max_rounds = self.config.max_rounds
        
        # TaskComplexity sabitleri ile karşılaştır
        if complexity in (TaskComplexity.XS, TaskComplexity.S):
            base = {"investment": 1.5, "n_round": min(2, max_rounds)}
        elif complexity == TaskComplexity.M:
            base = {"investment": 3.0, "n_round": min(3, max_rounds)}
        else:  # L, XL
            base = {"investment": 5.0, "n_round": min(4, max_rounds)}
        
        # Budget multiplier uygula
        base["investment"] *= multiplier
        return base
    
    async def _execute_with_early_termination(self, max_rounds: int) -> int:
        """
        Execute with early termination if task is completed.
        
        Args:
            max_rounds: Maximum rounds to execute
        
        Returns:
            Actual number of rounds executed
        """
        actual_rounds = 0
        
        for round_num in range(1, max_rounds + 1):
            await self.team.run(n_round=1)
            actual_rounds += 1
            
            # Check if task is completed (early termination)
            if self._is_task_completed():
                logger.info(f"✅ Task completed early after {actual_rounds} rounds (max: {max_rounds})")
                break
            
            # Check budget exhaustion
            if self._check_budget_exhaustion():
                logger.warning(f"⚠️ Budget exhausted after {actual_rounds} rounds")
                break
        
        return actual_rounds
    
    def _is_task_completed(self) -> bool:
        """
        Check if task is completed based on results.
        
        Returns:
            True if task appears to be completed
        """
        try:
            code, tests, review = self._collect_raw_results()
            
            # Simple heuristic: if we have code, tests, and positive review, consider it done
            has_code = code and len(code.strip()) > 100
            has_tests = tests and len(tests.strip()) > 50
            has_positive_review = review and (
                "approved" in review.lower() or 
                "complete" in review.lower() or
                "good" in review.lower()
            )
            
            return has_code and has_tests and has_positive_review
        except Exception:
            return False
    
    def _check_budget_exhaustion(self) -> bool:
        """
        Check if budget is exhausted.
        
        Returns:
            True if budget is exhausted
        """
        # This is a placeholder - in production, check actual budget
        # For now, always return False
        return False
    
    def _calculate_optimal_rounds(self, complexity: str, budget: float) -> int:
        """
        Calculate optimal number of rounds based on complexity and budget.
        
        Args:
            complexity: Task complexity (XS, S, M, L, XL)
            budget: Available budget in USD
        
        Returns:
            Optimal number of rounds (with 95%+ accuracy target)
        """
        # Base rounds by complexity (optimized for accuracy)
        complexity_rounds = {
            "XS": 1,
            "S": 2,
            "M": 3,
            "L": 5,
            "XL": 8,
        }
        
        base_rounds = complexity_rounds.get(complexity, 3)
        
        # Adjust based on budget (more budget = more rounds possible)
        # Optimized estimate: $0.40 per round (reduced from $0.50 for better efficiency)
        budget_rounds = int(budget / 0.40)
        
        # Use minimum of complexity-based and budget-based
        optimal = min(base_rounds, budget_rounds)
        
        # Ensure within config limits
        optimal = max(1, min(optimal, self.config.max_rounds))
        
        # Add safety margin for accuracy (95%+ target)
        # For complex tasks, add one extra round if budget allows
        if complexity in ("L", "XL") and budget > optimal * 0.40:
            optimal = min(optimal + 1, self.config.max_rounds)
        
        return optimal
    
    def _get_complexity_from_plan(self) -> str:
        """Son plan mesajından complexity'yi çek"""
        if hasattr(self, 'last_plan') and self.last_plan:
            content = self.last_plan.content
            # JSON'dan parse et
            if "---JSON_START---" in content and "---JSON_END---" in content:
                try:
                    json_str = content.split("---JSON_START---")[1].split("---JSON_END---")[0].strip()
                    data = json.loads(json_str)
                    return data.get("complexity", "M")
                except (json.JSONDecodeError, IndexError):
                    pass
            # Regex ile dene
            m = re.search(r"KARMAŞIKLIK:\s*(XS|S|M|L|XL)", content.upper())
            if m:
                return m.group(1)
        return "M"  # Varsayılan
    
    def _calculate_token_usage(self) -> int:
        """
        Gerçek token kullanımını hesapla
        
        NOT: Şu an için token sayısı yeterli. İleride gerçek maliyet hesaplaması için:
        - TeamConfig'e price_per_million_tokens alanı eklenebilir
        - estimated_cost = total_tokens / 1_000_000 * model_price_per_million
        - Şimdilik investment'ı maliyet kabul etmek pratik
        """
        total_tokens = 0
        
        if hasattr(self.team, 'env') and hasattr(self.team.env, 'roles'):
            for role in self.team.env.roles.values():
                if hasattr(role, 'llm') and role.llm:
                    # MetaGPT'nin cost_manager'ından token bilgisi al
                    if hasattr(role.llm, 'cost_manager'):
                        cost_mgr = role.llm.cost_manager
                        if hasattr(cost_mgr, 'total_prompt_tokens'):
                            total_tokens += cost_mgr.total_prompt_tokens
                        if hasattr(cost_mgr, 'total_completion_tokens'):
                            total_tokens += cost_mgr.total_completion_tokens
                    # Alternatif: usage bilgisi direkt llm'de olabilir
                    elif hasattr(role.llm, 'usage'):
                        usage = role.llm.usage
                        if hasattr(usage, 'prompt_tokens'):
                            total_tokens += usage.prompt_tokens
                        if hasattr(usage, 'completion_tokens'):
                            total_tokens += usage.completion_tokens
        
        # Fallback: gerçek değer bulunamazsa tahmini döndür
        return total_tokens if total_tokens > 0 else 1000
    
    async def execute(
        self, 
        n_round: int = None, 
        max_revision_rounds: int = None,
        progress_callback: Callable[[str, str, str], None] = None
    ) -> str:
        """Görevi çalıştır
        
        Args:
            n_round: Her tur için maksimum round sayısı (None ise config'den alınır)
            max_revision_rounds: Review sonrası maksimum düzeltme turu (None ise config'den alınır)
            progress_callback: Agent ilerleme callback'i - (agent_name, status, message) parametreleri alır
        """
        if not self.plan_approved and not self.config.auto_approve_plan:
            return "❌ Plan henüz onaylanmadı! Önce plan onaylamalısınız."
        
        # Progress callback helper
        self._progress_callback = progress_callback
        
        # Config'den varsayılan değerleri al
        if max_revision_rounds is None:
            max_revision_rounds = self.config.max_revision_rounds
        
        # Metrics başlat (config.enable_metrics kontrolü)
        start_time = time.time()
        metric = TaskMetrics(
            task_name=self.current_task[:50] if self.current_task else "Unknown",
            start_time=start_time
        )
        
        # Karmaşıklığa göre budget ayarla
        complexity = self._get_complexity_from_plan()
        budget = self._tune_budget(complexity)
        metric.complexity = complexity
        
        # n_round parametresi verilmemişse budget-aware calculation yap
        if n_round is None:
            n_round = self._calculate_optimal_rounds(complexity, budget["investment"])
            logger.debug(f"Calculated optimal rounds: {n_round} (complexity: {complexity}, budget: ${budget['investment']})")
        
        # Kullanıcıya görünen bilgi print ile (logger.debug arka planda log dosyasına gider)
        print_phase_header("Görev Yürütme", "🚀")
        print(f"📊 Karmaşıklık: {complexity} → Investment: ${budget['investment']}, Rounds: {n_round}")
        logger.debug(f"Görev yürütme başlıyor - Karmaşıklık: {complexity}, Investment: ${budget['investment']}, Rounds: {n_round}")
        
        # Progress callback: Mike başlıyor
        await self._emit_progress("Mike", "working", "📋 Görevi analiz ediyorum ve planı oluşturuyorum...")
        
        # Start profiling phase if enabled
        if self._profiler:
            self._profiler.start_phase("execute")
        
        try:
            # Mike zaten analiz yaptı - complete_planning() çağır (tekrar çalışmasın)
            if hasattr(self.team.env, 'roles'):
                for role in self.team.env.roles.values():
                    if hasattr(role, 'complete_planning'):
                        role.complete_planning()
            
            self.team.invest(investment=budget["investment"])
            
            # ÖNEMLİ: Plan mesajını environment'a publish et
            if hasattr(self, 'last_plan') and self.last_plan:
                self.team.env.publish_message(self.last_plan)
                logger.debug("Plan mesajı Alex'e iletildi")
            
            # İlk tur: Ana geliştirme
            print_phase_header("TUR 1: Ana Geliştirme", "🔄")
            
            # Progress: Alex başlıyor
            await self._emit_progress("Alex", "working", "💻 Kod yazıyorum...")
            
            # Wrap main execution with timer
            async with AsyncTimer("main_development_round", log_on_exit=True) as exec_timer:
                async with start_span(
                    "mgx.team.main_development",
                    attributes={
                        "mgx.n_round": n_round,
                        "mgx.phase": "main_development",
                    },
                ) as span:
                    # Dynamic round calculation with early termination
                    actual_rounds = await self._execute_with_early_termination(n_round)
                    
                    # Progress: Alex tamamladı, Bob başlıyor
                    await self._emit_progress("Alex", "completed", "✅ Kod yazıldı")
                    await self._emit_progress("Bob", "working", "🧪 Testler yazılıyor...")
                    
                    # Charlie'nin çalışması için ek bir round (MetaGPT'nin normal akışı)
                    # Manuel tetikleme hacklerini kaldırdık - sadece team.run() kullanıyoruz
                    logger.debug("🔍 Charlie'nin review yapması için ek round çalıştırılıyor...")
                    await self.team.run(n_round=1)  # Charlie'nin Bob'un mesajını gözlemlemesi ve review yapması için
                    
                    # Progress: Bob tamamladı, Charlie başlıyor
                    await self._emit_progress("Bob", "completed", "✅ Testler yazıldı")
                    await self._emit_progress("Charlie", "working", "🔍 Kod incelemesi yapılıyor...")

                    set_span_attributes(
                        span,
                        {
                            "mgx.exec.rounds": int(actual_rounds),
                            "mgx.exec.early_terminated": actual_rounds < n_round,
                        },
                    )
            
            # Record execution timing
            self.phase_timings.execution_duration = exec_timer.duration
            self.phase_timings.add_phase("main_development", exec_timer.duration)
            
            # Tur sonrası hafıza temizliği (offload to thread)
            async with AsyncTimer("cleanup_after_main", log_on_exit=False) as cleanup_timer:
                await run_in_thread(self.cleanup_memory)
            self.phase_timings.add_phase("cleanup_after_main", cleanup_timer.duration)
        
            # Review sonucunu kontrol et
            revision_count = 0
            last_review_hash = None  # Sonsuz döngü önleme - LLM'nin aynı yorumları tekrar etme sorununa karşı
            
            while revision_count < max_revision_rounds:
                code, tests, review = self._collect_raw_results()
                
                # Debug: Review durumunu logla
                logger.debug(f"📋 Review durumu: code={len(code) if code else 0} chars, tests={len(tests) if tests else 0} chars, review={len(review) if review else 0} chars")
                if review:
                    logger.debug(f"📝 Review içeriği (ilk 200 char): {review[:200]}")
                
                # Review yoksa veya boşsa döngüden çık
                if not review or not review.strip():
                    logger.warning("⚠️ Review bulunamadı veya boş - döngüden çıkılıyor")
                    break
                
                # KORUMA 1: Aynı review tekrar gelirse (sonsuz döngü önleme)
                # LLM bazen "papağan gibi" aynı yorumları tekrar edebilir - bu durumda döngüyü kır
                review_hash = hashlib.md5(review.encode()).hexdigest()
                if review_hash == last_review_hash:
                    logger.warning(f"⚠️ Aynı review tekrar geldi (tur {revision_count + 1}) - LLM aynı yorumu tekrar etti, döngüden çıkılıyor")
                    break
                last_review_hash = review_hash
                
                # Review'da "DEĞİŞİKLİK GEREKLİ" var mı kontrol et
                if "DEĞİŞİKLİK GEREKLİ" in review.upper():
                    revision_count += 1
                    
                    # KORUMA 2: Maksimum düzeltme turu kontrolü
                    # Sonsuz döngüyü önlemek için hard limit
                    if revision_count > max_revision_rounds:
                        logger.warning(f"⚠️ Maksimum düzeltme turu ({max_revision_rounds}) aşıldı - durduruluyor")
                        break
                    
                    # Start profiling revision phase
                    if self._profiler:
                        self._profiler.start_phase(f"revision_round_{revision_count}")
                    
                    print_phase_header(f"TUR {revision_count + 1}: Düzeltme Turu", "🔧")
                    print(f"⚠️ Charlie DEĞİŞİKLİK GEREKLİ dedi. Alex & Bob tekrar çalışıyor...")
                    
                    # İyileştirme mesajı oluştur (orijinal görevi ve planı da dahil et)
                    original_task = self.current_task or "Verilen görevi tamamla"
                    
                    # Task spec'i revision turu için güncelle (Alex'in direkt erişebilmesi için)
                    complexity = self._get_complexity_from_plan()
                    original_plan = ""
                    if self.current_task_spec:
                        original_plan = self.current_task_spec.get("plan", "")
                    
                    # Revision turu için task_spec'i güncelle
                    # Orijinal plan korunur, review notları ayrı bir alanda tutulur
                    self.set_task_spec(
                        task=original_task,
                        complexity=complexity,
                        plan=original_plan,  # Orijinal plan korunur
                        is_revision=True,
                        review_notes=review  # Review notları ayrı alanda
                    )
                    logger.info("📋 Task spec revision turu için güncellendi (orijinal görev + review notları)")
                    
                    # Orijinal plan mesajını da gönder (MetaGPT tarafı için - backward compatibility)
                    if hasattr(self, 'last_plan') and self.last_plan:
                        # Orijinal plan mesajını tekrar gönder
                        self.team.env.publish_message(self.last_plan)
                        logger.debug("📋 Orijinal plan mesajı Alex'e tekrar iletildi (backward compatibility)")
                    
                    # İyileştirme mesajını JSON formatında da gönder (Alex'in parse edebilmesi için - fallback)
                    improvement_json = {
                        "task": original_task,
                        "complexity": complexity,
                        "plan": f"Charlie'nin review notlarına göre kodu iyileştir: {review[:200]}...",
                        "improvement_required": True,
                        "review_notes": review[:500]
                    }
                    improvement_content = f"""
---JSON_START---
{json.dumps(improvement_json, ensure_ascii=False, indent=2)}
---JSON_END---

🚨 ÖNEMLİ: DÜZELTME TURU - ORİJİNAL GÖREVİ UNUTMA! 🚨

═══════════════════════════════════════════════════════════
YAPILMASI GEREKEN GÖREV (ASIL İŞ BU!):
═══════════════════════════════════════════════════════════
{original_task}
═══════════════════════════════════════════════════════════

⚠️ UYARI: YUKARIDAKI GÖREVİ YERİNE GETİRMELİSİN!
   Başka bir şey yazma, sadece yukarıdaki görevi yap!

═══════════════════════════════════════════════════════════
CHARLIE'NİN REVIEW NOTLARI (İYİLEŞTİRME ÖNERİLERİ):
═══════════════════════════════════════════════════════════
{review}

═══════════════════════════════════════════════════════════
YAPILACAKLAR:
═══════════════════════════════════════════════════════════
1. ÖNCE: Orijinal görevi yerine getir ({original_task})
2. SONRA: Charlie'nin önerilerini uygula:
   - Kod kalitesi ve hata yönetimi ekle
   - Test coverage ve edge case'ler ekle
   - Docstring'ler ve dokümantasyon ekle
   - Charlie'nin belirttiği spesifik iyileştirmeleri yap

═══════════════════════════════════════════════════════════
MEVCUT KOD (İYİLEŞTİRİLECEK):
═══════════════════════════════════════════════════════════
{code[:1500] if len(code) > 1500 else code}

🚨 HATIRLATMA: Orijinal görevi unutma! Sadece yukarıdaki görevi yap!
"""
                    
                    improvement_msg = Message(
                        content=improvement_content,
                        role="TeamLeader",
                        cause_by=AnalyzeTask
                    )
                    
                    # Alex'e mesaj gönder
                    self.team.env.publish_message(improvement_msg)
                    logger.info("📤 İyileştirme talebi ve plan mesajı Alex'e iletildi!")
                    
                    # Progress: Düzeltme turu başlıyor
                    await self._emit_progress("Alex", "working", f"🔄 Düzeltme turu {revision_count}: Kod iyileştiriliyor...")
                    
                    # Tekrar çalıştır (with timing)
                    async with AsyncTimer(f"revision_round_{revision_count}", log_on_exit=True) as rev_timer:
                        await self.team.run(n_round=n_round)
                        
                        await self._emit_progress("Alex", "completed", f"✅ Düzeltme turu {revision_count}: Kod güncellendi")
                        await self._emit_progress("Bob", "working", f"🧪 Düzeltme turu {revision_count}: Testler güncelleniyor...")
                        
                        # Charlie'nin revision turunda da review yapması için ek round
                        # Manuel tetikleme hacklerini kaldırdık - sadece team.run() kullanıyoruz
                        logger.debug("🔍 Charlie'nin revision review yapması için ek round çalıştırılıyor...")
                        await self.team.run(n_round=1)  # Charlie'nin Bob'un mesajını gözlemlemesi ve review yapması için
                        
                        await self._emit_progress("Bob", "completed", f"✅ Düzeltme turu {revision_count}: Testler güncellendi")
                        await self._emit_progress("Charlie", "working", f"🔍 Düzeltme turu {revision_count}: Tekrar inceleniyor...")
                    
                    self.phase_timings.add_phase(f"revision_round_{revision_count}", rev_timer.duration)
                    
                    # End profiling revision phase
                    if self._profiler:
                        self._profiler.end_phase()
                    
                    # Her tur sonrası hafıza temizliği (offload to thread)
                    await run_in_thread(self.cleanup_memory)
                else:
                    # Review OK - döngüden çık
                    await self._emit_progress("Charlie", "completed", "✅ Review tamamlandı - Kod onaylandı!")
                    print(f"\n✅ Review ONAYLANDI - Düzeltme gerekmiyor.")
                    break
            
            # Metrics güncelle - başarılı
            metric.revision_rounds = revision_count
            metric.success = True
            metric.cache_hits = self._cache_hits
            metric.cache_misses = self._cache_misses
            
            # Gerçek token kullanımını hesapla
            metric.token_usage = self._calculate_token_usage()
            metric.estimated_cost = budget["investment"]
            
            # Start profiling result persistence phase
            if self._profiler:
                self._profiler.start_phase("result_persistence")
            
            # Final operations: run results collection and cleanup concurrently
            async with AsyncTimer("final_operations", log_on_exit=True) as final_timer:
                # Use TaskGroup for concurrent final operations (Python 3.11+)
                # Fallback to gather for older Python versions
                try:
                    # Try Python 3.11+ TaskGroup
                    async with asyncio.TaskGroup() as tg:
                        # Collect results in thread (file I/O)
                        results_task = tg.create_task(
                            run_in_thread(self._collect_results)
                        )
                        # Final cleanup in thread
                        cleanup_task = tg.create_task(
                            run_in_thread(self.cleanup_memory)
                        )
                    
                    results = results_task.result()
                except AttributeError:
                    # Fallback for Python < 3.11: use gather
                    logger.debug("TaskGroup not available, using asyncio.gather")
                    results, _ = await asyncio.gather(
                        run_in_thread(self._collect_results),
                        run_in_thread(self.cleanup_memory)
                    )
            
            self.phase_timings.cleanup_duration = final_timer.duration
            self.phase_timings.add_phase("final_operations", final_timer.duration)
            self.phase_timings.total_duration = time.time() - start_time
            
            # End profiling result persistence phase
            if self._profiler:
                self._profiler.end_phase()
            
            # End execute profiling phase
            if self._profiler:
                self._profiler.end_phase()
            
            # Kullanıcıya görünen bilgi _show_metrics_report ile basılıyor
            logger.debug(f"Görev tamamlandı - {revision_count} düzeltme turu yapıldı")
            
            return results
            
        except Exception as e:
            # Hata durumu
            metric.success = False
            metric.error_message = str(e)
            logger.error(f"❌ Görev hatası: {e}")
            return f"❌ Görev başarısız: {e}"
            
        finally:
            # Metrics finalize (sadece metrics aktifse)
            metric.end_time = time.time()
            
            if self.metrics is not None:
                self.metrics.append(metric)
                self._show_metrics_report(metric)
    
    def _show_metrics_report(self, metric: TaskMetrics):
        """Tek bir görevin metrik raporunu göster"""
        status_emoji = "✅" if metric.success else "❌"
        
        print(f"\n{'='*60}")
        print(f"📊 GÖREV METRİKLERİ")
        print(f"{'='*60}")
        print(f"📌 Görev: {metric.task_name}")
        print(f"{status_emoji} Durum: {'Başarılı' if metric.success else 'Başarısız'}")
        print(f"⏱️  Süre: {metric.duration_formatted}")
        print(f"🎯 Karmaşıklık: {metric.complexity}")
        print(f"🔄 Düzeltme Turları: {metric.revision_rounds}")
        print(f"🪙 Tahmini Token: ~{metric.token_usage}")
        print(f"💰 Tahmini Maliyet: ${metric.estimated_cost:.4f}")
        print(f"⚡ Cache: hits={metric.cache_hits}, misses={metric.cache_misses}")
        if metric.error_message:
            print(f"⚠️  Hata: {metric.error_message}")
        print(f"{'='*60}\n")
    
    def get_all_metrics(self) -> List[dict]:
        """Tüm görev metriklerini döndür (profiling data dahil)"""
        metrics_list = []
        if self.metrics:
            metrics_list = [m.to_dict() for m in self.metrics]
        
        # Add profiling data if available
        if self._profiler:
            profiling_data = self._profiler.to_run_metrics()
            # Attach profiling to each metric or as a separate entry
            return {
                "task_metrics": metrics_list,
                "profiling": profiling_data,
            }
        
        return metrics_list
    
    def get_metrics_summary(self) -> str:
        """Tüm metriklerin özetini döndür"""
        if not self.metrics:
            return "📊 Metrikler devre dışı veya henüz kaydedilmedi."
        
        total_tasks = len(self.metrics)
        successful = sum(1 for m in self.metrics if m.success)
        failed = total_tasks - successful
        total_duration = sum(m.duration_seconds for m in self.metrics)
        total_cost = sum(m.estimated_cost for m in self.metrics)
        
        summary = f"""
╔══════════════════════════════════════════════════════════╗
║                  📊 METRİK ÖZETİ                          ║
╚══════════════════════════════════════════════════════════╝

📌 Toplam Görev: {total_tasks}
✅ Başarılı: {successful}
❌ Başarısız: {failed}
⏱️  Toplam Süre: {total_duration:.1f}s
💰 Toplam Maliyet: ${total_cost:.4f}
"""
        return summary
    
    def get_phase_timings(self) -> dict:
        """Get phase timing data for the current task."""
        return self.phase_timings.to_dict()
    
    def show_phase_timings(self) -> str:
        """Get a formatted phase timings report."""
        return self.phase_timings.summary()
    
    def _collect_raw_results(self) -> tuple:
        """Üretilen kod, test ve review'ları ham olarak döndür
        
        Returns:
            tuple: (code, tests, review) - Her biri string
        """
        code_content = ""
        test_content = ""
        review_content = ""
        
        if hasattr(self.team, 'env') and hasattr(self.team.env, 'roles'):
            for role in self.team.env.roles.values():
                # Adapter kullanarak güvenli erişim
                mem_store = MetaGPTAdapter.get_memory_store(role)
                if mem_store is None:
                    continue
                
                # Mesajları adapter üzerinden al
                messages = MetaGPTAdapter.get_messages(mem_store)
                
                # Her role için en son mesajı al (mesajlar zaman sırasına göre)
                for msg in messages:
                    # En son mesajları al (sonraki mesajlar öncekileri override eder)
                    if msg.role == "Engineer":
                        code_content = msg.content
                    elif msg.role == "Tester":
                        test_content = msg.content
                    elif msg.role == "Reviewer":
                        review_content = msg.content
        
        return code_content, test_content, review_content
    
    async def _emit_progress(self, agent_name: str, status: str, message: str):
        """Agent ilerleme durumunu callback'e bildir
        
        Args:
            agent_name: Agent adı (Mike, Alex, Bob, Charlie)
            status: Durum (working, completed, error)
            message: İlerleme mesajı
        """
        if hasattr(self, '_progress_callback') and self._progress_callback:
            try:
                # Callback async olabilir
                import asyncio
                if asyncio.iscoroutinefunction(self._progress_callback):
                    await self._progress_callback(agent_name, status, message)
                else:
                    self._progress_callback(agent_name, status, message)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
        
        # Console'a da yazdır
        status_emoji = "🔄" if status == "working" else "✅" if status == "completed" else "❌"
        print(f"{status_emoji} {agent_name}: {message}")
        logger.debug(f"Agent progress: {agent_name} - {status} - {message}")
    
    def _collect_results(self) -> str:
        """Üretilen kod, test ve review'ları topla ve kaydet"""
        code_content, test_content, review_content = self._collect_raw_results()
        
        # Sonuçları kaydet
        self._save_results(code_content, test_content, review_content)
        
        # Özet sonuç
        summary = f"""
╔══════════════════════════════════════════════════════════╗
║                    📊 SONUÇ ÖZETİ                         ║
╚══════════════════════════════════════════════════════════╝

💻 Alex (Engineer): {'✅ Kod yazıldı' if code_content else '❌ Kod yok'}
🧪 Bob (Tester): {'✅ Testler yazıldı' if test_content else '❌ Test yok'}
🔍 Charlie (Reviewer): {'✅ Review tamamlandı' if review_content else '❌ Review yok'}

📁 Dosyalar output/ dizinine kaydedildi.
"""
        return summary
    
    def _safe_write_file(self, path: str, content: str):
        """
        Dosyayı güvenli şekilde yaz:
        - Klasörü oluştur
        - Dosya zaten varsa .bak_yedek al
        - Sonra yeni içeriği yaz
        """
        import shutil
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        if os.path.exists(path):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{path}.bak_{ts}"
            shutil.copy2(path, backup_path)
            logger.info(f"🧯 Yedek alındı: {backup_path}")
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.info(f"💾 Dosya yazıldı: {path}")
    
    def _save_results(self, code: str, tests: str, review: str):
        """Üretilen kodu, testleri ve review'ı dosyalara kaydet - HTML/CSS/JS dahil"""
        # re ve datetime zaten en üstte import edilmiş
        
        # Output dizini oluştur
        if not self.output_dir_base:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"{self.output_dir_base}/mgx_team_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        saved_files = []
        
        # Kod dosyalarını kaydet - tüm dilleri destekle
        if code:
            # HTML dosyalarını çıkar ve kaydet
            html_blocks = re.findall(r'```html\s*(.*?)\s*```', code, re.DOTALL | re.IGNORECASE)
            for i, block in enumerate(html_blocks):
                if block.strip():
                    filename = "index.html" if i == 0 else f"page_{i}.html"
                    html_path = f"{output_dir}/{filename}"
                    self._safe_write_file(html_path, block.strip())
                    saved_files.append(filename)
            
            # CSS dosyalarını çıkar ve kaydet
            css_blocks = re.findall(r'```css\s*(.*?)\s*```', code, re.DOTALL | re.IGNORECASE)
            for i, block in enumerate(css_blocks):
                if block.strip():
                    filename = "style.css" if i == 0 else f"style_{i}.css"
                    css_path = f"{output_dir}/{filename}"
                    self._safe_write_file(css_path, block.strip())
                    saved_files.append(filename)
            
            # JavaScript dosyalarını çıkar ve kaydet
            js_blocks = re.findall(r'```(?:javascript|js)\s*(.*?)\s*```', code, re.DOTALL | re.IGNORECASE)
            for i, block in enumerate(js_blocks):
                if block.strip():
                    filename = "script.js" if i == 0 else f"script_{i}.js"
                    js_path = f"{output_dir}/{filename}"
                    self._safe_write_file(js_path, block.strip())
                    saved_files.append(filename)
            
            # PHP dosyalarını çıkar ve kaydet
            php_blocks = re.findall(r'```php\s*(.*?)\s*```', code, re.DOTALL | re.IGNORECASE)
            for i, block in enumerate(php_blocks):
                if block.strip():
                    filename = "index.php" if i == 0 else f"page_{i}.php"
                    php_path = f"{output_dir}/{filename}"
                    self._safe_write_file(php_path, block.strip())
                    saved_files.append(filename)
            
            # Python kod bloklarını çıkar (farklı formatları destekle)
            python_blocks = re.findall(r'```python\s*(.*?)\s*```', code, re.DOTALL | re.IGNORECASE)
            # Eğer spesifik dil belirtilmemiş bloklar varsa onları da al
            generic_blocks = re.findall(r'```\s*\n(.*?)\s*```', code, re.DOTALL)
            
            all_python_blocks = python_blocks + [b for b in generic_blocks if 'def ' in b or 'import ' in b or 'class ' in b]
            
            if all_python_blocks:
                main_py_path = f"{output_dir}/main.py"
                main_py_content = "# MGX Style Team tarafından üretildi\n"
                main_py_content += f"# Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                
                for block in all_python_blocks:
                    if block.strip():
                        main_py_content += block.strip() + "\n\n"
                
                self._safe_write_file(main_py_path, main_py_content)
                saved_files.append("main.py")
            elif not html_blocks and not css_blocks and not js_blocks and not php_blocks:
                # Hiçbir kod bloğu bulunamazsa ham içeriği Python olarak kaydet
                main_py_path = f"{output_dir}/main.py"
                main_py_content = "# MGX Style Team tarafından üretildi\n"
                main_py_content += f"# Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                main_py_content += code
                self._safe_write_file(main_py_path, main_py_content)
                saved_files.append("main.py")
        
        # Test dosyasını kaydet
        if tests:
            test_blocks = re.findall(r'```(?:python)?\s*(.*?)\s*```', tests, re.DOTALL)
            
            test_py_path = f"{output_dir}/test_main.py"
            test_py_content = "# MGX Style Team tarafından üretildi - TEST DOSYASI\n"
            test_py_content += f"# Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            if test_blocks:
                for block in test_blocks:
                    if block.strip():
                        test_py_content += block.strip() + "\n\n"
            else:
                test_py_content += tests
            
            self._safe_write_file(test_py_path, test_py_content)
            saved_files.append("test_main.py")
        
        # Review dosyasını kaydet
        if review:
            review_path = f"{output_dir}/review.md"
            review_content = "# Kod İnceleme Raporu\n\n"
            review_content += f"**Tarih:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            review_content += review
            
            self._safe_write_file(review_path, review_content)
            saved_files.append("review.md")
        
        logger.info(f"📁 Tüm dosyalar kaydedildi ({len(saved_files)} dosya): {output_dir}/")
    
    def get_progress(self) -> str:
        """İlerleme durumunu al"""
        if not self.progress:
            return "📊 Henüz ilerleme kaydedilmedi."
        
        return "\n".join([f"✅ {p}" for p in self.progress])
    
    # ============================================
    # INCREMENTAL DEVELOPMENT - Artımlı Geliştirme
    # ============================================
    
    async def run_incremental(self, requirement: str, project_path: str = None, 
                               fix_bug: bool = False, ask_confirmation: bool = True) -> str:
        """
        Mevcut projeye yeni özellik ekle veya bug düzelt
        
        Args:
            requirement: Yeni gereksinim veya bug açıklaması
            project_path: Mevcut proje yolu (None ise yeni proje)
            fix_bug: True ise bug düzeltme modu
            ask_confirmation: True ise plan onayı için kullanıcıdan input bekler
                             False ise sessiz modda otomatik onaylar (non-interactive)
        
        Returns:
            Sonuç özeti
        """
        
        mode = "🐛 BUG DÜZELTME" if fix_bug else "➕ YENİ ÖZELLİK"
        
        # Kullanıcıya görünen bilgi incremental_main fonksiyonunda print ile basılıyor
        logger.debug(f"{mode} modu başlatılıyor")
        
        if project_path:
            logger.debug(f"Proje yolu: {project_path}")
            
            # Proje yapısını kontrol et
            if os.path.exists(project_path):
                docs_path = os.path.join(project_path, "docs")
                src_path = os.path.join(project_path, "src")
                
                # Mevcut dosyaları oku
                existing_files = []
                if os.path.exists(src_path):
                    for f in os.listdir(src_path):
                        if f.endswith('.py'):
                            existing_files.append(f)
                
                logger.info(f"📄 Mevcut dosyalar: {existing_files}")
                
                # Mevcut kodu hafızaya ekle
                self.add_to_memory("System", "ProjectContext", f"Proje: {project_path}, Dosyalar: {existing_files}")
        
        # Analiz et
        logger.info(f"\n📨 İstek: {requirement}")
        
        if fix_bug:
            # Bug düzeltme analizi
            analysis_prompt = f"""[INCREMENTAL - BUG DÜZELTME]

Hata: {requirement}

Lütfen:
1. Hatanın olası nedenini belirle
2. Düzeltme planı oluştur
3. Etkilenecek dosyaları listele
"""
        else:
            # Yeni özellik analizi
            analysis_prompt = f"""[INCREMENTAL - YENİ ÖZELLİK]

İstek: {requirement}

Lütfen:
1. Özelliğin karmaşıklığını değerlendir (XS/S/M/L/XL)
2. Mevcut koda etkisini analiz et
3. Uygulama planı oluştur
"""
        
        # Mike'a analiz yaptır (analysis_prompt dahil)
        analysis = await self.analyze_and_plan(analysis_prompt)
        
        # Plan onayı
        print(f"\n{'='*50}")
        print(f"📋 {mode} PLANI:")
        print(f"{'='*50}")
        print(analysis)
        
        if ask_confirmation:
            # Interactive mod - kullanıcıdan onay bekle
            print(f"\n⚠️ Devam etmek için ENTER'a basın (iptal için 'q'):")
            user_input = input()
            if user_input.lower() == 'q':
                return "❌ İşlem iptal edildi."
        else:
            # Non-interactive / sessiz mod - otomatik onayla
            logger.info("🤖 Sessiz mod: Plan otomatik onaylandı")
        
        self.approve_plan()
        
        # Değişiklikleri uygula
        result = await self.execute(n_round=3)
        
        # Sonuç
        summary = f"""
        {'='*50}
        ✅ {mode} TAMAMLANDI!
        {'='*50}
        
        📝 İstek: {requirement}
        📁 Proje: {project_path or 'Yeni Proje'}
        
        📋 Yapılan Değişiklikler:
        {result[:500]}...
        
        💾 Hafıza güncellendi.
        """
        
        logger.info(summary)
        return summary
    
    async def add_feature(self, feature: str, project_path: str) -> str:
        """Mevcut projeye yeni özellik ekle"""
        return await self.run_incremental(feature, project_path, fix_bug=False)
    
    async def fix_bug(self, bug_description: str, project_path: str) -> str:
        """Mevcut projedeki bug'ı düzelt"""
        return await self.run_incremental(bug_description, project_path, fix_bug=True)
    
    def list_project_files(self, project_path: str) -> list:
        """Proje dosyalarını listele"""
        
        files = []
        for root, dirs, filenames in os.walk(project_path):
            # .git ve __pycache__ gibi klasörleri atla
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', '.venv']]
            
            for f in filenames:
                if f.endswith(('.py', '.js', '.ts', '.html', '.css', '.json', '.yaml', '.yml')):
                    rel_path = os.path.relpath(os.path.join(root, f), project_path)
                    files.append(rel_path)
        
        return files
    
    def get_project_summary(self, project_path: str) -> str:
        """Proje özetini al"""
        
        files = self.list_project_files(project_path)
        
        summary = f"""
        📁 PROJE ÖZETİ: {project_path}
        {'='*40}
        
        📄 Dosya Sayısı: {len(files)}
        
        📂 Dosyalar:
        """
        
        for f in files[:20]:  # İlk 20 dosya
            summary += f"\n        - {f}"
        
        if len(files) > 20:
            summary += f"\n        ... ve {len(files) - 20} dosya daha"
        
        return summary


# ============================================
# KULLANIM ÖRNEĞİ
# ============================================
async def main(human_reviewer: bool = False, custom_task: str = None):
    """
    MGX tarzı takım örneği
    
    Args:
        human_reviewer: True ise Charlie (Reviewer) insan olarak çalışır
        custom_task: Özel görev tanımı (None ise varsayılan görev)
    """
    
    mode_text = "🧑 İNSAN MODU" if human_reviewer else "🤖 LLM MODU"
    
    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║           MGX STYLE MULTI-AGENT TEAM                     ║
    ║                                                          ║
    ║  👤 Mike (Team Leader) - Görev analizi ve planlama       ║
    ║  👤 Alex (Engineer) - Kod yazma                          ║
    ║  👤 Bob (Tester) - Test yazma                            ║
    ║  👤 Charlie (Reviewer) - Kod inceleme [{mode_text}]      ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Takımı oluştur (human_reviewer=True yaparak insan olarak katılabilirsin)
    mgx_team = MGXStyleTeam(human_reviewer=human_reviewer)
    
    # Görev tanımla (varsayılan veya özel)
    task = custom_task or "Listedeki sayıların çarpımını hesaplayan bir Python fonksiyonu yaz"
    
    # 1. Analiz ve Plan (stream ile canlı gösterilir)
    print("\n📋 ADIM 1: Görev Analizi ve Plan Oluşturma")
    print("-" * 50)
    await mgx_team.analyze_and_plan(task)
    # Stream ile canlı gösterildi, tekrar print etmeye gerek yok
    
    # 2. Plan Onayı (gerçek uygulamada kullanıcıdan alınır)
    print("\n✅ ADIM 2: Plan Onayı")
    print("-" * 50)
    mgx_team.approve_plan()
    
    # 3. Görev Yürütme (her agent canlı çıktı verir)
    print("\n🚀 ADIM 3: Görev Yürütme")
    print("-" * 50)
    await mgx_team.execute()  # Karmaşıklığa göre otomatik ayarlanır
    # Agent'ların çıktıları stream ile canlı gösterildi
    
    # 4. Hafıza Günlüğü
    print("\n📋 ADIM 4: Hafıza Günlüğü")
    print("-" * 50)
    print(mgx_team.show_memory_log())
    
    # 5. İlerleme Durumu
    print("\n📊 ADIM 5: İlerleme Durumu")
    print("-" * 50)
    print(mgx_team.get_progress())
    
    print("\n" + "=" * 50)
    print("🎊 MGX Style Takım çalışması tamamlandı!")
    print("=" * 50)


def cli_main():
    """CLI entry point - parses arguments and runs appropriate mode."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="MGX Style Multi-Agent Team",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  # Normal mod (yeni görev)
  python mgx_style_team.py
  
  # İnsan reviewer modu
  python mgx_style_team.py --human
  
  # Yeni özellik ekle (mevcut projeye)
  python mgx_style_team.py --add-feature "Add login system" --project-path "./my_project"
  
  # Bug düzelt
  python mgx_style_team.py --fix-bug "TypeError: x is not defined" --project-path "./my_project"
  
  # Özel görev
  python mgx_style_team.py --task "Fibonacci hesaplayan fonksiyon yaz"
        """
    )
    
    parser.add_argument(
        "--human", 
        action="store_true", 
        help="Charlie (Reviewer) için insan modu aktif et"
    )
    
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Özel görev tanımı"
    )
    
    parser.add_argument(
        "--project-path",
        type=str,
        default=None,
        help="Mevcut proje yolu (incremental development için)"
    )
    
    parser.add_argument(
        "--add-feature",
        type=str,
        default=None,
        help="Mevcut projeye yeni özellik ekle"
    )
    
    parser.add_argument(
        "--fix-bug",
        type=str,
        default=None,
        help="Mevcut projedeki bug'ı düzelt"
    )
    
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Plan onayı bekleme (sessiz mod)"
    )
    
    args = parser.parse_args()
    
    # Incremental Development modları
    if args.add_feature:
        print("\n➕ YENİ ÖZELLİK EKLEME MODU")
        asyncio.run(incremental_main(args.add_feature, args.project_path, fix_bug=False, ask_confirmation=not args.no_confirm))
    
    elif args.fix_bug:
        print("\n🐛 BUG DÜZELTME MODU")
        asyncio.run(incremental_main(args.fix_bug, args.project_path, fix_bug=True, ask_confirmation=not args.no_confirm))
    
    # Normal mod
    else:
        if args.human:
            print("\n🧑 İNSAN MODU AKTİF: Charlie olarak siz review yapacaksınız!")
            print("   Sıra size geldiğinde terminal'den input beklenir.\n")
        
        if args.task:
            print(f"\n📝 ÖZEL GÖREV: {args.task}\n")
        
        asyncio.run(main(human_reviewer=args.human, custom_task=args.task))


async def incremental_main(requirement: str, project_path: str = None, fix_bug: bool = False, ask_confirmation: bool = True):
    """
    Artımlı geliştirme modu
    
    Args:
        requirement: Yeni gereksinim veya bug açıklaması
        project_path: Mevcut proje yolu
        fix_bug: True ise bug düzeltme modu
        ask_confirmation: True ise plan onayı bekle (sessiz mod için False)
    """
    mode = "🐛 BUG DÜZELTME" if fix_bug else "➕ YENİ ÖZELLİK"
    
    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║        MGX STYLE - INCREMENTAL DEVELOPMENT               ║
    ║                                                          ║
    ║  {mode:^52} ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    mgx_team = MGXStyleTeam(human_reviewer=False)
    
    if project_path:
        print(f"\n📁 Proje: {project_path}")
        print(mgx_team.get_project_summary(project_path))
    
    result = await mgx_team.run_incremental(requirement, project_path, fix_bug, ask_confirmation)
    print(result)


if __name__ == "__main__":
    cli_main()