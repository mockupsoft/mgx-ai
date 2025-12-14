# -*- coding: utf-8 -*-
"""
WebSocket Router

Real-time event streaming via WebSocket connections.
Handles subscription to task/run events and stream all events.
"""

import logging
import asyncio
import uuid
from typing import Optional, Set

from fastapi import APIRouter, WebSocket, status
from fastapi.exceptions import WebSocketDisconnect

from backend.services import get_event_broadcaster

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])

# Track active WebSocket connections
active_connections: Set[str] = set()


@router.websocket("/tasks/{task_id}")
async def websocket_task_stream(
    websocket: WebSocket,
    task_id: str,
):
    """
    Subscribe to real-time events for a specific task.
    
    WebSocket endpoint for streaming task-specific events.
    
    Events include:
    - analysis_start: Task analysis has started
    - plan_ready: Execution plan is ready for review
    - approval_required: Waiting for user approval
    - approved: Plan was approved
    - rejected: Plan was rejected
    - progress: Execution progress update
    - completion: Task completed successfully
    - failure: Task failed
    - cancelled: Task was cancelled
    
    Connection format:
        ws://localhost:8000/ws/tasks/{task_id}
    
    Message format (JSON):
        {
            "event_type": "plan_ready",
            "timestamp": "2024-01-01T12:00:00Z",
            "task_id": "task_123",
            "run_id": "run_456",
            "data": {...},
            "message": "Plan ready for approval"
        }
    
    Reconnection:
    - Client should reconnect with exponential backoff on disconnect
    - Server will replay recent events if available
    """
    await websocket.accept()
    
    subscriber_id = f"ws_task_{task_id}_{uuid.uuid4()}"
    broadcaster = get_event_broadcaster()
    
    logger.info(f"WebSocket connected for task {task_id}: {subscriber_id}")
    active_connections.add(subscriber_id)
    
    try:
        # Subscribe to task-specific channel
        event_queue = await broadcaster.subscribe(
            subscriber_id,
            [f"task:{task_id}"],
        )
        
        # Send events to WebSocket client
        while True:
            try:
                # Wait for event with timeout to allow graceful shutdown
                event = await asyncio.wait_for(
                    event_queue.get(),
                    timeout=60,  # Connection keep-alive timeout
                )
                
                await websocket.send_json(event)
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": asyncio.get_event_loop().time(),
                })
            except Exception as e:
                logger.error(f"Error sending event: {e}")
                break
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for task {task_id}")
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
    
    finally:
        active_connections.discard(subscriber_id)
        await broadcaster.unsubscribe(subscriber_id)
        logger.info(f"WebSocket disconnected for task {task_id}: {subscriber_id}")


@router.websocket("/runs/{run_id}")
async def websocket_run_stream(
    websocket: WebSocket,
    run_id: str,
):
    """
    Subscribe to real-time events for a specific run.
    
    WebSocket endpoint for streaming run-specific events.
    Receives all events associated with a run execution.
    
    Connection format:
        ws://localhost:8000/ws/runs/{run_id}
    
    Message format:
        Same as /ws/tasks/{task_id}
    """
    await websocket.accept()
    
    subscriber_id = f"ws_run_{run_id}_{uuid.uuid4()}"
    broadcaster = get_event_broadcaster()
    
    logger.info(f"WebSocket connected for run {run_id}: {subscriber_id}")
    active_connections.add(subscriber_id)
    
    try:
        # Subscribe to run-specific channel
        event_queue = await broadcaster.subscribe(
            subscriber_id,
            [f"run:{run_id}"],
        )
        
        # Send events to WebSocket client
        while True:
            try:
                event = await asyncio.wait_for(
                    event_queue.get(),
                    timeout=60,
                )
                
                await websocket.send_json(event)
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": asyncio.get_event_loop().time(),
                })
            except Exception as e:
                logger.error(f"Error sending event: {e}")
                break
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for run {run_id}")
    except Exception as e:
        logger.error(f"WebSocket error for run {run_id}: {e}")
    
    finally:
        active_connections.discard(subscriber_id)
        await broadcaster.unsubscribe(subscriber_id)
        logger.info(f"WebSocket disconnected for run {run_id}: {subscriber_id}")


