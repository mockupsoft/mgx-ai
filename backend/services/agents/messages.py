# -*- coding: utf-8 -*-
"""Agent message bus.

Persists agent messages and publishes them to the EventBroadcaster.

Delivery guarantees are intentionally simple:
- messages are always persisted before being published
- retention is capped per-agent (count based)
- clients may ACK the last seen message id for best-effort replay logic
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.models import AgentMessage, AgentMessageDirection
from backend.schemas import EventPayload, EventTypeEnum
from backend.services.events import get_event_broadcaster

logger = logging.getLogger(__name__)


@dataclass
class SubscriberAckState:
    last_message_id: str
    updated_at: datetime


class AgentMessageBus:
    def __init__(
        self,
        retention_limit: Optional[int] = None,
        ack_window_seconds: Optional[int] = None,
    ):
        self.retention_limit = retention_limit or getattr(settings, "agent_message_retention_limit", 1000)
        self.ack_window_seconds = ack_window_seconds or getattr(settings, "agent_message_ack_window_seconds", 3600)
        self._acks: dict[str, SubscriberAckState] = {}

    def ack(self, subscriber_id: str, message_id: str) -> None:
        self._acks[subscriber_id] = SubscriberAckState(last_message_id=message_id, updated_at=datetime.utcnow())

    def get_last_ack(self, subscriber_id: str) -> Optional[str]:
        state = self._acks.get(subscriber_id)
        if state is None:
            return None

        if datetime.utcnow() - state.updated_at > timedelta(seconds=self.ack_window_seconds):
            self._acks.pop(subscriber_id, None)
            return None

        return state.last_message_id

    async def append(
        self,
        session: AsyncSession,
        *,
        workspace_id: str,
        project_id: str,
        agent_instance_id: str,
        direction: AgentMessageDirection,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
        task_id: Optional[str] = None,
        run_id: Optional[str] = None,
        broadcast: bool = True,
    ) -> AgentMessage:
        message = AgentMessage(
            workspace_id=workspace_id,
            project_id=project_id,
            agent_instance_id=agent_instance_id,
            direction=direction,
            payload=payload or {},
            correlation_id=correlation_id,
            task_id=task_id,
            run_id=run_id,
        )
        session.add(message)
        await session.flush()

        await self._apply_retention(session=session, agent_instance_id=agent_instance_id)

        if broadcast:
            await self._broadcast_message(message)

        return message

    async def list_history(
        self,
        session: AsyncSession,
        *,
        workspace_id: str,
        agent_instance_id: str,
        skip: int = 0,
        limit: int = 50,
        direction: Optional[AgentMessageDirection] = None,
        correlation_id: Optional[str] = None,
    ) -> list[AgentMessage]:
        query = sa.select(AgentMessage).where(
            AgentMessage.workspace_id == workspace_id,
            AgentMessage.agent_instance_id == agent_instance_id,
        )

        if direction is not None:
            query = query.where(AgentMessage.direction == direction)

        if correlation_id is not None:
            query = query.where(AgentMessage.correlation_id == correlation_id)

        query = query.order_by(AgentMessage.created_at.desc()).offset(skip).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())

    async def _apply_retention(self, *, session: AsyncSession, agent_instance_id: str) -> None:
        if not self.retention_limit or self.retention_limit <= 0:
            return

        overflow_ids_subq = (
            sa.select(AgentMessage.id)
            .where(AgentMessage.agent_instance_id == agent_instance_id)
            .order_by(AgentMessage.created_at.desc())
            .offset(self.retention_limit)
        )

        await session.execute(sa.delete(AgentMessage).where(AgentMessage.id.in_(overflow_ids_subq)))

    async def _broadcast_message(self, message: AgentMessage) -> None:
        broadcaster = get_event_broadcaster()

        event = EventPayload(
            event_type=EventTypeEnum.AGENT_MESSAGE,
            timestamp=message.created_at or datetime.utcnow(),
            workspace_id=message.workspace_id,
            agent_id=message.agent_instance_id,
            task_id=message.task_id,
            run_id=message.run_id,
            data={
                "message": message.to_dict(),
            },
        )

        await broadcaster.publish(event)


_bus: Optional[AgentMessageBus] = None


def get_agent_message_bus() -> AgentMessageBus:
    global _bus
    if _bus is None:
        _bus = AgentMessageBus()
    return _bus


__all__ = ["AgentMessageBus", "get_agent_message_bus"]
