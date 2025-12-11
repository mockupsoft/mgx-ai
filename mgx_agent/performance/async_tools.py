#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Async performance tools for MGX Agent.

Provides:
- AsyncTimer: Context manager for timing async operations
- bounded_gather: Limit concurrent asyncio.gather operations
- with_timeout: Wrap async functions with timeout handling
- run_in_thread: Offload blocking operations to thread pool
- PhaseTimings: Track phase durations across workflow
"""

import asyncio
import time
import functools
from typing import List, Awaitable, TypeVar, Callable, Any, Optional, Dict
from dataclasses import dataclass, field
from metagpt.logs import logger

T = TypeVar('T')


@dataclass
class PhaseTimings:
    """Track timing data for workflow phases."""
    
    analysis_duration: float = 0.0
    planning_duration: float = 0.0
    execution_duration: float = 0.0
    review_duration: float = 0.0
    cleanup_duration: float = 0.0
    total_duration: float = 0.0
    phase_details: Dict[str, float] = field(default_factory=dict)
    
    def add_phase(self, phase_name: str, duration: float):
        """Add a phase timing."""
        self.phase_details[phase_name] = duration
        logger.debug(f"⏱️  Phase '{phase_name}': {duration:.3f}s")
    
    def get_phase(self, phase_name: str) -> float:
        """Get timing for a specific phase."""
        return self.phase_details.get(phase_name, 0.0)
    
    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "analysis_duration": self.analysis_duration,
            "planning_duration": self.planning_duration,
            "execution_duration": self.execution_duration,
            "review_duration": self.review_duration,
            "cleanup_duration": self.cleanup_duration,
            "total_duration": self.total_duration,
            "phase_details": self.phase_details,
        }
    
    def summary(self) -> str:
        """Get a human-readable summary."""
        return f"""
╔══════════════════════════════════════════════════════════╗
║                  ⏱️  TIMING SUMMARY                       ║
╚══════════════════════════════════════════════════════════╝

📊 Analysis:   {self.analysis_duration:.2f}s
📋 Planning:   {self.planning_duration:.2f}s
🚀 Execution:  {self.execution_duration:.2f}s
🔍 Review:     {self.review_duration:.2f}s
🧹 Cleanup:    {self.cleanup_duration:.2f}s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️  Total:      {self.total_duration:.2f}s
"""


class AsyncTimer:
    """
    Context manager for timing async operations.

    Usage:
        async with AsyncTimer("my_operation") as timer:
            await some_async_function()
        print(f"Duration: {timer.duration}s")
    """

    def __init__(self, operation_name: str = "operation", log_on_exit: bool = True):
        """Initialize timer."""
        self.operation_name = operation_name
        self.log_on_exit = log_on_exit
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.duration: float = 0.0

    async def __aenter__(self):
        """Start timing."""
        self.start_time = time.perf_counter()
        logger.debug(f"⏱️  Starting: {self.operation_name}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Stop timing and optionally log."""
        self.end_time = time.perf_counter()
        if self.start_time is None:
            self.duration = 0.0
        else:
            self.duration = self.end_time - self.start_time

        try:
            from mgx_agent.performance.profiler import get_active_profiler

            profiler = get_active_profiler()
            if profiler is not None:
                profiler.record_timer(self.operation_name, self.duration)
        except Exception:
            # Profiler must never break business logic.
            pass

        if self.log_on_exit:
            if exc_type is None:
                logger.info(f"✅ {self.operation_name}: {self.duration:.3f}s")
            else:
                logger.warning(
                    f"⚠️  {self.operation_name}: {self.duration:.3f}s (error: {exc_type.__name__})"
                )

        return False
    
    def get_duration(self) -> float:
        """Get duration in seconds."""
        return self.duration


