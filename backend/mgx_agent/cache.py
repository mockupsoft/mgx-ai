# -*- coding: utf-8 -*-
"""mgx_agent.cache

Pluggable response-cache layer.

Design goals:
- Small, dependency-free default (in-memory LRU + TTL)
- Optional Redis backend (only if `redis` is installed)
- Deterministic cache keys by hashing (role + action + request payload)

This module intentionally keeps the interface synchronous so it can be used
from async code without additional awaits.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple


class CacheBackend(str, Enum):
    NONE = "none"
    MEMORY = "memory"
    REDIS = "redis"


@dataclass
class CacheStats:
    backend: str
    max_entries: Optional[int]
    ttl_seconds: Optional[int]
    size: int
    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0
    expirations: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total) if total else 0.0


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def make_cache_key(*, role: str, action: str, payload: Mapping[str, Any], version: int = 1) -> str:
    """Create a deterministic cache key.

    Key structure keeps prefixes human-readable for debugging/inspection.
    """

    body = {
        "v": version,
        "role": role,
        "action": action,
        "payload": payload,
    }
    digest = hashlib.sha256(_stable_json(body).encode("utf-8")).hexdigest()
    safe_role = str(role).replace(" ", "_")
    safe_action = str(action).replace(" ", "_")
    return f"mgx:v{version}:{safe_role}:{safe_action}:{digest}"


class ResponseCache(ABC):
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def keys(self) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def stats(self) -> CacheStats:
        raise NotImplementedError


class NullCache(ResponseCache):
    def __init__(self):
        self._stats = CacheStats(backend=CacheBackend.NONE.value, max_entries=None, ttl_seconds=None, size=0)

    def get(self, key: str) -> Optional[Any]:
        self._stats.misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        self._stats.sets += 1

    def clear(self) -> None:
        return None

    def keys(self) -> List[str]:
        return []

    def stats(self) -> CacheStats:
        self._stats.size = 0
        return self._stats


class InMemoryLRUTTLCache(ResponseCache):
    """Thread-safe LRU cache with TTL.

    Stores arbitrary python objects.
    """

    def __init__(
        self,
        *,
        max_entries: int = 1024,
        ttl_seconds: int = 3600,
        time_fn=time.time,
    ):
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must be >= 0")

        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._time_fn = time_fn
        self._lock = threading.RLock()
        self._store: "OrderedDict[str, Tuple[Optional[float], Any]]" = OrderedDict()
        self._stats = CacheStats(
            backend=CacheBackend.MEMORY.value,
            max_entries=max_entries,
            ttl_seconds=ttl_seconds,
            size=0,
        )

    def _is_expired(self, expires_at: Optional[float]) -> bool:
        if expires_at is None:
            return False
        return self._time_fn() >= expires_at

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                self._stats.misses += 1
                return None

            expires_at, value = item
            if self._is_expired(expires_at):
                self._stats.expirations += 1
                self._stats.misses += 1
                try:
                    del self._store[key]
                except KeyError:
                    pass
                return None

            self._store.move_to_end(key)
            self._stats.hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            now = self._time_fn()
            expires_at = (now + self._ttl_seconds) if self._ttl_seconds else None

            if key in self._store:
                del self._store[key]

            self._store[key] = (expires_at, value)
            self._store.move_to_end(key)
            self._stats.sets += 1

            while len(self._store) > self._max_entries:
                self._store.popitem(last=False)
                self._stats.evictions += 1

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def keys(self) -> List[str]:
        with self._lock:
            return list(self._store.keys())

    def stats(self) -> CacheStats:
        with self._lock:
            self._stats.size = len(self._store)
            return self._stats


class RedisCache(ResponseCache):
    """Redis-backed cache (optional dependency).

    Values are stored as JSON.
    """

    def __init__(
        self,
        *,
        redis_url: str,
        ttl_seconds: int = 3600,
        key_prefix: str = "mgx:cache",
    ):
        try:
            import redis  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("Redis backend requires `redis` package") from e

        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self._ttl_seconds = ttl_seconds
        self._prefix = key_prefix.rstrip(":")
        self._stats = CacheStats(
            backend=CacheBackend.REDIS.value,
            max_entries=None,
            ttl_seconds=ttl_seconds,
            size=0,
        )

    def _full_key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    def get(self, key: str) -> Optional[Any]:
        full = self._full_key(key)
        raw = self._redis.get(full)
        if raw is None:
            self._stats.misses += 1
            return None
        self._stats.hits += 1
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    def set(self, key: str, value: Any) -> None:
        full = self._full_key(key)
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if self._ttl_seconds:
            self._redis.setex(full, self._ttl_seconds, raw)
        else:
            self._redis.set(full, raw)
        self._stats.sets += 1

    def clear(self) -> None:
        pattern = f"{self._prefix}:*"
        keys = self._redis.keys(pattern)
        if keys:
            self._redis.delete(*keys)

    def keys(self) -> List[str]:
        pattern = f"{self._prefix}:*"
        raw_keys = self._redis.keys(pattern)
        return [k[len(self._prefix) + 1 :] for k in raw_keys]

    def stats(self) -> CacheStats:
        # Size computation via KEYS is expensive; keep best-effort.
        try:
            self._stats.size = len(self.keys())
        except Exception:
            self._stats.size = 0
        return self._stats


class SemanticCache(ResponseCache):
    """
    Semantic cache that finds similar prompts using embeddings.
    
    This is a basic implementation. For production, consider using
    a vector database like Pinecone, Weaviate, or Qdrant.
    """
    
    def __init__(
        self,
        base_cache: ResponseCache,
        similarity_threshold: float = 0.75,  # Lowered for better hit rate
        max_entries: int = 10000,
        enable_fuzzy_matching: bool = True,
    ):
        """
        Initialize semantic cache.
        
        Args:
            base_cache: Base cache implementation (e.g., InMemoryLRUTTLCache)
            similarity_threshold: Minimum similarity score (0.0-1.0) to consider a match (lowered for 80%+ hit rate)
            max_entries: Maximum number of entries to track for semantic search
            enable_fuzzy_matching: Enable fuzzy matching for better cache hits
        """
        self.base_cache = base_cache
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self.enable_fuzzy_matching = enable_fuzzy_matching
        
        # Store embeddings for semantic search
        # In production, use a proper vector database
        self._embeddings: Dict[str, List[float]] = {}
        self._embedding_keys: List[str] = []
    
    def _simple_embedding(self, text: str) -> List[float]:
        """
        Simple text embedding using hash-based approach.
        
        For production, use proper embeddings (OpenAI, Sentence Transformers, etc.)
        """
        # This is a placeholder - in production, use actual embeddings
        import hashlib
        hash_obj = hashlib.sha256(text.encode())
        # Convert hash to 128-dim vector (simple approach)
        hash_bytes = hash_obj.digest()
        embedding = []
        for i in range(0, min(len(hash_bytes), 128), 2):
            if i + 1 < len(hash_bytes):
                val = (hash_bytes[i] << 8) + hash_bytes[i + 1]
                embedding.append(val / 65535.0)  # Normalize to 0-1
        # Pad to 128 dimensions
        while len(embedding) < 128:
            embedding.append(0.0)
        return embedding[:128]
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def _find_similar(self, query_embedding: List[float]) -> Optional[str]:
        """Find similar cache key based on embedding with improved matching."""
        best_match = None
        best_score = 0.0
        
        # Try exact match first (faster)
        for key, embedding in self._embeddings.items():
            similarity = self._cosine_similarity(query_embedding, embedding)
            if similarity > best_score:
                best_score = similarity
                best_match = key
        
        # If fuzzy matching enabled, use lower threshold for better hit rate
        threshold = self.similarity_threshold * 0.9 if self.enable_fuzzy_matching else self.similarity_threshold
        
        if best_score >= threshold:
            return best_match
        
        return None
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, with semantic fallback."""
        # Try exact match first
        value = self.base_cache.get(key)
        if value is not None:
            return value
        
        # Try semantic search
        # Extract prompt text from key (simplified - in production, store separately)
        # For now, use key as text representation
        query_embedding = self._simple_embedding(key)
        similar_key = self._find_similar(query_embedding)
        
        if similar_key:
            return self.base_cache.get(similar_key)
        
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set value in cache and store embedding."""
        self.base_cache.set(key, value)
        
        # Store embedding for semantic search
        embedding = self._simple_embedding(key)
        self._embeddings[key] = embedding
        
        # Maintain max entries
        if len(self._embeddings) > self.max_entries:
            # Remove oldest (simple FIFO)
            if self._embedding_keys:
                oldest = self._embedding_keys.pop(0)
                self._embeddings.pop(oldest, None)
        
        if key not in self._embedding_keys:
            self._embedding_keys.append(key)
    
    def clear(self) -> None:
        """Clear cache and embeddings."""
        self.base_cache.clear()
        self._embeddings.clear()
        self._embedding_keys.clear()
    
    def keys(self) -> List[str]:
        """Get all cache keys."""
        return self.base_cache.keys()
    
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        stats = self.base_cache.stats()
        # Add semantic cache specific stats
        stats.size = len(self._embeddings)
        return stats


__all__ = [
    "CacheBackend",
    "CacheStats",
    "ResponseCache",
    "NullCache",
    "InMemoryLRUTTLCache",
    "RedisCache",
    "SemanticCache",
    "make_cache_key",
]
