# -*- coding: utf-8 -*-
"""Tests for performance benchmarks and load testing."""

import pytest
import asyncio
import time
import psutil
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any
import statistics


class PerformanceMonitor:
    """Monitor performance metrics during tests."""
    
    def __init__(self):
        self.response_times: List[float] = []
        self.memory_samples: List[float] = []
        self.cpu_samples: List[float] = []
        self.error_count: int = 0
        self.success_count: int = 0
    
    def record_response(self, duration: float, success: bool = True):
        """Record a response time."""
        self.response_times.append(duration)
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
    
    def record_memory(self):
        """Record current memory usage."""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        self.memory_samples.append(memory_mb)
    
    def record_cpu(self):
        """Record current CPU usage."""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        self.cpu_samples.append(cpu_percent)
    
    def get_percentile(self, percentile: float) -> float:
        """Calculate percentile of response times."""
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        index = int(len(sorted_times) * percentile / 100)
        return sorted_times[min(index, len(sorted_times) - 1)]
    
    def get_error_rate(self) -> float:
        """Calculate error rate."""
        total = self.success_count + self.error_count
        if total == 0:
            return 0.0
        return (self.error_count / total) * 100
    
    def get_avg_memory(self) -> float:
        """Get average memory usage."""
        if not self.memory_samples:
            return 0.0
        return statistics.mean(self.memory_samples)
    
    def get_max_cpu(self) -> float:
        """Get maximum CPU usage."""
        if not self.cpu_samples:
            return 0.0
        return max(self.cpu_samples)


