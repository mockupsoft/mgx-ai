# -*- coding: utf-8 -*-
"""
SQLAlchemy base models and mixins for the application (SQLAlchemy 1.x compatible).
"""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    Column, DateTime, String, Text, JSON, Boolean, Integer, 
    ForeignKey, Index, func, select
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession


# Create the declarative base for models
Base = declarative_base()


class TimestampMixin:
    """Mixin to add created_at and updated_at timestamps."""
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class UUIDMixin:
    """Mixin to add UUID primary key."""
    pass  # Will be implemented in individual models


class SerializationMixin:
    """Mixin to add serialization helpers."""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update model instance from dictionary."""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    @classmethod
    async def get_by_id(cls, session: AsyncSession, id: str) -> Optional[Any]:
        """Get instance by ID."""
        from sqlalchemy import select as sql_select
        result = await session.execute(sql_select(cls).where(cls.id == id))
        return result.scalar_one_or_none()
    
    async def save(self, session: AsyncSession) -> None:
        """Save the instance to the database."""
        session.add(self)
        await session.flush()
    
    async def delete(self, session: AsyncSession) -> None:
        """Delete the instance from the database."""
        await session.delete(self)