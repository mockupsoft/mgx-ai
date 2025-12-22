# -*- coding: utf-8 -*-
"""Pre-deployment checklist."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

from .base import BaseValidator, ValidationResult


@dataclass
class ChecklistItem:
    """Single checklist item."""
    
    name: str
    status: str = "pending"  # pending, pass, fail, manual, not_applicable
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status,
            "description": self.description,
            "details": self.details,
            "assignee": self.assignee,
            "due_date": self.due_date,
        }


class PreDeploymentChecklist:
    """Pre-deployment checklist."""
    
    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
        self.items: List[ChecklistItem] = []
    
    def add_item(
        self,
        name: str,
        description: str = "",
        status: str = "pending",
        assignee: Optional[str] = None,
    ) -> None:
        """Add a checklist item."""
        item = ChecklistItem(
            name=name,
            description=description,
            status=status,
            assignee=assignee,
        )
        self.items.append(item)
    
    def set_item_status(self, item_name: str, status: str) -> None:
        """Set status of a checklist item."""
        for item in self.items:
            if item.name == item_name:
                item.status = status
                break
    
    def build_default_checklist(self) -> None:
        """Build default pre-deployment checklist."""
        self.items = [
            ChecklistItem(
                name="docker_image_valid",
                description="Docker image passed all validation checks",
                status="pending",
            ),
            ChecklistItem(
                name="k8s_manifests_valid",
                description="Kubernetes manifests are valid and properly configured",
                status="pending",
            ),
            ChecklistItem(
                name="health_checks_pass",
                description="Health checks configured and passing",
                status="pending",
            ),
            ChecklistItem(
                name="security_validation_passed",
                description="Security validation passed all checks",
                status="pending",
            ),
            ChecklistItem(
                name="configuration_complete",
                description="All required configuration is complete and valid",
                status="pending",
            ),
            ChecklistItem(
                name="backup_plan",
                description="Data backup plan in place",
                status="pending",
                assignee="ops-team",
            ),
            ChecklistItem(
                name="rollback_procedure",
                description="Rollback procedure documented and tested",
                status="pending",
                assignee="ops-team",
            ),
            ChecklistItem(
                name="monitoring_configured",
                description="Monitoring and alerting configured",
                status="pending",
                assignee="devops-team",
            ),
            ChecklistItem(
                name="load_testing_passed",
                description="Load testing completed and passed",
                status="pending",
                assignee="qa-team",
            ),
            ChecklistItem(
                name="security_review_approved",
                description="Security review approved (manual verification)",
                status="pending",
                assignee="security-team",
            ),
            ChecklistItem(
                name="deployment_window_scheduled",
                description="Deployment window scheduled and communicated",
                status="pending",
                assignee="ops-team",
            ),
            ChecklistItem(
                name="stakeholder_approval",
                description="Stakeholder approval obtained",
                status="pending",
                assignee="project-manager",
            ),
        ]
    
    def all_passed(self) -> bool:
        """Check if all items passed."""
        for item in self.items:
            if item.status not in ["pass", "not_applicable"]:
                return False
        return True
    
    def get_status_summary(self) -> Dict[str, int]:
        """Get count of items by status."""
        summary = {
            "pending": 0,
            "pass": 0,
            "fail": 0,
            "manual": 0,
            "not_applicable": 0,
        }
        
        for item in self.items:
            if item.status in summary:
                summary[item.status] += 1
        
        return summary
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "workspace_id": self.workspace_id,
            "total_items": len(self.items),
            "all_passed": self.all_passed(),
            "status_summary": self.get_status_summary(),
            "items": [item.to_dict() for item in self.items],
        }
