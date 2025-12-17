# -*- coding: utf-8 -*-
"""Budget management service for workspace and project budgets."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.entities import (
    WorkspaceBudget,
    ProjectBudget,
    LLMCall,
    ResourceUsage,
)
from backend.db.models.enums import BudgetAlertType

logger = logging.getLogger(__name__)


class BudgetManager:
    """
    Service for managing budgets and alerts.
    
    Handles:
    - Creating and updating workspace/project budgets
    - Checking budget thresholds
    - Sending budget alerts
    - Budget enforcement
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the budget manager.
        
        Args:
            session: Database session for persistence
        """
        self.session = session

    async def create_workspace_budget(
        self,
        workspace_id: str,
        monthly_budget_usd: float,
        alert_threshold_percent: int = 80,
        alert_emails: Optional[List[str]] = None,
        hard_limit: bool = False,
    ) -> WorkspaceBudget:
        """
        Create or update workspace budget.
        
        Args:
            workspace_id: Workspace identifier
            monthly_budget_usd: Monthly budget limit in USD
            alert_threshold_percent: Alert threshold percentage
            alert_emails: Email addresses for alerts
            hard_limit: Whether to enforce hard limit
        
        Returns:
            Created or updated WorkspaceBudget
        """
        # Check if budget already exists
        stmt = select(WorkspaceBudget).where(
            WorkspaceBudget.workspace_id == workspace_id
        )
        result = await self.session.execute(stmt)
        budget = result.scalar_one_or_none()
        
        now = datetime.utcnow()
        
        if budget:
            # Update existing budget
            budget.monthly_budget_usd = monthly_budget_usd
            budget.alert_threshold_percent = alert_threshold_percent
            budget.alert_emails = alert_emails or []
            budget.hard_limit = hard_limit
            budget.is_enabled = True
        else:
            # Create new budget
            budget = WorkspaceBudget(
                workspace_id=workspace_id,
                monthly_budget_usd=monthly_budget_usd,
                alert_threshold_percent=alert_threshold_percent,
                alert_emails=alert_emails or [],
                hard_limit=hard_limit,
                budget_period_start=now,
                budget_period_end=now + timedelta(days=30),
            )
            self.session.add(budget)
        
        await self.session.commit()
        await self.session.refresh(budget)
        
        logger.info(
            f"{'Updated' if budget else 'Created'} workspace budget: "
            f"workspace={workspace_id}, budget=${monthly_budget_usd:.2f}"
        )
        
        return budget

    async def create_project_budget(
        self,
        project_id: str,
        workspace_id: str,
        monthly_budget_usd: float,
    ) -> ProjectBudget:
        """
        Create or update project budget.
        
        Args:
            project_id: Project identifier
            workspace_id: Workspace identifier
            monthly_budget_usd: Monthly budget limit in USD
        
        Returns:
            Created or updated ProjectBudget
        """
        # Check if budget already exists
        stmt = select(ProjectBudget).where(
            ProjectBudget.project_id == project_id
        )
        result = await self.session.execute(stmt)
        budget = result.scalar_one_or_none()
        
        if budget:
            # Update existing budget
            budget.monthly_budget_usd = monthly_budget_usd
            budget.is_enabled = True
        else:
            # Create new budget
            budget = ProjectBudget(
                project_id=project_id,
                workspace_id=workspace_id,
                monthly_budget_usd=monthly_budget_usd,
            )
            self.session.add(budget)
        
        await self.session.commit()
        await self.session.refresh(budget)
        
        logger.info(
            f"{'Updated' if budget else 'Created'} project budget: "
            f"project={project_id}, budget=${monthly_budget_usd:.2f}"
        )
        
        return budget

    async def get_workspace_budget(
        self,
        workspace_id: str,
    ) -> Optional[WorkspaceBudget]:
        """
        Get workspace budget.
        
        Args:
            workspace_id: Workspace identifier
        
        Returns:
            WorkspaceBudget or None
        """
        stmt = select(WorkspaceBudget).where(
            WorkspaceBudget.workspace_id == workspace_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_workspace_spending(
        self,
        workspace_id: str,
    ) -> Optional[WorkspaceBudget]:
        """
        Update workspace budget with current month's spending.
        
        Args:
            workspace_id: Workspace identifier
        
        Returns:
            Updated WorkspaceBudget or None
        """
        budget = await self.get_workspace_budget(workspace_id)
        if not budget:
            logger.warning(f"No budget found for workspace: {workspace_id}")
            return None
        
        # Calculate start of current month
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Calculate LLM costs for current month
        from sqlalchemy import func, select
        
        stmt_llm = select(func.sum(LLMCall.cost_usd)).where(
            LLMCall.workspace_id == workspace_id,
            LLMCall.timestamp >= month_start,
        )
        result_llm = await self.session.execute(stmt_llm)
        llm_cost = result_llm.scalar() or 0.0
        
        # Calculate compute costs for current month
        stmt_compute = select(func.sum(ResourceUsage.cost_usd)).where(
            ResourceUsage.workspace_id == workspace_id,
            ResourceUsage.timestamp >= month_start,
        )
        result_compute = await self.session.execute(stmt_compute)
        compute_cost = result_compute.scalar() or 0.0
        
        # Update budget
        total_spent = float(llm_cost) + float(compute_cost)
        budget.current_month_spent = total_spent
        
        await self.session.commit()
        await self.session.refresh(budget)
        
        logger.info(
            f"Updated workspace spending: workspace={workspace_id}, "
            f"spent=${total_spent:.2f}, budget=${budget.monthly_budget_usd:.2f}"
        )
        
        return budget

    async def check_budget_threshold(
        self,
        workspace_id: str,
    ) -> Dict:
        """
        Check if budget threshold has been reached.
        
        Args:
            workspace_id: Workspace identifier
        
        Returns:
            Dictionary with budget status and alert info
        """
        # Update spending
        budget = await self.update_workspace_spending(workspace_id)
        
        if not budget or not budget.is_enabled:
            return {
                "has_budget": False,
                "alert_needed": False,
            }
        
        usage_percent = budget.budget_used_percent
        
        # Determine alert level
        alert_type = None
        if usage_percent >= 100:
            alert_type = BudgetAlertType.THRESHOLD_100
        elif usage_percent >= 90:
            alert_type = BudgetAlertType.THRESHOLD_90
        elif usage_percent >= budget.alert_threshold_percent:
            alert_type = BudgetAlertType.THRESHOLD_80
        
        alert_needed = alert_type is not None
        
        # Check if alert already sent
        if alert_needed and alert_type:
            alerts_sent = budget.alerts_sent or []
            alert_key = f"{alert_type.value}_{datetime.utcnow().strftime('%Y-%m')}"
            already_sent = alert_key in alerts_sent
            
            if already_sent:
                alert_needed = False
        
        return {
            "has_budget": True,
            "budget": budget.monthly_budget_usd,
            "spent": budget.current_month_spent,
            "remaining": budget.budget_remaining,
            "usage_percent": usage_percent,
            "alert_needed": alert_needed,
            "alert_type": alert_type.value if alert_type else None,
            "is_over_budget": budget.is_over_budget,
            "hard_limit": budget.hard_limit,
        }

    async def send_budget_alert(
        self,
        workspace_id: str,
        alert_type: BudgetAlertType,
    ) -> bool:
        """
        Send budget alert and record it.
        
        Args:
            workspace_id: Workspace identifier
            alert_type: Type of alert to send
        
        Returns:
            True if alert sent successfully
        """
        budget = await self.get_workspace_budget(workspace_id)
        if not budget:
            return False
        
        # Record alert
        alerts_sent = budget.alerts_sent or []
        alert_key = f"{alert_type.value}_{datetime.utcnow().strftime('%Y-%m')}"
        
        if alert_key not in alerts_sent:
            alerts_sent.append(alert_key)
            budget.alerts_sent = alerts_sent
            budget.last_alert_at = datetime.utcnow()
            
            await self.session.commit()
            
            logger.warning(
                f"Budget alert sent: workspace={workspace_id}, "
                f"alert_type={alert_type.value}, "
                f"spent=${budget.current_month_spent:.2f}, "
                f"budget=${budget.monthly_budget_usd:.2f}"
            )
            
            # TODO: Implement actual email/notification sending
            # For now, just log the alert
            return True
        
        return False

    async def check_and_alert(
        self,
        workspace_id: str,
    ) -> Dict:
        """
        Check budget and send alert if needed.
        
        Args:
            workspace_id: Workspace identifier
        
        Returns:
            Dictionary with check results
        """
        status = await self.check_budget_threshold(workspace_id)
        
        if status["alert_needed"]:
            alert_type = BudgetAlertType(status["alert_type"])
            alert_sent = await self.send_budget_alert(workspace_id, alert_type)
            status["alert_sent"] = alert_sent
        else:
            status["alert_sent"] = False
        
        return status

    async def can_execute(
        self,
        workspace_id: str,
        estimated_cost: float = 0.0,
    ) -> Dict:
        """
        Check if execution can proceed within budget.
        
        Args:
            workspace_id: Workspace identifier
            estimated_cost: Estimated cost of execution
        
        Returns:
            Dictionary with execution permission and reason
        """
        budget = await self.get_workspace_budget(workspace_id)
        
        if not budget or not budget.is_enabled:
            return {
                "can_execute": True,
                "reason": "No budget limit set",
            }
        
        # Update spending
        await self.update_workspace_spending(workspace_id)
        await self.session.refresh(budget)
        
        if not budget.hard_limit:
            return {
                "can_execute": True,
                "reason": "Soft limit - execution allowed",
                "budget_warning": budget.is_over_budget,
            }
        
        projected_cost = budget.current_month_spent + estimated_cost
        
        if projected_cost > budget.monthly_budget_usd:
            return {
                "can_execute": False,
                "reason": "Budget exceeded - hard limit enforced",
                "budget": budget.monthly_budget_usd,
                "spent": budget.current_month_spent,
                "estimated_cost": estimated_cost,
                "projected_total": projected_cost,
            }
        
        return {
            "can_execute": True,
            "reason": "Within budget",
            "budget": budget.monthly_budget_usd,
            "spent": budget.current_month_spent,
            "remaining": budget.budget_remaining,
        }


# Global manager instance
_manager: Optional[BudgetManager] = None


def get_budget_manager(session: AsyncSession) -> BudgetManager:
    """
    Get budget manager instance.
    
    Args:
        session: Database session
    
    Returns:
        BudgetManager instance
    """
    return BudgetManager(session)
