# -*- coding: utf-8 -*-
"""
Backend Configuration Module

Pydantic settings with .env support for:
- API server configuration (host, port)
- MGX agent defaults (team settings, cache)
- PostgreSQL connection information
"""

from typing import Optional
from pydantic import BaseSettings, Field
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False
        extra = 'ignore'
    
    # API Server Settings
    api_host: str = Field(default="127.0.0.1", description="API server host")
    api_port: int = Field(default=8000, ge=1024, le=65535, description="API server port")
    api_reload: bool = Field(default=False, description="Enable auto-reload (development only)")
    api_workers: int = Field(default=1, ge=1, le=16, description="Number of Uvicorn workers")
    
    # MGX Team Settings (Defaults)
    mgx_max_rounds: int = Field(default=5, ge=1, le=20, description="Default max rounds for team execution")
    mgx_max_revision_rounds: int = Field(default=2, ge=0, le=5, description="Default max revision rounds")
    mgx_max_memory_size: int = Field(default=50, ge=10, le=500, description="Default team memory size limit")
    mgx_enable_caching: bool = Field(default=True, description="Enable response caching")
    mgx_cache_backend: str = Field(default="memory", description="Cache backend: none | memory | redis")
    mgx_cache_max_entries: int = Field(default=1024, ge=1, le=100_000, description="Max cache entries for LRU")
    mgx_cache_ttl_seconds: int = Field(default=3600, ge=60, le=86400, description="Cache TTL in seconds")
    
    # Database Settings
    db_host: str = Field(default="localhost", description="PostgreSQL host")
    db_port: int = Field(default=5432, ge=1024, le=65535, description="PostgreSQL port")
    db_user: str = Field(default="postgres", description="PostgreSQL user")
    db_password: str = Field(default="postgres", description="PostgreSQL password")
    db_name: str = Field(default="mgx_agent", description="PostgreSQL database name")
    db_pool_size: int = Field(default=10, ge=1, le=100, description="Database connection pool size")
    db_max_overflow: int = Field(default=20, ge=0, le=200, description="Max overflow connections")
    
    # Redis Settings (for distributed caching)
    redis_url: Optional[str] = Field(default=None, description="Redis URL (e.g., redis://localhost:6379)")
    
    # Application Settings
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    
    @property
    def database_url(self) -> str:
        """Generate PostgreSQL connection URL."""
        return (
            f"postgresql://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )
    
    @property
    def async_database_url(self) -> str:
        """Generate async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )
    
    def __str__(self) -> str:
        """String representation of settings (hide sensitive data)."""
        return f"""Settings(
    API: {self.api_host}:{self.api_port} (workers={self.api_workers}, reload={self.api_reload})
    MGX: max_rounds={self.mgx_max_rounds}, cache={self.mgx_cache_backend}
    DB: {self.db_host}:{self.db_port}/{self.db_name}
    Redis: {self.redis_url or 'not configured'}
)"""


# Global settings instance
settings = Settings()

__all__ = ['Settings', 'settings']