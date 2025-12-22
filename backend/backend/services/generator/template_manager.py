# -*- coding: utf-8 -*-
"""Template management for project generation."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.db.models import (
    ProjectTemplate, 
    TemplateFeature, 
    StackType, 
    TemplateFeatureType,
    ProjectTemplateStatus
)


class TemplateManager:
    """Manages project templates and their metadata."""

    def __init__(self, db: Session):
        self.db = db
        self.template_path = Path(__file__).parent / "templates"

    async def list_templates(self, stack: Optional[StackType] = None) -> List[Dict[str, Any]]:
        """List available project templates."""
        query = self.db.query(ProjectTemplate).filter(
            ProjectTemplate.status == ProjectTemplateStatus.ACTIVE
        )
        
        if stack:
            query = query.filter(ProjectTemplate.stack == stack)
        
        templates = query.all()
        return [self._template_to_dict(template) for template in templates]

    async def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get template by ID."""
        template = self.db.query(ProjectTemplate).filter(
            ProjectTemplate.id == template_id
        ).first()
        
        if not template:
            return None
            
        return self._template_to_dict(template)

    async def get_template_by_stack(self, stack: StackType) -> Optional[Dict[str, Any]]:
        """Get template by stack type."""
        template = self.db.query(ProjectTemplate).filter(
            ProjectTemplate.stack == stack,
            ProjectTemplate.status == ProjectTemplateStatus.ACTIVE
        ).first()
        
        if not template:
            return None
            
        return self._template_to_dict(template)

    async def create_template(
        self,
        name: str,
        stack: StackType,
        manifest: Dict[str, Any],
        description: Optional[str] = None,
        author: Optional[str] = None,
        default_features: Optional[List[str]] = None,
        supported_features: Optional[List[str]] = None,
        environment_variables: Optional[List[str]] = None
    ) -> ProjectTemplate:
        """Create a new project template."""
        
        template = ProjectTemplate(
            name=name,
            stack=stack,
            manifest=manifest,
            description=description,
            author=author,
            default_features=default_features or [],
            supported_features=supported_features or [],
            environment_variables=environment_variables or [],
            status=ProjectTemplateStatus.DRAFT
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        return template

    async def load_template_from_disk(self, stack: StackType) -> Optional[Dict[str, Any]]:
        """Load template manifest from disk."""
        template_dir = self.template_path / stack.value
        manifest_file = template_dir / "manifest.json"
        
        if not manifest_file.exists():
            return None
            
        with open(manifest_file, 'r') as f:
            manifest = json.load(f)
            
        return manifest

    async def list_features(self, stack: Optional[StackType] = None) -> List[Dict[str, Any]]:
        """List available template features."""
        query = self.db.query(TemplateFeature)
        
        if stack:
            query = query.filter(
                TemplateFeature.compatible_stacks.contains([stack.value])
            )
        
        features = query.all()
        return [self._feature_to_dict(feature) for feature in features]

    async def get_feature(self, feature_name: str) -> Optional[Dict[str, Any]]:
        """Get feature by name."""
        feature = self.db.query(TemplateFeature).filter(
            TemplateFeature.name == feature_name
        ).first()
        
        if not feature:
            return None
            
        return self._feature_to_dict(feature)

    def _template_to_dict(self, template: ProjectTemplate) -> Dict[str, Any]:
        """Convert template model to dictionary."""
        return {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "stack": template.stack.value,
            "version": template.version,
            "status": template.status.value,
            "author": template.author,
            "manifest": template.manifest,
            "default_features": template.default_features or [],
            "supported_features": template.supported_features or [],
            "environment_variables": template.environment_variables or [],
            "usage_count": template.usage_count,
            "last_used_at": template.last_used_at.isoformat() if template.last_used_at else None,
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
        }

    def _feature_to_dict(self, feature: TemplateFeature) -> Dict[str, Any]:
        """Convert feature model to dictionary."""
        return {
            "id": feature.id,
            "name": feature.name,
            "display_name": feature.display_name,
            "description": feature.description,
            "feature_type": feature.feature_type.value,
            "compatible_stacks": feature.compatible_stacks or [],
            "dependencies": feature.dependencies or [],
            "conflicts": feature.conflicts or [],
            "version": feature.version,
            "author": feature.author,
            "tags": feature.tags or [],
            "usage_count": feature.usage_count,
            "created_at": feature.created_at.isoformat() if feature.created_at else None,
            "updated_at": feature.updated_at.isoformat() if feature.updated_at else None,
        }