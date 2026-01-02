# -*- coding: utf-8 -*-
"""
WebSocket Router

Real-time event streaming via WebSocket connections.
Handles subscription to task/run events and stream all events.
"""

import logging
import asyncio
import uuid
import pty
import os
import select
from typing import Optional, Set

from fastapi import APIRouter, WebSocket, status, WebSocketDisconnect, Query

from backend.services import get_event_broadcaster
from backend.schemas import EventPayload

logger = logging.getLogger(__name__)


def transform_event_for_frontend(event: EventPayload | dict) -> dict:
    """
    Transform EventPayload format to frontend-expected format.
    
    Backend format: EventPayload model with event_type enum
    Frontend format: {type: "agent_message", payload: {...}}
    """
    if isinstance(event, EventPayload):
        event_dict = event.model_dump(mode='json')
        return {
            "type": event.event_type.value,  # Enum'dan string'e çevir
            "payload": event_dict,
        }
    elif isinstance(event, dict) and "event_type" in event:
        return {
            "type": event["event_type"],
            "payload": event,
        }
    return event

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
                
                # Transform EventPayload to frontend format
                frontend_event = transform_event_for_frontend(event)
                await websocket.send_json(frontend_event)
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
                
                frontend_event = transform_event_for_frontend(event)
                await websocket.send_json(frontend_event)
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
    Supports dynamic subscription via subscribe messages from frontend.
    
    WebSocket endpoint for a global event stream.
    Useful for dashboards and monitoring.
    
    Connection format:
        ws://localhost:8000/ws/stream
    
    Message format (from client):
        { "type": "subscribe", "payload": { "taskId": "...", "runId": "...", ... } }
    
    Message format (to client):
        { "type": "agent_message", "payload": {...} }
    """
    await websocket.accept()
    
    subscriber_id = f"ws_stream_{uuid.uuid4()}"
    broadcaster = get_event_broadcaster()
    
    logger.info(f"WebSocket connected to global stream: {subscriber_id}")
    active_connections.add(subscriber_id)
    
    try:
        # Initial subscription to all events
        channels = ["all"]
        event_queue = await broadcaster.subscribe(
            subscriber_id,
            channels,
        )
        
        async def handle_client_messages():
            """Handle subscribe messages from frontend."""
            nonlocal event_queue, channels
            while True:
                try:
                    # Wait for message from client with timeout
                    data = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=1.0,  # Short timeout to allow event processing
                    )
                    
                    # Handle subscribe messages
                    if isinstance(data, dict) and data.get("type") == "subscribe":
                        payload = data.get("payload", {})
                        new_channels = ["all"]  # Always include "all"
                        
                        # Add task-specific channel
                        if task_id := payload.get("taskId"):
                            new_channels.append(f"task:{task_id}")
                        
                        # Add run-specific channel
                        if run_id := payload.get("runId"):
                            new_channels.append(f"run:{run_id}")
                        
                        # Add agent-specific channels
                        if agent_id := payload.get("agentId"):
                            new_channels.append(f"agent:{agent_id}")
                        
                        # Add workspace/project channels
                        if workspace_id := payload.get("workspaceId"):
                            new_channels.append(f"workspace:{workspace_id}")
                        
                        # Update subscription
                        if set(new_channels) != set(channels):
                            channels[:] = new_channels
                            event_queue = await broadcaster.subscribe(
                                subscriber_id,
                                channels,
                            )
                            logger.info(f"Updated subscription for {subscriber_id} to {channels}")
                    
                except asyncio.TimeoutError:
                    # Timeout is expected, continue to allow event processing
                    continue
                except WebSocketDisconnect:
                    logger.info(f"Client disconnected in message handler: {subscriber_id}")
                    break
                except Exception as e:
                    logger.error(f"Error handling client message: {e}", exc_info=True)
                    continue
        
        async def handle_event_stream():
            """Send events to WebSocket client."""
            nonlocal event_queue
            while True:
                try:
                    event = await asyncio.wait_for(
                        event_queue.get(),
                        timeout=60,
                    )
                    
                    frontend_event = transform_event_for_frontend(event)
                    await websocket.send_json(frontend_event)
                except asyncio.TimeoutError:
                    # Send heartbeat
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": asyncio.get_event_loop().time(),
                    })
                except WebSocketDisconnect:
                    logger.info(f"Client disconnected in event stream: {subscriber_id}")
                    break
                except Exception as e:
                    logger.error(f"Error sending event: {e}", exc_info=True)
                    break
        
        # Run both handlers concurrently
        await asyncio.gather(
            handle_client_messages(),
            handle_event_stream(),
            return_exceptions=True
        )
    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected from global stream")
    except Exception as e:
        logger.error(f"WebSocket error for global stream: {e}", exc_info=True)
    
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
                frontend_event = transform_event_for_frontend(event)
                await websocket.send_json(frontend_event)
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
                frontend_event = transform_event_for_frontend(event)
                await websocket.send_json(frontend_event)
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


@router.websocket("/workflows/{workflow_id}")
async def websocket_workflow_stream(websocket: WebSocket, workflow_id: str):
    """Subscribe to real-time events for a specific workflow definition."""
    
    await websocket.accept()
    
    subscriber_id = f"ws_workflow_{workflow_id}_{uuid.uuid4()}"
    broadcaster = get_event_broadcaster()
    
    logger.info(f"WebSocket connected for workflow {workflow_id}: {subscriber_id}")
    active_connections.add(subscriber_id)
    
    try:
        # Subscribe to workflow-specific channel
        event_queue = await broadcaster.subscribe(
            subscriber_id,
            [f"workflow:{workflow_id}"],
        )
        
        # Send events to WebSocket client
        while True:
            try:
                event = await asyncio.wait_for(
                    event_queue.get(),
                    timeout=60,  # Connection keep-alive timeout
                )
                
                frontend_event = transform_event_for_frontend(event)
                await websocket.send_json(frontend_event)
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": asyncio.get_event_loop().time(),
                    "workflow_id": workflow_id,
                })
            except Exception as e:
                logger.error(f"Error sending workflow event: {e}")
                break
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for workflow {workflow_id}")
    except Exception as e:
        logger.error(f"WebSocket error for workflow {workflow_id}: {e}")
    
    finally:
        active_connections.discard(subscriber_id)
        await broadcaster.unsubscribe(subscriber_id)
        logger.info(f"WebSocket disconnected for workflow {workflow_id}: {subscriber_id}")


@router.websocket("/workflows/executions/{execution_id}")
async def websocket_workflow_execution_stream(
    websocket: WebSocket,
    execution_id: str,
):
    """Subscribe to real-time events for a specific workflow execution."""
    
    await websocket.accept()
    
    subscriber_id = f"ws_workflow_run_{execution_id}_{uuid.uuid4()}"
    broadcaster = get_event_broadcaster()
    
    logger.info(f"WebSocket connected for workflow execution {execution_id}: {subscriber_id}")
    active_connections.add(subscriber_id)
    
    try:
        # Subscribe to execution-specific channel
        event_queue = await broadcaster.subscribe(
            subscriber_id,
            [f"workflow-run:{execution_id}"],
        )
        
        # Send events to WebSocket client
        while True:
            try:
                event = await asyncio.wait_for(
                    event_queue.get(),
                    timeout=60,  # Connection keep-alive timeout
                )
                
                frontend_event = transform_event_for_frontend(event)
                await websocket.send_json(frontend_event)
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": asyncio.get_event_loop().time(),
                    "workflow_execution_id": execution_id,
                })
            except Exception as e:
                logger.error(f"Error sending workflow execution event: {e}")
                break
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for workflow execution {execution_id}")
    except Exception as e:
        logger.error(f"WebSocket error for workflow execution {execution_id}: {e}")
    
    finally:
        active_connections.discard(subscriber_id)
        await broadcaster.unsubscribe(subscriber_id)
        logger.info(f"WebSocket disconnected for workflow execution {execution_id}: {subscriber_id}")


@router.websocket("/workflows/steps/{step_id}")
async def websocket_workflow_step_stream(websocket: WebSocket, step_id: str):
    """Subscribe to real-time events for a specific workflow step."""
    
    await websocket.accept()
    
    subscriber_id = f"ws_workflow_step_{step_id}_{uuid.uuid4()}"
    broadcaster = get_event_broadcaster()
    
    logger.info(f"WebSocket connected for workflow step {step_id}: {subscriber_id}")
    active_connections.add(subscriber_id)
    
    try:
        # Subscribe to step-specific channel
        event_queue = await broadcaster.subscribe(
            subscriber_id,
            [f"workflow-step:{step_id}"],
        )
        
        # Send events to WebSocket client
        while True:
            try:
                event = await asyncio.wait_for(
                    event_queue.get(),
                    timeout=60,  # Connection keep-alive timeout
                )
                
                frontend_event = transform_event_for_frontend(event)
                await websocket.send_json(frontend_event)
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": asyncio.get_event_loop().time(),
                    "workflow_step_id": step_id,
                })
            except Exception as e:
                logger.error(f"Error sending workflow step event: {e}")
                break
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for workflow step {step_id}")
    except Exception as e:
        logger.error(f"WebSocket error for workflow step {step_id}: {e}")
    
    finally:
        active_connections.discard(subscriber_id)
        await broadcaster.unsubscribe(subscriber_id)
        logger.info(f"WebSocket disconnected for workflow step {step_id}: {subscriber_id}")


@router.websocket("/workflows/stream")
async def websocket_workflows_all_stream(websocket: WebSocket):
    """Subscribe to all workflow events across all workflows."""
    
    await websocket.accept()
    
    subscriber_id = f"ws_workflows_stream_{uuid.uuid4()}"
    broadcaster = get_event_broadcaster()
    
    logger.info(f"WebSocket connected to workflows global stream: {subscriber_id}")
    active_connections.add(subscriber_id)
    
    try:
        # Subscribe to all workflow events
        event_queue = await broadcaster.subscribe(
            subscriber_id,
            ["workflows"],  # Add workflows channel to events.py broadcaster
        )
        
        # Send events to WebSocket client
        while True:
            try:
                event = await asyncio.wait_for(
                    event_queue.get(),
                    timeout=60,  # Connection keep-alive timeout
                )
                
                frontend_event = transform_event_for_frontend(event)
                await websocket.send_json(frontend_event)
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": asyncio.get_event_loop().time(),
                    "stream": "workflows",
                })
            except Exception as e:
                logger.error(f"Error sending workflows stream event: {e}")
                break
    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected from workflows global stream")
    except Exception as e:
        logger.error(f"WebSocket error for workflows global stream: {e}")
    
    finally:
        active_connections.discard(subscriber_id)
        await broadcaster.unsubscribe(subscriber_id)
        logger.info(f"WebSocket disconnected from workflows global stream: {subscriber_id}")


@router.websocket("/terminal/{task_id}")
async def websocket_terminal(
    websocket: WebSocket,
    task_id: str,
    run_id: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for terminal emulation.
    
    Creates a PTY (pseudo-terminal) and forwards stdin/stdout via WebSocket.
    """
    await websocket.accept()
    
    logger.info(f"Terminal WebSocket connected for task {task_id}")
    
    # Create PTY
    pid, fd = pty.fork()
    
    if pid == 0:
        # Child process: execute shell
        os.execvpe("bash", ["bash"], os.environ)
    else:
        # Parent process: handle WebSocket communication
        try:
            # Set terminal to non-blocking mode
            import fcntl
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            async def read_pty():
                """Read from PTY and send to WebSocket."""
                while True:
                    try:
                        # Use select to check if data is available
                        ready, _, _ = select.select([fd], [], [], 0.1)
                        if ready:
                            data = os.read(fd, 1024)
                            if data:
                                await websocket.send_text(data.decode('utf-8', errors='ignore'))
                    except Exception as e:
                        logger.error(f"Error reading from PTY: {e}")
                        break
            
            async def write_pty():
                """Read from WebSocket and write to PTY."""
                while True:
                    try:
                        data = await websocket.receive_text()
                        if data:
                            os.write(fd, data.encode('utf-8'))
                    except WebSocketDisconnect:
                        break
                    except Exception as e:
                        logger.error(f"Error writing to PTY: {e}")
                        break
            
            # Run both tasks concurrently
            await asyncio.gather(
                read_pty(),
                write_pty(),
                return_exceptions=True
            )
        except WebSocketDisconnect:
            logger.info(f"Terminal WebSocket disconnected for task {task_id}")
        except Exception as e:
            logger.error(f"Terminal WebSocket error for task {task_id}: {e}")
        finally:
            # Cleanup
            try:
                os.close(fd)
                os.waitpid(pid, 0)
            except Exception as e:
                logger.warning(f"Error cleaning up PTY: {e}")


__all__ = ['router']
