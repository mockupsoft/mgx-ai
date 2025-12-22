# -*- coding: utf-8 -*-
"""Database seeding script for Project Generator templates."""

import asyncio
import sys
from pathlib import Path

# Add the backend directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.models import Base, ProjectTemplate, TemplateFeature
from backend.db.models.enums import (
    StackType, 
    TemplateFeatureType, 
    ProjectTemplateStatus
)
from backend.services.generator.template_manager import TemplateManager


async def seed_templates():
    """Seed the database with initial project templates."""
    
    # Create database connection
    engine = create_engine("sqlite:///generator_templates.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("🌱 Seeding project generator templates...")
        
        # Create templates
        await create_express_ts_template(session)
        await create_fastapi_template(session) 
        await create_nextjs_template(session)
        await create_laravel_template(session)
        
        # Create common features
        await create_common_features(session)
        
        session.commit()
        print("✅ Database seeding completed successfully!")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error seeding database: {str(e)}")
        raise
    finally:
        session.close()


async def create_express_ts_template(session):
    """Create Express.js TypeScript template."""
    print("📦 Creating Express.js TypeScript template...")
    
    template = ProjectTemplate(
        name="Express.js API Server",
        description="RESTful API server built with Express.js and TypeScript",
        stack=StackType.EXPRESS_TS,
        version="1.0.0",
        status=ProjectTemplateStatus.ACTIVE,
        author="Project Generator",
        manifest={
            "files": {
                "package.json": "express_ts/package.json.template",
                "tsconfig.json": "express_ts/tsconfig.json.template",
                "src/server.ts": "express_ts/src/server.ts.template",
                "src/routes/health.ts": "express_ts/src/routes/health.ts.template",
                "src/middleware/auth.ts": "express_ts/src/middleware/auth.ts.template",
                "src/middleware/error.ts": "express_ts/src/middleware/error.ts.template",
                "src/utils/logger.ts": "express_ts/src/utils/logger.ts.template",
                "tests/health.test.ts": "express_ts/tests/health.test.ts.template",
                ".eslintrc.json": "express_ts/.eslintrc.json.template",
                ".prettierrc": "express_ts/.prettierrc.template",
                "README.md": "express_ts/README.md.template",
                "SETUP_GUIDE.md": "common/SETUP_GUIDE.md.template"
            },
            "scripts": {
                "dev": "npm run dev",
                "build": "npm run build",
                "test": "npm test",
                "start": "node dist/server.js",
                "lint": "eslint src --ext .ts",
                "lint:fix": "eslint src --ext .ts --fix",
                "format": "prettier --write src"
            },
            "env_vars": [
                "PORT", "NODE_ENV", "DATABASE_URL", "LOG_LEVEL", "CORS_ORIGIN", "JWT_SECRET"
            ]
        },
        default_features=["testing", "logging", "validation"],
        supported_features=[
            "auth", "database", "logging", "validation", "testing", 
            "docker", "cicd", "api_docs", "websocket", "file_upload"
        ],
        environment_variables=[
            "PORT", "NODE_ENV", "DATABASE_URL", "LOG_LEVEL", 
            "CORS_ORIGIN", "JWT_SECRET"
        ]
    )
    
    session.add(template)
    session.flush()  # Get the ID
    
    print(f"  ✓ Created template: {template.name} (ID: {template.id})")


async def create_fastapi_template(session):
    """Create FastAPI Python template."""
    print("🐍 Creating FastAPI Python template...")
    
    template = ProjectTemplate(
        name="FastAPI Python Server",
        description="Modern Python web framework for building APIs",
        stack=StackType.FASTAPI,
        version="1.0.0",
        status=ProjectTemplateStatus.ACTIVE,
        author="Project Generator",
        manifest={
            "files": {
                "main.py": "fastapi/main.py.template",
                "requirements.txt": "fastapi/requirements.txt.template",
                "pyproject.toml": "fastapi/pyproject.toml.template",
                "app/api/health.py": "fastapi/app/api/health.py.template",
                "app/core/config.py": "fastapi/app/core/config.py.template",
                "tests/test_health.py": "fastapi/tests/test_health.py.template",
                "Dockerfile": "fastapi/Dockerfile.template",
                ".env.example": "fastapi/.env.example.template",
                "README.md": "fastapi/README.md.template"
            },
            "scripts": {
                "dev": "uvicorn main:app --reload --host 0.0.0.0 --port 8000",
                "build": "echo 'No build step required for Python'",
                "test": "pytest",
                "start": "uvicorn main:app --host 0.0.0.0 --port 8000",
                "lint": "black . && flake8 .",
                "format": "black ."
            },
            "env_vars": [
                "APP_NAME", "APP_VERSION", "DEBUG", "DATABASE_URL", "SECRET_KEY", "ALLOWED_HOSTS"
            ]
        },
        default_features=["testing", "logging"],
        supported_features=[
            "auth", "database", "logging", "validation", "testing", "docker", "api_docs"
        ],
        environment_variables=[
            "APP_NAME", "APP_VERSION", "DEBUG", "DATABASE_URL", "SECRET_KEY", "ALLOWED_HOSTS"
        ]
    )
    
    session.add(template)
    session.flush()
    
    print(f"  ✓ Created template: {template.name} (ID: {template.id})")


async def create_nextjs_template(session):
    """Create Next.js React template."""
    print("⚛️ Creating Next.js React template...")
    
    template = ProjectTemplate(
        name="Next.js React App",
        description="Full-stack React framework with server-side rendering",
        stack=StackType.NEXTJS,
        version="1.0.0",
        status=ProjectTemplateStatus.DRAFT,  # Template files not fully implemented yet
        author="Project Generator",
        manifest={
            "files": {
                "package.json": "nextjs/package.json.template",
                "tsconfig.json": "nextjs/tsconfig.json.template",
                "next.config.ts": "nextjs/next.config.ts.template",
                "app/page.tsx": "nextjs/app/page.tsx.template",
                "app/layout.tsx": "nextjs/app/layout.tsx.template",
                "app/api/health/route.ts": "nextjs/app/api/health/route.ts.template",
                "components/Header.tsx": "nextjs/components/Header.tsx.template",
                "styles/globals.css": "nextjs/styles/globals.css.template",
                "Dockerfile": "nextjs/Dockerfile.template",
                ".env.local.example": "nextjs/.env.local.example.template",
                "README.md": "nextjs/README.md.template"
            },
            "scripts": {
                "dev": "next dev",
                "build": "next build",
                "start": "next start",
                "test": "jest",
                "lint": "next lint",
                "format": "prettier --write ."
            },
            "env_vars": ["NEXT_PUBLIC_API_URL", "NODE_ENV", "PORT"]
        },
        default_features=["testing"],
        supported_features=["auth", "database", "testing", "docker", "cicd"],
        environment_variables=["NEXT_PUBLIC_API_URL", "NODE_ENV", "PORT"]
    )
    
    session.add(template)
    session.flush()
    
    print(f"  ✓ Created template: {template.name} (ID: {template.id})")


async def create_laravel_template(session):
    """Create Laravel PHP template."""
    print("🎼 Creating Laravel PHP template...")
    
    template = ProjectTemplate(
        name="Laravel PHP Framework",
        description="PHP web application framework with expressive, elegant syntax",
        stack=StackType.LARAVEL,
        version="1.0.0",
        status=ProjectTemplateStatus.DRAFT,  # Template files not fully implemented yet
        author="Project Generator",
        manifest={
            "files": {
                "composer.json": "laravel/composer.json.template",
                "artisan": "laravel/artisan.template",
                "app/Http/Controllers/HealthController.php": "laravel/app/Http/Controllers/HealthController.php.template",
                "routes/api.php": "laravel/routes/api.php.template",
                "tests/Feature/HealthTest.php": "laravel/tests/Feature/HealthTest.php.template",
                "Dockerfile": "laravel/Dockerfile.template",
                ".env.example": "laravel/.env.example.template",
                "README.md": "laravel/README.md.template"
            },
            "scripts": {
                "dev": "php artisan serve",
                "build": "npm run build && php artisan optimize",
                "test": "phpunit",
                "start": "php artisan serve --host=0.0.0.0 --port=8000",
                "lint": "php-cs-fixer fix --dry-run --diff",
                "format": "php-cs-fixer fix"
            },
            "env_vars": ["APP_NAME", "APP_ENV", "APP_DEBUG", "DB_CONNECTION", "DB_HOST", "DB_PORT"]
        },
        default_features=["testing"],
        supported_features=["auth", "database", "testing", "docker"],
        environment_variables=["APP_NAME", "APP_ENV", "APP_DEBUG", "DB_CONNECTION", "DB_HOST", "DB_PORT"]
    )
    
    session.add(template)
    session.flush()
    
    print(f"  ✓ Created template: {template.name} (ID: {template.id})")


async def create_common_features(session):
    """Create common template features."""
    print("🔧 Creating common template features...")
    
    features = [
        TemplateFeature(
            name="authentication",
            display_name="Authentication System",
            description="JWT-based authentication with login/register endpoints",
            feature_type=TemplateFeatureType.AUTH,
            compatible_stacks=["express_ts", "fastapi", "nextjs", "laravel"],
            version="1.0.0",
            author="Project Generator",
            tags=["auth", "security", "jwt"]
        ),
        TemplateFeature(
            name="database",
            display_name="Database Integration", 
            description="Database setup with ORM and migration tools",
            feature_type=TemplateFeatureType.DATABASE,
            compatible_stacks=["express_ts", "fastapi", "nextjs", "laravel"],
            version="1.0.0",
            author="Project Generator",
            tags=["database", "orm", "migrations"]
        ),
        TemplateFeature(
            name="logging",
            display_name="Structured Logging",
            description="Comprehensive logging system with structured output",
            feature_type=TemplateFeatureType.LOGGING,
            compatible_stacks=["express_ts", "fastapi", "nextjs", "laravel"],
            version="1.0.0",
            author="Project Generator",
            tags=["logging", "monitoring", "debugging"]
        ),
        TemplateFeature(
            name="testing",
            display_name="Testing Framework",
            description="Complete testing setup with unit and integration tests",
            feature_type=TemplateFeatureType.TESTING,
            compatible_stacks=["express_ts", "fastapi", "nextjs", "laravel"],
            version="1.0.0",
            author="Project Generator",
            tags=["testing", "unit-tests", "integration"]
        ),
        TemplateFeature(
            name="docker",
            display_name="Docker Configuration",
            description="Docker containerization with multi-stage builds",
            feature_type=TemplateFeatureType.DOCKER,
            compatible_stacks=["express_ts", "fastapi", "nextjs", "laravel"],
            version="1.0.0",
            author="Project Generator",
            tags=["docker", "containerization", "deployment"]
        ),
        TemplateFeature(
            name="api_docs",
            display_name="API Documentation",
            description="Automatic API documentation with Swagger/OpenAPI",
            feature_type=TemplateFeatureType.API_DOCS,
            compatible_stacks=["express_ts", "fastapi"],
            version="1.0.0",
            author="Project Generator",
            tags=["api", "documentation", "swagger"]
        )
    ]
    
    for feature in features:
        session.add(feature)
        session.flush()
        print(f"  ✓ Created feature: {feature.display_name} (ID: {feature.id})")


if __name__ == "__main__":
    asyncio.run(seed_templates())