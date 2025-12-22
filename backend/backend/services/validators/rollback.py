# -*- coding: utf-8 -*-
"""Rollback validation."""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from .base import BaseValidator, ValidationResult


@dataclass
class RollbackValidation:
    """Rollback validation result."""
    
    from_version: str
    to_version: str
    validation_passed: bool = False
    
    previous_version_available: bool = False
    database_rollback_valid: bool = False
    within_sla_window: bool = False
    
    procedure_steps: List[str] = field(default_factory=list)
    manual_steps: List[str] = field(default_factory=list)
    database_rollback_steps: List[str] = field(default_factory=list)
    
    estimated_rollback_time_minutes: int = 0
    issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "from_version": self.from_version,
            "to_version": self.to_version,
            "validation_passed": self.validation_passed,
            "previous_version_available": self.previous_version_available,
            "database_rollback_valid": self.database_rollback_valid,
            "within_sla_window": self.within_sla_window,
            "procedure_steps": self.procedure_steps,
            "manual_steps": self.manual_steps,
            "database_rollback_steps": self.database_rollback_steps,
            "estimated_rollback_time_minutes": self.estimated_rollback_time_minutes,
            "issues": self.issues,
        }


class RollbackValidator(BaseValidator):
    """Validates rollback procedures."""
    
    MAX_ROLLBACK_TIME_MINUTES = 30  # SLA for rollback
    
    async def validate_rollback_plan(
        self,
        validation_id: str,
        from_version: str,
        to_version: str,
        artifacts: Dict[str, Any],
    ) -> RollbackValidation:
        """Validate rollback plan."""
        rollback = RollbackValidation(
            from_version=from_version,
            to_version=to_version,
        )
        
        try:
            # Check previous version availability
            await self._check_version_availability(rollback, to_version, artifacts)
            
            # Check database rollback procedure
            await self._check_database_rollback(rollback, artifacts)
            
            # Check rollback SLA
            await self._check_rollback_sla(rollback)
            
            # Build procedure steps
            await self._build_rollback_procedure(rollback)
            
            # Check manual intervention steps
            await self._identify_manual_steps(rollback)
            
            # Overall validation
            rollback.validation_passed = (
                rollback.previous_version_available and
                rollback.database_rollback_valid and
                rollback.within_sla_window and
                len(rollback.issues) == 0
            )
            
        except Exception as e:
            rollback.issues.append(str(e))
            self.logger.error(f"Rollback validation failed: {e}")
        
        return rollback
    
    async def _check_version_availability(
        self,
        rollback: RollbackValidation,
        target_version: str,
        artifacts: Dict[str, Any],
    ) -> None:
        """Check if target version image is available."""
        images = artifacts.get("docker_images", {})
        
        if target_version in images:
            rollback.previous_version_available = True
            self.logger.info(f"Previous version {target_version} is available")
        else:
            rollback.issues.append(f"Previous version image {target_version} not found")
            self.logger.warning(f"Previous version {target_version} not available")
    
    async def _check_database_rollback(
        self,
        rollback: RollbackValidation,
        artifacts: Dict[str, Any],
    ) -> None:
        """Check database rollback procedure."""
        db_plan = artifacts.get("database_rollback_plan", {})
        
        if not db_plan:
            rollback.database_rollback_valid = False
            rollback.issues.append("No database rollback plan provided")
            return
        
        # Check required fields
        required_fields = ["backup_available", "rollback_script", "estimated_time"]
        missing_fields = [f for f in required_fields if f not in db_plan]
        
        if missing_fields:
            rollback.issues.append(f"Database rollback plan missing: {', '.join(missing_fields)}")
            return
        
        # Validate backup
        backup_available = db_plan.get("backup_available", False)
        if not backup_available:
            rollback.issues.append("Database backup not available for rollback")
            return
        
        rollback.database_rollback_valid = True
        rollback.database_rollback_steps = db_plan.get("steps", [])
        
        self.logger.info("Database rollback plan is valid")
    
    async def _check_rollback_sla(self, rollback: RollbackValidation) -> None:
        """Check if rollback can be done within SLA."""
        estimated_time = 0
        
        # Estimate from procedure steps
        rollback.procedure_steps = [
            "Stop current version deployment",
            "Scale down new version replicas",
            "Restore database from backup",
            "Update service to route to previous version",
            "Run health checks",
            "Verify application state",
        ]
        
        # Rough estimate: 2-3 minutes per major step
        estimated_time = len(rollback.procedure_steps) * 3
        
        if rollback.database_rollback_steps:
            estimated_time += 10  # Add time for database rollback
        
        rollback.estimated_rollback_time_minutes = estimated_time
        
        if estimated_time <= self.MAX_ROLLBACK_TIME_MINUTES:
            rollback.within_sla_window = True
            self.logger.info(f"Rollback within SLA window: {estimated_time} minutes")
        else:
            rollback.issues.append(f"Rollback takes {estimated_time} minutes, exceeds SLA of {self.MAX_ROLLBACK_TIME_MINUTES} minutes")
            self.logger.warning(f"Rollback exceeds SLA: {estimated_time} > {self.MAX_ROLLBACK_TIME_MINUTES}")
    
    async def _build_rollback_procedure(self, rollback: RollbackValidation) -> None:
        """Build detailed rollback procedure."""
        # Already set in _check_rollback_sla
        pass
    
    async def _identify_manual_steps(self, rollback: RollbackValidation) -> None:
        """Identify steps requiring manual intervention."""
        rollback.manual_steps = [
            "Verify data integrity after rollback",
            "Monitor application metrics for 5 minutes",
            "Notify stakeholders of rollback completion",
            "Document rollback cause and lessons learned",
        ]
        
        self.logger.info(f"Identified {len(rollback.manual_steps)} manual intervention steps")
