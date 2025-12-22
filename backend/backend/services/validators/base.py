# -*- coding: utf-8 -*-
"""Base validator classes and utilities."""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


class CheckStatus(str, Enum):
    """Status of a validation check."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class CheckResult:
    """Result of a single validation check."""
    
    name: str
    status: CheckStatus
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    remediation: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "description": self.description,
            "details": self.details,
            "error_message": self.error_message,
            "remediation": self.remediation,
        }


@dataclass
class ValidationResult:
    """Result of a validation run."""
    
    validation_id: str
    status: str
    passed_checks: int = 0
    failed_checks: int = 0
    warning_checks: int = 0
    total_checks: int = 0
    checks: List[CheckResult] = field(default_factory=list)
    error_message: Optional[str] = None
    
    def add_check(self, check: CheckResult) -> None:
        """Add a check result."""
        self.checks.append(check)
        self.total_checks += 1
        
        if check.status == CheckStatus.PASSED:
            self.passed_checks += 1
        elif check.status == CheckStatus.FAILED:
            self.failed_checks += 1
        elif check.status == CheckStatus.WARNING:
            self.warning_checks += 1
    
    def is_passing(self) -> bool:
        """Check if all critical checks passed."""
        return self.failed_checks == 0
    
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return self.warning_checks > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "validation_id": self.validation_id,
            "status": self.status,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "warning_checks": self.warning_checks,
            "total_checks": self.total_checks,
            "checks": [check.to_dict() for check in self.checks],
            "error_message": self.error_message,
        }


class BaseValidator:
    """Base class for validators."""
    
    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def validate(self) -> ValidationResult:
        """Run validation. Must be implemented by subclasses."""
        raise NotImplementedError
    
    def _create_result(self, validation_id: str, status: str) -> ValidationResult:
        """Create a validation result."""
        return ValidationResult(validation_id=validation_id, status=status)
    
    def _add_passed_check(
        self,
        result: ValidationResult,
        name: str,
        description: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a passed check."""
        check = CheckResult(
            name=name,
            status=CheckStatus.PASSED,
            description=description,
            details=details or {},
        )
        result.add_check(check)
        self.logger.info(f"✓ {name}")
    
    def _add_failed_check(
        self,
        result: ValidationResult,
        name: str,
        error_message: str,
        description: str = "",
        remediation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a failed check."""
        check = CheckResult(
            name=name,
            status=CheckStatus.FAILED,
            description=description,
            details=details or {},
            error_message=error_message,
            remediation=remediation,
        )
        result.add_check(check)
        self.logger.warning(f"✗ {name}: {error_message}")
    
    def _add_warning_check(
        self,
        result: ValidationResult,
        name: str,
        warning_message: str,
        description: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a check with warning."""
        check = CheckResult(
            name=name,
            status=CheckStatus.WARNING,
            description=description,
            details=details or {},
            error_message=warning_message,
        )
        result.add_check(check)
        self.logger.warning(f"⚠ {name}: {warning_message}")
    
    def _add_skipped_check(
        self,
        result: ValidationResult,
        name: str,
        reason: str,
        description: str = "",
    ) -> None:
        """Add a skipped check."""
        check = CheckResult(
            name=name,
            status=CheckStatus.SKIPPED,
            description=description,
            error_message=reason,
        )
        result.add_check(check)
        self.logger.info(f"⊘ {name}: {reason}")
