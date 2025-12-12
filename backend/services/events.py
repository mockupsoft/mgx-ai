# -*- coding: utf-8 -*-
"""
Event broadcaster service for real-time events.

Provides pub/sub functionality for task and run events.
Used by WebSocket endpoints and background tasks to publish/subscribe to events.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable, Set
from datetime import datetime
from dataclasses import dataclass

from backend.schemas import EventPayload

logger = logging.getLogger(__name__)


@dataclass
class EventSubscriber:
    """Represents a subscriber to event channels."""
    subscriber_id: str
    queue: asyncio.Queue
    channels: Set[str]  # Subscribed channels (e.g., "task:123", "all")


class EventBroadcaster:
    """
    In-memory event broadcaster for real-time updates.
    
    Handles pub/sub for task/run events with support for:
    - Channel-based subscriptions (task:id, run:id, etc.)
    - Wildcard subscriptions (all)
    - Automatic cleanup of disconnected subscribers
    """
    
    def __init__(self, max_queue_size: int = 100):
        """
        Initialize the event broadcaster.
        
        Args:
            max_queue_size: Maximum events per subscriber queue
        """
        self.max_queue_size = max_queue_size
        self._subscribers: Dict[str, EventSubscriber] = {}
        self._lock = asyncio.Lock()
        logger.info(f"EventBroadcaster initialized (max_queue_size={max_queue_size})")
    
    async def subscribe(
        self,
        subscriber_id: str,
        channels: list[str],
    ) -> asyncio.Queue:
        """
        Subscribe to one or more event channels.
        
        Args:
            subscriber_id: Unique subscriber identifier
            channels: List of channels to subscribe to
                     Use "all" for all events
                     Use "task:{id}" for task-specific events
                     Use "run:{id}" for run-specific events
        
        Returns:
            Queue for receiving events
        """
        async with self._lock:
            if subscriber_id in self._subscribers:
                # Update existing subscription
                subscriber = self._subscribers[subscriber_id]
                subscriber.channels.update(channels)
                return subscriber.queue
            
            # Create new subscriber
            queue = asyncio.Queue(maxsize=self.max_queue_size)
            subscriber = EventSubscriber(
                subscriber_id=subscriber_id,
                queue=queue,
                channels=set(channels),
            )
            self._subscribers[subscriber_id] = subscriber
            logger.info(f"Subscriber {subscriber_id} subscribed to {channels}")
            return queue
    
    async def unsubscribe(self, subscriber_id: str):
        """
        Unsubscribe from all channels.
        
        Args:
            subscriber_id: Subscriber to remove
        """
        async with self._lock:
            if subscriber_id in self._subscribers:
                del self._subscribers[subscriber_id]
                logger.info(f"Subscriber {subscriber_id} unsubscribed")
    
    async def publish(self, event: EventPayload, channel: Optional[str] = None):
        """
        Publish an event to all subscribed subscribers.
        
        Args:
            event: Event payload to broadcast
            channel: Optional specific channel to publish to
                    If None, derives from event (task:{task_id}, run:{run_id})
        """
        # Determine channels for this event
        channels = set()
        if channel:
            channels.add(channel)
        else:
            if event.task_id:
                channels.add(f"task:{event.task_id}")
            if event.run_id:
                channels.add(f"run:{event.run_id}")
        
        channels.add("all")  # Always publish to "all"
        
        event_dict = event.model_dump(mode='json')
        
        async with self._lock:
            disconnected = []
            
            for subscriber_id, subscriber in self._subscribers.items():
                # Check if subscriber is interested in this event
                should_receive = any(
                    channel in subscriber.channels for channel in channels
                )
                
                if not should_receive:
                    continue
                
                try:
                    # Try to put event with timeout to avoid blocking
                    subscriber.queue.put_nowait(event_dict)
                except asyncio.QueueFull:
                    logger.warning(f"Queue full for subscriber {subscriber_id}, dropping oldest event")
                    try:
                        subscriber.queue.get_nowait()
                        subscriber.queue.put_nowait(event_dict)
                    except Exception as e:
                        logger.error(f"Error managing queue for {subscriber_id}: {e}")
                        disconnected.append(subscriber_id)
            
            # Cleanup disconnected subscribers
            for subscriber_id in disconnected:
                if subscriber_id in self._subscribers:
                    del self._subscribers[subscriber_id]
        
        logger.debug(f"Published event {event.event_type} to channels {channels}")
    
    async def get_subscriber_count(self) -> int:
        """Get total number of connected subscribers."""
        async with self._lock:
            return len(self._subscribers)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get broadcaster statistics."""
        return {
            "subscriber_count": len(self._subscribers),
            "max_queue_size": self.max_queue_size,
        }


# Global broadcaster instance
_broadcaster: Optional[EventBroadcaster] = None


def get_event_broadcaster() -> EventBroadcaster:
    """
    Get or create the global event broadcaster instance.
    
    Usage:
        from backend.services import get_event_broadcaster
        
        # Subscribe to events
        broadcaster = get_event_broadcaster()
        queue = await broadcaster.subscribe("ws_client_1", ["task:123"])
        
        # Receive events
        while True:
            event = await queue.get()
            await websocket.send_json(event)
        
        # Publish events
        await broadcaster.publish(event, channel="task:123")
    """
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = EventBroadcaster()
    return _broadcaster


__all__ = [
    'EventBroadcaster',
    'EventSubscriber',
    'get_event_broadcaster',
]
