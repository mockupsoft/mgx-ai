"""Tests for Template and Prompt Library System.

Comprehensive test suite for template management functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from backend.db.models.entities import ReusableModule, PromptTemplate, ADR
from backend.db.models.enums import TemplateCategory, PromptOutputFormat, TemplateVisibility, ADRStatus
from backend.services.templates.template_manager import TemplateManager, TemplateEnhancer
from backend.services.templates.template_seeder import TemplateSeeder


class TestTemplateManager:
    """Test cases for TemplateManager."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()
    
    @pytest.fixture
    def template_manager(self, mock_db):
        """Create template manager with mock database."""
        return TemplateManager(mock_db)
    
    @pytest.mark.asyncio
    async def test_create_module_template(self, template_manager):
        """Test creating a module template."""
        # Mock the database operations
        with patch.object(template_manager.module_repo, 'create_module', new_callable=AsyncMock) as mock_create:
            # Setup mock return value
            mock_module = Mock()
            mock_module.id = "test-module-id"
            mock_module.name = "test-module"
            mock_module.category = TemplateCategory.AUTHENTICATION
            mock_module.description = "Test module"
            mock_module.version = "1.0.0"
            mock_module.tech_stacks = []
            mock_module.dependencies = []
            mock_module.documentation = None
            mock_module.params = []
            mock_module.author = "Test Author"
            mock_module.usage_count = 0
            mock_module.rating = 0.0
            mock_module.visibility = TemplateVisibility.PRIVATE
            mock_module.is_active = True
            mock_module.tags = []
            mock_module.created_by = None
            mock_module.updated_by = None
            mock_create.return_value = mock_module
            
            # Mock file and parameter creation
            with patch.object(template_manager.file_repo, 'create_file_template', new_callable=AsyncMock):
                with patch.object(template_manager.param_repo, 'create_parameter', new_callable=AsyncMock):
                    result = await template_manager.create_module_template(
                        name="test-module",
                        category=TemplateCategory.AUTHENTICATION,
                        description="Test module",
                        files=[],
                        parameters=[]
                    )
                    
                    assert result == mock_module
                    template_manager.module_repo.create_module.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_apply_module_template(self, template_manager):
        """Test applying a module template."""
        # Mock the module retrieval
        mock_module = Mock()
        mock_module.name = "test-module"
        
        # Mock file templates
        mock_file = Mock()
        mock_file.content = "Hello {{name}}!"
        mock_file.path = "src/{{module}}/test.txt"
        
        # Mock parameters
        mock_param = Mock()
        mock_param.required = True
        mock_param.name = "name"
        
        with patch.object(template_manager.module_repo, 'get_module', return_value=mock_module):
            with patch.object(template_manager.file_repo, 'get_files_by_module', return_value=[mock_file]):
                with patch.object(template_manager.param_repo, 'get_parameters_by_module', return_value=[mock_param]):
                    with patch.object(template_manager.module_repo, 'increment_usage'):
                        with patch.object(template_manager, '_render_template_content', return_value="Hello World!"):
                            with patch.object(template_manager, '_create_file_structure'):
                                result = await template_manager.apply_module_template(
                                    module_id="test-id",
                                    parameters={"name": "World"},
                                    output_path="/tmp/test"
                                )
                                
                                assert result["module_name"] == "test-module"
                                assert result["files_generated"] == 1
                                assert result["parameters_used"] == {"name": "World"}
    
    @pytest.mark.asyncio
    async def test_apply_module_template_missing_params(self, template_manager):
        """Test applying module template with missing required parameters."""
        mock_module = Mock()
        mock_module.name = "test-module"
        
        # Mock required parameter
        mock_param = Mock()
        mock_param.required = True
        mock_param.name = "required_param"
        
        with patch.object(template_manager.module_repo, 'get_module', return_value=mock_module):
            with patch.object(template_manager.file_repo, 'get_files_by_module', return_value=[]):
                with patch.object(template_manager.param_repo, 'get_parameters_by_module', return_value=[mock_param]):
                    with pytest.raises(ValueError, match="Missing required parameters"):
                        await template_manager.apply_module_template(
                            module_id="test-id",
                            parameters={},  # Missing required_param
                            output_path="/tmp/test"
                        )
    
    @pytest.mark.asyncio
    async def test_generate_prompt(self, template_manager):
        """Test generating a prompt from template."""
        mock_template = Mock()
        mock_template.template = "Hello {{name}}, welcome to {{place}}!"
        
        with patch.object(template_manager.prompt_repo, 'get_prompt_template', return_value=mock_template):
            with patch.object(template_manager.prompt_repo, 'increment_usage'):
                with patch.object(template_manager.prompt_repo, 'generate_prompt', return_value="Hello John, welcome to Earth!"):
                    result = await template_manager.generate_prompt(
                        template_id="test-id",
                        variables={"name": "John", "place": "Earth"}
                    )
                    
                    assert result == "Hello John, welcome to Earth!"
                    template_manager.prompt_repo.generate_prompt.assert_called_once_with("test-id", {"name": "John", "place": "Earth"})
    
    @pytest.mark.asyncio
    async def test_search_templates(self, template_manager):
        """Test searching templates."""
        # Mock module templates
        mock_module = Mock()
        mock_module.id = "module-id"
        mock_module.name = "auth-module"
        mock_module.description = "Authentication module"
        mock_module.category = TemplateCategory.AUTHENTICATION
        mock_module.rating = 4.5
        mock_module.usage_count = 100
        
        # Mock prompt templates
        mock_prompt = Mock()
        mock_prompt.id = "prompt-id"
        mock_prompt.name = "api-design"
        mock_prompt.template = "Design a REST API..."
        mock_prompt.category = TemplateCategory.API_DESIGN
        mock_prompt.output_format = PromptOutputFormat.CODE
        mock_prompt.rating = 4.0
        mock_prompt.usage_count = 50
        
        with patch.object(template_manager.module_repo, 'list_modules', return_value=([mock_module], 1)):
            with patch.object(template_manager.prompt_repo, 'list_prompt_templates', return_value=([mock_prompt], 1)):
                results = await template_manager.search_templates(
                    query="auth",
                    template_type="all",
                    limit=20
                )
                
                assert len(results) == 2
                assert results[0]["type"] == "module"
                assert results[0]["name"] == "auth-module"
                assert results[1]["type"] == "prompt"
                assert results[1]["name"] == "api-design"


