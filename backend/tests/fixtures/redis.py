# -*- coding: utf-8 -*-
"""
Redis Fixtures

Provides fixtures for Redis testing including:
- Mock Redis client
- Test cache setup
- Cache data factories
"""

import pytest
from unittest.mock import Mock, MagicMock
from typing import Dict, Any, Optional
import time


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    mock_client = MagicMock()
    mock_client._data: Dict[str, tuple] = {}  # key -> (value, expiry)
    
    def get(key: str) -> Optional[str]:
        if key in mock_client._data:
            value, expiry = mock_client._data[key]
            if expiry and time.time() > expiry:
                del mock_client._data[key]
                return None
            return value
        return None
    
    def setex(key: str, ttl: int, value: str):
        expiry = time.time() + ttl if ttl else None
        mock_client._data[key] = (value, expiry)
    
    def set(key: str, value: str):
        mock_client._data[key] = (value, None)
    
    def delete(*keys: str) -> int:
        count = 0
        for key in keys:
            if key in mock_client._data:
                del mock_client._data[key]
                count += 1
        return count
    
    def keys(pattern: str):
        # Simple pattern matching
        prefix = pattern.replace("*", "")
        return [k for k in mock_client._data.keys() if k.startswith(prefix)]
    
    def ping() -> str:
        return "PONG"
    
    mock_client.get = get
    mock_client.setex = setex
    mock_client.set = set
    mock_client.delete = delete
    mock_client.keys = keys
    mock_client.ping = ping
    
    return mock_client


@pytest.fixture
def redis_cache_fixture(mock_redis_client):
    """Create a Redis cache fixture."""
    from mgx_agent.cache import RedisCache
    
    with pytest.mock.patch('mgx_agent.cache.redis.Redis') as mock_redis_class:
        mock_redis_class.from_url.return_value = mock_redis_client
        cache = RedisCache(redis_url="redis://localhost:6379/0", ttl_seconds=3600)
        cache._redis = mock_redis_client
        return cache

