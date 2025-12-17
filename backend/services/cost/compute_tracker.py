# -*- coding: utf-8 -*-
"""Compute resource usage tracking service."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.entities import ResourceUsage
from backend.db.models.enums import ResourceType

logger = logging.getLogger(__name__)


# Resource pricing configuration (USD)
RESOURCE_PRICING = {
    "cpu": {
        "unit": "core-hour",
        "cost_per_unit": 0.05,  # $0.05 per core-hour
    },
    "memory": {
        "unit": "gb-hour",
        "cost_per_unit": 0.01,  # $0.01 per GB-hour
    },
    "gpu": {
        "unit": "gpu-hour",
        "cost_per_unit": 1.50,  # $1.50 per GPU-hour
    },
    "storage": {
        "unit": "gb-month",
        "cost_per_unit": 0.10,  # $0.10 per GB-month
    },
    "bandwidth": {
        "unit": "gb",
        "cost_per_unit": 0.12,  # $0.12 per GB
    },
    "sandbox": {
        "unit": "execution-minute",
        "cost_per_unit": 0.002,  # $0.002 per minute
    },
    "database": {
        "unit": "operation",
        "cost_per_unit": 0.00001,  # $0.00001 per operation
    },
}


class ComputeTracker:
    """
    Service for tracking compute resource usage and costs.
    
    Handles:
    - Logging resource usage (CPU, memory, GPU, storage, etc.)
    - Calculating resource costs
    - Aggregating usage by workspace, project, execution
    - Generating usage summaries
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the compute tracker.
        
        Args:
            session: Database session for persistence
        """
        self.session = session

    def calculate_resource_cost(
        self,
        resource_type: str,
        usage_value: float,
        duration_seconds: Optional[float] = None,
    ) -> float:
        """
        Calculate the cost of resource usage.
        
        Args:
            resource_type: Type of resource (cpu, memory, gpu, etc.)
            usage_value: Amount of resource used
            duration_seconds: Duration of usage in seconds
        
        Returns:
            Total cost in USD
        """
        resource_lower = resource_type.lower()
        
        if resource_lower not in RESOURCE_PRICING:
            logger.warning(f"Unknown resource type: {resource_type}, using default pricing")
            return usage_value * 0.01  # Default: $0.01 per unit
        
        pricing = RESOURCE_PRICING[resource_lower]
        cost_per_unit = pricing["cost_per_unit"]
        
        # For time-based resources, convert duration to hours
        if duration_seconds is not None and "hour" in pricing["unit"]:
            hours = duration_seconds / 3600
            cost = usage_value * hours * cost_per_unit
        elif duration_seconds is not None and "minute" in pricing["unit"]:
            minutes = duration_seconds / 60
            cost = minutes * cost_per_unit
        else:
            cost = usage_value * cost_per_unit
        
        logger.debug(
            f"Resource cost calculation: {resource_type} - "
            f"{usage_value} {pricing['unit']}, ${cost:.6f}"
        )
        
        return cost

    async def log_resource_usage(
        self,
        workspace_id: str,
        execution_id: str,
        resource_type: str,
        usage_value: float,
        unit: str,
        duration_seconds: Optional[float] = None,
        metadata: Optional[Dict] = None,
    ) -> ResourceUsage:
        """
        Log compute resource usage.
        
        Args:
            workspace_id: Workspace identifier
            execution_id: Execution identifier
            resource_type: Type of resource (cpu, memory, gpu, etc.)
            usage_value: Amount of resource used
            unit: Unit of measurement
            duration_seconds: Duration of usage in seconds
            metadata: Additional metadata
        
        Returns:
            Created ResourceUsage record
        """
        cost_usd = self.calculate_resource_cost(resource_type, usage_value, duration_seconds)
        
        resource_usage = ResourceUsage(
            workspace_id=workspace_id,
            execution_id=execution_id,
            resource_type=resource_type,
            usage_value=usage_value,
            unit=unit,
            cost_usd=cost_usd,
            duration_seconds=duration_seconds,
            usage_metadata=metadata or {},
        )
        
        self.session.add(resource_usage)
        await self.session.commit()
        await self.session.refresh(resource_usage)
        
        logger.info(
            f"Logged resource usage: {resource_type} - "
            f"{usage_value} {unit}, ${cost_usd:.4f} - "
            f"workspace={workspace_id}, execution={execution_id}"
        )
        
        return resource_usage

    async def track_sandbox_execution(
        self,
        workspace_id: str,
        execution_id: str,
        cpu_cores: float,
        memory_mb: int,
        duration_seconds: float,
    ) -> List[ResourceUsage]:
        """
        Track resource usage for a sandbox execution.
        
        Args:
            workspace_id: Workspace identifier
            execution_id: Execution identifier
            cpu_cores: Number of CPU cores used
            memory_mb: Memory used in MB
            duration_seconds: Execution duration in seconds
        
        Returns:
            List of created ResourceUsage records
        """
        records = []
        
        # Track CPU usage
        cpu_record = await self.log_resource_usage(
            workspace_id=workspace_id,
            execution_id=execution_id,
            resource_type="cpu",
            usage_value=cpu_cores,
            unit="cores",
            duration_seconds=duration_seconds,
            metadata={"source": "sandbox"},
        )
        records.append(cpu_record)
        
        # Track memory usage (convert MB to GB)
        memory_gb = memory_mb / 1024
        memory_record = await self.log_resource_usage(
            workspace_id=workspace_id,
            execution_id=execution_id,
            resource_type="memory",
            usage_value=memory_gb,
            unit="gb",
            duration_seconds=duration_seconds,
            metadata={"source": "sandbox", "mb": memory_mb},
        )
        records.append(memory_record)
        
        # Track sandbox execution time
        sandbox_record = await self.log_resource_usage(
            workspace_id=workspace_id,
            execution_id=execution_id,
            resource_type="sandbox",
            usage_value=1,
            unit="execution",
            duration_seconds=duration_seconds,
            metadata={"source": "sandbox", "cpu_cores": cpu_cores, "memory_mb": memory_mb},
        )
        records.append(sandbox_record)
        
        logger.info(
            f"Tracked sandbox execution: {cpu_cores} cores, {memory_mb}MB, "
            f"{duration_seconds:.2f}s - execution={execution_id}"
        )
        
        return records

    async def get_execution_compute_costs(
        self,
        execution_id: str,
    ) -> Dict:
        """
        Get aggregated compute costs for an execution.
        
        Args:
            execution_id: Execution identifier
        
        Returns:
            Dictionary with cost summary
        """
        stmt = select(
            func.sum(ResourceUsage.cost_usd).label("total_cost"),
            func.count(ResourceUsage.id).label("record_count"),
        ).where(ResourceUsage.execution_id == execution_id)
        
        result = await self.session.execute(stmt)
        row = result.first()
        
        if not row or row.total_cost is None:
            return {
                "total_cost": 0.0,
                "record_count": 0,
            }
        
        # Get breakdown by resource type
        stmt_by_type = select(
            ResourceUsage.resource_type,
            func.sum(ResourceUsage.cost_usd).label("cost"),
            func.sum(ResourceUsage.usage_value).label("usage"),
        ).where(
            ResourceUsage.execution_id == execution_id
        ).group_by(
            ResourceUsage.resource_type
        )
        
        result_by_type = await self.session.execute(stmt_by_type)
        by_type = {}
        for row in result_by_type:
            by_type[row.resource_type] = {
                "cost": float(row.cost),
                "usage": float(row.usage),
            }
        
        return {
            "total_cost": float(row.total_cost),
            "record_count": int(row.record_count),
            "by_type": by_type,
        }

    async def get_workspace_usage(
        self,
        workspace_id: str,
        period: str = "month",
    ) -> Dict:
        """
        Get aggregated resource usage for a workspace.
        
        Args:
            workspace_id: Workspace identifier
            period: Time period (day, week, month, all)
        
        Returns:
            Dictionary with usage summary and breakdown
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
            func.sum(ResourceUsage.cost_usd).label("total_cost"),
            func.count(ResourceUsage.id).label("record_count"),
        ).where(
            ResourceUsage.workspace_id == workspace_id,
            ResourceUsage.timestamp >= start_date,
        )
        
        result = await self.session.execute(stmt)
        row = result.first()
        
        total_cost = float(row.total_cost) if row.total_cost else 0.0
        record_count = int(row.record_count) if row.record_count else 0
        
        # Get usage breakdown by resource type
        stmt_by_type = select(
            ResourceUsage.resource_type,
            func.sum(ResourceUsage.cost_usd).label("cost"),
            func.sum(ResourceUsage.usage_value).label("usage"),
            func.count(ResourceUsage.id).label("count"),
        ).where(
            ResourceUsage.workspace_id == workspace_id,
            ResourceUsage.timestamp >= start_date,
        ).group_by(
            ResourceUsage.resource_type
        )
        
        result_by_type = await self.session.execute(stmt_by_type)
        by_type = []
        for row in result_by_type:
            by_type.append({
                "resource_type": row.resource_type,
                "cost": float(row.cost),
                "usage": float(row.usage),
                "count": int(row.count),
            })
        
        return {
            "period": period,
            "total_cost": total_cost,
            "record_count": record_count,
            "by_type": by_type,
        }


# Global tracker instance
_tracker: Optional[ComputeTracker] = None


def get_compute_tracker(session: AsyncSession) -> ComputeTracker:
    """
    Get compute tracker instance.
    
    Args:
        session: Database session
    
    Returns:
        ComputeTracker instance
    """
    return ComputeTracker(session)
