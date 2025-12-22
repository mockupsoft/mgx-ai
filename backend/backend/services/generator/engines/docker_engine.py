# -*- coding: utf-8 -*-
"""Docker configuration generation engine."""

import json
from pathlib import Path
from typing import Dict, Any, List


class DockerEngine:
    """Handles generation of Docker configuration files."""

    def __init__(self):
        self.stack_dockerfiles = {
            "express_ts": "express_ts/Dockerfile.template",
            "fastapi": "fastapi/Dockerfile.template", 
            "nextjs": "nextjs/Dockerfile.template",
            "laravel": "laravel/Dockerfile.template",
        }

    async def generate_docker_files(
        self,
        project_path: Path,
        template: Dict[str, Any],
        features: List[Dict[str, Any]],
        custom_settings: Dict[str, Any]
    ):
        """Generate Docker configuration files."""
        
        # Generate Dockerfile
        await self._generate_dockerfile(project_path, template, features, custom_settings)
        
        # Generate docker-compose.yml
        await self._generate_docker_compose(project_path, template, features, custom_settings)
        
        # Generate .dockerignore
        await self._generate_dockerignore(project_path, template, features, custom_settings)

    async def _generate_dockerfile(
        self,
        project_path: Path,
        template: Dict[str, Any],
        features: List[Dict[str, Any]],
        custom_settings: Dict[str, Any]
    ):
        """Generate Dockerfile from template."""
        stack = template.get("stack", "")
        dockerfile_template = self.stack_dockerfiles.get(stack)
        
        if dockerfile_template:
            # Use template-specific Dockerfile
            template_path = Path(__file__).parent.parent / "templates" / dockerfile_template
            
            if template_path.exists():
                with open(template_path, 'r') as f:
                    dockerfile_content = f.read()
                
                # Process template variables
                dockerfile_content = self._process_template_variables(dockerfile_content, custom_settings)
                
                dockerfile_path = project_path / "Dockerfile"
                with open(dockerfile_path, 'w') as f:
                    f.write(dockerfile_content)
            else:
                # Generate Dockerfile from scratch
                await self._generate_dockerfile_from_scratch(project_path, stack, custom_settings)
        else:
            await self._generate_dockerfile_from_scratch(project_path, stack, custom_settings)

    async def _generate_dockerfile_from_scratch(
        self,
        project_path: Path,
        stack: str,
        custom_settings: Dict[str, Any]
    ):
        """Generate Dockerfile from scratch based on stack."""
        port = custom_settings.get("port", 3000)
        
        if stack == "express_ts":
            dockerfile_content = f"""# Express.js with TypeScript Dockerfile
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Expose port
EXPOSE {port}

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
  CMD curl -f http://localhost:{port}/health || exit 1

# Start the application
CMD ["npm", "start"]
"""
        elif stack == "fastapi":
            dockerfile_content = f"""# FastAPI Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE {port}

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
  CMD curl -f http://localhost:{port}/health || exit 1

# Start the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "{port}"]
"""
        elif stack == "nextjs":
            dockerfile_content = f"""# Next.js Dockerfile
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Expose port
EXPOSE {port}

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
  CMD curl -f http://localhost:{port}/api/health || exit 1

# Start the application
CMD ["npm", "start"]
"""
        else:
            # Generic Dockerfile
            dockerfile_content = f"""# Generic Dockerfile
FROM alpine:latest

WORKDIR /app

# Add your application files here
COPY . .

# Expose port
EXPOSE {port}

# Start command (modify as needed)
CMD ["echo", "Container started successfully"]
"""
        
        dockerfile_path = project_path / "Dockerfile"
        with open(dockerfile_path, 'w') as f:
            f.write(dockerfile_content)

    async def _generate_docker_compose(
        self,
        project_path: Path,
        template: Dict[str, Any],
        features: List[Dict[str, Any]],
        custom_settings: Dict[str, Any]
    ):
        """Generate docker-compose.yml file."""
        
        stack = template.get("stack", "")
        project_name = custom_settings.get("project_name", "my-project")
        port = custom_settings.get("port", 3000)
        
        # Check if database feature is enabled
        has_database = any(feature.get("feature_type") == "database" for feature in features)
        
        services = {
            "app": {
                "build": ".",
                "ports": [f"{port}:{port}"],
                "environment": ["NODE_ENV=development"],
                "volumes": [".:/app", "/app/node_modules"],
                "depends_on": [],
            }
        }
        
        # Add database if feature is enabled
        if has_database:
            services["app"]["depends_on"].append("database")
            services["database"] = {
                "image": "postgres:15-alpine",
                "environment": {
                    "POSTGRES_DB": "myapp",
                    "POSTGRES_USER": "user",
                    "POSTGRES_PASSWORD": "password",
                },
                "volumes": ["postgres_data:/var/lib/postgresql/data"],
                "ports": ["5432:5432"],
            }
        
        # Add Redis if caching is enabled
        has_cache = any(feature.get("feature_type") == "cache" for feature in features)
        if has_cache:
            services["app"]["depends_on"].append("redis")
            services["redis"] = {
                "image": "redis:7-alpine",
                "ports": ["6379:6379"],
            }
        
        docker_compose = {
            "version": "3.8",
            "services": services,
            "volumes": {},
        }
        
        if has_database:
            docker_compose["volumes"]["postgres_data"] = {}
        
        # Write docker-compose.yml
        compose_path = project_path / "docker-compose.yml"
        with open(compose_path, 'w') as f:
            json.dump(docker_compose, f, indent=2)

    async def _generate_dockerignore(
        self,
        project_path: Path,
        template: Dict[str, Any],
        features: List[Dict[str, Any]],
        custom_settings: Dict[str, Any]
    ):
        """Generate .dockerignore file."""
        
        stack = template.get("stack", "")
        
        common_ignore = [
            ".git",
            ".gitignore",
            "README.md",
            "Dockerfile",
            "docker-compose.yml",
            ".dockerignore",
            "node_modules",
            "__pycache__",
            "*.pyc",
            ".pytest_cache",
            ".coverage",
            "htmlcov",
            ".tox",
            "venv",
            ".venv",
            ".env",
            ".env.local",
            ".env.production",
            "logs",
            "*.log",
            "coverage",
            ".nyc_output",
        ]
        
        stack_specific_ignore = []
        
        if stack == "express_ts":
            stack_specific_ignore = [
                "dist",
                "build",
                ".tsbuildinfo",
            ]
        elif stack == "fastapi":
            stack_specific_ignore = [
                "__pycache__",
                "*.pyc",
                ".pytest_cache",
                ".coverage",
            ]
        elif stack == "nextjs":
            stack_specific_ignore = [
                ".next",
                "out",
                "dist",
            ]
        
        all_ignore = common_ignore + stack_specific_ignore
        
        dockerignore_path = project_path / ".dockerignore"
        with open(dockerignore_path, 'w') as f:
            f.write("\n".join(all_ignore))

    def _process_template_variables(self, content: str, custom_settings: Dict[str, Any]) -> str:
        """Process template variables in Docker files."""
        replacements = {
            "{{PORT}}": str(custom_settings.get("port", 3000)),
            "{{PROJECT_NAME}}": custom_settings.get("project_name", "my-project"),
            "{{NODE_ENV}}": custom_settings.get("node_env", "development"),
        }
        
        for placeholder, value in replacements.items():
            content = content.replace(placeholder, str(value))
        
        return content