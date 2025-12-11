# -*- coding: utf-8 -*-
"""
MGX Agent Metrics Module

TaskMetrics sınıfı - görev izleme ve metrikleri
"""

from dataclasses import dataclass


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
