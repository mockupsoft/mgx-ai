# -*- coding: utf-8 -*-
"""Docker image validation."""

import re
from typing import Any, Dict, Optional

from .base import BaseValidator, ValidationResult


class DockerValidator(BaseValidator):
    """Validates Docker images for deployment readiness."""
    
    MAX_IMAGE_SIZE_BYTES = 500 * 1024 * 1024  # 500MB
    DANGEROUS_PATTERNS = [
        r'password\s*=',
        r'secret\s*=',
        r'api[_-]?key',
        r'aws[_-]?secret',
        r'private[_-]?key',
    ]
    
    async def validate_image(
        self,
        validation_id: str,
        image_id: str,
        image_metadata: Dict[str, Any],
    ) -> ValidationResult:
        """Validate a Docker image."""
        result = self._create_result(validation_id, "running")
        
        try:
            # Check if image exists
            await self._check_image_exists(result, image_id, image_metadata)
            
            # Check image size
            await self._check_image_size(result, image_metadata)
            
            # Check base image
            await self._check_base_image(result, image_metadata)
            
            # Check for hardcoded secrets
            await self._check_hardcoded_secrets(result, image_metadata)
            
            # Check entry point
            await self._check_entry_point(result, image_metadata)
            
            # Check health check
            await self._check_health_check(result, image_metadata)
            
            # Check non-root user
            await self._check_non_root_user(result, image_metadata)
            
            # Check image layers
            await self._check_image_layers(result, image_metadata)
            
            result.status = "passed" if result.is_passing() else ("warning" if result.has_warnings() else "failed")
            
        except Exception as e:
            result.error_message = str(e)
            result.status = "failed"
            self.logger.error(f"Docker validation failed: {e}")
        
        return result
    
    async def _check_image_exists(
        self,
        result: ValidationResult,
        image_id: str,
        metadata: Dict[str, Any],
    ) -> None:
        """Check if image exists and is accessible."""
        if not image_id or not metadata:
            self._add_failed_check(
                result,
                "Image Exists",
                "Image ID or metadata is missing",
                description="Verify Docker image is built and available"
            )
            return
        
        self._add_passed_check(
            result,
            "Image Exists",
            "Docker image is accessible",
            details={"image_id": image_id}
        )
    
    async def _check_image_size(
        self,
        result: ValidationResult,
        metadata: Dict[str, Any],
    ) -> None:
        """Check if image size is reasonable."""
        size = metadata.get("size_bytes", 0)
        
        if size > self.MAX_IMAGE_SIZE_BYTES:
            self._add_warning_check(
                result,
                "Image Size",
                f"Image size {size / (1024**2):.0f}MB exceeds 500MB warning threshold",
                description="Optimize Dockerfile to reduce image size",
                details={"size_mb": size / (1024**2), "max_mb": 500}
            )
        else:
            self._add_passed_check(
                result,
                "Image Size",
                f"Image size {size / (1024**2):.0f}MB is acceptable",
                details={"size_mb": size / (1024**2)}
            )
    
    async def _check_base_image(
        self,
        result: ValidationResult,
        metadata: Dict[str, Any],
    ) -> None:
        """Check base image for security issues."""
        base_image = metadata.get("base_image", "")
        
        if not base_image:
            self._add_warning_check(
                result,
                "Base Image",
                "Base image not specified in metadata",
                description="Specify an explicit base image version"
            )
            return
        
        # Check for 'latest' tag
        if base_image.endswith(":latest"):
            self._add_warning_check(
                result,
                "Base Image Tag",
                f"Using 'latest' tag: {base_image}",
                description="Use explicit version tags instead of 'latest'",
                remediation="Replace 'latest' with specific version (e.g., python:3.11-slim)"
            )
            return
        
        self._add_passed_check(
            result,
            "Base Image",
            f"Base image {base_image} uses specific version",
            details={"base_image": base_image}
        )
    
    async def _check_hardcoded_secrets(
        self,
        result: ValidationResult,
        metadata: Dict[str, Any],
    ) -> None:
        """Check for hardcoded secrets in Dockerfile or build args."""
        dockerfile = metadata.get("dockerfile_content", "")
        build_args = metadata.get("build_args", {})
        
        found_secrets = []
        
        # Check Dockerfile
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, dockerfile, re.IGNORECASE):
                found_secrets.append(pattern)
        
        # Check build args
        for key, value in build_args.items():
            if any(re.search(pattern, f"{key}={value}", re.IGNORECASE) for pattern in self.DANGEROUS_PATTERNS):
                found_secrets.append(key)
        
        if found_secrets:
            self._add_failed_check(
                result,
                "Hardcoded Secrets",
                f"Potential secrets detected: {', '.join(set(found_secrets))}",
                description="Ensure no secrets are hardcoded in Docker image",
                remediation="Use build arguments or environment variables for secrets, passed at build time"
            )
        else:
            self._add_passed_check(
                result,
                "Hardcoded Secrets",
                "No hardcoded secrets detected",
            )
    
    async def _check_entry_point(
        self,
        result: ValidationResult,
        metadata: Dict[str, Any],
    ) -> None:
        """Check if entry point is defined."""
        entry_point = metadata.get("entry_point") or metadata.get("cmd")
        
        if not entry_point:
            self._add_failed_check(
                result,
                "Entry Point",
                "No ENTRYPOINT or CMD defined",
                description="Define how the container should start",
                remediation="Add ENTRYPOINT or CMD to Dockerfile"
            )
        else:
            self._add_passed_check(
                result,
                "Entry Point",
                f"Entry point defined: {entry_point}",
                details={"entry_point": entry_point}
            )
    
    async def _check_health_check(
        self,
        result: ValidationResult,
        metadata: Dict[str, Any],
    ) -> None:
        """Check if health check is defined."""
        health_check = metadata.get("health_check")
        
        if not health_check:
            self._add_warning_check(
                result,
                "Health Check",
                "No HEALTHCHECK defined",
                description="Add health check to Docker image",
                details={}
            )
        else:
            self._add_passed_check(
                result,
                "Health Check",
                "Health check is defined",
                details=health_check
            )
    
    async def _check_non_root_user(
        self,
        result: ValidationResult,
        metadata: Dict[str, Any],
    ) -> None:
        """Check if container runs as non-root user."""
        user = metadata.get("user")
        
        if not user or user == "root":
            self._add_warning_check(
                result,
                "Non-Root User",
                "Container runs as root user",
                description="Create and use a non-root user for security",
                remediation="Add USER directive to Dockerfile to run as non-root"
            )
        else:
            self._add_passed_check(
                result,
                "Non-Root User",
                f"Container runs as user: {user}",
                details={"user": user}
            )
    
    async def _check_image_layers(
        self,
        result: ValidationResult,
        metadata: Dict[str, Any],
    ) -> None:
        """Check image layers are documented."""
        layers = metadata.get("layers", [])
        
        if not layers:
            self._add_warning_check(
                result,
                "Image Layers",
                "Image layer information not available",
                description="Verify image build process",
            )
        else:
            self._add_passed_check(
                result,
                "Image Layers",
                f"Image has {len(layers)} layers",
                details={"layer_count": len(layers)}
            )
