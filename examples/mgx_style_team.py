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

import os
import sys

# Lokal geliştirme: examples klasöründen çalışırken metagpt paketini bul
CURRENT_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List
from enum import Enum

from pydantic import BaseModel, Field, field_validator, ConfigDict
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from metagpt.actions import Action
from metagpt.logs import logger
from metagpt.roles import Role
from metagpt.schema import Message
from metagpt.team import Team
from metagpt.context import Context
from metagpt.config2 import Config


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
    cache_ttl_seconds: int = Field(default=3600, ge=60, le=86400, description="Cache TTL (saniye)")
    
    @field_validator('max_rounds')
    @classmethod
    def validate_max_rounds(cls, v):
        if v < 1:
            raise ValueError("max_rounds en az 1 olmalı")
        return v
    
    @field_validator('default_investment')
    @classmethod
    def validate_investment(cls, v):
        if v < 0.5:
            raise ValueError("investment en az $0.5 olmalı")
        return v
    
    @field_validator('budget_multiplier')
    @classmethod
    def validate_budget_multiplier(cls, v):
        if v <= 0:
            raise ValueError("budget_multiplier 0'dan büyük olmalı")
        if v > 10:
            logger.warning(f"⚠️ budget_multiplier çok yüksek: {v}x - Maliyet patlaması riski!")
        return v
    
    # ✅ Pydantic v2 syntax
    model_config = ConfigDict(use_enum_values=True)
    
    def to_dict(self) -> dict:
        """Config'i dict olarak döndür"""
        return self.model_dump()
    
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


class AnalyzeTask(Action):
    """Görevi analiz et"""
    
    PROMPT_TEMPLATE: str = """Görev: {task}

SADECE karmaşıklık seviyesini yaz:
- XS: Tek fonksiyon
- S: Birkaç fonksiyon  
- M: Modül düzeyinde
- L: Çoklu modül
- XL: Sistem düzeyinde

Yanıt formatı (SADECE bu kadar yaz):
KARMAŞIKLIK: [seviye]"""
    
    name: str = "AnalyzeTask"
    
    @llm_retry()
    async def run(self, task: str) -> str:
        try:
            prompt = self.PROMPT_TEMPLATE.format(task=task)
            rsp = await self._aask(prompt)
            return rsp
        except Exception as e:
            logger.error(f"❌ AnalyzeTask hatası: {e}")
            raise


class DraftPlan(Action):
    """Plan taslağı oluştur"""
    
    PROMPT_TEMPLATE: str = """Görev: {task}

Kısa ve öz plan yaz. SADECE şu formatı kullan:

1. Kod yaz - Alex (Engineer)
2. Test yaz - Bob (Tester)  
3. Review yap - Charlie (Reviewer)

Açıklama veya detay YAZMA. SADECE numaralı listeyi yaz."""
    
    name: str = "DraftPlan"
    
    @llm_retry()
    async def run(self, task: str, analysis: str) -> str:
        try:
            prompt = self.PROMPT_TEMPLATE.format(task=task)
            rsp = await self._aask(prompt)
            return rsp
        except Exception as e:
            logger.error(f"❌ DraftPlan hatası: {e}")
            raise


class WriteCode(Action):
    """Kod yaz"""
    
    PROMPT_TEMPLATE: str = """
Görev: {instruction}
Plan: {plan}

{review_section}

ADIM 1 - DÜŞÜN (YALNIZCA METİN):

- Bu görevi nasıl çözeceğini 3–7 madde halinde kısaca açıkla.
- Hangi fonksiyonları yazacağını ve hangi kütüphaneleri kullanacağını belirt.
- Edge case (uç durum) olarak neleri dikkate alacağını yaz.
- Bu düşünce kısmında HİÇBİR KOD yazma.

ADIM 2 - KODLA (SADECE AŞAĞIDAKİ BLOĞA KOD YAZ):

Aşağıdaki ```python``` bloğunda, yukarıdaki plana uygun ve edge case'leri de kapsayan
KESİN Python kodunu yaz.
Kodun temiz, okunabilir ve iyi yorumlanmış olsun.

{revision_instructions}

```python
# kodunuz buraya
```
"""
    
    name: str = "WriteCode"
    
    @llm_retry()
    async def run(self, instruction: str, plan: str = "", review_notes: str = "") -> str:
        try:
            # Review notları varsa ekle
            review_section = ""
            revision_instructions = ""
            if review_notes and review_notes.strip():
                review_section = f"""
Review Notları (İyileştirme Önerileri):
{review_notes}
"""
                revision_instructions = f"""
ÖNEMLİ: Bu bir düzeltme turu. Yukarıdaki review notlarını dikkate alarak mevcut kodu GÜNCELLE / İYİLEŞTİR.
Orijinal görevi unutma: {instruction}
"""
            
            prompt = self.PROMPT_TEMPLATE.format(
                instruction=instruction,
                plan=plan,
                review_section=review_section,
                revision_instructions=revision_instructions
            )
            rsp = await self._aask(prompt)
            return self._parse_code(rsp)
        except Exception as e:
            logger.error(f"❌ WriteCode hatası: {e}")
            raise
    
    @staticmethod
    def _parse_code(rsp: str) -> str:
        pattern = r"```python(.*)```"
        match = re.search(pattern, rsp, re.DOTALL)
        return match.group(1).strip() if match else rsp


