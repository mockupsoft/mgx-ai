# -*- coding: utf-8 -*-
"""
Paralel mikroservis orkestrasyonu veri modelleri.

ServiceSpec   : Bir mikroservisi tanımlayan değer nesnesi.
ServiceResult : Tek bir MGXStyleTeam çalışmasının çıktısı.
ParallelRunResult : Tüm servisleri ve entegrasyon dosyalarını içeren nihai sonuç.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ServiceSpec:
    """Bir mikroservis için gereksinimleri tanımlar."""

    name: str
    """İnsan tarafından okunabilir, URL-safe servis adı (örn. 'user-service')."""

    description: str
    """Bu servis için MGXStyleTeam'e iletilecek tam görev açıklaması."""

    stack: str
    """İstenen teknoloji yığını (örn. 'fastapi', 'express-ts', 'nextjs')."""

    port: int
    """Servise ayrılan port numarası (örn. 8001, 8002 …)."""

    dependencies: List[str] = field(default_factory=list)
    """Bu servisin çağırdığı diğer servislerin adları."""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "stack": self.stack,
            "port": self.port,
            "dependencies": self.dependencies,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ServiceSpec":
        return cls(
            name=str(data.get("name", "service")),
            description=str(data.get("description", "")),
            stack=str(data.get("stack", "fastapi")),
            port=int(data.get("port", 8000)),
            dependencies=list(data.get("dependencies") or []),
        )


@dataclass
class ServiceResult:
    """Tek bir MGXStyleTeam çalışmasının sonucunu tutar."""

    spec: ServiceSpec
    """Bu sonucun ait olduğu servis tanımı."""

    success: bool
    """Çalışmanın başarıyla tamamlanıp tamamlanmadığı."""

    output: str = ""
    """Takımın ham metin çıktısı."""

    output_dir: Optional[str] = None
    """Üretilen dosyaların kaydedildiği dizin yolu."""

    error: Optional[str] = None
    """Başarısızlık durumunda hata mesajı."""

    duration: float = 0.0
    """Çalışma süresi (saniye)."""

    def to_dict(self) -> dict:
        return {
            "service": self.spec.to_dict(),
            "success": self.success,
            "output": self.output[:2000] if self.output else "",
            "output_dir": self.output_dir,
            "error": self.error,
            "duration": round(self.duration, 3),
        }


@dataclass
class ParallelRunResult:
    """Tüm paralel servis çalışmalarının ve entegrasyon adımının nihai çıktısı."""

    task: str
    """Kullanıcının orijinal yüksek seviye görevi."""

    services: List[ServiceResult] = field(default_factory=list)
    """Her servis için ayrı MGXStyleTeam çıktısı."""

    integration_files: Dict[str, str] = field(default_factory=dict)
    """Dosya adı → içerik eşlemesi (docker-compose.yml, nginx.conf, …)."""

    success: bool = False
    """En az bir servis başarılıysa ve entegrasyon tamamlandıysa True."""

    duration: float = 0.0
    """Toplam çalışma süresi (saniye)."""

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "success": self.success,
            "duration": round(self.duration, 3),
            "services": [s.to_dict() for s in self.services],
            "integration_files": {k: v[:8000] for k, v in self.integration_files.items()},
            "stats": {
                "total": len(self.services),
                "succeeded": sum(1 for s in self.services if s.success),
                "failed": sum(1 for s in self.services if not s.success),
            },
        }


__all__ = [
    "ServiceSpec",
    "ServiceResult",
    "ParallelRunResult",
]