async def bounded_gather(
    *awaitables: Awaitable[T],
    max_concurrent: int = 5,
    return_exceptions: bool = False
) -> List[T]:
    """
    Run multiple async operations with a concurrency limit.
    
    Unlike asyncio.gather which runs all tasks concurrently,
    this limits the number of concurrent tasks to prevent
    resource exhaustion.
    
    Args:
        *awaitables: Async operations to run
        max_concurrent: Maximum number of concurrent operations
        return_exceptions: Whether to return exceptions instead of raising
    
    Returns:
        List of results in the same order as input
    
    Example:
        results = await bounded_gather(
            task1(), task2(), task3(),
            max_concurrent=2
        )
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def bounded_task(awaitable: Awaitable[T]) -> T:
        async with semaphore:
            return await awaitable
    
    # Wrap each awaitable with semaphore
    bounded_awaitables = [bounded_task(aw) for aw in awaitables]
    
    # Run all with gather
    return await asyncio.gather(*bounded_awaitables, return_exceptions=return_exceptions)


def with_timeout(timeout_seconds: float):
    """
    Decorator to add timeout handling to async functions.
    
    Args:
        timeout_seconds: Timeout in seconds
    
    Returns:
        Decorated function that raises asyncio.TimeoutError on timeout
    
    Example:
        @with_timeout(30.0)
        async def long_running_llm_call():
            return await llm.generate()
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.error(f"⏱️  Timeout ({timeout_seconds}s) exceeded for {func.__name__}")
                raise
        return wrapper
    return decorator


async def run_in_thread(func: Callable[..., T], *args, **kwargs) -> T:
    """
    Run a blocking function in a thread pool to avoid blocking the event loop.
    
    This is useful for I/O operations like file writes, database queries,
    or other synchronous operations that would otherwise block async execution.
    
    Args:
        func: Blocking function to run
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func
    
    Returns:
        Result from func
    
    Example:
        # Offload file write to thread
        await run_in_thread(save_file, "/path/to/file", content)
        
        # Offload memory cleanup
        await run_in_thread(cleanup_old_data, max_size=100)
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(func, **kwargs), *args)


async def with_retry(
    func: Callable[..., Awaitable[T]],
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> T:
    """
    Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries (seconds)
        backoff: Backoff multiplier for each retry
        exceptions: Tuple of exceptions to catch and retry
    
    Returns:
        Result from func
    
    Raises:
        Last exception if all retries fail
    
    Example:
        result = await with_retry(
            lambda: llm_call(),
            max_attempts=3,
            delay=2.0
        )
    """
    current_delay = delay
    last_exception = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt < max_attempts:
                logger.warning(
                    f"⚠️  Attempt {attempt}/{max_attempts} failed: {e}. "
                    f"Retrying in {current_delay:.1f}s..."
                )
                await asyncio.sleep(current_delay)
                current_delay *= backoff
            else:
                logger.error(f"❌ All {max_attempts} attempts failed.")
    
    raise last_exception


class AsyncBatchProcessor:
    """
    Process items in batches with concurrency control.
    
    Useful for processing large lists of items without overwhelming
    the system with too many concurrent operations.
    """
    
    def __init__(self, max_concurrent: int = 5, batch_size: int = 10):
        """
        Initialize batch processor.
        
        Args:
            max_concurrent: Max concurrent operations within a batch
            batch_size: Number of items to process per batch
        """
        self.max_concurrent = max_concurrent
        self.batch_size = batch_size
    
    async def process(
        self,
        items: List[Any],
        processor: Callable[[Any], Awaitable[T]]
    ) -> List[T]:
        """
        Process items in batches.
        
        Args:
            items: List of items to process
            processor: Async function to process each item
        
        Returns:
            List of results in same order as items
        """
        results = []
        
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            logger.debug(f"📦 Processing batch {i // self.batch_size + 1} ({len(batch)} items)")
            
            batch_results = await bounded_gather(
                *[processor(item) for item in batch],
                max_concurrent=self.max_concurrent,
                return_exceptions=True
            )
            
            results.extend(batch_results)
        
        return results


async def run_with_progress(
    awaitables: List[Awaitable[T]],
    operation_name: str = "operations",
    max_concurrent: int = 5
) -> List[T]:
    """
    Run async operations with progress logging.
    
    Args:
        awaitables: List of async operations
        operation_name: Name for logging
        max_concurrent: Max concurrent operations
    
    Returns:
        List of results
    """
    total = len(awaitables)
    logger.info(f"🚀 Starting {total} {operation_name}...")
    
    async with AsyncTimer(operation_name):
        results = await bounded_gather(
            *awaitables,
            max_concurrent=max_concurrent
        )
    
    logger.info(f"✅ Completed {total} {operation_name}")
    return results
