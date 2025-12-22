# -*- coding: utf-8 -*-
"""Test file for Project Generator & Scaffold Engine."""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, ProjectTemplate, TemplateFeature, GeneratedProject
from backend.db.models.enums import StackType, TemplateFeatureType, ProjectTemplateStatus
from backend.services.generator.generator import ProjectGenerator, ProjectGenerationError
from backend.services.generator.template_manager import TemplateManager


class TestProjectGenerator:
    """Test cases for ProjectGenerator."""

    @pytest.fixture
    def test_db(self):
        """Create a test database."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()

    @pytest.fixture 
    def generator(self, test_db):
        """Create a project generator instance."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield ProjectGenerator(test_db, Path(temp_dir))

    @pytest.mark.asyncio
    async def test_generate_project_basic(self, generator, test_db):
        """Test basic project generation."""
        # Create a test template
        template = ProjectTemplate(
            name="Test Express Template",
            stack=StackType.EXPRESS_TS,
            manifest={
                "files": {
                    "package.json": "express_ts/package.json.template",
                    "src/server.ts": "express_ts/src/server.ts.template"
                },
                "scripts": {
                    "dev": "npm run dev"
                },
                "env_vars": ["PORT", "NODE_ENV"]
            },
            status=ProjectTemplateStatus.ACTIVE
        )
        test_db.add(template)
        test_db.commit()
        test_db.refresh(template)

        # Mock workspace_id and other parameters
        workspace_id = "test-workspace-123"

        # Test generation
        result = await generator.generate_project(
            workspace_id=workspace_id,
            project_name="test-project",
            stack="express_ts",
            features=["testing", "logging"],
            custom_settings={"port": 3000},
            description="Test project"
        )

        assert result is not None
        assert result.name == "test-project"
        assert result.template_id == template.id
        assert result.status.value == "completed"
        assert result.files_created > 0

    @pytest.mark.asyncio
    async def test_generate_project_template_not_found(self, generator):
        """Test project generation with missing template."""
        workspace_id = "test-workspace-123"
        
        with pytest.raises(ProjectGenerationError, match="Template not found"):
            await generator.generate_project(
                workspace_id=workspace_id,
                project_name="test-project", 
                stack="express_ts"
            )

    @pytest.mark.asyncio
    async def test_get_generation_status(self, generator, test_db):
        """Test getting generation status."""
        # Create a test generated project
        project = GeneratedProject(
            workspace_id="test-workspace",
            name="test-project",
            template_id="test-template",
            status="completed"
        )
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)

        # Test getting status
        result = await generator.get_generation_status(project.id)
        
        assert result is not None
        assert result.id == project.id
        assert result.name == "test-project"


class TestTemplateManager:
    """Test cases for TemplateManager."""

    @pytest.fixture
    def test_db(self):
        """Create a test database."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()

    @pytest.fixture
    def template_manager(self, test_db):
        """Create a template manager instance."""
        return TemplateManager(test_db)

    @pytest.mark.asyncio
    async def test_list_templates(self, template_manager, test_db):
        """Test listing templates."""
        # Create test templates
        templates = [
            ProjectTemplate(
                name="Express Template",
                stack=StackType.EXPRESS_TS,
                manifest={"files": {}},
                status=ProjectTemplateStatus.ACTIVE
            ),
            ProjectTemplate(
                name="FastAPI Template", 
                stack=StackType.FASTAPI,
                manifest={"files": {}},
                status=ProjectTemplateStatus.DRAFT
            )
        ]
        
        for template in templates:
            test_db.add(template)
        test_db.commit()

        # Test listing all templates
        result = await template_manager.list_templates()
        assert len(result) == 1  # Only ACTIVE templates

        # Test filtering by stack
        result = await template_manager.list_templates(StackType.EXPRESS_TS)
        assert len(result) == 1
        assert result[0]["name"] == "Express Template"

    @pytest.mark.asyncio
    async def test_get_template(self, template_manager, test_db):
        """Test getting a specific template."""
        template = ProjectTemplate(
            name="Test Template",
            stack=StackType.EXPRESS_TS,
            manifest={"files": {}},
            status=ProjectTemplateStatus.ACTIVE
        )
        test_db.add(template)
        test_db.commit()
        test_db.refresh(template)

        # Test getting template by ID
        result = await template_manager.get_template(template.id)
        assert result is not None
        assert result["name"] == "Test Template"
        assert result["stack"] == "express_ts"


class TestFileEngine:
    """Test cases for FileEngine."""

    @pytest.fixture
    def file_engine(self):
        """Create a file engine instance."""
        return FileEngine()

    @pytest.mark.asyncio
    async def test_generate_file(self, file_engine):
        """Test file generation from template."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create a test template
            template_content = """{
  "name": "{{PROJECT_NAME}}",
  "version": "{{PROJECT_VERSION}}"
}"""
            
            template_dir = Path(temp_dir) / "templates" / "express_ts"
            template_dir.mkdir(parents=True)
            template_file = template_dir / "package.json.template"
            template_file.write_text(template_content)
            
            # Update file engine template path
            file_engine.templates_path = Path(temp_dir) / "templates"
            
            # Generate file
            custom_settings = {
                "project_name": "test-project",
                "version": "1.0.0"
            }
            
            await file_engine.generate_file(
                project_path,
                "package.json",
                "express_ts/package.json.template", 
                custom_settings
            )
            
            # Check if file was created and processed
            target_file = project_path / "package.json"
            assert target_file.exists()
            
            content = target_file.read_text()
            assert '"name": "test-project"' in content
            assert '"version": "1.0.0"' in content


class TestIntegration:
    """Integration tests for the complete generator system."""

    @pytest.fixture
    def test_db(self):
        """Create a test database."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()

    @pytest.mark.asyncio
    async def test_full_generation_workflow(self, test_db):
        """Test the complete project generation workflow."""
        # This would be a comprehensive integration test
        # that tests the full workflow from template creation to project generation
        pass


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])