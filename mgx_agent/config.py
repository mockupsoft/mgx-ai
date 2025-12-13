# -*- coding: utf-8 -*-
"""
MGX Agent Configuration Module

TeamConfig ve TaskComplexity sınıfları.
Pydantic v2 ile doğrulama.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, validator
from metagpt.logs import logger

__all__ = [
    'TaskComplexity',
    'LogLevel', 
    'TeamConfig',
    'DEFAULT_CONFIG',
]

# Import stack specs conditionally to avoid circular imports
def _get_stack_specs():
    """Lazy import to avoid circular dependency"""
    from .stack_specs import ProjectType, OutputMode
    return ProjectType, OutputMode

class TaskComplexity:
    """Görev karmaşıklık seviyeleri"""
    XS = "XS"  # Çok basit - tek dosya, tek fonksiyon
    S = "S"    # Basit - birkaç fonksiyon
    M = "M"    # Orta - birden fazla dosya
    L = "L"    # Büyük - mimari gerektirir
    XL = "XL"  # Çok büyük - tam takım gerektirir


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
    
    # Web Stack ayarları (Phase A)
    target_stack: Optional[str] = Field(
        default=None,
        description="Hedef stack (express-ts, nestjs, laravel, fastapi, react-vite, nextjs, vue-vite, devops-docker, ci-github-actions)"
    )
    project_type: Optional[str] = Field(
        default=None,
        description="Proje tipi: api | webapp | fullstack | devops"
    )
    output_mode: str = Field(
        default="generate_new",
        description="Çıktı modu: generate_new | patch_existing"
    )
    strict_requirements: bool = Field(
        default=False,
        description="Katı gereksinim modu (FILE manifest formatı zorunlu, açıklama yok)"
    )
    existing_project_path: Optional[str] = Field(
        default=None,
        description="Mevcut proje yolu (patch_existing modu için)"
    )
    constraints: list = Field(
        default_factory=list,
        description="Ek kısıtlamalar (örn: 'Use pnpm', 'No extra libraries')"
    )
    
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
    def validate_max_rounds(cls, v):
        if v < 1:
            raise ValueError("max_rounds en az 1 olmalı")
        return v
    
    @validator('default_investment')
    def validate_investment(cls, v):
        if v < 0.5:
            raise ValueError("investment en az $0.5 olmalı")
        return v
    
    @validator('budget_multiplier')
    def validate_budget_multiplier(cls, v):
        if v <= 0:
            raise ValueError("budget_multiplier 0'dan büyük olmalı")
        if v > 10:
            logger.warning(f"⚠️ budget_multiplier çok yüksek: {v}x - Maliyet patlaması riski!")
        return v
    
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
