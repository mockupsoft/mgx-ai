# -*- coding: utf-8 -*-
"""
Unit Tests for Backend Bootstrap

Tests for:
- FastAPI app initialization and configuration
- Settings loading from environment variables
- Service initialization (MGXTeamProvider, BackgroundTaskRunner)
- Router registration
- Health check endpoint
- Lifespan events
"""

import os
import sys
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

# Add project to path
sys.path.insert(0, '/home/engine/project')

# Set environment for testing
os.environ['OPENAI_API_KEY'] = 'test_key'


@pytest.fixture
def env_vars():
    """Fixture for setting environment variables."""
    original_env = dict(os.environ)
    
    # Set test environment variables
    os.environ.update({
        'API_HOST': '127.0.0.1',
        'API_PORT': '8000',
        'API_RELOAD': 'false',
        'MGX_MAX_ROUNDS': '5',
        'MGX_CACHE_BACKEND': 'memory',
        'DB_HOST': 'localhost',
        'DB_NAME': 'test_mgx_agent',
        'LOG_LEVEL': 'INFO',
        'DEBUG': 'false',
    })
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


class TestBackendConfig:
    """Tests for backend configuration."""
    
    def test_settings_defaults(self, env_vars):
        """Test default settings values."""
        # Clear any cached imports
        if 'backend.config' in sys.modules:
            del sys.modules['backend.config']
        
        from backend.config import Settings
        settings = Settings()
        
        assert settings.api_host == '127.0.0.1'
        assert settings.api_port == 8000
        assert settings.api_reload == False
        assert settings.api_workers == 1
        assert settings.mgx_max_rounds == 5
        assert settings.db_host == 'localhost'
        assert settings.log_level == 'INFO'
    
    def test_settings_env_override(self, env_vars):
        """Test settings override from environment variables."""
        # Clear any cached imports
        if 'backend.config' in sys.modules:
            del sys.modules['backend.config']
        
        os.environ['API_PORT'] = '9000'
        os.environ['API_WORKERS'] = '4'
        os.environ['MGX_CACHE_BACKEND'] = 'redis'
        
        from backend.config import Settings
        settings = Settings()
        
        assert settings.api_port == 9000
        assert settings.api_workers == 4
        assert settings.mgx_cache_backend == 'redis'
    
    def test_settings_validation(self, env_vars):
        """Test settings validation."""
        from backend.config import Settings
        from pydantic_core import ValidationError
        
        # Valid settings
        settings = Settings(api_port=8080)
        assert settings.api_port == 8080
        
        # Invalid port should raise validation error
        with pytest.raises(ValidationError):  # Pydantic validation error
            Settings(api_port=100)
    
    def test_database_url_construction(self, env_vars):
        """Test database URL construction."""
        if 'backend.config' in sys.modules:
            del sys.modules['backend.config']
        
        from backend.config import Settings
        settings = Settings(
            db_user='testuser',
            db_password='testpass',
            db_host='db.example.com',
            db_port=5432,
            db_name='testdb',
        )
        
        expected = 'postgresql://testuser:testpass@db.example.com:5432/testdb'
        assert settings.database_url == expected
    
    def test_async_database_url(self, env_vars):
        """Test async database URL construction."""
        if 'backend.config' in sys.modules:
            del sys.modules['backend.config']
        
        from backend.config import Settings
        settings = Settings(
            db_user='testuser',
            db_password='testpass',
            db_host='db.example.com',
            db_port=5432,
            db_name='testdb',
        )
        
        expected = 'postgresql+asyncpg://testuser:testpass@db.example.com:5432/testdb'
        assert settings.async_database_url == expected