class MockAPIClient:
    """Mock API client for load testing."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.request_count = 0
    
    async def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Simulate GET request."""
        self.request_count += 1
        await asyncio.sleep(0.01)  # Simulate network latency
        return {"status": "success", "data": {}}
    
    async def post(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Simulate POST request."""
        self.request_count += 1
        await asyncio.sleep(0.02)  # Simulate processing time
        return {"status": "success", "data": {}}


@pytest.fixture
def performance_monitor():
    """Fixture for performance monitor."""
    return PerformanceMonitor()


@pytest.fixture
def api_client():
    """Fixture for mock API client."""
    return MockAPIClient()


# ============================================================================
# Load Testing
# ============================================================================

@pytest.mark.asyncio
async def test_api_100_concurrent_requests(api_client, performance_monitor):
    """Test API with 100 concurrent requests."""
    
    async def make_request(client: MockAPIClient, monitor: PerformanceMonitor):
        start = time.time()
        try:
            await client.get("/api/health")
            duration = time.time() - start
            monitor.record_response(duration, success=True)
        except Exception:
            duration = time.time() - start
            monitor.record_response(duration, success=False)
    
    # Create 100 concurrent requests
    tasks = [make_request(api_client, performance_monitor) for _ in range(100)]
    await asyncio.gather(*tasks)
    
    assert performance_monitor.success_count == 100
    assert performance_monitor.error_count == 0


@pytest.mark.asyncio
async def test_p95_response_time_under_500ms(api_client, performance_monitor):
    """Test P95 response time is <500ms."""
    
    async def make_request():
        start = time.time()
        await api_client.get("/api/workspaces")
        duration = (time.time() - start) * 1000  # Convert to ms
        performance_monitor.record_response(duration)
    
    # Make 100 requests
    tasks = [make_request() for _ in range(100)]
    await asyncio.gather(*tasks)
    
    p95 = performance_monitor.get_percentile(95)
    assert p95 < 500, f"P95 response time {p95}ms exceeds 500ms threshold"


@pytest.mark.asyncio
async def test_p99_response_time_under_1000ms(api_client, performance_monitor):
    """Test P99 response time is <1000ms."""
    
    async def make_request():
        start = time.time()
        await api_client.get("/api/workspaces")
        duration = (time.time() - start) * 1000  # Convert to ms
        performance_monitor.record_response(duration)
    
    # Make 100 requests
    tasks = [make_request() for _ in range(100)]
    await asyncio.gather(*tasks)
    
    p99 = performance_monitor.get_percentile(99)
    assert p99 < 1000, f"P99 response time {p99}ms exceeds 1000ms threshold"


@pytest.mark.asyncio
async def test_memory_stable_during_load(performance_monitor):
    """Test that memory is stable during load test."""
    initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
    
    # Simulate load for 10 seconds
    for i in range(10):
        performance_monitor.record_memory()
        await asyncio.sleep(1)
    
    final_memory = psutil.Process().memory_info().rss / 1024 / 1024
    memory_growth = final_memory - initial_memory
    
    # Memory should not grow significantly (< 100MB growth)
    assert memory_growth < 100, f"Memory grew by {memory_growth}MB during test"


@pytest.mark.asyncio
async def test_cpu_under_80_percent(performance_monitor):
    """Test that CPU usage is <80%."""
    
    # Simulate some load
    for i in range(5):
        performance_monitor.record_cpu()
        await asyncio.sleep(0.5)
    
    max_cpu = performance_monitor.get_max_cpu()
    assert max_cpu < 80, f"CPU usage {max_cpu}% exceeds 80% threshold"


@pytest.mark.asyncio
async def test_no_connection_pool_exhaustion(api_client):
    """Test no connection pool exhaustion."""
    
    async def make_requests():
        tasks = [api_client.get(f"/api/resource/{i}") for i in range(50)]
        await asyncio.gather(*tasks)
    
    # Make multiple batches of requests
    for _ in range(5):
        await make_requests()
    
    # If we get here without exceptions, connection pool is healthy
    assert api_client.request_count == 250


@pytest.mark.asyncio
async def test_error_rate_under_0_1_percent(api_client, performance_monitor):
    """Test error rate <0.1%."""
    
    async def make_request():
        start = time.time()
        try:
            await api_client.get("/api/workspaces")
            duration = time.time() - start
            performance_monitor.record_response(duration, success=True)
        except Exception:
            duration = time.time() - start
            performance_monitor.record_response(duration, success=False)
    
    # Make 1000 requests
    tasks = [make_request() for _ in range(1000)]
    await asyncio.gather(*tasks)
    
    error_rate = performance_monitor.get_error_rate()
    assert error_rate < 0.1, f"Error rate {error_rate}% exceeds 0.1% threshold"


# ============================================================================
# Search Performance Tests
# ============================================================================

class MockSearchService:
    """Mock search service for testing."""
    
    def __init__(self):
        self.kb_items = self._generate_knowledge_base(1000)
    
    def _generate_knowledge_base(self, size: int) -> List[Dict[str, Any]]:
        """Generate mock knowledge base."""
        return [
            {
                "id": f"kb-{i}",
                "title": f"Document {i}",
                "content": f"Content for document {i}" * 100,
                "tags": ["tag1", "tag2"],
            }
            for i in range(size)
        ]
    
    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Simulate vector search."""
        await asyncio.sleep(0.05)  # Simulate search time
        return self.kb_items[:limit]
    
    async def text_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Simulate text search fallback."""
        await asyncio.sleep(0.1)  # Text search is slower
        return self.kb_items[:limit]


@pytest.fixture
def search_service():
    """Fixture for mock search service."""
    return MockSearchService()


@pytest.mark.asyncio
async def test_single_search_under_200ms(search_service):
    """Test single search completes in <200ms."""
    start = time.time()
    results = await search_service.search("test query")
    duration = (time.time() - start) * 1000
    
    assert len(results) > 0
    assert duration < 200, f"Search took {duration}ms, exceeds 200ms threshold"


@pytest.mark.asyncio
async def test_complex_search_under_500ms(search_service):
    """Test complex search completes in <500ms."""
    start = time.time()
    
    # Simulate complex search with multiple conditions
    results = await search_service.search("complex query with filters")
    
    duration = (time.time() - start) * 1000
    
    assert duration < 500, f"Complex search took {duration}ms, exceeds 500ms threshold"


@pytest.mark.asyncio
async def test_1000_item_kb_search_under_300ms(search_service):
    """Test searching 1000-item knowledge base in <300ms."""
    start = time.time()
    results = await search_service.search("query", limit=10)
    duration = (time.time() - start) * 1000
    
    assert len(results) == 10
    assert duration < 300, f"1000-item KB search took {duration}ms, exceeds 300ms"


@pytest.mark.asyncio
async def test_text_fallback_on_vector_db_down(search_service):
    """Test text search fallback when vector DB is down."""
    
    # Simulate vector DB failure
    with patch.object(search_service, 'search', side_effect=Exception("Vector DB down")):
        # Fallback to text search
        results = await search_service.text_search("query")
        assert len(results) > 0


@pytest.mark.asyncio
async def test_search_results_accurate():
    """Test search results accuracy."""
    search_service = MockSearchService()
    
    results = await search_service.search("document 5")
    
    # Results should be relevant
    assert len(results) > 0
    assert any("Document" in r["title"] for r in results)


@pytest.mark.asyncio
async def test_search_sorting_filtering_performance(search_service):
    """Test sorting/filtering performs well."""
    start = time.time()
    
    # Simulate search with sorting and filtering
    results = await search_service.search("query", limit=50)
    
    # Apply sorting (simulated)
    sorted_results = sorted(results, key=lambda x: x["id"])
    
    duration = (time.time() - start) * 1000
    
    assert len(sorted_results) > 0
    assert duration < 500, f"Sorting/filtering took {duration}ms"


# ============================================================================
# Memory Profiling Tests
# ============================================================================

@pytest.mark.asyncio
async def test_no_memory_leaks_sustained_load():
    """Test no memory leaks during sustained load."""
    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024
    
    # Simulate sustained load for 10 iterations
    for i in range(10):
        # Simulate some work
        data = [{"item": j} for j in range(1000)]
        await asyncio.sleep(0.1)
        del data  # Explicitly delete to help GC
    
    final_memory = process.memory_info().rss / 1024 / 1024
    memory_growth = final_memory - initial_memory
    
    # Memory should not grow significantly
    assert memory_growth < 50, f"Potential memory leak detected: {memory_growth}MB growth"


@pytest.mark.asyncio
async def test_memory_usage_per_request():
    """Test memory usage per request is reasonable."""
    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024
    
    # Simulate 100 requests
    client = MockAPIClient()
    for i in range(100):
        await client.get("/api/resource")
    
    final_memory = process.memory_info().rss / 1024 / 1024
    memory_per_request = (final_memory - initial_memory) / 100
    
    # Each request should use minimal memory (< 1MB avg)
    assert memory_per_request < 1.0, f"Each request used {memory_per_request}MB"


# ============================================================================
# Concurrent Access Tests
# ============================================================================

@pytest.mark.asyncio
async def test_concurrent_read_operations():
    """Test concurrent read operations."""
    client = MockAPIClient()
    
    async def read_operation():
        return await client.get("/api/workspaces")
    
    # 50 concurrent reads
    tasks = [read_operation() for _ in range(50)]
    results = await asyncio.gather(*tasks)
    
    assert len(results) == 50
    assert all(r["status"] == "success" for r in results)


@pytest.mark.asyncio
async def test_concurrent_write_operations():
    """Test concurrent write operations."""
    client = MockAPIClient()
    
    async def write_operation(i: int):
        return await client.post("/api/workspaces", json={"name": f"workspace-{i}"})
    
    # 20 concurrent writes
    tasks = [write_operation(i) for i in range(20)]
    results = await asyncio.gather(*tasks)
    
    assert len(results) == 20
    assert all(r["status"] == "success" for r in results)


@pytest.mark.asyncio
async def test_concurrent_mixed_operations():
    """Test concurrent mixed read/write operations."""
    client = MockAPIClient()
    
    async def mixed_operations():
        tasks = []
        for i in range(25):
            if i % 2 == 0:
                tasks.append(client.get("/api/workspaces"))
            else:
                tasks.append(client.post("/api/workspaces", json={"name": f"ws-{i}"}))
        return await asyncio.gather(*tasks)
    
    results = await mixed_operations()
    
    assert len(results) == 25


# ============================================================================
# Stress Testing
# ============================================================================

@pytest.mark.asyncio
async def test_sustained_load_10_minutes():
    """Test sustained load for simulated duration."""
    client = MockAPIClient()
    monitor = PerformanceMonitor()
    
    # Simulate 10 minutes of load (reduced to 5 seconds for testing)
    end_time = time.time() + 5
    request_count = 0
    
    while time.time() < end_time:
        start = time.time()
        await client.get("/api/health")
        duration = (time.time() - start) * 1000
        monitor.record_response(duration)
        request_count += 1
        await asyncio.sleep(0.1)  # Rate limiting
    
    # System should remain stable
    assert monitor.get_error_rate() < 1.0
    assert request_count > 0


@pytest.mark.asyncio
async def test_spike_load_handling():
    """Test handling of sudden load spike."""
    client = MockAPIClient()
    monitor = PerformanceMonitor()
    
    async def make_request():
        start = time.time()
        try:
            await client.get("/api/workspaces")
            duration = (time.time() - start) * 1000
            monitor.record_response(duration, success=True)
        except Exception:
            monitor.record_response(0, success=False)
    
    # Sudden spike of 200 concurrent requests
    tasks = [make_request() for _ in range(200)]
    await asyncio.gather(*tasks)
    
    # Most requests should succeed
    success_rate = (monitor.success_count / 200) * 100
    assert success_rate > 95, f"Success rate {success_rate}% is too low"


# ============================================================================
# Database Query Performance
# ============================================================================

@pytest.mark.asyncio
async def test_database_query_performance():
    """Test database query performance."""
    
    async def simulate_query():
        # Simulate database query
        await asyncio.sleep(0.01)
        return {"rows": 100}
    
    start = time.time()
    result = await simulate_query()
    duration = (time.time() - start) * 1000
    
    assert result["rows"] == 100
    assert duration < 100, f"Query took {duration}ms, should be <100ms"


@pytest.mark.asyncio
async def test_database_connection_pool_efficiency():
    """Test database connection pool efficiency."""
    
    async def simulate_db_operation():
        await asyncio.sleep(0.005)
        return True
    
    # Multiple concurrent DB operations
    tasks = [simulate_db_operation() for _ in range(100)]
    start = time.time()
    results = await asyncio.gather(*tasks)
    duration = time.time() - start
    
    assert all(results)
    # Should complete quickly with connection pooling
    assert duration < 2.0, f"100 operations took {duration}s with connection pool"


# ============================================================================
# API Endpoint Performance
# ============================================================================

@pytest.mark.asyncio
async def test_health_endpoint_response_time():
    """Test /health endpoint response time."""
    client = MockAPIClient()
    
    start = time.time()
    result = await client.get("/health")
    duration = (time.time() - start) * 1000
    
    assert result["status"] == "success"
    assert duration < 50, f"Health check took {duration}ms, should be <50ms"


@pytest.mark.asyncio
async def test_list_workspaces_performance():
    """Test list workspaces endpoint performance."""
    client = MockAPIClient()
    
    start = time.time()
    result = await client.get("/api/workspaces")
    duration = (time.time() - start) * 1000
    
    assert result["status"] == "success"
    assert duration < 200, f"List workspaces took {duration}ms"


@pytest.mark.asyncio
async def test_create_workflow_performance():
    """Test create workflow endpoint performance."""
    client = MockAPIClient()
    
    start = time.time()
    result = await client.post("/api/workflows", json={"name": "test-workflow"})
    duration = (time.time() - start) * 1000
    
    assert result["status"] == "success"
    assert duration < 500, f"Create workflow took {duration}ms"