class TestTemplateEnhancer:
    """Test cases for TemplateEnhancer."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()
    
    @pytest.fixture
    def template_enhancer(self, mock_db):
        """Create template enhancer with mock database."""
        return TemplateEnhancer(mock_db)
    
    @pytest.mark.asyncio
    async def test_apply_templates_to_project(self, template_enhancer):
        """Test applying templates to a project."""
        # Mock module retrieval
        mock_module = Mock()
        mock_module.id = "module-id"
        
        # Mock template manager
        with patch.object(template_enhancer, 'template_manager') as mock_manager:
            with patch.object(mock_manager.module_repo, 'get_module_by_name', return_value=mock_module):
                with patch.object(mock_manager, 'apply_module_template', return_value={
                    "module_name": "test-module",
                    "files_generated": 5,
                    "files": [],
                    "parameters_used": {}
                }):
                    result = await template_enhancer.apply_templates_to_project(
                        project_id="project-123",
                        modules=["test-module"],
                        parameters={"test-module": {}}
                    )
                    
                    assert result["project_id"] == "project-123"
                    assert result["templates_applied"] == 1
                    assert len(result["results"]) == 1
                    assert result["results"][0]["module"] == "test-module"
                    assert result["results"][0]["success"] == True
    
    @pytest.mark.asyncio
    async def test_apply_templates_to_project_missing_module(self, template_enhancer):
        """Test applying templates when module doesn't exist."""
        with patch.object(template_enhancer, 'template_manager') as mock_manager:
            with patch.object(mock_manager.module_repo, 'get_module_by_name', return_value=None):
                result = await template_enhancer.apply_templates_to_project(
                    project_id="project-123",
                    modules=["non-existent-module"],
                    parameters={}
                )
                
                assert result["project_id"] == "project-123"
                assert result["templates_applied"] == 1
                assert len(result["results"]) == 1
                assert result["results"][0]["module"] == "non-existent-module"
                assert result["results"][0]["success"] == False