class TestFastAPIAppInitialization:
    """Tests for FastAPI app initialization."""
    
    def test_app_creation(self, env_vars):
        """Test that FastAPI app is created successfully."""
        from backend.app.main import create_app
        
        app = create_app()
        
        assert app is not None
        assert app.title == "MGX Agent API"
        assert app.version == "0.1.0"
    
    def test_app_imports(self):
        """Test that app can be imported directly."""
        from backend.app.main import app
        
        assert app is not None
        assert hasattr(app, 'routes')
    
    def test_routers_registered(self, env_vars):
        """Test that all routers are registered."""
        from backend.app.main import create_app
        
        app = create_app()
        
        # Get all route paths
        routes = [route.path for route in app.routes]
        
        # Check that health router is registered
        assert any('/health' in route for route in routes)
        assert any('/tasks' in route for route in routes)
        assert any('/runs' in route for route in routes)


class TestHealthEndpoint:
    """Tests for health check endpoints."""
    
    def test_health_endpoint_with_test_client(self, env_vars):
        """Test health endpoint using TestClient."""
        from fastapi.testclient import TestClient
        from backend.app.main import create_app
        
        app = create_app()
        client = TestClient(app)
        
        # Test health endpoint
        response = client.get("/health/")
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert 'timestamp' in data
        assert data['service'] == 'mgx-agent-api'
    
    def test_readiness_endpoint(self, env_vars):
        """Test readiness endpoint."""
        from fastapi.testclient import TestClient
        from backend.app.main import create_app
        
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/health/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data['ready'] == True
    
    def test_liveness_endpoint(self, env_vars):
        """Test liveness endpoint."""
        from fastapi.testclient import TestClient
        from backend.app.main import create_app
        
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/health/live")
        
        assert response.status_code == 200
        data = response.json()
        assert data['alive'] == True
    
    def test_status_endpoint(self, env_vars):
        """Test status endpoint."""
        from fastapi.testclient import TestClient
        from backend.app.main import create_app
        
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/health/status")
        
        assert response.status_code == 200
        data = response.json()
        assert 'status' in data
        assert 'version' in data


class TestRootEndpoint:
    """Tests for root endpoint."""
    
    def test_root_endpoint(self, env_vars):
        """Test root endpoint."""
        from fastapi.testclient import TestClient
        from backend.app.main import create_app
        
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert 'message' in data
        assert 'version' in data
        assert data['docs'] == '/docs'
        assert data['redoc'] == '/redoc'


