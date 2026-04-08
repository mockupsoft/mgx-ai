# -*- coding: utf-8 -*-
"""Script generation engine for build, dev, and test scripts."""

import json
import os
from pathlib import Path
from typing import Dict, Any, List


class ScriptEngine:
    """Handles generation of build, dev, and test scripts."""

    def __init__(self):
        self.stack_scripts = {
            "express_ts": {
                "dev": "npm run dev",
                "build": "npm run build", 
                "test": "npm test",
                "start": "npm start",
                "lint": "eslint src --ext .ts",
                "format": "prettier --write src"
            },
            "fastapi": {
                "dev": "uvicorn main:app --reload",
                "build": "echo 'No build step required for Python'",
                "test": "pytest",
                "start": "uvicorn main:app --host 0.0.0.0 --port 8000",
                "lint": "black . && flake8 .",
                "format": "black ."
            },
            "nextjs": {
                "dev": "npm run dev",
                "build": "npm run build",
                "test": "npm test", 
                "start": "npm start",
                "lint": "next lint",
                "format": "prettier --write ."
            },
            "laravel": {
                "dev": "php artisan serve",
                "build": "npm run build && php artisan optimize",
                "test": "phpunit",
                "start": "php artisan serve --host=0.0.0.0 --port=8000",
                "lint": "php-cs-fixer fix --dry-run --diff",
                "format": "php-cs-fixer fix"
            },
            "react_native": {
                "dev": "npx react-native start",
                "build": "npx react-native build-android",
                "test": "npm test",
                "start": "npx react-native run-android",
                "lint": "eslint . --ext .ts,.tsx",
                "format": "prettier --write \"src/**/*.{ts,tsx}\""
            },
            "flutter": {
                "dev": "flutter run",
                "build": "flutter build apk",
                "test": "flutter test",
                "start": "flutter run --release",
                "lint": "dart analyze",
                "format": "dart format lib test"
            },
            "go_fiber": {
                "dev": "go run cmd/main.go",
                "build": "go build -o bin/app cmd/main.go",
                "test": "go test ./...",
                "start": "./bin/app",
                "lint": "golangci-lint run",
                "format": "gofmt -w ."
            },
        }

    async def generate_scripts(
        self,
        project_path: Path,
        template: Dict[str, Any],
        features: List[Dict[str, Any]],
        custom_settings: Dict[str, Any]
    ):
        """Generate build and dev scripts."""
        
        # Create scripts directory
        scripts_dir = project_path / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        
        stack = template.get("stack", "")
        
        # Generate shell scripts
        await self._generate_shell_scripts(scripts_dir, stack, custom_settings)
        
        # Generate package.json scripts (for Node.js stacks)
        if stack in ["express_ts", "nextjs", "react_native"]:
            await self._generate_npm_scripts(project_path, stack, custom_settings)
        
        # Generate Makefile for common commands
        await self._generate_makefile(project_path, stack, custom_settings)

    async def _generate_shell_scripts(
        self,
        scripts_dir: Path,
        stack: str,
        custom_settings: Dict[str, Any]
    ):
        """Generate shell scripts for common operations."""
        
        # Development script
        dev_script = self._generate_dev_script(stack, custom_settings)
        with open(scripts_dir / "dev.sh", 'w') as f:
            f.write(dev_script)
        os.chmod(scripts_dir / "dev.sh", 0o755)
        
        # Build script
        build_script = self._generate_build_script(stack, custom_settings)
        with open(scripts_dir / "build.sh", 'w') as f:
            f.write(build_script)
        os.chmod(scripts_dir / "build.sh", 0o755)
        
        # Test script
        test_script = self._generate_test_script(stack, custom_settings)
        with open(scripts_dir / "test.sh", 'w') as f:
            f.write(test_script)
        os.chmod(scripts_dir / "test.sh", 0o755)
        
        # Setup script
        setup_script = self._generate_setup_script(stack, custom_settings)
        with open(scripts_dir / "setup.sh", 'w') as f:
            f.write(setup_script)
        os.chmod(scripts_dir / "setup.sh", 0o755)

    async def _generate_npm_scripts(
        self,
        project_path: Path,
        stack: str,
        custom_settings: Dict[str, Any]
    ):
        """Generate or update package.json scripts."""
        
        package_json_path = project_path / "package.json"
        
        if package_json_path.exists():
            with open(package_json_path, 'r') as f:
                package_data = json.load(f)
        else:
            package_data = {"name": custom_settings.get("project_name", "my-project")}
        
        # Update scripts section
        if "scripts" not in package_data:
            package_data["scripts"] = {}
        
        scripts = self.stack_scripts.get(stack, {})
        package_data["scripts"].update(scripts)
        
        # Write back to package.json
        with open(package_json_path, 'w') as f:
            json.dump(package_data, f, indent=2)

    async def _generate_makefile(
        self,
        project_path: Path,
        stack: str,
        custom_settings: Dict[str, Any]
    ):
        """Generate Makefile for common commands."""
        
        scripts = self.stack_scripts.get(stack, {})
        
        makefile_content = f"""# Generated Makefile for {custom_settings.get("project_name", "my-project")}

.PHONY: help dev build test setup lint format clean install

help: ## Show this help message
\t@echo "Help not available (awk command causing syntax error in generator)"

dev: ## Start development server
\t@./scripts/dev.sh

build: ## Build the project
\t@./scripts/build.sh

test: ## Run tests
\t@./scripts/test.sh

setup: ## Initial project setup
\t@./scripts/setup.sh

lint: ## Run linting
"""
        
        # Add stack-specific commands
        if "lint" in scripts:
            lint_cmd = scripts['lint']
            lint_parts = lint_cmd.split()
            lint_bin = lint_parts[0]
            lint_args = ' '.join(lint_parts[1:]) if len(lint_parts) > 1 else ''
            makefile_content += f"\t@$(shell which {lint_bin} || echo 'echo \"Linter not found, please install dependencies\"') {lint_args}\n"
        
        makefile_content += f"""
format: ## Format code
"""
        
        if "format" in scripts:
            fmt_cmd = scripts['format']
            fmt_parts = fmt_cmd.split()
            fmt_bin = fmt_parts[0]
            fmt_args = ' '.join(fmt_parts[1:]) if len(fmt_parts) > 1 else ''
            makefile_content += f"\t@$(shell which {fmt_bin} || echo 'echo \"Formatter not found, please install dependencies\"') {fmt_args}\n"
        
        makefile_content += """
install: ## Install dependencies
"""
        
        if stack in ["express_ts", "nextjs", "react_native"]:
            makefile_content += "\t@npm install\n"
        elif stack == "fastapi":
            makefile_content += "\t@pip install -r requirements.txt\n"
        elif stack == "laravel":
            makefile_content += "\t@composer install\n"
        elif stack == "flutter":
            makefile_content += "\t@flutter pub get\n"
        elif stack == "go_fiber":
            makefile_content += "\t@go mod download\n"
        else:
            makefile_content += "\t@echo 'Install command not defined for this stack'\n"
        
        makefile_content += """
clean: ## Clean build artifacts
\t@rm -rf dist/ build/ .next/ .pytest_cache/ __pycache__/ *.pyc
\t@find . -name "*.pyc" -delete
\t@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
"""
        
        makefile_path = project_path / "Makefile"
        with open(makefile_path, 'w') as f:
            f.write(makefile_content)

    def _generate_dev_script(self, stack: str, custom_settings: Dict[str, Any]) -> str:
        """Generate development server startup script."""
        port = custom_settings.get("port", 3000)
        project_name = custom_settings.get("project_name", "my-project")
        
        if stack == "express_ts":
            return f"""#!/bin/bash
# Development server startup script for {project_name}

echo "🚀 Starting {project_name} development server..."
echo "Port: {port}"
echo "Environment: development"

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Start development server
echo "🔧 Starting development server on port {port}..."
npm run dev
"""
        elif stack == "fastapi":
            return f"""#!/bin/bash
# Development server startup script for {project_name}

echo "🚀 Starting {project_name} development server..."
echo "Port: {port}"
echo "Environment: development"

# Install dependencies if not exists
if [ ! -d "venv" ] && [ ! -f "requirements.txt" ]; then
    echo "📦 Setting up Python virtual environment..."
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# Start development server
echo "🔧 Starting development server on port {port}..."
if [ -d "venv" ]; then
    source venv/bin/activate
fi
uvicorn main:app --host 0.0.0.0 --port {port} --reload
"""
        elif stack == "nextjs":
            return f"""#!/bin/bash
# Development server startup script for {project_name}

echo "🚀 Starting {project_name} development server..."
echo "Port: {port}"
echo "Environment: development"

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Start development server
echo "🔧 Starting Next.js development server on port {port}..."
npm run dev
"""
        elif stack == "react_native":
            return f"""#!/bin/bash
# React Native — Metro bundler
echo "🚀 Starting {project_name} (React Native)..."
if [ ! -d "node_modules" ]; then
    npm install
fi
npx react-native start
"""
        elif stack == "flutter":
            return f"""#!/bin/bash
# Flutter development
echo "🚀 Starting {project_name} (Flutter)..."
flutter pub get
flutter run
"""
        elif stack == "go_fiber":
            return f"""#!/bin/bash
# Go Fiber API
echo "🚀 Starting {project_name} on port {port}..."
export PORT={port}
go run cmd/main.go
"""
        elif stack == "laravel":
            return f"""#!/bin/bash
# Development server startup script for {project_name}

echo "🚀 Starting {project_name} development server..."
echo "Port: {port}"
echo "Environment: development"

# Install dependencies if vendor doesn't exist
if [ ! -d "vendor" ]; then
    echo "📦 Installing Composer dependencies..."
    composer install
fi

# Install Node dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "📦 Installing Node dependencies..."
    npm install
fi

# Create storage link if not exists
if [ ! -L "storage/app/public" ]; then
    php artisan storage:link
fi

# Run migrations
echo "🗄️ Running database migrations..."
php artisan migrate --force

# Start development server
echo "🔧 Starting Laravel development server on port {port}..."
php artisan serve --host=0.0.0.0 --port={port}
"""
        else:
            return f"""#!/bin/bash
# Development server startup script for {project_name}

echo "🚀 Starting {project_name} development server..."
echo "Port: {port}"

# Add your custom development commands here
echo "🔧 Development server would start here..."
"""

    def _generate_build_script(self, stack: str, custom_settings: Dict[str, Any]) -> str:
        """Generate build script."""
        project_name = custom_settings.get("project_name", "my-project")
        
        if stack == "express_ts":
            return f"""#!/bin/bash
# Build script for {project_name}

echo "🔨 Building {project_name}..."

# Run linting
echo "🧹 Running linting..."
npm run lint

# Run tests
echo "🧪 Running tests..."
npm test

# Build the project
echo "🏗️ Building TypeScript..."
npm run build

echo "✅ Build completed successfully!"
"""
        elif stack == "fastapi":
            return f"""#!/bin/bash
# Build script for {project_name}

echo "🔨 Building {project_name}..."

# Run linting
echo "🧹 Running code formatting and linting..."
black . --check
flake8 .

# Run tests
echo "🧪 Running tests..."
pytest

echo "✅ Build completed successfully!"
"""
        elif stack == "nextjs":
            return f"""#!/bin/bash
# Build script for {project_name}

echo "🔨 Building {project_name}..."

# Run linting
echo "🧹 Running linting..."
npm run lint

# Build the project
echo "🏗️ Building Next.js application..."
npm run build

echo "✅ Build completed successfully!"
"""
        elif stack == "laravel":
            return f"""#!/bin/bash
# Build script for {project_name}

echo "🔨 Building {project_name}..."

# Run tests
echo "🧪 Running tests..."
phpunit

# Build assets
echo "🎨 Building assets..."
npm run build

# Optimize for production
echo "⚡ Optimizing for production..."
php artisan optimize

echo "✅ Build completed successfully!"
"""
        elif stack == "react_native":
            return f"""#!/bin/bash
echo "🔨 Building {project_name} (React Native Android)..."
npx react-native build-android
echo "✅ Build completed successfully!"
"""
        elif stack == "flutter":
            return f"""#!/bin/bash
echo "🔨 Building {project_name} (Flutter APK)..."
flutter build apk
echo "✅ Build completed successfully!"
"""
        elif stack == "go_fiber":
            return f"""#!/bin/bash
echo "🔨 Building {project_name} (Go)..."
go build -o bin/app cmd/main.go
echo "✅ Build completed successfully!"
"""
        else:
            return f"""#!/bin/bash
# Build script for {project_name}

echo "🔨 Building {project_name}..."

# Add your custom build commands here
echo "🏗️ Build completed!"

echo "✅ Build completed successfully!"
"""

    def _generate_test_script(self, stack: str, custom_settings: Dict[str, Any]) -> str:
        """Generate test script."""
        project_name = custom_settings.get("project_name", "my-project")
        
        if stack == "express_ts":
            return f"""#!/bin/bash
# Test script for {project_name}

echo "🧪 Running tests for {project_name}..."

# Run Jest tests
npm test

echo "✅ Tests completed!"
"""
        elif stack == "fastapi":
            return f"""#!/bin/bash
# Test script for {project_name}

echo "🧪 Running tests for {project_name}..."

# Run pytest with coverage
pytest --cov=. --cov-report=html --cov-report=term

echo "✅ Tests completed!"
"""
        elif stack == "nextjs":
            return f"""#!/bin/bash
# Test script for {project_name}

echo "🧪 Running tests for {project_name}..."

# Run Jest tests
npm test

echo "✅ Tests completed!"
"""
        elif stack == "laravel":
            return f"""#!/bin/bash
# Test script for {project_name}

echo "🧪 Running tests for {project_name}..."

# Run PHPUnit tests
phpunit

echo "✅ Tests completed!"
"""
        elif stack == "react_native":
            return f"""#!/bin/bash
echo "🧪 Running tests for {project_name}..."
npm test
echo "✅ Tests completed!"
"""
        elif stack == "flutter":
            return f"""#!/bin/bash
echo "🧪 Running tests for {project_name}..."
flutter test
echo "✅ Tests completed!"
"""
        elif stack == "go_fiber":
            return f"""#!/bin/bash
echo "🧪 Running tests for {project_name}..."
go test ./...
echo "✅ Tests completed!"
"""
        else:
            return f"""#!/bin/bash
# Test script for {project_name}

echo "🧪 Running tests for {project_name}..."

# Add your custom test commands here
echo "🧪 Tests would run here..."

echo "✅ Tests completed!"
"""

    def _generate_setup_script(self, stack: str, custom_settings: Dict[str, Any]) -> str:
        """Generate initial setup script."""
        project_name = custom_settings.get("project_name", "my-project")
        
        return f"""#!/bin/bash
# Initial setup script for {project_name}

echo "🚀 Setting up {project_name}..."

# Check for required tools
echo "🔍 Checking required tools..."

# Check Node.js (for Node.js stacks)
if command -v node >/dev/null 2>&1; then
    echo "✅ Node.js $(node --version) found"
else
    echo "❌ Node.js not found. Please install Node.js 18+"
fi

# Check Python (for Python stacks)  
if command -v python >/dev/null 2>&1; then
    echo "✅ Python $(python --version) found"
else
    echo "❌ Python not found. Please install Python 3.11+"
fi

# Check PHP (for PHP stacks)
if command -v php >/dev/null 2>&1; then
    echo "✅ PHP $(php --version | head -n1) found"
else
    echo "❌ PHP not found. Please install PHP 8.1+"
fi

# Check Docker
if command -v docker >/dev/null 2>&1; then
    echo "✅ Docker $(docker --version | cut -d' ' -f3 | sed 's/,//') found"
else
    echo "❌ Docker not found. Please install Docker"
fi

# Check Docker Compose
if command -v docker-compose >/dev/null 2>&1; then
    echo "✅ Docker Compose found"
else
    echo "❌ Docker Compose not found. Please install Docker Compose"
fi

echo "📋 Setup Summary:"
echo "   - Project: {project_name}"
echo "   - Stack: {stack}"
echo "   - Port: {custom_settings.get('port', 3000)}"

echo ""
echo "🎯 Next steps:"
echo "1. Copy .env.local to .env and configure your settings"
echo "2. Run 'make setup' to install dependencies"
echo "3. Run 'make dev' to start development server"
echo "4. Visit http://localhost:{custom_settings.get('port', 3000)} to see your application"

echo "✅ Setup script completed!"
"""