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

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List
from enum import Enum

from pydantic import BaseModel, Field, validator
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from metagpt.actions import Action
from metagpt.logs import logger
from metagpt.roles import Role
from metagpt.schema import Message

# Import from mgx_agent package for modular structure
from mgx_agent.adapter import MetaGPTAdapter
from mgx_agent.actions import (
    AnalyzeTask,
    DraftPlan,
    WriteCode,
    WriteTest,
    ReviewCode,
    RunSandboxTests,
)
from mgx_agent.stack_specs import infer_stack_from_task
from mgx_agent.performance.async_tools import AsyncTimer, with_timeout


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
    redis_url: str = Field(
        default="",
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
            "error": self.error_message if self.error_message else None
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
# ROLE HELPER MİXİN & ROLES
# ============================================
class RelevantMemoryMixin:
    """Token kullanımını azaltmak için relevant memories helper'ı"""
    
    def get_relevant_memories(self, role_filter: list = None, limit: int = 5) -> list:
        """Sadece ilgili hafıza mesajlarını getir.
        RoleContext üzerinden çalışır.
        
        Args:
            role_filter: Sadece bu role'lerden gelen mesajları al (örn: ["Engineer", "Tester"])
            limit: Maksimum mesaj sayısı
        
        Returns:
            Son N adet ilgili mesaj
        """
        # Adapter kullanarak güvenli erişim
        mem_store = MetaGPTAdapter.get_memory_store(self)
        if mem_store is None:
            return []
        
        # Mesajları adapter üzerinden al
        memories = MetaGPTAdapter.get_messages(mem_store)
        
        # Role filtresi uygula
        if role_filter:
            memories = [m for m in memories if getattr(m, "role", None) in role_filter]
        
        # Son N mesajı döndür
        if len(memories) > limit:
            return memories[-limit:]
        return memories
    
    def get_last_by(self, role_name: str, action_cls) -> str:
        """Belirli role ve action'dan gelen son mesajı bul
        
        Args:
            role_name: Aranacak role adı (örn: "Engineer", "Tester")
            action_cls: Aranacak action sınıfı (örn: WriteCode, WriteTest)
        
        Returns:
            Bulunan mesaj içeriği veya boş string
        """
        messages = self.get_relevant_memories(role_filter=[role_name], limit=5)
        for msg in reversed(messages):
            # Hem class hem string karşılaştırması (cause_by class veya string olabilir)
            if msg.cause_by == action_cls or msg.cause_by == action_cls.__name__:
                return msg.content
        return ""


# ============================================
# ROLE'LAR (MGX Tarzı İsimlerle)
# ============================================
class Mike(Role):
    """Team Leader - Görev analizi ve plan oluşturma"""
    
    name: str = "Mike"
    profile: str = "TeamLeader"
    goal: str = "Görevi analiz et, plan oluştur ve takımı yönet"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([AnalyzeTask, DraftPlan])
        self._is_planning_phase = True  # Planning tamamlanınca False olacak
    
    def complete_planning(self):
        """Planning'i sonlandırır - execute sırasında tekrar çalışmasını önler"""
        self._is_planning_phase = False
        self._watch([])  # Artık hiçbir mesajı izleme
        logger.info(f"📌 {self.name} ({self.profile}): Planning tamamlandı, execution'a katılmıyor.")
    
    async def _act(self) -> Message:
        """Override _act - planning phase bittiyse hiçbir şey yapma"""
        if not self._is_planning_phase:
            # Planning tamamlandı, boş message dön
            return Message(content="", role=self.profile)
        
        # Normal action çalıştırma
        return await super()._act()
    
    async def _observe(self) -> int:
        """Override observe - planning phase bittiyse mesaj alma"""
        if not self._is_planning_phase:
            return 0  # Hiçbir mesaj almadı gibi davran
        return await super()._observe()
    
    async def analyze_task(self, task: str) -> Message:
        """Doğrudan görev analizi yap (cache destekli)."""

        team_ref = getattr(self, "_team_ref", None)

        async def _compute() -> Message:
            logger.info(f"🎯 {self.name} ({self.profile}): Görev analiz ediliyor...")

            analyze_action = AnalyzeTask()
            analyze_action.llm = self.llm
            analysis = await analyze_action.run(task)

            draft_action = DraftPlan()
            draft_action.llm = self.llm
            plan = await draft_action.run(task, analysis)

            m = re.search(r"KARMAŞIKLIK:\s*(XS|S|M|L|XL)", str(analysis).upper())
            complexity = m.group(1) if m else "XS"

            payload = {
                "task": task,
                "complexity": complexity,
                "plan": plan,
            }

            if team_ref is not None:
                team_ref.set_task_spec(
                    task=task,
                    complexity=complexity,
                    plan=plan,
                    is_revision=False,
                    review_notes="",
                )

            result = f"""---JSON_START---
{json.dumps(payload, ensure_ascii=False, indent=2)}
---JSON_END---

GÖREV: {task}
KARMAŞIKLIK: {complexity}
PLAN:
{plan}
"""

            return Message(content=result, role=self.profile, cause_by=AnalyzeTask)

        if team_ref is not None and hasattr(team_ref, "cached_llm_call"):
            message = await team_ref.cached_llm_call(
                role=self.profile,
                action="AnalyzeTask+DraftPlan",
                payload={"task": task},
                compute=_compute,
                encode=lambda msg: {"content": msg.content, "role": msg.role},
                decode=lambda data: Message(
                    content=str(data.get("content", "")),
                    role=str(data.get("role", self.profile)),
                    cause_by=AnalyzeTask,
                ),
            )
            # Ensure task spec is available for downstream roles on cache hits.
            try:
                team_ref._sync_task_spec_from_plan(message.content, fallback_task=task)
            except Exception:
                pass
            return message

        return await _compute()


class Alex(RelevantMemoryMixin, Role):
    """Engineer - Kod yazma"""
    
    name: str = "Alex"
    profile: str = "Engineer"
    goal: str = "Temiz ve çalışan kod yaz"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([WriteCode])
        self._watch([AnalyzeTask, DraftPlan])  # Mike'ın çıktılarını izle
    
    async def _act(self) -> Message:
        print(f"\n{'='*60}")
        print(f"💻 ALEX (Engineer) - KOD YAZIYOR...")
        print(f"{'='*60}")
        
        # ÖNCE: MGXStyleTeam'den task_spec'i al (tek kaynak - hafıza taraması yerine)
        # This avoids repeated memory scans - task spec is set once by Mike
        instruction = ""
        plan = ""
        complexity = "N/A"
        review_notes = ""  # Review notları (revision turunda)
        all_messages = []  # Fallback için hazır (edge-case önleme)
        
        spec = None
        if hasattr(self, "_team_ref") and self._team_ref:
            spec = self._team_ref.get_task_spec()
        
        if spec:
            # Task spec'ten direkt al (en güvenilir kaynak)
            instruction = spec.get("task", "")
            plan = spec.get("plan", "")
            complexity = spec.get("complexity", "N/A")
            review_notes = spec.get("review_notes", "")
            is_revision = spec.get("is_revision", False)
            print(f"📝 Görev: {instruction}")
            print(f"📊 Karmaşıklık: {complexity}")
            if is_revision:
                print(f"⚠️ Revision turu - Review notları: {review_notes[:100]}...")
        
        # FALLBACK: Eğer spec yoksa veya instruction boşsa hafıza taraması yap
        if not instruction:
            logger.debug("⚠️ Alex: Task spec bulunamadı veya boş, hafıza taraması yapılıyor...")
            
            # Sadece TeamLeader mesajlarını al (token tasarrufu)
            # 1. rc.news (yeni gelen mesajlar) - Adapter üzerinden
            all_messages.extend(MetaGPTAdapter.get_news(self))
            
            # 2. Relevant memories - sadece TeamLeader'dan, son 3 mesaj
            all_messages.extend(self.get_relevant_memories(role_filter=["TeamLeader"], limit=3))
            
            # JSON_START ve JSON_END arasındaki JSON'u bul
            for m in all_messages:
                content = m.content if hasattr(m, 'content') else str(m)
                
                # Gömülü JSON'u ara
                if "---JSON_START---" in content and "---JSON_END---" in content:
                    try:
                        json_str = content.split("---JSON_START---")[1].split("---JSON_END---")[0].strip()
                        data = json.loads(json_str)
                        if "task" in data and "plan" in data:
                            instruction = data["task"]
                            plan = data["plan"]
                            complexity = data.get("complexity", "N/A")
                            print(f"📝 Görev: {instruction}")
                            print(f"📊 Karmaşıklık: {complexity}")
                            break
                    except (json.JSONDecodeError, IndexError, ValueError):
                        pass
        
        # Fallback: JSON bulunamadıysa düz metin ara
        if not instruction:
            for m in all_messages:
                content = m.content if hasattr(m, 'content') else str(m)
                if "GÖREV:" in content or "PLAN:" in content:
                    instruction = content
                    plan = content
                    print(f"📝 Düz metin plan kullanılıyor...")
                    break
        
        # Revision turu kontrolü: İyileştirme mesajından görevi al
        if not instruction:
            for m in all_messages:
                content = m.content if hasattr(m, 'content') else str(m)
                # İyileştirme mesajında "YAPILMASI GEREKEN GÖREV" bölümünü ara
                if "YAPILMASI GEREKEN GÖREV" in content or "ASIL İŞ BU" in content:
                    # Görev satırını bul
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if "YAPILMASI GEREKEN GÖREV" in line or "ASIL İŞ BU" in line:
                            # Sonraki birkaç satırı kontrol et
                            for j in range(i+1, min(i+5, len(lines))):
                                task_line = lines[j].strip()
                                if task_line and not task_line.startswith('═') and not task_line.startswith('⚠'):
                                    instruction = task_line
                                    print(f"📝 İyileştirme mesajından görev alındı: {instruction[:50]}...")
                                    break
                            if instruction:
                                break
                    if instruction:
                        break
        
        if not instruction:
            print(f"⚠️ Plan bulunamadı, varsayılan context kullanılıyor...")
            instruction = "Verilen görevi tamamla"
        
        print(f"📝 Plan alındı, kod üretiliyor...")
        
        # Progress göster
        print_step_progress(1, 3, "LLM'e istek gönderiliyor...", role=self)
        
        team_ref = getattr(self, "_team_ref", None)

        async def _compute_code() -> str:
            write_action = WriteCode()
            write_action.llm = self.llm
            return await write_action.run(instruction=instruction, plan=plan, review_notes=review_notes)

        print_step_progress(2, 3, "Kod üretiliyor...", role=self)

        if team_ref is not None and hasattr(team_ref, "cached_llm_call"):
            code = await team_ref.cached_llm_call(
                role=self.profile,
                action="WriteCode",
                payload={
                    "instruction": instruction,
                    "plan": plan,
                    "review_notes": review_notes,
                },
                compute=_compute_code,
            )
        else:
            code = await _compute_code()
        
        print_step_progress(3, 3, "Kod hazır!", role=self)
        
        # Tamamlandı bildirimi
        print(f"\n{'─'*50}")
        print(f"✅ ALEX: Kod tamamlandı! ({len(code)} karakter)")
        print(f"{'─'*50}\n")
        
        # Hafızaya ekle (adapter üzerinden)
        msg = Message(content=code, role=self.profile, cause_by=WriteCode)
        mem_store = MetaGPTAdapter.get_memory_store(self)
        MetaGPTAdapter.add_message(mem_store, msg)
        
        return msg


class Bob(RelevantMemoryMixin, Role):
    """Tester - Test yazma"""
    
    name: str = "Bob"
    profile: str = "Tester"
    goal: str = "Kapsamlı testler yaz"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([WriteTest])
        self._watch([WriteCode])  # Alex'in kodunu izle
    
    async def _act(self) -> Message:
        print(f"\n{'='*60}")
        print(f"🧪 BOB (Tester) - TEST YAZIYOR...")
        print(f"{'='*60}")
        
        # Alex'in kodunu role + cause_by ile bul (string hack yerine)
        code = self.get_last_by("Engineer", WriteCode)
        
        if not code:
            # Fallback: sadece Engineer mesajlarından son 2'yi al
            memories = self.get_relevant_memories(role_filter=["Engineer"], limit=2)
            if memories:
                code = memories[-1].content
            else:
                code = "No code found"
        
        print(f"📝 Alex'in kodu alındı, testler yazılıyor...")
        
        # Progress göster
        print_step_progress(1, 3, "Kod analiz ediliyor...", role=self)
        
        team_ref = getattr(self, "_team_ref", None)

        async def _compute_tests() -> str:
            test_action = WriteTest()
            test_action.llm = self.llm
            return await test_action.run(code, k=3)

        print_step_progress(2, 3, "Testler üretiliyor...", role=self)

        if team_ref is not None and hasattr(team_ref, "cached_llm_call"):
            tests = await team_ref.cached_llm_call(
                role=self.profile,
                action="WriteTest",
                payload={
                    "code": code,
                    "k": 3,
                },
                compute=_compute_tests,
            )
        else:
            tests = await _compute_tests()
        
        print_step_progress(3, 3, "Testler hazır!", role=self)
        
        # Tamamlandı bildirimi
        print(f"\n{'─'*50}")
        print(f"✅ BOB: Testler tamamlandı! ({len(tests)} karakter)")
        print(f"{'─'*50}\n")
        
        # Hafızaya ekle (adapter üzerinden)
        msg = Message(content=tests, role=self.profile, cause_by=WriteTest)
        mem_store = MetaGPTAdapter.get_memory_store(self)
        MetaGPTAdapter.add_message(mem_store, msg)
        
        return msg


class Charlie(RelevantMemoryMixin, Role):
    """Reviewer - Kod inceleme (İnsan olarak da kullanılabilir)"""
    
    name: str = "Charlie"
    profile: str = "Reviewer"
    goal: str = "Kod kalitesini değerlendir"
    
    def __init__(self, is_human: bool = False, config=None, **kwargs):
        if config:
            kwargs['config'] = config
        super().__init__(**kwargs)
        self.set_actions([ReviewCode])
        self._watch([WriteTest])  # Bob'un testlerini izle
        
        # İnsan etkileşimi flag'i - Terminal input ile çalışıyor
        if is_human:
            self.is_human = True
            logger.info(f"👤 {self.name} ({self.profile}): İNSAN REVIEWER MODU AKTİF")
            logger.info(f"   Sıra size gelince terminal'den input beklenir (ENTER ile submit)")
    
    async def _act(self) -> Message:
        logger.info("🔍 CHARLIE: _act() çağrıldı - Review başlıyor...")
        print(f"\n{'='*60}")
        print(f"🔍 CHARLIE (Reviewer) - KOD İNCELİYOR...")
        print(f"{'='*60}")
        
        # Kod ve testleri role + cause_by ile bul (string hack yerine)
        code = self.get_last_by("Engineer", WriteCode)
        tests = self.get_last_by("Tester", WriteTest)
        
        # Fallback: sadece Engineer ve Tester mesajlarından son 2'yi al
        if not code or not tests:
            memories = self.get_relevant_memories(role_filter=["Engineer", "Tester"], limit=4)
            for m in memories:
                content = m.content
                if not code and m.role == "Engineer":
                    code = content
                elif not tests and m.role == "Tester":
                    tests = content
        
        print(f"📝 Kod ve testler alındı, inceleniyor...")
        
        # Human reviewer modu kontrolü
        if hasattr(self, 'is_human') and self.is_human:
            # İnsan modu - terminal'den input al
            print(f"\n{'='*60}")
            print(f"👤 CHARLIE (HUMAN REVIEWER) - SİZİN SIRA!")
            print(f"{'='*60}")
            print(f"\n📝 KOD:\n{code[:1000] if code else 'No code found'}...")
            if len(code) > 1000:
                print(f"\n... (toplam {len(code)} karakter)")
            print(f"\n🧪 TESTLER:\n{tests[:1000] if tests else 'No tests found'}...")
            if len(tests) > 1000:
                print(f"\n... (toplam {len(tests)} karakter)")
            print(f"\n{'─'*60}")
            print("\n⚠️ Review'ınızı yazın (bitirmek için boş satır + ENTER):")
            print("   Format: 'SONUÇ: [ONAYLANDI / DEĞİŞİKLİK GEREKLİ]' + yorumlarınız")
            print(f"{'─'*60}\n")
            
            lines = []
            while True:
                try:
                    line = input()
                    if not line:
                        break
                    lines.append(line)
                except (EOFError, KeyboardInterrupt):
                    print("\n⚠️ Input kesildi, varsayılan review kullanılıyor.")
                    break
            
            review = "\n".join(lines)
            
            if not review.strip():
                review = "SONUÇ: ONAYLANDI\n\nİnsan reviewer tarafından onaylandı (boş input)."
            elif "SONUÇ:" not in review.upper():
                # SONUÇ formatı yoksa ekle
                review = f"SONUÇ: ONAYLANDI\n\n{review}"
            
            print(f"\n✅ Human review alındı ({len(review)} karakter)")
        else:
            # LLM modu
            print_step_progress(1, 4, "Kod kalitesi kontrol ediliyor...", role=self)
            
            team_ref = getattr(self, "_team_ref", None)
            code_in = code if code else "No code found"
            tests_in = tests if tests else "No tests found"

            disable_sandbox = os.getenv("DISABLE_SANDBOX_TESTING", "").lower() in (
                "true",
                "1",
                "yes",
            )

            if not disable_sandbox:
                print_step_progress(2, 4, "Sandbox (DinD) testleri çalıştırılıyor...", role=self)
            else:
                print_step_progress(2, 4, "Test coverage değerlendiriliyor...", role=self)

            target_stack = None
            if team_ref is not None:
                spec = team_ref.get_task_spec()
                task_text = (spec or {}).get("task") or ""
                if task_text.strip():
                    target_stack = infer_stack_from_task(task_text)
            if not target_stack and code_in and code_in != "No code found":
                target_stack = infer_stack_from_task(code_in[:800])

            sandbox_report = ""
            if not disable_sandbox:
                try:
                    sandbox_action = RunSandboxTests()
                    sandbox_action.llm = self.llm
                    sandbox_report = await sandbox_action.run(code_in, target_stack)
                except Exception as e:
                    logger.warning(f"⚠️ Charlie sandbox: {e}")
                    sandbox_report = f"## Sandbox Test Sonuçları\n- **Durum:** Hata: `{e}`\n"

            async def _compute_review() -> str:
                review_action = ReviewCode()
                review_action.llm = self.llm
                return await review_action.run(
                    code_in,
                    tests_in,
                    target_stack,
                    sandbox_report=sandbox_report,
                )

            print_step_progress(3, 4, "Review raporu hazırlanıyor...", role=self)

            if team_ref is not None and hasattr(team_ref, "cached_llm_call"):
                # revision_round payload'a eklenir → her tur için cache key farklı olur
                # (cache hit'den eski review dönme sorununu önler)
                revision_round = getattr(team_ref, "_current_revision_round", 0)
                review = await team_ref.cached_llm_call(
                    role=self.profile,
                    action="ReviewCode",
                    payload={
                        "code": code_in,
                        "tests": tests_in,
                        "revision_round": revision_round,
                    },
                    compute=_compute_review,
                    bypass_cache=not disable_sandbox,
                )
            else:
                review = await _compute_review()
            
            print_step_progress(4, 4, "Review tamamlandı!", role=self)
        
        # Tamamlandı bildirimi
        print(f"\n{'─'*50}")
        print(f"✅ CHARLIE: Review tamamlandı! ({len(review)} karakter)")
        print(f"{'─'*50}\n")
        
        # Hafızaya ekle (adapter üzerinden)
        msg = Message(content=review, role=self.profile, cause_by=ReviewCode)
        mem_store = MetaGPTAdapter.get_memory_store(self)
        MetaGPTAdapter.add_message(mem_store, msg)
        
        logger.info(f"✅ CHARLIE: Review mesajı hafızaya eklendi ({len(review)} karakter)")
        
        return msg
    
    async def _observe(self) -> int:
        """Override observe - Charlie için debug log ekle"""
        result = await super()._observe()
        if result > 0:
            logger.info(f"🔍 CHARLIE: {result} yeni mesaj gözlemlendi")
        return result


# ============================================
# MGX TARZI TAKIM
# ============================================