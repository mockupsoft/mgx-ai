# -*- coding: utf-8 -*-
"""
Unit Tests for mgx_agent.performance.async_tools

Tests async helpers: AsyncTimer, bounded_gather, with_timeout, run_in_thread, PhaseTimings

NOTE: Async tests require pytest-asyncio to be installed.
If async tests are skipped, install it with: pip install pytest-asyncio
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch

from mgx_agent.performance.async_tools import (
    AsyncTimer,
    bounded_gather,
    with_timeout,
    run_in_thread,
    PhaseTimings,
    with_retry,
    AsyncBatchProcessor,
    run_with_progress,
)


# ============================================
# ASYNC TIMER TESTS
# ============================================

def test_async_timer_basic(event_loop):
    """Test AsyncTimer context manager tracks duration."""
    async def run_test():
        async with AsyncTimer("test_op", log_on_exit=False) as timer:
            await asyncio.sleep(0.1)
        
        assert timer.duration >= 0.1
        assert timer.duration < 0.2
        assert timer.get_duration() == timer.duration
    
    event_loop.run_until_complete(run_test())


def test_async_timer_with_logging(event_loop, caplog):
    """Test AsyncTimer logs on exit when enabled."""
    async def run_test():
        async with AsyncTimer("test_op", log_on_exit=True):
            await asyncio.sleep(0.05)
    
    event_loop.run_until_complete(run_test())
    # Check that log was created (logger.info was called)
    assert len(caplog.records) > 0


def test_async_timer_on_exception(event_loop):
    """Test AsyncTimer handles exceptions gracefully."""
    async def run_test():
        try:
            async with AsyncTimer("test_op", log_on_exit=False) as timer:
                await asyncio.sleep(0.05)
                raise ValueError("test error")
        except ValueError:
            pass
        
        # Timer should still track duration even on exception
        assert timer.duration >= 0.05
    
    event_loop.run_until_complete(run_test())


# ============================================
# PHASE TIMINGS TESTS
# ============================================

def test_phase_timings_init():
    """Test PhaseTimings initialization."""
    pt = PhaseTimings()
    assert pt.analysis_duration == 0.0
    assert pt.planning_duration == 0.0
    assert pt.execution_duration == 0.0
    assert pt.review_duration == 0.0
    assert pt.cleanup_duration == 0.0
    assert pt.total_duration == 0.0
    assert pt.phase_details == {}


def test_phase_timings_add_phase():
    """Test adding phase timings."""
    pt = PhaseTimings()
    pt.add_phase("test_phase", 1.5)
    pt.add_phase("another_phase", 2.3)
    
    assert pt.get_phase("test_phase") == 1.5
    assert pt.get_phase("another_phase") == 2.3
    assert pt.get_phase("nonexistent") == 0.0
    assert len(pt.phase_details) == 2


def test_phase_timings_to_dict():
    """Test PhaseTimings.to_dict() conversion."""
    pt = PhaseTimings()
    pt.analysis_duration = 1.0
    pt.planning_duration = 2.0
    pt.execution_duration = 3.0
    pt.add_phase("custom", 0.5)
    
    result = pt.to_dict()
    assert result["analysis_duration"] == 1.0
    assert result["planning_duration"] == 2.0
    assert result["execution_duration"] == 3.0
    assert result["phase_details"]["custom"] == 0.5


def test_phase_timings_summary():
    """Test PhaseTimings.summary() formatting."""
    pt = PhaseTimings()
    pt.analysis_duration = 1.5
    pt.execution_duration = 3.0
    pt.total_duration = 5.0
    
    summary = pt.summary()
    assert "1.50s" in summary
    assert "3.00s" in summary
    assert "5.00s" in summary


# ============================================
# BOUNDED GATHER TESTS
# ============================================

@pytest.mark.asyncio
async def test_bounded_gather_basic():
    """Test bounded_gather executes all tasks."""
    async def task(n):
        await asyncio.sleep(0.01)
        return n * 2
    
    results = await bounded_gather(
        task(1), task(2), task(3), task(4),
        max_concurrent=2
    )
    
    assert results == [2, 4, 6, 8]


@pytest.mark.asyncio
async def test_bounded_gather_respects_limit():
    """Test bounded_gather respects concurrency limit."""
    concurrent_count = 0
    max_concurrent_seen = 0
    lock = asyncio.Lock()
    
    async def task(n):
        nonlocal concurrent_count, max_concurrent_seen
        
        async with lock:
            concurrent_count += 1
            max_concurrent_seen = max(max_concurrent_seen, concurrent_count)
        
        await asyncio.sleep(0.05)
        
        async with lock:
            concurrent_count -= 1
        
        return n
    
    results = await bounded_gather(
        task(1), task(2), task(3), task(4), task(5),
        max_concurrent=2
    )
    
    assert results == [1, 2, 3, 4, 5]
    assert max_concurrent_seen <= 2


@pytest.mark.asyncio
async def test_bounded_gather_with_exceptions():
    """Test bounded_gather with return_exceptions=True."""
    async def good_task():
        return "success"
    
    async def bad_task():
        raise ValueError("error")
    
    results = await bounded_gather(
        good_task(), bad_task(), good_task(),
        max_concurrent=2,
        return_exceptions=True
    )
    
    assert results[0] == "success"
    assert isinstance(results[1], ValueError)
    assert results[2] == "success"


# ============================================
# WITH TIMEOUT TESTS
# ============================================

@pytest.mark.asyncio
async def test_with_timeout_success():
    """Test with_timeout decorator allows fast operations."""
    @with_timeout(1.0)
    async def fast_op():
        await asyncio.sleep(0.1)
        return "success"
    
    result = await fast_op()
    assert result == "success"


@pytest.mark.asyncio
async def test_with_timeout_raises():
    """Test with_timeout decorator raises TimeoutError on slow operations."""
    @with_timeout(0.1)
    async def slow_op():
        await asyncio.sleep(1.0)
        return "success"
    
    with pytest.raises(asyncio.TimeoutError):
        await slow_op()


# ============================================
# RUN IN THREAD TESTS
# ============================================

@pytest.mark.asyncio
async def test_run_in_thread_basic():
    """Test run_in_thread offloads blocking operations."""
    def blocking_operation(x, y):
        time.sleep(0.05)
        return x + y
    
    result = await run_in_thread(blocking_operation, 2, 3)
    assert result == 5


@pytest.mark.asyncio
async def test_run_in_thread_with_kwargs():
    """Test run_in_thread with keyword arguments."""
    def blocking_operation(x, y=10):
        return x * y
    
    result = await run_in_thread(blocking_operation, 5, y=3)
    assert result == 15


@pytest.mark.asyncio
async def test_run_in_thread_exception():
    """Test run_in_thread propagates exceptions."""
    def failing_operation():
        raise ValueError("test error")
    
    with pytest.raises(ValueError, match="test error"):
        await run_in_thread(failing_operation)


# ============================================
# WITH RETRY TESTS
# ============================================

@pytest.mark.asyncio
async def test_with_retry_success():
    """Test with_retry succeeds on first try."""
    call_count = 0
    
    async def succeeding_task():
        nonlocal call_count
        call_count += 1
        return "success"
    
    result = await with_retry(succeeding_task, max_attempts=3, delay=0.01)
    assert result == "success"
    assert call_count == 1


@pytest.mark.asyncio
async def test_with_retry_eventually_succeeds():
    """Test with_retry retries and eventually succeeds."""
    call_count = 0
    
    async def flaky_task():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("temp error")
        return "success"
    
    result = await with_retry(
        flaky_task,
        max_attempts=5,
        delay=0.01,
        backoff=1.5
    )
    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_with_retry_exhausts_attempts():
    """Test with_retry raises after max attempts."""
    call_count = 0
    
    async def failing_task():
        nonlocal call_count
        call_count += 1
        raise ValueError("persistent error")
    
    with pytest.raises(ValueError, match="persistent error"):
        await with_retry(failing_task, max_attempts=3, delay=0.01)
    
    assert call_count == 3


# ============================================
# ASYNC BATCH PROCESSOR TESTS
# ============================================

@pytest.mark.asyncio
async def test_async_batch_processor():
    """Test AsyncBatchProcessor processes items in batches."""
    processor = AsyncBatchProcessor(max_concurrent=2, batch_size=3)
    
    items = list(range(10))
    
    async def double(x):
        await asyncio.sleep(0.01)
        return x * 2
    
    results = await processor.process(items, double)
    
    assert results == [x * 2 for x in items]
    assert len(results) == 10


@pytest.mark.asyncio
async def test_async_batch_processor_with_exceptions():
    """Test AsyncBatchProcessor handles exceptions."""
    processor = AsyncBatchProcessor(max_concurrent=2, batch_size=3)
    
    items = [1, 2, 3, 4, 5]
    
    async def flaky_processor(x):
        if x == 3:
            raise ValueError(f"error on {x}")
        return x * 2
    
    results = await processor.process(items, flaky_processor)
    
    # Check that some succeeded and one failed
    assert results[0] == 2
    assert results[1] == 4
    assert isinstance(results[2], ValueError)
    assert results[3] == 8
    assert results[4] == 10


# ============================================
# RUN WITH PROGRESS TESTS
# ============================================

@pytest.mark.asyncio
async def test_run_with_progress():
    """Test run_with_progress executes operations with logging."""
    async def task(n):
        await asyncio.sleep(0.01)
        return n * 2
    
    awaitables = [task(i) for i in range(5)]
    
    results = await run_with_progress(
        awaitables,
        operation_name="test_ops",
        max_concurrent=3
    )
    
    assert results == [0, 2, 4, 6, 8]


# ============================================
# INTEGRATION TESTS
# ============================================

@pytest.mark.asyncio
async def test_combined_async_tools():
    """Test multiple async tools working together."""
    async with AsyncTimer("combined_test", log_on_exit=False) as timer:
        # Use bounded_gather with timeout-wrapped tasks
        @with_timeout(1.0)
        async def task(n):
            await asyncio.sleep(0.05)
            return n * 2
        
        results = await bounded_gather(
            task(1), task(2), task(3),
            max_concurrent=2
        )
    
    assert results == [2, 4, 6]
    assert timer.duration >= 0.05
    assert timer.duration < 0.5


@pytest.mark.asyncio
async def test_phase_timings_workflow():
    """Test PhaseTimings tracking a complete workflow."""
    pt = PhaseTimings()
    
    # Simulate analyze phase
    async with AsyncTimer("analyze", log_on_exit=False) as t1:
        await asyncio.sleep(0.05)
    pt.analysis_duration = t1.duration
    pt.add_phase("analyze", t1.duration)
    
    # Simulate execute phase
    async with AsyncTimer("execute", log_on_exit=False) as t2:
        await asyncio.sleep(0.08)
    pt.execution_duration = t2.duration
    pt.add_phase("execute", t2.duration)
    
    # Simulate cleanup in thread
    await run_in_thread(time.sleep, 0.03)
    pt.cleanup_duration = 0.03
    
    pt.total_duration = pt.analysis_duration + pt.execution_duration + pt.cleanup_duration
    
    assert pt.analysis_duration >= 0.05
    assert pt.execution_duration >= 0.08
    assert pt.cleanup_duration >= 0.03
    assert pt.total_duration >= 0.16
    
    # Check summary format
    summary = pt.summary()
    assert "Analysis:" in summary
    assert "Execution:" in summary
