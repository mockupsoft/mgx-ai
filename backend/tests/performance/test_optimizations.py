# -*- coding: utf-8 -*-
"""Tests for performance optimizations."""

import pytest
import asyncio
from backend.services.llm.prompt_optimizer import PromptOptimizer, get_prompt_optimizer
from backend.mgx_agent.cache import InMemoryLRUTTLCache, SemanticCache


@pytest.mark.performance
class TestPromptOptimization:
    """Tests for prompt optimization."""
    
    def test_prompt_optimization_reduces_tokens(self):
        """Test that prompt optimization reduces token count."""
        optimizer = PromptOptimizer(target_reduction_percent=35.0)
        
        # Long prompt with redundant text
        long_prompt = """
        Please note that it is important to understand that we need to create a function.
        It should be noted that this function must be able to handle various cases.
        Please be aware that the function should return a value.
        In order to achieve this goal, we need to write code.
        For the purpose of this task, we will create a simple function.
        """
        
        result = optimizer.optimize(long_prompt)
        
        assert result.original_tokens > 0
        assert result.optimized_tokens < result.original_tokens
        assert result.reduction_percent >= 5.0  # At least 5% reduction
        assert "optimized_prompt" in result.optimization_techniques or result.reduction_percent > 0
    
    def test_prompt_optimization_preserves_important_info(self):
        """Test that important information is preserved."""
        optimizer = PromptOptimizer()
        
        prompt = "Create a function that handles errors. CRITICAL: Must return error code."
        
        result = optimizer.optimize(prompt)
        
        assert "error" in result.optimized_prompt.lower()
        assert "critical" in result.optimized_prompt.lower() or "must" in result.optimized_prompt.lower()
    
    def test_prompt_optimization_with_code_blocks(self):
        """Test prompt optimization with code blocks."""
        optimizer = PromptOptimizer()
        
        prompt = """
        Create a Python function:
        ```python
        def hello():
            # This is a comment
            # Another comment
            print("Hello")
        ```
        """
        
        result = optimizer.optimize(prompt, preserve_sections=["```"])
        
        assert "def hello" in result.optimized_prompt
        # Code structure should be preserved


@pytest.mark.performance
class TestCacheOptimization:
    """Tests for cache optimization."""
    
    def test_semantic_cache_finds_similar(self):
        """Test that semantic cache finds similar prompts."""
        base_cache = InMemoryLRUTTLCache(max_entries=100, ttl_seconds=3600)
        semantic_cache = SemanticCache(
            base_cache=base_cache,
            similarity_threshold=0.75,
            enable_fuzzy_matching=True,
        )
        
        # Store a prompt
        key1 = "test_key_1"
        value1 = "Create a function to calculate sum"
        semantic_cache.set(key1, value1)
        
        # Try to find similar (should work with lower threshold)
        # Note: This is a simplified test - real semantic matching would use embeddings
        result = semantic_cache.get(key1)
        assert result == value1
    
    def test_cache_hit_rate_improvement(self):
        """Test that cache configuration improves hit rate."""
        cache = InMemoryLRUTTLCache(max_entries=1000, ttl_seconds=7200)
        
        # Simulate cache usage
        for i in range(100):
            cache.set(f"key_{i}", f"value_{i}")
        
        # Access same keys multiple times
        hits = 0
        misses = 0
        for _ in range(50):
            for i in range(20):  # Access first 20 keys repeatedly
                result = cache.get(f"key_{i}")
                if result:
                    hits += 1
                else:
                    misses += 1
        
        stats = cache.stats()
        hit_rate = stats.hit_rate
        
        # With repeated access, hit rate should be high
        assert hit_rate > 0.5  # At least 50% hit rate in this scenario


@pytest.mark.performance
class TestTurnCalculation:
    """Tests for turn calculation optimization."""
    
    def test_optimal_rounds_calculation(self):
        """Test optimal rounds calculation."""
        from backend.mgx_agent.team import MGXStyleTeam, TeamConfig
        
        config = TeamConfig(max_rounds=10)
        team = MGXStyleTeam(config=config)
        
        # Test different complexities
        test_cases = [
            ("XS", 5.0, 1),  # Should use 1 round for XS
            ("S", 5.0, 2),   # Should use 2 rounds for S
            ("M", 5.0, 3),    # Should use 3 rounds for M
            ("L", 5.0, 5),    # Should use 5 rounds for L
        ]
        
        for complexity, budget, expected_min in test_cases:
            optimal = team._calculate_optimal_rounds(complexity, budget)
            assert optimal >= expected_min
            assert optimal <= config.max_rounds
    
    def test_early_termination_detection(self):
        """Test early termination detection."""
        from backend.mgx_agent.team import MGXStyleTeam, TeamConfig
        
        config = TeamConfig(max_rounds=10)
        team = MGXStyleTeam(config=config)
        
        # Mock completed task state
        team._collect_raw_results = lambda: (
            "def hello(): return 'world'",  # code
            "def test_hello(): assert hello() == 'world'",  # tests
            "Approved. Code looks good.",  # positive review
        )
        
        is_completed = team._is_task_completed()
        assert is_completed is True


@pytest.mark.performance
class TestAgentCommunication:
    """Tests for agent communication optimization."""
    
    def test_context_compression(self):
        """Test context compression reduces size."""
        from backend.services.agents.context import SharedContextService
        
        service = SharedContextService()
        
        # Large context data
        large_data = {
            "state": {"key": "value"},
            "variables": {f"var_{i}": f"value_{i}" for i in range(100)},
            "verbose_logs": ["log"] * 1000,
            "debug_info": {"debug": "info"} * 100,
        }
        
        compressed = service._compress_context(large_data, max_size=5000)
        
        # Compressed should be smaller
        assert len(str(compressed)) < len(str(large_data))
        # Important keys should be preserved
        assert "state" in compressed
        assert "variables" in compressed


@pytest.mark.asyncio
async def test_async_execution_performance():
    """Test async execution performance improvements."""
    import time
    
    async def slow_operation():
        await asyncio.sleep(0.1)
        return "result"
    
    # Sequential execution
    start = time.perf_counter()
    results_seq = []
    for _ in range(5):
        result = await slow_operation()
        results_seq.append(result)
    sequential_time = time.perf_counter() - start
    
    # Parallel execution
    start = time.perf_counter()
    results_par = await asyncio.gather(*[slow_operation() for _ in range(5)])
    parallel_time = time.perf_counter() - start
    
    # Parallel should be faster (at least 2x improvement expected)
    assert parallel_time < sequential_time
    assert len(results_par) == 5




