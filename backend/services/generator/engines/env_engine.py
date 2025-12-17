# -*- coding: utf-8 -*-
"""Environment configuration generation engine."""

import json
from pathlib import Path
from typing import Dict, Any, List


class EnvEngine:
    """Handles generation of environment configuration files."""

    def __init__(self):
        self.common_vars = [
            "NODE_ENV",
            "PORT", 
            "LOG_LEVEL",
            "DATABASE_URL",
            "JWT_SECRET",
            "CORS_ORIGIN",
            "API_PREFIX",
            "REDIS_URL",
            "SMTP_HOST",
            "SMTP_PORT",
            "SMTP_USER",
            "SMTP_PASS",
            "AWS_REGION",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
        ]

    async def generate_env_files(
        self,
        project_path: Path,
        template: Dict[str, Any],
        features: List[Dict[str, Any]],
        custom_settings: Dict[str, Any]
    ):
        """Generate environment configuration files."""
        
        # Generate .env.example
        await self._generate_env_example(project_path, template, features, custom_settings)
        
        # Generate .env.local for development
        await self._generate_env_local(project_path, template, features, custom_settings)
        
        # Generate .env.production for production
        await self._generate_env_production(project_path, template, features, custom_settings)

    async def _generate_env_example(
        self,
        project_path: Path,
        template: Dict[str, Any],
        features: List[Dict[str, Any]],
        custom_settings: Dict[str, Any]
    ):
        """Generate .env.example file."""
        env_vars = self._get_env_variables(template, features, custom_settings)
        
        content = self._format_env_vars(env_vars, include_comments=True)
        
        env_path = project_path / ".env.example"
        with open(env_path, 'w') as f:
            f.write(content)

    async def _generate_env_local(
        self,
        project_path: Path,
        template: Dict[str, Any],
        features: List[Dict[str, Any]],
        custom_settings: Dict[str, Any]
    ):
        """Generate .env.local file for development."""
        env_vars = self._get_env_variables(template, features, custom_settings)
        
        # Set development defaults
        env_vars.update({
            "NODE_ENV": "development",
            "LOG_LEVEL": "debug",
            "PORT": str(custom_settings.get("port", 3000)),
        })
        
        content = self._format_env_vars(env_vars, include_comments=False)
        
        env_path = project_path / ".env.local"
        with open(env_path, 'w') as f:
            f.write(content)

    async def _generate_env_production(
        self,
        project_path: Path,
        template: Dict[str, Any],
        features: List[Dict[str, Any]],
        custom_settings: Dict[str, Any]
    ):
        """Generate .env.production file for production."""
        env_vars = self._get_env_variables(template, features, custom_settings)
        
        # Set production defaults
        env_vars.update({
            "NODE_ENV": "production",
            "LOG_LEVEL": "info",
            "PORT": str(custom_settings.get("port", 8080)),
        })
        
        content = self._format_env_vars(env_vars, include_comments=False)
        
        env_path = project_path / ".env.production"
        with open(env_path, 'w') as f:
            f.write(content)

    def _get_env_variables(
        self,
        template: Dict[str, Any],
        features: List[Dict[str, Any]],
        custom_settings: Dict[str, Any]
    ) -> Dict[str, str]:
        """Get environment variables for the project."""
        
        # Start with template variables
        env_vars = {}
        template_env_vars = template.get("environment_variables", [])
        
        for var in template_env_vars:
            env_vars[var] = custom_settings.get(var.lower(), self._get_default_value(var))
        
        # Add feature-specific variables
        for feature in features:
            feature_type = feature.get("feature_type", "")
            
            if feature_type == "auth":
                env_vars.update(self._get_auth_variables(custom_settings))
            elif feature_type == "database":
                env_vars.update(self._get_database_variables(custom_settings))
            elif feature_type == "logging":
                env_vars.update(self._get_logging_variables(custom_settings))
            elif feature_type == "email":
                env_vars.update(self._get_email_variables(custom_settings))
            elif feature_type == "cache":
                env_vars.update(self._get_cache_variables(custom_settings))
        
        # Add common variables if not present
        for var in self.common_vars:
            if var not in env_vars:
                env_vars[var] = custom_settings.get(var.lower(), self._get_default_value(var))
        
        return env_vars

    def _get_auth_variables(self, custom_settings: Dict[str, Any]) -> Dict[str, str]:
        """Get authentication-related environment variables."""
        return {
            "JWT_SECRET": custom_settings.get("jwt_secret", "your-super-secret-jwt-key-change-this"),
            "JWT_EXPIRES_IN": custom_settings.get("jwt_expires_in", "24h"),
            "BCRYPT_ROUNDS": custom_settings.get("bcrypt_rounds", "12"),
        }

    def _get_database_variables(self, custom_settings: Dict[str, Any]) -> Dict[str, str]:
        """Get database-related environment variables."""
        return {
            "DATABASE_URL": custom_settings.get("database_url", "postgresql://user:password@localhost:5432/dbname"),
            "DB_HOST": custom_settings.get("db_host", "localhost"),
            "DB_PORT": custom_settings.get("db_port", "5432"),
            "DB_NAME": custom_settings.get("db_name", "myapp"),
            "DB_USER": custom_settings.get("db_user", "user"),
            "DB_PASS": custom_settings.get("db_pass", "password"),
        }

    def _get_logging_variables(self, custom_settings: Dict[str, Any]) -> Dict[str, str]:
        """Get logging-related environment variables."""
        return {
            "LOG_LEVEL": custom_settings.get("log_level", "info"),
            "LOG_FORMAT": custom_settings.get("log_format", "json"),
            "LOG_FILE": custom_settings.get("log_file", "logs/app.log"),
        }

    def _get_email_variables(self, custom_settings: Dict[str, Any]) -> Dict[str, str]:
        """Get email-related environment variables."""
        return {
            "SMTP_HOST": custom_settings.get("smtp_host", "smtp.gmail.com"),
            "SMTP_PORT": custom_settings.get("smtp_port", "587"),
            "SMTP_SECURE": custom_settings.get("smtp_secure", "false"),
            "SMTP_USER": custom_settings.get("smtp_user", ""),
            "SMTP_PASS": custom_settings.get("smtp_pass", ""),
            "FROM_EMAIL": custom_settings.get("from_email", "noreply@example.com"),
            "FROM_NAME": custom_settings.get("from_name", "My App"),
        }

    def _get_cache_variables(self, custom_settings: Dict[str, Any]) -> Dict[str, str]:
        """Get cache-related environment variables."""
        return {
            "REDIS_URL": custom_settings.get("redis_url", "redis://localhost:6379"),
            "CACHE_TTL": custom_settings.get("cache_ttl", "3600"),
        }

    def _get_default_value(self, var_name: str) -> str:
        """Get default value for environment variable."""
        defaults = {
            "NODE_ENV": "development",
            "PORT": "3000",
            "LOG_LEVEL": "info",
            "DATABASE_URL": "",
            "JWT_SECRET": "",
            "CORS_ORIGIN": "*",
            "API_PREFIX": "/api",
            "REDIS_URL": "redis://localhost:6379",
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "",
            "SMTP_PASS": "",
            "AWS_REGION": "us-east-1",
            "AWS_ACCESS_KEY_ID": "",
            "AWS_SECRET_ACCESS_KEY": "",
        }
        
        return defaults.get(var_name, "")

    def _format_env_vars(self, env_vars: Dict[str, str], include_comments: bool = False) -> str:
        """Format environment variables as a string."""
        if not include_comments:
            return "\n".join([f"{key}={value}" for key, value in env_vars.items()])
        
        lines = []
        for key, value in env_vars.items():
            comment = self._get_var_comment(key)
            if comment:
                lines.append(f"# {comment}")
            lines.append(f"{key}={value}")
            lines.append("")  # Empty line
        
        return "\n".join(lines).rstrip()

    def _get_var_comment(self, var_name: str) -> str:
        """Get comment description for environment variable."""
        comments = {
            "NODE_ENV": "Environment (development, production, test)",
            "PORT": "Server port",
            "LOG_LEVEL": "Logging level (debug, info, warn, error)",
            "DATABASE_URL": "Database connection URL",
            "JWT_SECRET": "JWT signing secret",
            "CORS_ORIGIN": "CORS allowed origin",
            "API_PREFIX": "API route prefix",
            "REDIS_URL": "Redis connection URL",
            "SMTP_HOST": "SMTP server hostname",
            "SMTP_PORT": "SMTP server port",
            "SMTP_USER": "SMTP username",
            "SMTP_PASS": "SMTP password",
            "AWS_REGION": "AWS region",
            "AWS_ACCESS_KEY_ID": "AWS access key ID",
            "AWS_SECRET_ACCESS_KEY": "AWS secret access key",
            "JWT_EXPIRES_IN": "JWT token expiration time",
            "BCRYPT_ROUNDS": "BCrypt salt rounds",
            "DB_HOST": "Database host",
            "DB_PORT": "Database port",
            "DB_NAME": "Database name",
            "DB_USER": "Database username",
            "DB_PASS": "Database password",
            "LOG_FORMAT": "Log format (json, text)",
            "LOG_FILE": "Log file path",
            "SMTP_SECURE": "Use TLS for SMTP",
            "FROM_EMAIL": "Default from email address",
            "FROM_NAME": "Default from name",
            "CACHE_TTL": "Cache time-to-live in seconds",
        }
        
        return comments.get(var_name, f"{var_name} configuration")