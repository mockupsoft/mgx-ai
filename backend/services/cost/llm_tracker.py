# -*- coding: utf-8 -*-
"""LLM cost tracking service for monitoring API call costs and token usage."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.entities import LLMCall, ExecutionCost
from backend.db.models.enums import LLMProvider

logger = logging.getLogger(__name__)


# Model pricing configuration (USD per 1K tokens)
# Updated pricing as of 2024
PRICING_CONFIG = {
    "openai": {
        "gpt-4": {"prompt": 0.03, "completion": 0.06},
        "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
        "gpt-4-32k": {"prompt": 0.06, "completion": 0.12},
        "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
        "gpt-3.5-turbo-16k": {"prompt": 0.001, "completion": 0.002},
    },
    "anthropic": {
        "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
        "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
        "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125},
        "claude-2.1": {"prompt": 0.008, "completion": 0.024},
        "claude-2": {"prompt": 0.008, "completion": 0.024},
    },
    "claude": {  # Alias for anthropic
        "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
        "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
        "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125},
    },
    "mistral": {
        "mistral-large": {"prompt": 0.008, "completion": 0.024},
        "mistral-medium": {"prompt": 0.0027, "completion": 0.0081},
        "mistral-small": {"prompt": 0.002, "completion": 0.006},
        "mistral-tiny": {"prompt": 0.00025, "completion": 0.00075},
    },
    "google": {
        "gemini-pro": {"prompt": 0.00025, "completion": 0.0005},
        "gemini-ultra": {"prompt": 0.0025, "completion": 0.005},
    },
    "local": {
        "default": {"prompt": 0.0, "completion": 0.0},
    },
    "default": {
        "default": {"prompt": 0.001, "completion": 0.002},
    },
}


class LLMCostTracker:
    """
    Service for tracking LLM API call costs and token usage.
    
    Handles:
    - Logging individual LLM calls with token counts
    - Calculating costs based on model pricing
    - Aggregating costs by workspace, project, execution
    - Generating cost summaries and reports
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the LLM cost tracker.
        
        Args:
            session: Database session for persistence
        """
        self.session = session

    def calculate_cost(
        self,
        provider: str,
        model: str,
        tokens_prompt: int,
        tokens_completion: int,
    ) -> float:
        """
        Calculate the cost of an LLM API call.
        
        Args:
            provider: LLM provider name (openai, claude, etc.)
            model: Model name (gpt-4, claude-3-opus, etc.)
            tokens_prompt: Number of prompt tokens
            tokens_completion: Number of completion tokens
        
        Returns:
            Total cost in USD
        """
        provider_lower = provider.lower()
        model_lower = model.lower()
        
        # Get pricing for provider
        provider_pricing = PRICING_CONFIG.get(provider_lower, PRICING_CONFIG["default"])
        
        # Get pricing for specific model, fallback to default
        model_pricing = None
        for model_key, pricing in provider_pricing.items():
            if model_key in model_lower:
                model_pricing = pricing
                break
        
        if model_pricing is None:
            model_pricing = provider_pricing.get("default", PRICING_CONFIG["default"]["default"])
        
        # Calculate cost (pricing is per 1K tokens)
        prompt_cost = (tokens_prompt / 1000) * model_pricing["prompt"]
        completion_cost = (tokens_completion / 1000) * model_pricing["completion"]
        
        total_cost = prompt_cost + completion_cost
        
        logger.debug(
            f"Cost calculation: {provider}/{model} - "
            f"Prompt: {tokens_prompt} tokens (${prompt_cost:.6f}), "
            f"Completion: {tokens_completion} tokens (${completion_cost:.6f}), "
            f"Total: ${total_cost:.6f}"
        )
        
        return total_cost

    async def log_llm_call(
        self,
        workspace_id: str,
        execution_id: str,
        provider: str,
        model: str,
        tokens_prompt: int,
        tokens_completion: int,
        latency_ms: Optional[int] = None,
        metadata: Optional[Dict] = None,
        project_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> LLMCall:
        """
        Log an LLM API call with cost calculation.
        
        Args:
            workspace_id: Workspace identifier
            execution_id: Execution identifier (task run, workflow, etc.)
            provider: LLM provider name
            model: Model name
            tokens_prompt: Number of prompt tokens
            tokens_completion: Number of completion tokens
            latency_ms: API call latency in milliseconds
            metadata: Additional metadata (temperature, max_tokens, etc.)
        
        Returns:
            Created LLMCall record
        """
        tokens_total = tokens_prompt + tokens_completion
        cost_usd = self.calculate_cost(provider, model, tokens_prompt, tokens_completion)

        call_metadata = dict(metadata or {})
        if project_id is not None:
            call_metadata.setdefault("project_id", project_id)
        if agent_id is not None:
            call_metadata.setdefault("agent_id", agent_id)

        llm_call = LLMCall(
            workspace_id=workspace_id,
            execution_id=execution_id,
            provider=provider,
            model=model,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            tokens_total=tokens_total,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            call_metadata=call_metadata,
        )
        
        self.session.add(llm_call)
        await self.session.commit()
        await self.session.refresh(llm_call)
        
        logger.info(
            f"Logged LLM call: {provider}/{model} - "
            f"{tokens_total} tokens, ${cost_usd:.4f} - "
            f"workspace={workspace_id}, execution={execution_id}"
        )
        
        return llm_call

    async def get_execution_llm_costs(
        self,
        execution_id: str,
    ) -> Dict:
        """
        Get aggregated LLM costs for an execution.
        
        Args:
            execution_id: Execution identifier
        
        Returns:
            Dictionary with cost summary
        """
        stmt = select(
            func.sum(LLMCall.cost_usd).label("total_cost"),
            func.sum(LLMCall.tokens_total).label("total_tokens"),
            func.count(LLMCall.id).label("call_count"),
        ).where(LLMCall.execution_id == execution_id)
        
        result = await self.session.execute(stmt)
        row = result.first()
        
        if not row or row.total_cost is None:
            return {
                "total_cost": 0.0,
                "total_tokens": 0,
                "call_count": 0,
            }
        
        return {
            "total_cost": float(row.total_cost),
            "total_tokens": int(row.total_tokens),
            "call_count": int(row.call_count),
        }

    async def get_workspace_costs(
        self,
        workspace_id: str,
        period: str = "month",
    ) -> Dict:
        """
        Get aggregated costs for a workspace.
        
        Args:
            workspace_id: Workspace identifier
            period: Time period (day, week, month, all)
        
        Returns:
            Dictionary with cost summary and breakdown
        """
        # Calculate time range
        now = datetime.utcnow()
        if period == "day":
            start_date = now - timedelta(days=1)
        elif period == "week":
            start_date = now - timedelta(weeks=1)
        elif period == "month":
            start_date = now - timedelta(days=30)
        else:  # all
            start_date = datetime(2000, 1, 1)
        
        # Get total costs
        stmt = select(
            func.sum(LLMCall.cost_usd).label("total_cost"),
            func.sum(LLMCall.tokens_total).label("total_tokens"),
            func.count(LLMCall.id).label("call_count"),
        ).where(
            LLMCall.workspace_id == workspace_id,
            LLMCall.timestamp >= start_date,
        )
        
        result = await self.session.execute(stmt)
        row = result.first()
        
        total_cost = float(row.total_cost) if row.total_cost else 0.0
        total_tokens = int(row.total_tokens) if row.total_tokens else 0
        call_count = int(row.call_count) if row.call_count else 0
        
        # Get cost breakdown by model
        stmt_by_model = select(
            LLMCall.provider,
            LLMCall.model,
            func.sum(LLMCall.cost_usd).label("cost"),
            func.sum(LLMCall.tokens_total).label("tokens"),
            func.count(LLMCall.id).label("calls"),
        ).where(
            LLMCall.workspace_id == workspace_id,
            LLMCall.timestamp >= start_date,
        ).group_by(
            LLMCall.provider,
            LLMCall.model,
        )
        
        result_by_model = await self.session.execute(stmt_by_model)
        by_model = []
        for row in result_by_model:
            by_model.append({
                "provider": row.provider,
                "model": row.model,
                "cost": float(row.cost),
                "tokens": int(row.tokens),
                "calls": int(row.calls),
            })
        
        # Get token breakdown (prompt vs completion)
        stmt_token_breakdown = select(
            func.sum(LLMCall.tokens_prompt).label("total_prompt_tokens"),
            func.sum(LLMCall.tokens_completion).label("total_completion_tokens"),
            func.avg(LLMCall.tokens_prompt).label("avg_prompt_tokens"),
            func.avg(LLMCall.tokens_completion).label("avg_completion_tokens"),
        ).where(
            LLMCall.workspace_id == workspace_id,
            LLMCall.timestamp >= start_date,
        )
        
        result_token_breakdown = await self.session.execute(stmt_token_breakdown)
        token_row = result_token_breakdown.first()
        
        token_breakdown = {
            "total_prompt_tokens": int(token_row.total_prompt_tokens) if token_row.total_prompt_tokens else 0,
            "total_completion_tokens": int(token_row.total_completion_tokens) if token_row.total_completion_tokens else 0,
            "avg_prompt_tokens": float(token_row.avg_prompt_tokens) if token_row.avg_prompt_tokens else 0.0,
            "avg_completion_tokens": float(token_row.avg_completion_tokens) if token_row.avg_completion_tokens else 0.0,
        }
        
        # Calculate prompt/completion ratio
        if token_breakdown["total_prompt_tokens"] + token_breakdown["total_completion_tokens"] > 0:
            total = token_breakdown["total_prompt_tokens"] + token_breakdown["total_completion_tokens"]
            token_breakdown["prompt_ratio"] = token_breakdown["total_prompt_tokens"] / total
            token_breakdown["completion_ratio"] = token_breakdown["total_completion_tokens"] / total
        else:
            token_breakdown["prompt_ratio"] = 0.0
            token_breakdown["completion_ratio"] = 0.0
        
        return {
            "period": period,
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "token_breakdown": token_breakdown,
            "call_count": call_count,
            "by_model": by_model,
        }
    
    async def analyze_token_usage_patterns(
        self,
        workspace_id: str,
        period: str = "month",
    ) -> Dict:
        """
        Analyze token usage patterns for optimization recommendations.
        
        Args:
            workspace_id: Workspace identifier
            period: Time period to analyze
        
        Returns:
            Dictionary with usage patterns and recommendations
        """
        # Calculate time range
        now = datetime.utcnow()
        if period == "day":
            start_date = now - timedelta(days=1)
        elif period == "week":
            start_date = now - timedelta(weeks=1)
        elif period == "month":
            start_date = now - timedelta(days=30)
        else:
            start_date = datetime(2000, 1, 1)
        
        # Get token usage statistics
        stmt = select(
            func.avg(LLMCall.tokens_prompt).label("avg_prompt"),
            func.avg(LLMCall.tokens_completion).label("avg_completion"),
            func.avg(LLMCall.tokens_total).label("avg_total"),
            func.max(LLMCall.tokens_total).label("max_total"),
            func.min(LLMCall.tokens_total).label("min_total"),
            func.count(LLMCall.id).label("call_count"),
        ).where(
            LLMCall.workspace_id == workspace_id,
            LLMCall.timestamp >= start_date,
        )
        
        result = await self.session.execute(stmt)
        row = result.first()
        
        if not row or row.call_count == 0:
            return {
                "patterns": {},
                "anomalies": [],
                "recommendations": [],
            }
        
        avg_prompt = float(row.avg_prompt) if row.avg_prompt else 0.0
        avg_completion = float(row.avg_completion) if row.avg_completion else 0.0
        avg_total = float(row.avg_total) if row.avg_total else 0.0
        max_total = int(row.max_total) if row.max_total else 0
        min_total = int(row.min_total) if row.min_total else 0
        
        # Detect anomalies (calls with unusually high token usage)
        anomaly_threshold = avg_total * 3  # 3x average is considered anomaly
        stmt_anomalies = select(LLMCall).where(
            LLMCall.workspace_id == workspace_id,
            LLMCall.timestamp >= start_date,
            LLMCall.tokens_total > anomaly_threshold,
        ).order_by(LLMCall.tokens_total.desc()).limit(10)
        
        result_anomalies = await self.session.execute(stmt_anomalies)
        anomalies = []
        for call in result_anomalies.scalars():
            anomalies.append({
                "id": call.id,
                "timestamp": call.timestamp.isoformat(),
                "provider": call.provider,
                "model": call.model,
                "tokens_total": call.tokens_total,
                "tokens_prompt": call.tokens_prompt,
                "tokens_completion": call.tokens_completion,
                "cost_usd": call.cost_usd,
            })
        
        # Generate recommendations
        recommendations = []
        
        # High prompt token usage
        if avg_prompt > 2000:
            recommendations.append({
                "type": "high_prompt_tokens",
                "priority": "medium",
                "message": f"Average prompt tokens ({avg_prompt:.0f}) is high. Consider prompt optimization or compression.",
                "current_value": avg_prompt,
                "target_value": 1500,
            })
        
        # High completion token usage
        if avg_completion > 2000:
            recommendations.append({
                "type": "high_completion_tokens",
                "priority": "medium",
                "message": f"Average completion tokens ({avg_completion:.0f}) is high. Consider setting max_tokens limits.",
                "current_value": avg_completion,
                "target_value": 1500,
            })
        
        # High prompt/completion ratio (mostly prompt)
        if avg_prompt > 0 and avg_completion > 0:
            ratio = avg_prompt / avg_completion
            if ratio > 3.0:
                recommendations.append({
                    "type": "high_prompt_ratio",
                    "priority": "low",
                    "message": f"Prompt/completion ratio ({ratio:.2f}) is high. Consider optimizing prompts.",
                    "current_ratio": ratio,
                    "target_ratio": 2.0,
                })
        
        # Anomalies detected
        if anomalies:
            recommendations.append({
                "type": "token_anomalies",
                "priority": "high",
                "message": f"Found {len(anomalies)} calls with unusually high token usage. Review these calls.",
                "anomaly_count": len(anomalies),
            })
        
        return {
            "patterns": {
                "avg_prompt_tokens": avg_prompt,
                "avg_completion_tokens": avg_completion,
                "avg_total_tokens": avg_total,
                "max_tokens": max_total,
                "min_tokens": min_total,
                "total_calls": int(row.call_count),
            },
            "anomalies": anomalies,
            "recommendations": recommendations,
        }
    
    async def get_token_optimization_recommendations(
        self,
        workspace_id: str,
    ) -> List[Dict]:
        """
        Get token optimization recommendations.
        
        Args:
            workspace_id: Workspace identifier
        
        Returns:
            List of optimization recommendations
        """
        patterns = await self.analyze_token_usage_patterns(workspace_id)
        return patterns.get("recommendations", [])

    async def get_daily_costs(
        self,
        workspace_id: str,
        days: int = 30,
    ) -> List[Dict]:
        """
        Get daily cost breakdown for a workspace.
        
        Args:
            workspace_id: Workspace identifier
            days: Number of days to retrieve
        
        Returns:
            List of daily cost summaries
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        stmt = select(
            func.date(LLMCall.timestamp).label("date"),
            func.sum(LLMCall.cost_usd).label("cost"),
            func.sum(LLMCall.tokens_total).label("tokens"),
            func.count(LLMCall.id).label("calls"),
        ).where(
            LLMCall.workspace_id == workspace_id,
            LLMCall.timestamp >= start_date,
        ).group_by(
            func.date(LLMCall.timestamp)
        ).order_by(
            func.date(LLMCall.timestamp)
        )
        
        result = await self.session.execute(stmt)
        
        daily_costs = []
        for row in result:
            daily_costs.append({
                "date": row.date.isoformat() if row.date else None,
                "cost": float(row.cost) if row.cost else 0.0,
                "tokens": int(row.tokens) if row.tokens else 0,
                "calls": int(row.calls) if row.calls else 0,
            })
        
        return daily_costs


# Global tracker instance
_tracker: Optional[LLMCostTracker] = None


def get_llm_tracker(session: AsyncSession) -> LLMCostTracker:
    """
    Get LLM cost tracker instance.
    
    Args:
        session: Database session
    
    Returns:
        LLMCostTracker instance
    """
    return LLMCostTracker(session)
