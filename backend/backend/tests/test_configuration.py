import pytest
from backend.config import Settings
import os
from unittest.mock import patch

class TestConfiguration:
    
    def test_settings_load_defaults(self):
        """Test loading settings with defaults"""
        settings = Settings()
        assert settings.api_host == "127.0.0.1"
        assert settings.api_port == 8000
        
    def test_settings_env_override(self):
        """Test overriding settings with environment variables"""
        with patch.dict(os.environ, {"API_PORT": "9000", "MGX_ENV": "production"}):
            # Reload settings or create new instance
            # Pydantic BaseSettings reads env vars on init
            settings = Settings()
            assert settings.api_port == 9000
            
    def test_database_url_generation(self):
        """Test database URL generation"""
        settings = Settings(
            db_user="user",
            db_password="password",
            db_host="localhost",
            db_port=5432,
            db_name="testdb"
        )
        assert str(settings.database_url) == "postgresql://user:password@localhost:5432/testdb"
        assert str(settings.async_database_url) == "postgresql+asyncpg://user:password@localhost:5432/testdb"

    def test_required_settings(self):
        """Test validation of required settings"""
        # Assuming some settings might be required without defaults in strict mode
        pass
