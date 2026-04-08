# -*- coding: utf-8 -*-
"""MGXStyleTeam CLI/API run history (output/ metadata)."""

from uuid import uuid4

from sqlalchemy import Column, DateTime, Float, JSON, String, Text

from .base import Base, TimestampMixin, SerializationMixin


class MgxRun(Base, TimestampMixin, SerializationMixin):
    """Kayıt: MGX takım görevi tamamlandığında üretilen çıktı özeti."""

    __tablename__ = "mgx_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()), index=True)
    task = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="success", index=True)
    complexity = Column(String(8), nullable=True)
    output_dir = Column(String(1024), nullable=True)
    plan_summary = Column(JSON, nullable=True)
    results_summary = Column(JSON, nullable=True)
    duration = Column(Float, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<MgxRun(id={self.id}, status={self.status!r})>"