class WriteTest(Action):
    """Test yaz"""
    
    PROMPT_TEMPLATE: str = """
    Kod:
    {code}
    
    ÖNEMLİ: Bu kod için pytest kullanarak TAM OLARAK {k} ADET unit test yaz.
    DAHA FAZLA YAZMA! Sadece {k} adet test yaz.
    
    Kurallar:
    1. TAM OLARAK {k} adet test yaz (daha fazla değil!)
    2. Her test farklı bir senaryoyu test etmeli:
       - Pozitif senaryo (normal kullanım)
       - Negatif senaryo (hata durumları)
       - Edge case (sınır değerleri)
    3. Aynı testi tekrar yazma - her test benzersiz olmalı
    4. Test isimleri açıklayıcı olsun
    
    Sadece {k} adet test yaz, daha fazla değil!
    
    ```python
    import pytest
    
    # Test 1: [açıklama]
    def test_1():
        # kod
    
    # Test 2: [açıklama]
    def test_2():
        # kod
    
    # Test {k}: [açıklama]
    def test_{k}():
        # kod
    ```
    
    UYARI: Sadece {k} adet test yaz, daha fazla yazma!
    """
    
    name: str = "WriteTest"
    
    @staticmethod
    def _parse_code(rsp: str) -> str:
        pattern = r"```python(.*)```"
        match = re.search(pattern, rsp, re.DOTALL)
        return match.group(1).strip() if match else rsp.strip()
    
    @staticmethod
    def _limit_tests(code: str, k: int) -> str:
        """
        Test kodundan sadece ilk k adet test fonksiyonunu al.
        LLM daha fazla test yazsa bile sadece k adet test döndürür.
        
        Args:
            code: Test kodu
            k: Maksimum test sayısı
            
        Returns:
            Sadece k adet test içeren kod
        """
        lines = code.splitlines()
        result = []
        test_count = 0
        in_test_function = False
        
        for i, line in enumerate(lines):
            # Test fonksiyonu başlangıcını tespit et
            if re.match(r'^\s*def\s+test_', line):
                if test_count >= k:
                    # K adet test bulundu, daha fazlasını alma
                    break
                test_count += 1
                in_test_function = True
                result.append(line)
            elif in_test_function:
                # Test fonksiyonu içindeyiz
                result.append(line)
                # Bir sonraki test fonksiyonu veya dosya sonu gelirse dur
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if re.match(r'^\s*def\s+test_', next_line):
                        # Bir sonraki test başlıyor, eğer k adet test bulunduysa dur
                        if test_count >= k:
                            break
            else:
                # Test fonksiyonu dışındayız (import, class tanımları vs.)
                result.append(line)
        
        # Eğer hiç test bulunamadıysa orijinal kodu döndür
        if test_count == 0:
            return code
        
        return "\n".join(result)
    
    @llm_retry()
    async def run(self, code: str, k: int = 3) -> str:
        try:
            prompt = self.PROMPT_TEMPLATE.format(code=code, k=k)
            rsp = await self._aask(prompt)
            raw_code = self._parse_code(rsp)
            # Post-process: Test sayısını k ile sınırla (LLM daha fazla yazsa bile)
            limited_code = self._limit_tests(raw_code, k)
            logger.debug(f"📊 WriteTest: {k} adet test sınırı uygulandı")
            return limited_code
        except Exception as e:
            logger.error(f"❌ WriteTest hatası: {e}")
            raise


