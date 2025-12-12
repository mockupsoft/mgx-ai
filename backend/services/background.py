# -*- coding: utf-8 -*-
"""
Background Task Runner Service

Handles async task execution in the background with status tracking.
"""

import asyncio
import logging
import uuid
from typing import Optional, Callable, Any, Dict
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Background task status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundTask:
    """
    Represents a background task with metadata.
    """
    task_id: str
    name: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['started_at'] = self.started_at.isoformat() if self.started_at else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        return data


class BackgroundTaskRunner:
    """
    Manages background task execution and tracking.
    
    Allows running async operations without blocking the HTTP response.
    """
    
    def __init__(self, max_tasks: int = 100):
        """
        Initialize the task runner.
        
        Args:
            max_tasks: Maximum concurrent tasks to track
        """
        self.max_tasks = max_tasks
        self._tasks: Dict[str, BackgroundTask] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        logger.info(f"BackgroundTaskRunner initialized (max_tasks={max_tasks})")
    
    async def submit(
        self,
        coro: Callable,
        name: str = "unnamed_task",
    ) -> str:
        """
        Submit a background task.
        
        Args:
            coro: Async callable to execute
            name: Task name for logging/identification
        
        Returns:
            Task ID for status tracking
        """
        if len(self._tasks) >= self.max_tasks:
            raise RuntimeError(f"Too many tasks ({self.max_tasks} limit reached)")
        
        task_id = str(uuid.uuid4())
        task = BackgroundTask(
            task_id=task_id,
            name=name,
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        
        self._tasks[task_id] = task
        await self._queue.put((task_id, coro))
        
        logger.info(f"Task submitted: {task_id} ({name})")
        return task_id
    
    async def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a background task.
        
        Args:
            task_id: Task ID from submit()
        
        Returns:
            Task status dict or None if not found
        """
        task = self._tasks.get(task_id)
        if task is None:
            return None
        return task.to_dict()
    
    async def _worker(self):
        """Worker coroutine that processes background tasks."""
        logger.info("BackgroundTaskRunner worker started")
        
        while self._running:
            try:
                # Get task with timeout to allow graceful shutdown
                task_id, coro = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=0.5
                )
            except asyncio.TimeoutError:
                continue
            
            task = self._tasks[task_id]
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            
            logger.info(f"Task started: {task_id} ({task.name})")
            
            try:
                result = await coro()
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.utcnow()
                logger.info(f"Task completed: {task_id}")
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.utcnow()
                logger.error(f"Task failed: {task_id} - {str(e)}")
            
            self._queue.task_done()
    
    async def start(self, num_workers: int = 2):
        """
        Start background task processing.
        
        Args:
            num_workers: Number of worker coroutines
        """
        if self._running:
            logger.warning("Task runner already running")
            return
        
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker())
            for _ in range(num_workers)
        ]
        logger.info(f"BackgroundTaskRunner started with {num_workers} workers")
    
    async def stop(self):
        """Stop background task processing and wait for pending tasks."""
        if not self._running:
            return
        
        logger.info("Stopping BackgroundTaskRunner")
        
        # Wait for queue to be empty
        await self._queue.join()
        
        # Stop workers
        self._running = False
        for worker in self._workers:
            await worker
        
        logger.info("BackgroundTaskRunner stopped")
    
    def cleanup_old_tasks(self, keep_recent: int = 50):
        """
        Clean up old completed tasks (garbage collection).
        
        Args:
            keep_recent: Number of recent tasks to keep
        """
        if len(self._tasks) <= keep_recent:
            return
        
        # Sort by completion time and keep only recent ones
        completed = [
            (task_id, task)
            for task_id, task in self._tasks.items()
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
        ]
        completed.sort(key=lambda x: x[1].completed_at or datetime.utcnow())
        
        to_remove = len(completed) - keep_recent
        for task_id, _ in completed[:to_remove]:
            del self._tasks[task_id]
            logger.debug(f"Cleaned up task: {task_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get task runner statistics."""
        statuses = {}
        for task in self._tasks.values():
            status = task.status.value
            statuses[status] = statuses.get(status, 0) + 1
        
        return {
            "total_tasks": len(self._tasks),
            "statuses": statuses,
            "running": self._running,
        }


# Global task runner instance
_runner: Optional[BackgroundTaskRunner] = None


def get_task_runner() -> BackgroundTaskRunner:
    """
    Get the global background task runner instance.
    
    Usage:
        from backend.services import get_task_runner
        
        @app.on_event("startup")
        async def startup():
            runner = get_task_runner()
            await runner.start()
        
        @app.post("/background-tasks")
        async def submit_task(task: str):
            runner = get_task_runner()
            task_id = await runner.submit(some_async_func(), name=task)
            return {"task_id": task_id}
    """
    global _runner
    if _runner is None:
        _runner = BackgroundTaskRunner()
    return _runner


__all__ = [
    'BackgroundTask',
    'TaskStatus',
    'BackgroundTaskRunner',
    'get_task_runner',
]
