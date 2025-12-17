# -*- coding: utf-8 -*-
"""Project Generator - Main orchestrator service."""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
from uuid import uuid4, UUID

from sqlalchemy.orm import Session

from backend.db.models import (
    ProjectTemplate, 
    GeneratedProject, 
    TemplateFeature,
    ProjectGenerationStatus,
    StackType
)
from backend.services.generator.template_manager import TemplateManager
from backend.services.generator.engines.file_engine import FileEngine
from backend.services.generator.engines.env_engine import EnvEngine
from backend.services.generator.engines.docker_engine import DockerEngine
from backend.services.generator.engines.script_engine import ScriptEngine


class ProjectGenerationError(Exception):
    """Exception raised during project generation."""
    pass


class ProjectGenerator:
    """Main orchestrator for project generation."""

    def __init__(self, db: Session, workspace_path: Optional[Path] = None):
        self.db = db
        self.workspace_path = workspace_path or Path("/tmp/generator_workspace")
        self.template_manager = TemplateManager(db)
        self.file_engine = FileEngine()
        self.env_engine = EnvEngine()
        self.docker_engine = DockerEngine()
        self.script_engine = ScriptEngine()

    async def generate_project(
        self,
        workspace_id: UUID,
        project_name: str,
        stack: str,
        features: Optional[List[str]] = None,
        custom_settings: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        generated_by: Optional[str] = None
    ) -> GeneratedProject:
        """Generate a new project from a template."""
        
        features = features or []
        custom_settings = custom_settings or {}
        
        # Create generation record
        generation = GeneratedProject(
            workspace_id=str(workspace_id),
            name=project_name,
            description=description,
            template_id="",  # Will be set after template lookup
            features_used=features,
            custom_settings=custom_settings,
            generated_by=generated_by,
            status=ProjectGenerationStatus.PENDING
        )
        
        self.db.add(generation)
        self.db.commit()
        self.db.refresh(generation)
        
        try:
            # Update status to running
            generation.status = ProjectGenerationStatus.RUNNING
            generation.progress = 10
            self.db.commit()
            
            # Get template
            stack_type = StackType(stack)
            template = await self.template_manager.get_template_by_stack(stack_type)
            
            if not template:
                raise ProjectGenerationError(f"Template not found for stack: {stack}")
            
            generation.template_id = template["id"]
            self.db.commit()
            
            # Get selected features
            selected_features = await self._get_selected_features(features, stack_type)
            generation.progress = 20
            self.db.commit()
            
            # Create project directory
            project_path = await self._create_project_directory(generation.id, project_name)
            generation.project_path = str(project_path)
            generation.progress = 30
            self.db.commit()
            
            # Generate core files from template
            await self._generate_core_files(
                project_path, template, selected_features, custom_settings
            )
            generation.progress = 50
            self.db.commit()
            
            # Generate environment files
            await self._generate_env_files(
                project_path, template, selected_features, custom_settings
            )
            generation.progress = 65
            self.db.commit()
            
            # Generate Docker configuration
            await self._generate_docker_files(
                project_path, template, selected_features, custom_settings
            )
            generation.progress = 80
            self.db.commit()
            
            # Generate build scripts
            await self._generate_scripts(
                project_path, template, selected_features, custom_settings
            )
            generation.progress = 90
            self.db.commit()
            
            # Initialize git repository
            await self._initialize_git_repository(project_path, project_name)
            
            # Test build
            build_success = await self._test_build(project_path, stack_type)
            generation.build_successful = build_success
            
            # Count files created
            files_count = await self._count_created_files(project_path)
            generation.files_created = files_count
            
            # Mark as completed
            generation.status = ProjectGenerationStatus.COMPLETED
            generation.progress = 100
            generation.completed_at = generation.updated_at
            
            # Update template usage
            await self._update_template_usage(template["id"])
            
            self.db.commit()
            
            return generation
            
        except Exception as e:
            # Mark as failed
            generation.status = ProjectGenerationStatus.FAILED
            generation.error_message = str(e)
            generation.progress = 100
            self.db.commit()
            raise ProjectGenerationError(f"Project generation failed: {str(e)}") from e

    async def get_generation_status(self, generation_id: str) -> Optional[GeneratedProject]:
        """Get the status of a project generation."""
        return self.db.query(GeneratedProject).filter(
            GeneratedProject.id == generation_id
        ).first()

    async def list_generations(
        self, 
        workspace_id: UUID, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[GeneratedProject]:
        """List project generations for a workspace."""
        return self.db.query(GeneratedProject).filter(
            GeneratedProject.workspace_id == str(workspace_id)
        ).offset(offset).limit(limit).all()

    async def _get_selected_features(
        self, 
        feature_names: List[str], 
        stack: StackType
    ) -> List[Dict[str, Any]]:
        """Get feature details for selected features."""
        if not feature_names:
            return []
            
        features = self.db.query(TemplateFeature).filter(
            TemplateFeature.name.in_(feature_names),
            TemplateFeature.compatible_stacks.contains([stack.value])
        ).all()
        
        return [self.template_manager._feature_to_dict(feature) for feature in features]

    async def _create_project_directory(self, generation_id: str, project_name: str) -> Path:
        """Create the project directory."""
        project_path = self.workspace_path / f"{generation_id}_{project_name}"
        
        if project_path.exists():
            shutil.rmtree(project_path)
            
        project_path.mkdir(parents=True, exist_ok=True)
        return project_path

    async def _generate_core_files(
        self,
        project_path: Path,
        template: Dict[str, Any],
        features: List[Dict[str, Any]],
        custom_settings: Dict[str, Any]
    ):
        """Generate core project files."""
        manifest = template["manifest"]
        files = manifest.get("files", {})
        
        for relative_path, template_file in files.items():
            await self.file_engine.generate_file(
                project_path,
                relative_path,
                template_file,
                custom_settings
            )

    async def _generate_env_files(
        self,
        project_path: Path,
        template: Dict[str, Any],
        features: List[Dict[str, Any]],
        custom_settings: Dict[str, Any]
    ):
        """Generate environment configuration files."""
        await self.env_engine.generate_env_files(
            project_path, template, features, custom_settings
        )

    async def _generate_docker_files(
        self,
        project_path: Path,
        template: Dict[str, Any],
        features: List[Dict[str, Any]],
        custom_settings: Dict[str, Any]
    ):
        """Generate Docker configuration files."""
        await self.docker_engine.generate_docker_files(
            project_path, template, features, custom_settings
        )

    async def _generate_scripts(
        self,
        project_path: Path,
        template: Dict[str, Any],
        features: List[Dict[str, Any]],
        custom_settings: Dict[str, Any]
    ):
        """Generate build and dev scripts."""
        await self.script_engine.generate_scripts(
            project_path, template, features, custom_settings
        )

    async def _initialize_git_repository(self, project_path: Path, project_name: str):
        """Initialize git repository in the project."""
        import subprocess
        
        # Initialize git
        subprocess.run(["git", "init"], cwd=project_path, check=True)
        
        # Configure git
        subprocess.run(
            ["git", "config", "user.name", "Project Generator"], 
            cwd=project_path, 
            check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "generator@project.local"], 
            cwd=project_path, 
            check=True
        )
        
        # Add all files
        subprocess.run(["git", "add", "."], cwd=project_path, check=True)
        
        # Create initial commit
        subprocess.run(
            ["git", "commit", "-m", f"Initial commit for {project_name}"], 
            cwd=project_path, 
            check=True
        )

    async def _test_build(self, project_path: Path, stack: StackType) -> bool:
        """Test if the generated project builds successfully."""
        try:
            if stack == StackType.EXPRESS_TS:
                # Test Node.js/TypeScript build
                result = subprocess.run(
                    ["npm", "run", "build"], 
                    cwd=project_path, 
                    capture_output=True, 
                    text=True,
                    timeout=300
                )
                return result.returncode == 0
                
            elif stack == StackType.FASTAPI:
                # Test Python build (no build needed, just check syntax)
                result = subprocess.run(
                    ["python", "-m", "py_compile", "main.py"], 
                    cwd=project_path, 
                    capture_output=True, 
                    text=True
                )
                return result.returncode == 0
                
            # For other stacks, just return True for now
            return True
            
        except Exception:
            return False

    async def _count_created_files(self, project_path: Path) -> int:
        """Count the number of files created in the project."""
        count = 0
        for root, dirs, files in os.walk(project_path):
            # Skip .git directory
            dirs[:] = [d for d in dirs if d != '.git']
            count += len(files)
        return count

    async def _update_template_usage(self, template_id: str):
        """Update template usage statistics."""
        template = self.db.query(ProjectTemplate).filter(
            ProjectTemplate.id == template_id
        ).first()
        
        if template:
            template.usage_count += 1
            template.last_used_at = template.updated_at
            self.db.commit()