# -*- coding: utf-8 -*-
"""
MGX Agent Stack Specifications Module

Web geliştirme stack'leri için teknik spesifikasyonlar.
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

__all__ = [
    'StackCategory',
    'ProjectType',
    'OutputMode',
    'StackSpec',
    'STACK_SPECS',
    'get_stack_spec',
    'infer_stack_from_task',
]


class StackCategory(str, Enum):
    """Stack kategorileri"""
    BACKEND = "backend"
    FRONTEND = "frontend"
    DEVOPS = "devops"


class ProjectType(str, Enum):
    """Proje tipleri"""
    API = "api"
    WEBAPP = "webapp"
    FULLSTACK = "fullstack"
    DEVOPS = "devops"


class OutputMode(str, Enum):
    """Çıktı modları"""
    GENERATE_NEW = "generate_new"
    PATCH_EXISTING = "patch_existing"


class StackSpec(BaseModel):
    """Stack teknik spesifikasyonu"""
    
    stack_id: str = Field(..., description="Benzersiz stack kimliği")
    name: str = Field(..., description="İnsan okunabilir isim")
    category: StackCategory = Field(..., description="Stack kategorisi")
    language: str = Field(..., description="Programlama dili (ts/js/php/py/cs)")
    
    # Araçlar
    test_framework: str = Field(..., description="Test framework (jest/vitest/phpunit/pytest)")
    package_manager: str = Field(..., description="Paket yöneticisi (npm/pnpm/composer/pip)")
    linter_formatter: str = Field(..., description="Linter & formatter (eslint+prettier/pint/ruff)")
    
    # Proje yapısı
    project_layout: Dict[str, str] = Field(
        default_factory=dict,
        description="Beklenen dosya/klasör yapısı"
    )
    
    # Komutlar
    run_commands: Dict[str, str] = Field(
        default_factory=dict,
        description="Geliştirme komutları (dev/build/test/start)"
    )
    
    # Özellikler
    docker_templates: bool = Field(default=False, description="Docker template desteği")
    ci_templates: bool = Field(default=False, description="CI/CD template desteği")
    
    # Ek bilgiler
    common_dependencies: List[str] = Field(
        default_factory=list,
        description="Yaygın kullanılan bağımlılıklar"
    )
    file_extensions: List[str] = Field(
        default_factory=list,
        description="Kullanılan dosya uzantıları"
    )
    
    class Config:
        use_enum_values = True


# Stack Specifications
STACK_SPECS: Dict[str, StackSpec] = {
    # Backend Stacks
    "express-ts": StackSpec(
        stack_id="express-ts",
        name="Node.js + Express (TypeScript)",
        category=StackCategory.BACKEND,
        language="ts",
        test_framework="jest",
        package_manager="npm",
        linter_formatter="eslint+prettier",
        project_layout={
            "src/": "Kaynak kod klasörü",
            "src/routes/": "API route'ları",
            "src/controllers/": "Controller'lar",
            "src/models/": "Model'ler",
            "src/middleware/": "Middleware'ler",
            "src/config/": "Konfigürasyon",
            "tests/": "Test dosyaları",
            "package.json": "Bağımlılık tanımları",
            "tsconfig.json": "TypeScript konfigürasyonu",
            ".env.example": "Çevre değişkenleri örneği"
        },
        run_commands={
            "dev": "npm run dev",
            "build": "npm run build",
            "test": "npm test",
            "start": "npm start"
        },
        docker_templates=True,
        ci_templates=True,
        common_dependencies=["express", "dotenv", "cors", "helmet"],
        file_extensions=[".ts", ".js", ".json"]
    ),
    
    "nestjs": StackSpec(
        stack_id="nestjs",
        name="Node.js + NestJS (TypeScript)",
        category=StackCategory.BACKEND,
        language="ts",
        test_framework="jest",
        package_manager="npm",
        linter_formatter="eslint+prettier",
        project_layout={
            "src/": "Kaynak kod klasörü",
            "src/modules/": "NestJS modülleri",
            "src/controllers/": "Controller'lar",
            "src/services/": "Servisler",
            "src/entities/": "Entity'ler",
            "src/dto/": "Data Transfer Objects",
            "test/": "Test dosyaları",
            "package.json": "Bağımlılık tanımları",
            "tsconfig.json": "TypeScript konfigürasyonu",
            "nest-cli.json": "NestJS CLI konfigürasyonu"
        },
        run_commands={
            "dev": "npm run start:dev",
            "build": "npm run build",
            "test": "npm test",
            "start": "npm run start:prod"
        },
        docker_templates=True,
        ci_templates=True,
        common_dependencies=["@nestjs/core", "@nestjs/common", "@nestjs/platform-express"],
        file_extensions=[".ts", ".js", ".json"]
    ),
    
    "laravel": StackSpec(
        stack_id="laravel",
        name="PHP + Laravel",
        category=StackCategory.BACKEND,
        language="php",
        test_framework="phpunit",
        package_manager="composer",
        linter_formatter="pint",
        project_layout={
            "app/": "Uygulama mantığı",
            "app/Http/Controllers/": "Controller'lar",
            "app/Models/": "Eloquent model'leri",
            "routes/": "Route tanımları",
            "database/migrations/": "Veritabanı migration'ları",
            "tests/": "Test dosyaları",
            "composer.json": "Bağımlılık tanımları",
            ".env.example": "Çevre değişkenleri örneği"
        },
        run_commands={
            "dev": "php artisan serve",
            "build": "composer install",
            "test": "php artisan test",
            "start": "php artisan serve"
        },
        docker_templates=True,
        ci_templates=True,
        common_dependencies=["laravel/framework", "guzzlehttp/guzzle"],
        file_extensions=[".php", ".blade.php"]
    ),
    
    "fastapi": StackSpec(
        stack_id="fastapi",
        name="Python + FastAPI",
        category=StackCategory.BACKEND,
        language="py",
        test_framework="pytest",
        package_manager="pip",
        linter_formatter="ruff",
        project_layout={
            "app/": "Uygulama kod klasörü",
            "app/routers/": "API router'ları",
            "app/models/": "Pydantic model'leri",
            "app/services/": "İş mantığı servisleri",
            "app/config.py": "Konfigürasyon",
            "tests/": "Test dosyaları",
            "requirements.txt": "Bağımlılıklar",
            ".env.example": "Çevre değişkenleri örneği"
        },
        run_commands={
            "dev": "uvicorn app.main:app --reload",
            "build": "pip install -r requirements.txt",
            "test": "pytest",
            "start": "uvicorn app.main:app"
        },
        docker_templates=True,
        ci_templates=True,
        common_dependencies=["fastapi", "uvicorn", "pydantic", "python-dotenv"],
        file_extensions=[".py"]
    ),
    
    "dotnet-api": StackSpec(
        stack_id="dotnet-api",
        name=".NET Web API (C#)",
        category=StackCategory.BACKEND,
        language="cs",
        test_framework="xunit",
        package_manager="dotnet",
        linter_formatter="dotnet-format",
        project_layout={
            "Controllers/": "API controller'ları",
            "Models/": "Data model'leri",
            "Services/": "İş mantığı servisleri",
            "Program.cs": "Uygulama giriş noktası",
            "appsettings.json": "Konfigürasyon",
            "*.csproj": "Proje dosyası"
        },
        run_commands={
            "dev": "dotnet run",
            "build": "dotnet build",
            "test": "dotnet test",
            "start": "dotnet run"
        },
        docker_templates=True,
        ci_templates=True,
        common_dependencies=["Microsoft.AspNetCore.App"],
        file_extensions=[".cs", ".csproj", ".json"]
    ),
    
    # Frontend Stacks
    "react-vite": StackSpec(
        stack_id="react-vite",
        name="React + Vite (TypeScript)",
        category=StackCategory.FRONTEND,
        language="ts",
        test_framework="vitest",
        package_manager="npm",
        linter_formatter="eslint+prettier",
        project_layout={
            "src/": "Kaynak kod klasörü",
            "src/components/": "React component'leri",
            "src/pages/": "Sayfa component'leri",
            "src/hooks/": "Custom React hooks",
            "src/utils/": "Yardımcı fonksiyonlar",
            "src/App.tsx": "Ana uygulama component'i",
            "src/main.tsx": "Giriş noktası",
            "public/": "Statik dosyalar",
            "package.json": "Bağımlılık tanımları",
            "vite.config.ts": "Vite konfigürasyonu",
            "tsconfig.json": "TypeScript konfigürasyonu"
        },
        run_commands={
            "dev": "npm run dev",
            "build": "npm run build",
            "test": "npm test",
            "start": "npm run preview"
        },
        docker_templates=True,
        ci_templates=True,
        common_dependencies=["react", "react-dom", "vite", "@vitejs/plugin-react"],
        file_extensions=[".tsx", ".ts", ".css", ".json"]
    ),
    
    "nextjs": StackSpec(
        stack_id="nextjs",
        name="Next.js (TypeScript)",
        category=StackCategory.FRONTEND,
        language="ts",
        test_framework="jest",
        package_manager="npm",
        linter_formatter="eslint+prettier",
        project_layout={
            "app/": "App router (Next.js 13+)",
            "pages/": "Pages router (alternatif)",
            "components/": "React component'leri",
            "lib/": "Yardımcı fonksiyonlar",
            "public/": "Statik dosyalar",
            "styles/": "CSS dosyaları",
            "package.json": "Bağımlılık tanımları",
            "next.config.js": "Next.js konfigürasyonu",
            "tsconfig.json": "TypeScript konfigürasyonu"
        },
        run_commands={
            "dev": "npm run dev",
            "build": "npm run build",
            "test": "npm test",
            "start": "npm start"
        },
        docker_templates=True,
        ci_templates=True,
        common_dependencies=["next", "react", "react-dom"],
        file_extensions=[".tsx", ".ts", ".css", ".json"]
    ),
    
    "vue-vite": StackSpec(
        stack_id="vue-vite",
        name="Vue + Vite (TypeScript)",
        category=StackCategory.FRONTEND,
        language="ts",
        test_framework="vitest",
        package_manager="npm",
        linter_formatter="eslint+prettier",
        project_layout={
            "src/": "Kaynak kod klasörü",
            "src/components/": "Vue component'leri",
            "src/views/": "Sayfa view'ları",
            "src/composables/": "Composition API composables",
            "src/router/": "Vue Router konfigürasyonu",
            "src/stores/": "Pinia store'ları",
            "src/App.vue": "Ana uygulama component'i",
            "src/main.ts": "Giriş noktası",
            "public/": "Statik dosyalar",
            "package.json": "Bağımlılık tanımları",
            "vite.config.ts": "Vite konfigürasyonu"
        },
        run_commands={
            "dev": "npm run dev",
            "build": "npm run build",
            "test": "npm test",
            "start": "npm run preview"
        },
        docker_templates=True,
        ci_templates=True,
        common_dependencies=["vue", "vite", "@vitejs/plugin-vue"],
        file_extensions=[".vue", ".ts", ".css", ".json"]
    ),
    
    # DevOps Stacks
    "devops-docker": StackSpec(
        stack_id="devops-docker",
        name="Docker + Docker Compose",
        category=StackCategory.DEVOPS,
        language="yaml",
        test_framework="none",
        package_manager="none",
        linter_formatter="hadolint",
        project_layout={
            "Dockerfile": "Docker image tanımı",
            "docker-compose.yml": "Multi-container orchestration",
            ".dockerignore": "Docker build ignore dosyası",
            "nginx.conf": "Nginx konfigürasyonu (opsiyonel)",
            ".env.example": "Çevre değişkenleri örneği"
        },
        run_commands={
            "dev": "docker-compose up",
            "build": "docker-compose build",
            "test": "docker-compose run --rm app test",
            "start": "docker-compose up -d"
        },
        docker_templates=True,
        ci_templates=False,
        common_dependencies=[],
        file_extensions=[".yml", ".yaml", ".conf"]
    ),
    
    "ci-github-actions": StackSpec(
        stack_id="ci-github-actions",
        name="GitHub Actions CI/CD",
        category=StackCategory.DEVOPS,
        language="yaml",
        test_framework="none",
        package_manager="none",
        linter_formatter="actionlint",
        project_layout={
            ".github/workflows/": "GitHub Actions workflow'ları",
            ".github/workflows/ci.yml": "CI pipeline",
            ".github/workflows/deploy.yml": "Deployment pipeline (opsiyonel)"
        },
        run_commands={
            "dev": "act",
            "build": "N/A",
            "test": "act -j test",
            "start": "N/A"
        },
        docker_templates=False,
        ci_templates=True,
        common_dependencies=[],
        file_extensions=[".yml", ".yaml"]
    ),
}


def get_stack_spec(stack_id: str) -> Optional[StackSpec]:
    """Stack ID'ye göre spec getir"""
    return STACK_SPECS.get(stack_id)


