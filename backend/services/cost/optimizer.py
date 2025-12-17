# -*- coding: utf-8 -*-
"""Cost optimization service for analyzing and recommending cost reductions."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.entities import LLMCall, ResourceUsage, ExecutionCost

logger = logging.getLogger(__name__)


class CostOptimizer:
    """
    Service for analyzing costs and providing optimization recommendations.
    
    Handles:
    - Analyzing cost patterns
    - Identifying optimization opportunities
    - Generating actionable recommendations
    - Cost forecasting
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the cost optimizer.
        
        Args:
            session: Database session for queries
        """
        self.session = session

    async def get_recommendations(
        self,
        workspace_id: str,
        period: str = "month",
    ) -> List[Dict]:
        """
        Get cost optimization recommendations for a workspace.
        
        Args:
            workspace_id: Workspace identifier
            period: Time period to analyze (day, week, month)
        
        Returns:
            List of optimization recommendations
        """
        recommendations = []
        
        # Calculate time range
        now = datetime.utcnow()
        if period == "day":
            start_date = now - timedelta(days=1)
        elif period == "week":
            start_date = now - timedelta(weeks=1)
        else:  # month
            start_date = now - timedelta(days=30)
        
        # Analyze LLM usage patterns
        llm_recs = await self._analyze_llm_usage(workspace_id, start_date)
        recommendations.extend(llm_recs)
        
        # Analyze resource usage patterns
        resource_recs = await self._analyze_resource_usage(workspace_id, start_date)
        recommendations.extend(resource_recs)
        
        # Analyze execution patterns
        execution_recs = await self._analyze_execution_patterns(workspace_id, start_date)
        recommendations.extend(execution_recs)
        
        return recommendations

    async def _analyze_llm_usage(
        self,
        workspace_id: str,
        start_date: datetime,
    ) -> List[Dict]:
        """Analyze LLM usage and generate recommendations."""
        recommendations = []
        
        # Check for expensive model usage
        stmt = select(
            LLMCall.provider,
            LLMCall.model,
            func.count(LLMCall.id).label("call_count"),
            func.sum(LLMCall.cost_usd).label("total_cost"),
            func.avg(LLMCall.tokens_total).label("avg_tokens"),
        ).where(
            LLMCall.workspace_id == workspace_id,
            LLMCall.timestamp >= start_date,
        ).group_by(
            LLMCall.provider,
            LLMCall.model,
        ).order_by(
            func.sum(LLMCall.cost_usd).desc()
        )
        
        result = await self.session.execute(stmt)
        models = result.all()
        
        if not models:
            return recommendations
        
        # Check if using expensive models for simple tasks
        for model_row in models:
            provider = model_row.provider
            model = model_row.model
            call_count = model_row.call_count
            total_cost = float(model_row.total_cost)
            avg_tokens = float(model_row.avg_tokens)
            
            # GPT-4 optimization
            if "gpt-4" in model.lower() and "turbo" not in model.lower():
                if avg_tokens < 500:
                    recommendations.append({
                        "type": "model_downgrade",
                        "priority": "high",
                        "title": "Use GPT-4 Turbo for simple tasks",
                        "description": f"You're using {model} with average {avg_tokens:.0f} tokens. "
                                     f"Consider using gpt-4-turbo for 67% cost savings.",
                        "current_model": model,
                        "recommended_model": "gpt-4-turbo",
                        "estimated_savings": total_cost * 0.67,
                        "impact": f"${total_cost * 0.67:.2f}/month",
                    })
            
            # Claude Opus optimization
            if "opus" in model.lower():
                recommendations.append({
                    "type": "model_downgrade",
                    "priority": "medium",
                    "title": "Consider Claude Sonnet for better value",
                    "description": f"Claude Opus costs 5x more than Sonnet. "
                                 f"Test if Sonnet meets your needs for {call_count} calls.",
                    "current_model": model,
                    "recommended_model": "claude-3-sonnet",
                    "estimated_savings": total_cost * 0.80,
                    "impact": f"${total_cost * 0.80:.2f}/month",
                })
        
        # Check for high token usage
        stmt_tokens = select(
            func.sum(LLMCall.tokens_total).label("total_tokens"),
            func.count(LLMCall.id).label("call_count"),
        ).where(
            LLMCall.workspace_id == workspace_id,
            LLMCall.timestamp >= start_date,
        )
        
        result_tokens = await self.session.execute(stmt_tokens)
        tokens_row = result_tokens.first()
        
        if tokens_row and tokens_row.total_tokens:
            total_tokens = int(tokens_row.total_tokens)
            call_count = int(tokens_row.call_count)
            avg_tokens_per_call = total_tokens / call_count if call_count > 0 else 0
            
            if avg_tokens_per_call > 2000:
                recommendations.append({
                    "type": "token_optimization",
                    "priority": "medium",
                    "title": "Optimize prompt length",
                    "description": f"Average {avg_tokens_per_call:.0f} tokens per call. "
                                 f"Consider prompt optimization, caching, or summarization.",
                    "current_avg": avg_tokens_per_call,
                    "target_avg": 1500,
                    "estimated_savings_percent": 25,
                })
        
        return recommendations

    async def _analyze_resource_usage(
        self,
        workspace_id: str,
        start_date: datetime,
    ) -> List[Dict]:
        """Analyze resource usage and generate recommendations."""
        recommendations = []
        
        # Check for high CPU/memory usage
        stmt = select(
            ResourceUsage.resource_type,
            func.count(ResourceUsage.id).label("usage_count"),
            func.sum(ResourceUsage.cost_usd).label("total_cost"),
            func.avg(ResourceUsage.usage_value).label("avg_usage"),
        ).where(
            ResourceUsage.workspace_id == workspace_id,
            ResourceUsage.timestamp >= start_date,
        ).group_by(
            ResourceUsage.resource_type
        )
        
        result = await self.session.execute(stmt)
        resources = result.all()
        
        for resource_row in resources:
            resource_type = resource_row.resource_type
            total_cost = float(resource_row.total_cost)
            
            if resource_type == "sandbox" and total_cost > 10:
                recommendations.append({
                    "type": "sandbox_optimization",
                    "priority": "medium",
                    "title": "Optimize sandbox execution time",
                    "description": f"Sandbox executions cost ${total_cost:.2f}. "
                                 f"Consider caching results or optimizing execution time.",
                    "current_cost": total_cost,
                    "estimated_savings": total_cost * 0.30,
                })
        
        return recommendations

    async def _analyze_execution_patterns(
        self,
        workspace_id: str,
        start_date: datetime,
    ) -> List[Dict]:
        """Analyze execution patterns and generate recommendations."""
        recommendations = []
        
        # Check for execution frequency
        stmt = select(
            func.count(ExecutionCost.id).label("execution_count"),
            func.avg(ExecutionCost.total_cost).label("avg_cost"),
            func.sum(ExecutionCost.total_cost).label("total_cost"),
        ).where(
            ExecutionCost.workspace_id == workspace_id,
            ExecutionCost.timestamp >= start_date,
        )
        
        result = await self.session.execute(stmt)
        row = result.first()
        
        if row and row.execution_count:
            execution_count = int(row.execution_count)
            avg_cost = float(row.avg_cost)
            total_cost = float(row.total_cost)
            
            # High frequency executions
            days = (datetime.utcnow() - start_date).days or 1
            executions_per_day = execution_count / days
            
            if executions_per_day > 50 and avg_cost > 0.50:
                recommendations.append({
                    "type": "execution_batching",
                    "priority": "high",
                    "title": "Consider batching executions",
                    "description": f"Running {executions_per_day:.0f} executions/day at ${avg_cost:.2f} each. "
                                 f"Batching could reduce overhead costs by 20-30%.",
                    "current_frequency": executions_per_day,
                    "estimated_savings": total_cost * 0.25,
                })
            
            # High cost per execution
            if avg_cost > 5.0:
                recommendations.append({
                    "type": "execution_optimization",
                    "priority": "high",
                    "title": "High cost per execution detected",
                    "description": f"Average ${avg_cost:.2f} per execution. "
                                 f"Review execution plans and consider optimization.",
                    "avg_cost": avg_cost,
                    "target_cost": 2.0,
                })
        
        return recommendations

    async def forecast_monthly_cost(
        self,
        workspace_id: str,
    ) -> Dict:
        """
        Forecast end-of-month cost based on current trends.
        
        Args:
            workspace_id: Workspace identifier
        
        Returns:
            Dictionary with forecast data
        """
        # Get current month's data
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        days_elapsed = (now - month_start).days + 1
        
        # Calculate total days in month
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)
        total_days = (next_month - month_start).days
        
        # Get current month spending
        stmt_llm = select(func.sum(LLMCall.cost_usd)).where(
            LLMCall.workspace_id == workspace_id,
            LLMCall.timestamp >= month_start,
        )
        result_llm = await self.session.execute(stmt_llm)
        llm_cost = float(result_llm.scalar() or 0.0)
        
        stmt_compute = select(func.sum(ResourceUsage.cost_usd)).where(
            ResourceUsage.workspace_id == workspace_id,
            ResourceUsage.timestamp >= month_start,
        )
        result_compute = await self.session.execute(stmt_compute)
        compute_cost = float(result_compute.scalar() or 0.0)
        
        current_total = llm_cost + compute_cost
        
        # Simple linear forecast
        daily_avg = current_total / days_elapsed if days_elapsed > 0 else 0
        forecast_total = daily_avg * total_days
        
        # Calculate confidence (higher confidence with more data)
        confidence = min(days_elapsed / total_days, 0.95)
        
        return {
            "current_month_spent": current_total,
            "llm_cost": llm_cost,
            "compute_cost": compute_cost,
            "days_elapsed": days_elapsed,
            "total_days": total_days,
            "daily_average": daily_avg,
            "forecast_end_of_month": forecast_total,
            "forecast_confidence": confidence,
            "projection_accuracy": "low" if confidence < 0.3 else "medium" if confidence < 0.7 else "high",
        }


# Global optimizer instance
_optimizer: Optional[CostOptimizer] = None


def get_cost_optimizer(session: AsyncSession) -> CostOptimizer:
    """
    Get cost optimizer instance.
    
    Args:
        session: Database session
    
    Returns:
        CostOptimizer instance
    """
    return CostOptimizer(session)