class ReviewCode(Action):
    """Kodu incele ve geri bildirim ver"""
    
    PROMPT_TEMPLATE: str = """
    Kod:
    {code}
    
    Testler:
    {tests}
    
    Bu kodu ve testleri DİKKATLİCE incele:
    1. Kod kalitesi nasıl? Hata yönetimi var mı? Input validation var mı?
    2. Test coverage yeterli mi? Edge case'ler test edilmiş mi?
    3. Docstring'ler var mı? Kod dokümantasyonu yeterli mi?
    4. İyileştirme gereken noktalar var mı?
    
    ÖNEMLİ: Eğer kodda eksiklikler, hatalar veya iyileştirme gereken noktalar varsa MUTLAKA "DEĞİŞİKLİK GEREKLİ" yaz.
    Sadece kod mükemmel ve hiçbir sorun yoksa "ONAYLANDI" yaz.
    
    SONUÇ: [ONAYLANDI / DEĞİŞİKLİK GEREKLİ]
    
    YORUMLAR:
    - [yorum 1]
    - [yorum 2]
    - [yorum 3]
    """
    
    name: str = "ReviewCode"
    
    @llm_retry()
    async def run(self, code: str, tests: str) -> str:
        try:
            prompt = self.PROMPT_TEMPLATE.format(code=code, tests=tests)
            rsp = await self._aask(prompt)
            return rsp
        except Exception as e:
            logger.error(f"❌ ReviewCode hatası: {e}")
            raise