def infer_stack_from_task(task: str) -> str:
    """Görev açıklamasından stack tahmin et"""
    task_lower = task.lower()
    
    # Backend - specific framework checks first
    if "nest" in task_lower or "nestjs" in task_lower:
        return "nestjs"
    elif "laravel" in task_lower or ("php" in task_lower and "laravel" in task_lower):
        return "laravel"
    elif "fastapi" in task_lower:
        return "fastapi"
    elif ".net" in task_lower or "c#" in task_lower or "csharp" in task_lower or "dotnet" in task_lower:
        return "dotnet-api"
    
    # Backend keywords (general)
    if any(kw in task_lower for kw in ["api", "backend", "server", "endpoint", "rest"]):
        if "python" in task_lower:
            return "fastapi"
        elif "php" in task_lower:
            return "laravel"
        else:
            return "express-ts"  # Default backend
    
    # Frontend keywords
    elif any(kw in task_lower for kw in ["ui", "frontend", "dashboard", "page", "component"]):
        if "next" in task_lower:
            return "nextjs"
        elif "vue" in task_lower:
            return "vue-vite"
        else:
            return "react-vite"  # Default frontend
    
    # DevOps keywords
    elif any(kw in task_lower for kw in ["docker", "container", "compose"]):
        return "devops-docker"
    elif any(kw in task_lower for kw in ["ci", "cd", "github actions", "pipeline"]):
        return "ci-github-actions"
    
    # Default
    return "fastapi"