@router.websocket("/stream")
async def websocket_all_events(websocket: WebSocket):
    """
    Subscribe to all events across all tasks and runs.
    
    WebSocket endpoint for a global event stream.
    Useful for dashboards and monitoring.
    
    Connection format:
        ws://localhost:8000/ws/stream
    
    Message format:
        Same as other WebSocket endpoints, but includes all events.
    """
    await websocket.accept()
    
    subscriber_id = f"ws_stream_{uuid.uuid4()}"
    broadcaster = get_event_broadcaster()
    
    logger.info(f"WebSocket connected to global stream: {subscriber_id}")
    active_connections.add(subscriber_id)
    
    try:
        # Subscribe to all events
        event_queue = await broadcaster.subscribe(
            subscriber_id,
            ["all"],
        )
        
        # Send events to WebSocket client
        while True:
            try:
                event = await asyncio.wait_for(
                    event_queue.get(),
                    timeout=60,
                )
                
                await websocket.send_json(event)
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": asyncio.get_event_loop().time(),
                })
            except Exception as e:
                logger.error(f"Error sending event: {e}")
                break
    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected from global stream")
    except Exception as e:
        logger.error(f"WebSocket error for global stream: {e}")
    
    finally:
        active_connections.discard(subscriber_id)
        await broadcaster.unsubscribe(subscriber_id)
        logger.info(f"WebSocket disconnected from global stream: {subscriber_id}")


@router.websocket("/agents/stream")
async def websocket_agents_stream(
    websocket: WebSocket,
    workspace_id: Optional[str] = None,
    agent_id: Optional[str] = None,
):
    """Subscribe to agent events.

    Filters:
    - workspace_id: subscribe to workspace:{id} agent events
    - agent_id: comma-separated list of agent ids (agent:{id})
    """

    await websocket.accept()

    subscriber_id = f"ws_agents_{uuid.uuid4()}"
    broadcaster = get_event_broadcaster()

    channels: list[str]
    if agent_id:
        channels = [f"agent:{a.strip()}" for a in agent_id.split(",") if a.strip()]
    elif workspace_id:
        channels = [f"workspace:{workspace_id}"]
    else:
        channels = ["agents"]

    logger.info(f"WebSocket connected to agents stream: {subscriber_id} channels={channels}")
    active_connections.add(subscriber_id)

    try:
        event_queue = await broadcaster.subscribe(subscriber_id, channels)

        while True:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=60)
                await websocket.send_json(event)
            except asyncio.TimeoutError:
                await websocket.send_json(
                    {
                        "type": "heartbeat",
                        "timestamp": asyncio.get_event_loop().time(),
                        "subscriber_id": subscriber_id,
                        "channels": channels,
                    }
                )
            except Exception as e:
                logger.error(f"Error sending agents stream event: {e}")
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected from agents stream")
    except Exception as e:
        logger.error(f"WebSocket error for agents stream: {e}")

    finally:
        active_connections.discard(subscriber_id)
        await broadcaster.unsubscribe(subscriber_id)
        logger.info(f"WebSocket disconnected from agents stream: {subscriber_id}")


@router.websocket("/agents/{agent_id}")
async def websocket_agent_stream(websocket: WebSocket, agent_id: str):
    """Subscribe to real-time events for a specific agent."""

    await websocket.accept()

    subscriber_id = f"ws_agent_{agent_id}_{uuid.uuid4()}"
    broadcaster = get_event_broadcaster()

    logger.info(f"WebSocket connected for agent {agent_id}: {subscriber_id}")
    active_connections.add(subscriber_id)

    try:
        event_queue = await broadcaster.subscribe(subscriber_id, [f"agent:{agent_id}"])

        while True:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=60)
                await websocket.send_json(event)
            except asyncio.TimeoutError:
                await websocket.send_json(
                    {
                        "type": "heartbeat",
                        "timestamp": asyncio.get_event_loop().time(),
                        "agent_id": agent_id,
                    }
                )
            except Exception as e:
                logger.error(f"Error sending agent event: {e}")
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for agent {agent_id}")
    except Exception as e:
        logger.error(f"WebSocket error for agent {agent_id}: {e}")

    finally:
        active_connections.discard(subscriber_id)
        await broadcaster.unsubscribe(subscriber_id)
        logger.info(f"WebSocket disconnected for agent {agent_id}: {subscriber_id}")


__all__ = ['router']