# ============================================
# METAGPT ADAPTER - İç Yapı Bağımlılığını Soyutlama
# ============================================
class MetaGPTAdapter:
    """
    MetaGPT'nin iç yapısına erişimi soyutlayan adapter sınıfı.
    
    Bu sınıf, MetaGPT'nin private değişkenlerine doğrudan erişimi engeller
    ve API değişikliklerine karşı koruma sağlar.
    
    MetaGPT güncellendiğinde sadece bu sınıfı güncellemek yeterli olacaktır.
    """
    
    @staticmethod
    def get_memory_store(role) -> object:
        """
        Role'dan memory store'u güvenli şekilde al.
        
        Args:
            role: MetaGPT Role instance
            
        Returns:
            Memory store object veya None
        """
        if not hasattr(role, "rc"):
            return None
        if not hasattr(role.rc, "memory"):
            return None
        return role.rc.memory
    
    @staticmethod
    def get_messages(mem_store) -> list:
        """
        Memory store'dan mesajları güvenli şekilde al.
        
        Args:
            mem_store: Memory store object
            
        Returns:
            Mesaj listesi (boş liste değil, her zaman list)
        """
        if mem_store is None:
            return []
        
        # MetaGPT API'sine göre güvenli erişim
        if hasattr(mem_store, "get"):
            # Standart API: memory.get() -> list[Message]
            try:
                return list(mem_store.get())
            except Exception:
                return []
        elif hasattr(mem_store, "__iter__"):
            # Fallback: iterable olarak kullan
            try:
                return list(mem_store)
            except Exception:
                return []
        else:
            # Son çare: storage attribute'una eriş (eğer varsa)
            if hasattr(mem_store, "storage"):
                return list(mem_store.storage) if mem_store.storage else []
            return []
    
    @staticmethod
    def add_message(mem_store, message) -> bool:
        """
        Memory store'a mesaj ekle.
        
        Args:
            mem_store: Memory store object
            message: Message instance
            
        Returns:
            True if successful, False otherwise
        """
        if mem_store is None:
            return False
        
        try:
            if hasattr(mem_store, "add"):
                mem_store.add(message)
                return True
            else:
                # Fallback: storage'a doğrudan ekle (eğer varsa)
                if hasattr(mem_store, "storage"):
                    if message not in mem_store.storage:
                        mem_store.storage.append(message)
                    return True
                return False
        except Exception as e:
            logger.warning(f"⚠️ Mesaj eklenirken hata: {e}")
            return False
    
    @staticmethod
    def clear_memory(mem_store, keep_last_n: int) -> bool:
        """
        Memory store'u temizle, son N mesajı tut.
        
        Args:
            mem_store: Memory store object
            keep_last_n: Tutulacak mesaj sayısı
            
        Returns:
            True if successful, False otherwise
        """
        if mem_store is None:
            return False
        
        try:
            # Mevcut mesajları al
            messages = MetaGPTAdapter.get_messages(mem_store)
            
            if len(messages) <= keep_last_n:
                # Zaten limit içinde, temizlik gerekmiyor
                return True
            
            # Son N mesajı tut
            messages_to_keep = messages[-keep_last_n:]
            
            # Temizleme stratejileri (öncelik sırasına göre)
            
            # Strateji 1: clear() + add() API'si varsa
            if hasattr(mem_store, "clear") and hasattr(mem_store, "add"):
                mem_store.clear()
                for msg in messages_to_keep:
                    mem_store.add(msg)
                return True
            
            # Strateji 2: storage attribute'una erişim varsa
            if hasattr(mem_store, "storage"):
                mem_store.storage = messages_to_keep
                # Index'i de güncelle (eğer varsa)
                # NOT: Bu adapter katmanı - MetaGPT storage/index yapısı değişirse bu kısım kırılabilir
                # Ancak adapter pattern'in amacı budur: Bu katman kırılırsa diğer logic sağlam kalır
                if hasattr(mem_store, "index"):
                    # Index'i sıfırla ve yeniden oluştur
                    mem_store.index.clear()
                    for msg in messages_to_keep:
                        if hasattr(msg, "cause_by") and msg.cause_by:
                            cause_by_key = str(msg.cause_by) if not isinstance(msg.cause_by, str) else msg.cause_by
                            if cause_by_key not in mem_store.index:
                                mem_store.index[cause_by_key] = []
                            mem_store.index[cause_by_key].append(msg)
                return True
            
            # Strateji 3: _memory private attribute (son çare - riskli ama gerekli)
            if hasattr(mem_store, "_memory"):
                mem_store._memory = messages_to_keep
                logger.warning("⚠️ _memory private attribute kullanıldı - MetaGPT güncellemesinde kırılabilir!")
                return True
            
            # Hiçbir strateji çalışmadı
            logger.warning("⚠️ Memory temizliği yapılamadı - uygun API bulunamadı")
            return False
            
        except Exception as e:
            logger.error(f"❌ Memory temizliği hatası: {e}")
            return False
    
    @staticmethod
    def get_messages_by_role(mem_store, role_name: str) -> list:
        """
        Belirli role'den gelen mesajları getir.
        
        Args:
            mem_store: Memory store object
            role_name: Role adı (örn: "Engineer", "Tester")
            
        Returns:
            Mesaj listesi
        """
        if mem_store is None:
            return []
        
        try:
            # Strateji 1: get_by_role() API'si varsa
            if hasattr(mem_store, "get_by_role"):
                return list(mem_store.get_by_role(role_name))
            
            # Strateji 2: Manuel filtreleme
            all_messages = MetaGPTAdapter.get_messages(mem_store)
            return [msg for msg in all_messages if hasattr(msg, "role") and msg.role == role_name]
            
        except Exception as e:
            logger.warning(f"⚠️ Role mesajları alınırken hata: {e}")
            return []
    
    @staticmethod
    def get_news(role) -> list:
        """
        Role'un yeni mesajlarını (rc.news) güvenli şekilde al.
        
        Args:
            role: MetaGPT Role instance
            
        Returns:
            Yeni mesaj listesi (boş liste değil, her zaman list)
        """
        if not hasattr(role, "rc"):
            return []
        if not hasattr(role.rc, "news"):
            return []
        
        try:
            news = role.rc.news
            if news is None:
                return []
            # news bir liste olabilir veya başka bir iterable
            return list(news) if hasattr(news, "__iter__") else []
        except Exception as e:
            logger.warning(f"⚠️ News alınırken hata: {e}")
            return []