class TestTemplateRepositories:
    """Test cases for template repositories."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return Mock()
    
    def test_module_template_repository_create(self, mock_db_session):
        """Test creating module template in repository."""
        from backend.services.templates.repositories.module_templates import ModuleTemplateRepository
        
        repo = ModuleTemplateRepository(mock_db_session)
        
        # Mock query and add operations
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        mock_db_session.add = Mock()
        mock_db_session.commit = Mock()
        mock_db_session.refresh = Mock()
        
        # This would test the repository method, but we'd need to mock the SQLAlchemy operations
        # For now, we'll just verify the repository can be instantiated
        assert repo.db == mock_db_session
    
    def test_prompt_template_repository_create(self, mock_db_session):
        """Test creating prompt template in repository."""
        from backend.services.templates.repositories.prompt_templates import PromptTemplateRepository
        
        repo = PromptTemplateRepository(mock_db_session)
        assert repo.db == mock_db_session
    
    def test_adr_repository_create(self, mock_db_session):
        """Test ADR repository operations."""
        from backend.services.templates.repositories.adr_templates import ADRRepository
        
        repo = ADRRepository(mock_db_session)
        assert repo.db == mock_db_session


class TestTemplateSeeder:
    """Test cases for TemplateSeeder."""
    
    @pytest.fixture
    def mock_template_manager(self):
        """Mock template manager."""
        return Mock()
    
    @pytest.fixture
    def template_seeder(self, mock_template_manager):
        """Create template seeder with mock manager."""
        return TemplateSeeder(mock_template_manager)
    
    @pytest.mark.asyncio
    async def test_seed_all_templates(self, template_seeder):
        """Test seeding all templates."""
        # Mock successful seeding
        template_seeder.manager.create_module_template = AsyncMock()
        template_seeder.manager.create_prompt_template = AsyncMock()
        
        result = await template_seeder.seed_all_templates()
        
        assert "module_templates" in result
        assert "prompt_templates" in result
        assert "adrs" in result
    
    @pytest.mark.asyncio
    async def test_seed_module_templates(self, template_seeder):
        """Test seeding module templates."""
        template_seeder.manager.create_module_template = AsyncMock()
        
        count = await template_seeder._seed_module_templates()
        
        assert count > 0
        # Should have called create_module_template at least 3 times (jwt-auth, product-catalog, shopping-cart)
        assert template_seeder.manager.create_module_template.call_count >= 3
    
    @pytest.mark.asyncio
    async def test_seed_prompt_templates(self, template_seeder):
        """Test seeding prompt templates."""
        template_seeder.manager.create_prompt_template = AsyncMock()
        
        count = await template_seeder._seed_prompt_templates()
        
        assert count > 0
        # Should have called create_prompt_template at least 3 times
        assert template_seeder.manager.create_prompt_template.call_count >= 3


class TestTemplateAPI:
    """Test cases for template API endpoints."""

    def test_list_module_templates_endpoint(self, client):
        """Test listing module templates endpoint."""
        response = client.get("/api/templates/modules")
        
        # Should return 200 even if no templates exist
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert data["template_type"] == "module"
    
    def test_list_prompt_templates_endpoint(self, client):
        """Test listing prompt templates endpoint."""
        response = client.get("/api/templates/prompts")
        
        # Should return 200 even if no templates exist
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["template_type"] == "prompt"
    
    def test_search_templates_endpoint(self, client):
        """Test searching templates endpoint."""
        response = client.get("/api/templates/search", params={
            "query": "test",
            "template_type": "module"
        })
        
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data
        assert "total" in data
        assert "query" in data
    
    def test_marketplace_endpoint(self, client):
        """Test marketplace endpoint."""
        response = client.get("/api/templates/marketplace")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "popular_modules" in data
        assert "popular_prompts" in data
        assert "categories" in data
        assert "total_templates" in data


if __name__ == "__main__":
    pytest.main([__file__])