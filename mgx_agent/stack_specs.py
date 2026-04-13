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
    FULLSTACK = "fullstack"
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
    
    "react-native": StackSpec(
        stack_id="react-native",
        name="React Native (TypeScript)",
        category=StackCategory.FRONTEND,
        language="ts",
        test_framework="jest",
        package_manager="npm",
        linter_formatter="eslint+prettier",
        project_layout={
            "src/screens/": "Ekran bileşenleri",
            "src/components/": "Ortak bileşenler",
            "src/navigation/": "React Navigation yapılandırması",
            "src/hooks/": "Custom hooks",
            "src/services/": "API servisleri",
            "App.tsx": "Ana uygulama bileşeni",
            "package.json": "Bağımlılık tanımları",
            "metro.config.js": "Metro bundler yapılandırması",
        },
        run_commands={
            "dev": "npx react-native start",
            "build": "npx react-native build-android",
            "test": "npm test",
            "start": "npx react-native run-android",
        },
        docker_templates=True,
        ci_templates=True,
        common_dependencies=["react-native", "@react-navigation/native", "react-native-screens"],
        file_extensions=[".tsx", ".ts", ".json"],
    ),
    
    "flutter": StackSpec(
        stack_id="flutter",
        name="Flutter (Dart)",
        category=StackCategory.FRONTEND,
        language="dart",
        test_framework="flutter_test",
        package_manager="pub",
        linter_formatter="dart-format",
        project_layout={
            "lib/": "Dart kaynak kodu",
            "lib/screens/": "Ekran widget'ları",
            "lib/widgets/": "Ortak widget'lar",
            "lib/services/": "API ve iş servisleri",
            "lib/models/": "Veri modelleri",
            "lib/main.dart": "Giriş noktası",
            "pubspec.yaml": "Bağımlılık tanımları",
            "test/": "Widget ve unit testler",
        },
        run_commands={
            "dev": "flutter run",
            "build": "flutter build apk",
            "test": "flutter test",
            "start": "flutter run --release",
        },
        docker_templates=True,
        ci_templates=True,
        common_dependencies=["flutter", "http", "provider", "shared_preferences"],
        file_extensions=[".dart", ".yaml"],
    ),
    
    "go-fiber": StackSpec(
        stack_id="go-fiber",
        name="Go + Fiber",
        category=StackCategory.BACKEND,
        language="go",
        test_framework="go-test",
        package_manager="go-modules",
        linter_formatter="golangci-lint",
        project_layout={
            "cmd/": "Uygulama giriş noktaları",
            "internal/handlers/": "HTTP handler'ları",
            "internal/services/": "İş mantığı",
            "internal/models/": "Veri modelleri",
            "internal/middleware/": "Fiber middleware",
            "config/": "Yapılandırma",
            "go.mod": "Go modül tanımı",
            "go.sum": "Bağımlılık kilitleme",
            ".env.example": "Çevre değişkenleri örneği",
        },
        run_commands={
            "dev": "go run cmd/main.go",
            "build": "go build -o bin/app cmd/main.go",
            "test": "go test ./...",
            "start": "./bin/app",
        },
        docker_templates=True,
        ci_templates=True,
        common_dependencies=["github.com/gofiber/fiber/v2", "github.com/joho/godotenv"],
        file_extensions=[".go", ".mod", ".sum"],
    ),
    
    # Vanilla HTML/CSS/JS Stack (No Framework)
    "vanilla-html": StackSpec(
        stack_id="vanilla-html",
        name="Vanilla HTML/CSS/JavaScript",
        category=StackCategory.FRONTEND,
        language="js",
        test_framework="none",
        package_manager="none",
        linter_formatter="prettier",
        project_layout={
            "index.html": "Ana HTML sayfası",
            "style.css": "CSS stilleri",
            "script.js": "JavaScript kodu",
            "assets/": "Resimler ve diğer medya dosyaları"
        },
        run_commands={
            "dev": "python -m http.server 8080",
            "build": "echo 'No build step for vanilla HTML'",
            "test": "echo 'No tests configured'",
            "start": "python -m http.server 8080"
        },
        docker_templates=False,
        ci_templates=False,
        common_dependencies=[],
        file_extensions=[".html", ".css", ".js"]
    ),
    
    # ── Golden Path Stacks ────────────────────────────────────────────────────
    # Bu stack'ler Web / Mobile / Special mod için tanımlı golden path'lerdir.
    # Varsayılan: Laravel + PostgreSQL zorunlu.

    "laravel-blade": StackSpec(
        stack_id="laravel-blade",
        name="Laravel + Blade + PostgreSQL (Web Mode)",
        category=StackCategory.FULLSTACK,
        language="php",
        test_framework="phpunit",
        package_manager="composer",
        linter_formatter="pint",
        project_layout={
            "app/Models/": "Eloquent modelleri",
            "app/Http/Controllers/": "Web & API controller'ları",
            "app/Http/Requests/": "FormRequest doğrulama",
            "resources/views/": "Blade şablonları",
            "resources/views/components/": "Blade bileşenleri",
            "database/migrations/": "PostgreSQL migration'ları",
            "routes/web.php": "Web route'ları",
            "routes/api.php": "API route'ları",
            "config/": "Uygulama konfigürasyonları",
            "tests/Feature/": "Feature testleri",
            "tests/Unit/": "Unit testleri",
            "composer.json": "Bağımlılıklar",
            ".env.example": "Çevre değişkenleri",
        },
        run_commands={
            "dev": "php artisan serve",
            "build": "composer install && npm run build",
            "test": "php artisan test",
            "start": "php artisan serve",
        },
        docker_templates=True,
        ci_templates=True,
        common_dependencies=[
            "laravel/framework",
            "laravel/sanctum",
            "spatie/laravel-permission",
        ],
        file_extensions=[".php", ".blade.php", ".sql"],
    ),

    "flutter-laravel": StackSpec(
        stack_id="flutter-laravel",
        name="Flutter + Laravel API + PostgreSQL (Mobile Mode)",
        category=StackCategory.FULLSTACK,
        language="dart",
        test_framework="flutter_test",
        package_manager="pub",
        linter_formatter="dart-format",
        project_layout={
            "lib/features/": "Feature-based modüller",
            "lib/core/": "Shared servisler & yardımcılar",
            "lib/shared/": "Ortak widget'lar",
            "lib/app/": "Router & theme tanımları",
            "lib/main.dart": "Giriş noktası",
            "pubspec.yaml": "Flutter bağımlılıkları",
            "test/": "Widget ve unit testler",
            "backend/app/Http/Controllers/Api/": "Laravel API controller'ları",
            "backend/app/Http/Resources/": "API resource sınıfları",
            "backend/database/migrations/": "PostgreSQL migration'ları",
        },
        run_commands={
            "dev": "flutter run",
            "build": "flutter build apk",
            "test": "flutter test",
            "start": "flutter run --release",
        },
        docker_templates=True,
        ci_templates=True,
        common_dependencies=[
            "flutter",
            "riverpod",
            "dio",
            "flutter_secure_storage",
            "go_router",
        ],
        file_extensions=[".dart", ".yaml", ".php"],
    ),

    "laravel-react": StackSpec(
        stack_id="laravel-react",
        name="Laravel API + React + PostgreSQL (Special Mode)",
        category=StackCategory.FULLSTACK,
        language="ts",
        test_framework="vitest",
        package_manager="npm",
        linter_formatter="eslint+prettier",
        project_layout={
            "src/features/": "Feature-based React modülleri",
            "src/components/": "Ortak bileşenler",
            "src/hooks/": "Custom React hooks",
            "src/lib/api/": "Axios / TanStack Query istemcisi",
            "src/stores/": "Zustand store'ları",
            "src/App.tsx": "Ana uygulama",
            "backend/app/Http/Controllers/Api/": "Laravel API controller'ları",
            "backend/config/cors.php": "CORS konfigürasyonu",
            "backend/database/migrations/": "PostgreSQL migration'ları",
            "backend/routes/api.php": "API route'ları",
        },
        run_commands={
            "dev": "npm run dev",
            "build": "npm run build",
            "test": "npm test",
            "start": "npm run preview",
        },
        docker_templates=True,
        ci_templates=True,
        common_dependencies=[
            "react",
            "react-router-dom",
            "@tanstack/react-query",
            "zustand",
            "axios",
            "tailwindcss",
        ],
        file_extensions=[".tsx", ".ts", ".php", ".sql"],
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
    """
    Görev açıklamasından stack tahmin et.

    Öncelik sırası:
    1. Vanilla HTML (açık HTML/statik sayfa isteği, framework yok)
    2. Golden path stacks (laravel-blade, flutter-laravel, laravel-react)
    3. Mobile (react-native, flutter)
    4. Spesifik backend/frontend framework'ler
    5. Genel anahtar kelimeler
    6. Varsayılan: fastapi
    """
    task_lower = task.lower()

    # 1. Vanilla HTML — açık talep + framework yok
    _vanilla_kws = [
        "html", "vanilla", "static page", "basit web", "basit sayfa",
        "sayaç", "counter", "hesap makinesi", "calculator", "landing page",
        "tek sayfa", "single page html",
    ]
    _framework_kws = ["react", "vue", "next", "angular", "svelte", "laravel", "flutter"]
    if any(kw in task_lower for kw in _vanilla_kws):
        if not any(fw in task_lower for fw in _framework_kws):
            return "vanilla-html"

    # 2. Golden path stacks — flutter + laravel birlikte → flutter-laravel
    _flutter_kws = ["flutter", "dart", "mobil uygulama", "android uygulama", "ios uygulama",
                    "mobile app", "mobil app"]
    _laravel_kws = ["laravel", "blade", "php"]
    _react_kws = ["react", "spa", "single page app", "dashboard", "frontend", "vite"]
    _web_app_kws = ["web uygulaması", "web application", "web app", "tam stack", "full stack",
                    "fullstack"]

    is_flutter = any(kw in task_lower for kw in _flutter_kws)
    is_laravel = any(kw in task_lower for kw in _laravel_kws)
    is_react = any(kw in task_lower for kw in _react_kws)
    is_web_app = any(kw in task_lower for kw in _web_app_kws)

    if is_flutter and is_laravel:
        return "flutter-laravel"
    if is_flutter:
        return "flutter-laravel"  # Flutter → golden path (Laravel backend)
    if is_laravel and is_react:
        return "laravel-react"
    if is_laravel:
        return "laravel-blade"   # Laravel → golden path (Blade)
    if is_react and is_web_app:
        return "laravel-react"   # Full-stack React → golden path

    # 3. Mobile (React Native)
    if "react native" in task_lower or "react-native" in task_lower or "reactnative" in task_lower:
        return "react-native"

    # 4. Go
    if ("go" in task_lower and ("fiber" in task_lower or "golang" in task_lower)) or "go-fiber" in task_lower:
        return "go-fiber"

    # 5. Spesifik backend framework'ler
    if "nest" in task_lower or "nestjs" in task_lower:
        return "nestjs"
    if "fastapi" in task_lower:
        return "fastapi"
    if ".net" in task_lower or "c#" in task_lower or "csharp" in task_lower or "dotnet" in task_lower:
        return "dotnet-api"

    # 6. Genel backend/frontend anahtar kelimeleri
    if any(kw in task_lower for kw in ["api", "backend", "server", "endpoint", "rest"]):
        if "python" in task_lower:
            return "fastapi"
        if "php" in task_lower:
            return "laravel-blade"
        return "express-ts"

    if any(kw in task_lower for kw in ["ui", "component", "page"]):
        if "next" in task_lower:
            return "nextjs"
        if "vue" in task_lower:
            return "vue-vite"
        return "react-vite"

    if any(kw in task_lower for kw in ["docker", "container", "compose"]):
        return "devops-docker"
    if any(kw in task_lower for kw in ["ci", "cd", "github actions", "pipeline"]):
        return "ci-github-actions"

    # Default
    return "fastapi"


# ---------------------------------------------------------------------------
# Stack Compliance Guard
# ---------------------------------------------------------------------------

_GOLDEN_PATH_STACKS = {"laravel-blade", "flutter-laravel", "laravel-react"}
_GOLDEN_PATH_DB = "PostgreSQL"

def validate_and_correct_stack(stack_id: str, task: str) -> tuple[str, str]:
    """
    Golden path projeler için stack doğrulama ve otomatik düzeltme.

    KURALAR (sırayla uygulanır):
    1. Yanlış veritabanı (MySQL/MongoDB/SQLite) → PostgreSQL'e zorla + uyar
    2. Mobil anahtar kelimesi + vanilla-html → flutter-laravel
    3. React Native isteği → flutter-laravel golden path + uyar
    4. Flutter + Node.js backend → flutter-laravel (Laravel backend) + uyar
    5. React SPA + vanilla-html → laravel-react
    6. "Web sitesi" + React → laravel-react golden path

    Returns:
        (corrected_stack_id, warning_message)
        warning_message boşsa düzeltme yapılmamıştır.
    """
    task_lower = task.lower()
    warnings: list[str] = []

    # ── Kural 1: Yanlış veritabanı ────────────────────────────────────────────
    _wrong_dbs = {
        "mysql": "MySQL",
        "mongodb": "MongoDB",
        "mongo": "MongoDB",
        "sqlite": "SQLite",
        "mariadb": "MariaDB",
        "mssql": "MSSQL",
        "oracle": "Oracle DB",
        "firebase": "Firebase Firestore",
        "supabase": "Supabase",
        "dynamodb": "DynamoDB",
        "cassandra": "Cassandra",
        "redis db": "Redis (as primary DB)",
    }
    detected_wrong_db = next(
        (label for kw, label in _wrong_dbs.items() if kw in task_lower), None
    )
    if detected_wrong_db:
        if stack_id not in ("vanilla-html", "devops-docker", "ci-github-actions"):
            warnings.append(
                f"⚠️ VERİTABANI DÜZELTMESİ: '{detected_wrong_db}' yerine "
                f"PostgreSQL 16+ kullanılıyor. Golden path standardı PostgreSQL'dir. "
                f"Laravel migration'ları ve Eloquent PostgreSQL için yapılandırıldı."
            )
            # stack_id zaten golden path ise koru, değilse uygun golden path'e çek
            if stack_id not in _GOLDEN_PATH_STACKS:
                # Mobil mi web mi?
                _mobile_kws = ["mobil", "mobile", "flutter", "android", "ios", "react native"]
                _react_kws = ["react", "spa", "dashboard", "admin", "panel"]
                if any(kw in task_lower for kw in _mobile_kws):
                    stack_id = "flutter-laravel"
                elif any(kw in task_lower for kw in _react_kws):
                    stack_id = "laravel-react"
                else:
                    stack_id = "laravel-blade"

    # ── Kural 2: React Native → flutter-laravel ───────────────────────────────
    _rn_kws = ["react native", "react-native", "reactnative"]
    if any(kw in task_lower for kw in _rn_kws):
        if stack_id != "flutter-laravel":
            warnings.append(
                "⚠️ STACK DÜZELTMESİ: 'React Native' yerine 'Flutter + Laravel API' "
                "golden path kullanılıyor. Flutter, MGX'in mobil golden path standardıdır. "
                "Backend Laravel 11+ + PostgreSQL + Sanctum olarak yapılandırıldı."
            )
            stack_id = "flutter-laravel"

    # ── Kural 3: Mobil + vanilla-html uyumsuzluğu ─────────────────────────────
    if stack_id == "vanilla-html":
        _mobile_kws = ["mobil", "mobile", "flutter", "android", "ios", "uygulama", "app"]
        if any(kw in task_lower for kw in _mobile_kws):
            warnings.append(
                "⚠️ STACK DÜZELTMESİ: Mobil uygulama isteği vanilla-HTML ile uyumsuz. "
                "'flutter-laravel' golden path'e geçildi."
            )
            stack_id = "flutter-laravel"

    # ── Kural 4: Flutter + Node.js backend → flutter-laravel ──────────────────
    _flutter_kws = ["flutter", "dart"]
    _node_backends = ["node.js", "nodejs", "node js", "express", "fastify", "nest"]
    is_flutter = any(kw in task_lower for kw in _flutter_kws)
    is_node_backend = any(kw in task_lower for kw in _node_backends)
    if is_flutter and is_node_backend:
        warnings.append(
            "⚠️ BACKEND DÜZELTMESİ: Flutter projesi için Node.js yerine "
            "Laravel 11+ API backend kullanılıyor. "
            "Golden path: Flutter + Laravel Sanctum + PostgreSQL."
        )
        stack_id = "flutter-laravel"

    # ── Kural 5: React SPA + web uygulaması isteği ────────────────────────────
    _react_spa_kws = ["react spa", "react uygulama", "react app", "spa", "single page"]
    _web_context = ["web", "site", "platform", "dashboard", "admin", "panel", "portal"]
    if (
        any(kw in task_lower for kw in _react_spa_kws)
        and any(kw in task_lower for kw in _web_context)
        and stack_id not in ("laravel-react", "laravel-blade")
    ):
        warnings.append(
            "⚠️ STACK GÜNCELLEME: React SPA projesi için 'laravel-react' golden path kullanılıyor. "
            "Backend Laravel 11+ API + PostgreSQL, frontend React 18+ + Vite + Tailwind."
        )
        stack_id = "laravel-react"

    combined_warning = "\n".join(warnings)
    return stack_id, combined_warning