# ============================================
# ROLE HELPER MİXİN - Token Tasarrufu
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
        self._analysis_cache = {}  # Tekrar eden görevler için cache
    
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
        """Doğrudan görev analizi yap (cache destekli)"""
        
        # Cache key oluştur
        task_hash = hashlib.md5(task.encode()).hexdigest()
        
        # Cache'de var mı kontrol et (TTL ile)
        if task_hash in self._analysis_cache:
            cached = self._analysis_cache[task_hash]
            
            # TTL kontrolü
            cache_age = time.time() - cached['timestamp']
            cache_ttl = 3600  # Varsayılan 1 saat
            
            # Config'den TTL al (varsa - environment'tan veya role config'inden)
            if hasattr(self, 'config') and hasattr(self.config, 'cache_ttl_seconds'):
                cache_ttl = self.config.cache_ttl_seconds
            elif hasattr(self, 'env') and hasattr(self.env, 'config'):
                # Environment config'inden al
                env_config = getattr(self.env, 'config', None)
                if env_config and hasattr(env_config, 'cache_ttl_seconds'):
                    cache_ttl = env_config.cache_ttl_seconds
            
            if cache_age < cache_ttl:
                logger.info(f"⚡ {self.name}: Cache hit (age: {cache_age:.0f}s, TTL: {cache_ttl}s)")
                print(f"\n{'─'*50}")
                print(f"⚡ MIKE: Analiz CACHE'den yüklendi! (Hız kazancı)")
                print(f"📊 Karmaşıklık: {cached['complexity']}")
                print(f"{'─'*50}")
                print(f"\n⚠️ Plan onayınızı bekliyorum. Onaylamak için 'ONAY' yazın.\n")
                return cached['message']
            else:
                logger.info(f"⏰ {self.name}: Cache expired (age: {cache_age:.0f}s > TTL: {cache_ttl}s)")
                del self._analysis_cache[task_hash]
        
        logger.info(f"🎯 {self.name} ({self.profile}): Görev analiz ediliyor...")
        
        # Görevi analiz et (stream=False ile tekrarı önle)
        analyze_action = AnalyzeTask()
        analyze_action.llm = self.llm
        analysis = await analyze_action.run(task)
        
        # Plan taslağı oluştur
        draft_action = DraftPlan()
        draft_action.llm = self.llm
        plan = await draft_action.run(task, analysis)
        
        # Karmaşıklık seviyesini regex ile çıkar
        m = re.search(r"KARMAŞIKLIK:\s*(XS|S|M|L|XL)", analysis.upper())
        complexity = m.group(1) if m else "XS"
        
        # Özet çıktı (plan zaten stream ile gösterildi)
        print(f"\n{'─'*50}")
        print(f"✅ MIKE: Analiz ve plan tamamlandı!")
        print(f"📊 Karmaşıklık: {complexity}")
        print(f"{'─'*50}")
        print(f"\n⚠️ Plan onayınızı bekliyorum. Onaylamak için 'ONAY' yazın.\n")
        
        # JSON + düz metin formatı (Alex her iki formatta da okuyabilir)
        payload = {
            "task": task,
            "complexity": complexity,
            "plan": plan,
        }
        
        # MGXStyleTeam'e task_spec'i set et (tek kaynak - hafıza taraması yerine)
        if hasattr(self, "_team_ref") and self._team_ref:
            self._team_ref.set_task_spec(
                task=task,
                complexity=complexity,
                plan=plan,
                is_revision=False,
                review_notes=""
            )
            logger.debug(f"📋 Mike: Task spec MGXStyleTeam'e set edildi")
        
        # JSON'u metin içine göm - kolayca parse edilebilir
        result = f"""---JSON_START---
{json.dumps(payload, ensure_ascii=False, indent=2)}
---JSON_END---

GÖREV: {task}
KARMAŞIKLIK: {complexity}
PLAN:
{plan}
"""
        
        message = Message(content=result, role=self.profile, cause_by=AnalyzeTask)
        
        # Cache'e kaydet
        self._analysis_cache[task_hash] = {
            'message': message,
            'complexity': complexity,
            'plan': plan,
            'timestamp': time.time()
        }
        logger.info(f"💾 {self.name}: Analiz cache'e kaydedildi (hash: {task_hash[:8]}...)")
        
        return message


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
        
        # Kod yaz (instruction ve plan ayrı ayrı)
        write_action = WriteCode()
        write_action.llm = self.llm
        
        print_step_progress(2, 3, "Kod üretiliyor...", role=self)
        # Review notlarını da gönder (revision turunda - zaten yukarıda set edildi)
        code = await write_action.run(instruction=instruction, plan=plan, review_notes=review_notes)
        
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
        
        # Testleri yaz
        test_action = WriteTest()
        test_action.llm = self.llm
        
        print_step_progress(2, 3, "Testler üretiliyor...", role=self)
        # Test sayısını sınırla (3-5 arası, çok fazla test yazılmasını önle)
        tests = await test_action.run(code, k=3)
        
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
        
        # İnsan etkileşimi flag'i (TODO: Gerçek human-in-the-loop henüz implement edilmedi)
        if is_human:
            self.is_human = True
            logger.info(f"👤 {self.name} ({self.profile}): HUMAN FLAG SET - Şu an LLM kullanıyor (ileride terminal input eklenecek)")
    
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
            print_step_progress(2, 4, "Test coverage değerlendiriliyor...", role=self)
            
            # Review yap
            review_action = ReviewCode()
            review_action.llm = self.llm
            
            print_step_progress(3, 4, "Review raporu hazırlanıyor...", role=self)
            review = await review_action.run(code if code else "No code found", tests if tests else "No tests found")
            
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
class MGXStyleTeam:
    """MGX tarzı takım yöneticisi"""
    
    def __init__(self, config: TeamConfig = None, human_reviewer: bool = False, max_memory_size: int = 50):
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
        self.context = Context()
        self.team = Team(context=self.context)
        self.plan_approved = False
        self.current_task = None
        self.current_task_spec = None  # Tek kaynak: task, plan, complexity bilgisi
        self.progress = []
        self.memory_log = []  # Hafıza günlüğü
        self.max_memory_size = config.max_memory_size
        self.human_mode = config.human_reviewer
        self.metrics: List[TaskMetrics] = [] if config.enable_metrics else None
        
        # Her role için farklı LLM config'leri yükle
        if config.use_multi_llm:
            try:
                mike_config = Config.from_home("mike_llm.yaml")
                alex_config = Config.from_home("alex_llm.yaml")
                bob_config = Config.from_home("bob_llm.yaml")
                charlie_config = Config.from_home("charlie_llm.yaml")
                self.multi_llm_mode = True
                logger.info("🎯 Multi-LLM modu aktif - Her role farklı model kullanacak!")
            except Exception as e:
                mike_config = alex_config = bob_config = charlie_config = None
                self.multi_llm_mode = False
                logger.info("📦 Tek LLM modu - Tüm roller aynı modeli kullanacak")
        else:
            mike_config = alex_config = bob_config = charlie_config = None
            self.multi_llm_mode = False
            logger.info("📦 Tek LLM modu - Tüm roller aynı modeli kullanacak")
        
        # Takımı oluştur (her role farklı config ile)
        roles_list = [
            Mike(config=mike_config) if mike_config else Mike(),
            Alex(config=alex_config) if alex_config else Alex(),
            Bob(config=bob_config) if bob_config else Bob(),
            Charlie(is_human=config.human_reviewer, config=charlie_config) if charlie_config else Charlie(is_human=config.human_reviewer)
        ]
        
        # Role'lara team referansı ekle (progress bar için)
        for role in roles_list:
            role._team_ref = self
        
        self.team.hire(roles_list)
        
        # Role referanslarını sakla (team.env.roles erişimini azaltmak için)
        self._mike = roles_list[0]  # Mike
        self._alex = roles_list[1]   # Alex
        self._bob = roles_list[2]    # Bob
        self._charlie = roles_list[3]  # Charlie
        
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
    
    async def analyze_and_plan(self, task: str) -> str:
        """Görevi analiz et ve plan oluştur"""
        self.current_task = task
        
        # Kullanıcıya görünen bilgi main() fonksiyonunda print ile basılıyor
        logger.debug(f"Yeni görev analiz ediliyor: {task}")
        
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
        
        # Mike analiz etsin
        analysis = await mike.analyze_task(task)
        
        # ÖNEMLİ: Plan mesajını team environment'a publish et
        # Bu sayede Alex (Engineer) plan mesajını alacak
        self.last_plan = analysis
        
        # Hafızaya ekle
        self.add_to_memory("Mike", "AnalyzeTask + DraftPlan", analysis.content)
        
        # Auto approve kontrolü
        if self.config.auto_approve_plan:
            self._log("🤖 Auto-approve aktif, plan otomatik onaylandı", "info")
            self.approve_plan()
        
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
    
    async def execute(self, n_round: int = None, max_revision_rounds: int = None) -> str:
        """Görevi çalıştır
        
        Args:
            n_round: Her tur için maksimum round sayısı (None ise config'den alınır)
            max_revision_rounds: Review sonrası maksimum düzeltme turu (None ise config'den alınır)
        """
        if not self.plan_approved and not self.config.auto_approve_plan:
            return "❌ Plan henüz onaylanmadı! Önce plan onaylamalısınız."
        
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
        
        # n_round parametresi verilmemişse budget'tan al
        if n_round is None:
            n_round = budget["n_round"]
        
        # Kullanıcıya görünen bilgi print ile (logger.debug arka planda log dosyasına gider)
        print_phase_header("Görev Yürütme", "🚀")
        print(f"📊 Karmaşıklık: {complexity} → Investment: ${budget['investment']}, Rounds: {n_round}")
        logger.debug(f"Görev yürütme başlıyor - Karmaşıklık: {complexity}, Investment: ${budget['investment']}, Rounds: {n_round}")
        
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
            
            await self.team.run(n_round=n_round)
            
            # Charlie'nin çalışması için ek bir round (MetaGPT'nin normal akışı)
            # Manuel tetikleme hacklerini kaldırdık - sadece team.run() kullanıyoruz
            logger.debug("🔍 Charlie'nin review yapması için ek round çalıştırılıyor...")
            await self.team.run(n_round=1)  # Charlie'nin Bob'un mesajını gözlemlemesi ve review yapması için
            
            # Tur sonrası hafıza temizliği
            self.cleanup_memory()
        
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
                    
                    # Tekrar çalıştır
                    await self.team.run(n_round=n_round)
                    
                    # Charlie'nin revision turunda da review yapması için ek round
                    # Manuel tetikleme hacklerini kaldırdık - sadece team.run() kullanıyoruz
                    logger.debug("🔍 Charlie'nin revision review yapması için ek round çalıştırılıyor...")
                    await self.team.run(n_round=1)  # Charlie'nin Bob'un mesajını gözlemlemesi ve review yapması için
                    
                    # Her tur sonrası hafıza temizliği
                    self.cleanup_memory()
                else:
                    # Review OK - döngüden çık
                    print(f"\n✅ Review ONAYLANDI - Düzeltme gerekmiyor.")
                    break
            
            # Metrics güncelle - başarılı
            metric.revision_rounds = revision_count
            metric.success = True
            
            # Gerçek token kullanımını hesapla
            metric.token_usage = self._calculate_token_usage()
            metric.estimated_cost = budget["investment"]
            
            # Final sonuçları topla ve kaydet
            results = self._collect_results()
            
            # Final hafıza temizliği
            self.cleanup_memory()
            
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
        if metric.error_message:
            print(f"⚠️  Hata: {metric.error_message}")
        print(f"{'='*60}\n")
    
    def get_all_metrics(self) -> List[dict]:
        """Tüm görev metriklerini döndür"""
        if not self.metrics:
            return []
        return [m.to_dict() for m in self.metrics]
    
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
        import os
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
        """Üretilen kodu, testleri ve review'ı dosyalara kaydet"""
        import os
        # re ve datetime zaten en üstte import edilmiş
        
        # Output dizini oluştur
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"output/mgx_team_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Kod dosyasını kaydet
        if code:
            # Python kod bloklarını çıkar (farklı formatları destekle)
            code_blocks = re.findall(r'```(?:python)?\s*(.*?)\s*```', code, re.DOTALL)
            
            main_py_path = f"{output_dir}/main.py"
            main_py_content = "# MGX Style Team tarafından üretildi\n"
            main_py_content += f"# Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            if code_blocks:
                for block in code_blocks:
                    # Boş blokları atla
                    if block.strip():
                        main_py_content += block.strip() + "\n\n"
            else:
                # Kod bloğu bulunamazsa ham içeriği kaydet
                main_py_content += code
            
            # Güvenli yaz (varsa .bak al)
            self._safe_write_file(main_py_path, main_py_content)
        
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
            
            # Güvenli yaz (varsa .bak al)
            self._safe_write_file(test_py_path, test_py_content)
        
        # Review dosyasını kaydet
        if review:
            review_path = f"{output_dir}/review.md"
            review_content = "# Kod İnceleme Raporu\n\n"
            review_content += f"**Tarih:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            review_content += review
            
            # Güvenli yaz (varsa .bak al)
            self._safe_write_file(review_path, review_content)
        
        logger.info(f"📁 Tüm dosyalar kaydedildi: {output_dir}/")
    
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
        import os
        
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
        import os
        
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
        import os
        
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