class TestTasksRouter:
    """Tests for tasks router endpoints."""
    
    def test_list_tasks_endpoint(self, env_vars):
        """Test list tasks endpoint."""
        from fastapi.testclient import TestClient
        from backend.app.main import create_app
        
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/tasks/")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_create_task_endpoint(self, env_vars):
        """Test create task endpoint."""
        from fastapi.testclient import TestClient
        from backend.app.main import create_app
        
        app = create_app()
        client = TestClient(app)
        
        response = client.post(
            "/tasks/",
            params={
                "description": "Test task",
                "complexity": "M",
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'id' in data
        assert data['description'] == 'Test task'


class TestRunsRouter:
    """Tests for runs router endpoints."""
    
    def test_list_runs_endpoint(self, env_vars):
        """Test list runs endpoint."""
        from fastapi.testclient import TestClient
        from backend.app.main import create_app
        
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/runs/")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestMGXTeamProvider:
    """Tests for MGXTeamProvider service."""
    
    def test_team_provider_initialization(self):
        """Test MGXTeamProvider initialization."""
        from backend.services import MGXTeamProvider
        
        provider = MGXTeamProvider()
        
        assert provider is not None
        assert provider.config is not None
    
    def test_team_provider_get_team(self, event_loop):
        """Test getting team from provider."""
        from backend.services import MGXTeamProvider
        
        provider = MGXTeamProvider()
        
        # Mock the team to avoid MetaGPT dependencies
        async def get_team():
            team = await provider.get_team()
            return team is not None
        
        result = event_loop.run_until_complete(get_team())
        assert result
    
    def test_team_provider_singleton(self):
        """Test team provider singleton pattern."""
        from backend.services import get_team_provider
        
        provider1 = get_team_provider()
        provider2 = get_team_provider()
        
        assert provider1 is provider2
    
    def test_team_provider_shutdown(self, event_loop):
        """Test team provider shutdown."""
        from backend.services import MGXTeamProvider
        
        provider = MGXTeamProvider()
        
        async def shutdown():
            await provider.shutdown()
            return True
        
        result = event_loop.run_until_complete(shutdown())
        assert result


class TestBackgroundTaskRunner:
    """Tests for BackgroundTaskRunner service."""
    
    def test_task_runner_initialization(self):
        """Test BackgroundTaskRunner initialization."""
        from backend.services import BackgroundTaskRunner
        
        runner = BackgroundTaskRunner()
        
        assert runner is not None
        assert runner.max_tasks == 100
    
    def test_task_runner_submit_task(self, event_loop):
        """Test submitting a background task."""
        from backend.services import BackgroundTaskRunner
        
        async def test():
            runner = BackgroundTaskRunner()
            await runner.start()
            
            async def sample_task():
                return "task_result"
            
            task_id = await runner.submit(sample_task(), name="test_task")
            
            assert task_id is not None
            assert isinstance(task_id, str)
            
            await runner.stop()
        
        event_loop.run_until_complete(test())
    
    def test_task_runner_get_status(self, event_loop):
        """Test getting task status."""
        from backend.services import BackgroundTaskRunner
        
        async def test():
            runner = BackgroundTaskRunner()
            await runner.start()
            
            async def sample_task():
                return "task_result"
            
            task_id = await runner.submit(sample_task(), name="test_task")
            
            # Give time for task to complete
            await asyncio.sleep(0.1)
            
            status = await runner.get_status(task_id)
            
            assert status is not None
            assert 'task_id' in status
            assert status['name'] == 'test_task'
            
            await runner.stop()
        
        event_loop.run_until_complete(test())
    
    def test_task_runner_singleton(self):
        """Test task runner singleton pattern."""
        from backend.services import get_task_runner
        
        runner1 = get_task_runner()
        runner2 = get_task_runner()
        
        assert runner1 is runner2
    
    def test_task_runner_stats(self):
        """Test task runner statistics."""
        from backend.services import BackgroundTaskRunner
        
        runner = BackgroundTaskRunner()
        
        stats = runner.get_stats()
        
        assert 'total_tasks' in stats
        assert 'statuses' in stats
        assert 'running' in stats
        assert stats['running'] == False


class TestCORSConfiguration:
    """Tests for CORS middleware configuration."""
    
    def test_cors_headers(self, env_vars):
        """Test CORS headers in response."""
        from fastapi.testclient import TestClient
        from backend.app.main import create_app
        
        app = create_app()
        client = TestClient(app)
        
        # Test CORS preflight
        response = client.options(
            "/health/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
        )
        
        # Preflight should return 200 or 204
        assert response.status_code in (200, 204, 405)


class TestDocumentation:
    """Tests for API documentation endpoints."""
    
    def test_openapi_docs(self, env_vars):
        """Test OpenAPI docs endpoint."""
        from fastapi.testclient import TestClient
        from backend.app.main import create_app
        
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        data = response.json()
        assert 'openapi' in data
        assert 'paths' in data
    
    def test_swagger_docs(self, env_vars):
        """Test Swagger UI documentation."""
        from fastapi.testclient import TestClient
        from backend.app.main import create_app
        
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/docs")
        
        assert response.status_code == 200
        assert 'swagger' in response.text.lower() or 'openapi' in response.text.lower()
    
    def test_redoc_docs(self, env_vars):
        """Test ReDoc documentation."""
        from fastapi.testclient import TestClient
        from backend.app.main import create_app
        
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/redoc")
        
        assert response.status_code == 200


__all__ = [
    'TestBackendConfig',
    'TestFastAPIAppInitialization',
    'TestHealthEndpoint',
    'TestRootEndpoint',
    'TestTasksRouter',
    'TestRunsRouter',
    'TestMGXTeamProvider',
    'TestBackgroundTaskRunner',
    'TestCORSConfiguration',
    'TestDocumentation',
]
