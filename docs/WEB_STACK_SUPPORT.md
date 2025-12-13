# Web Stack Desteği - TEM Agent

MGX AI artık **production-ready web development** için tam stack desteği sunuyor! 🚀

## 📋 İçindekiler

- [Desteklenen Stack'ler](#desteklenen-stackler)
- [Özellikler](#özellikler)
- [Kullanım](#kullanım)
- [JSON Task Format](#json-task-format)
- [Örnekler](#örnekler)
- [Stack-Aware Actions](#stack-aware-actions)
- [Output Validation](#output-validation)
- [Sınırlamalar](#sınırlamalar)

---

## 🎯 Desteklenen Stack'ler

### Backend (5 stack)

| Stack ID | İsim | Test Framework | Package Manager | Dil |
|----------|------|----------------|-----------------|-----|
| `express-ts` | Node.js + Express (TypeScript) | Jest | npm/pnpm | TS |
| `nestjs` | Node.js + NestJS (TypeScript) | Jest | npm/pnpm | TS |
| `laravel` | PHP + Laravel | PHPUnit | Composer | PHP |
| `fastapi` | Python + FastAPI | Pytest | pip | Python |
| `dotnet-api` | .NET Web API (C#) | xUnit | dotnet | C# |

### Frontend (3 stack)

| Stack ID | İsim | Test Framework | Package Manager | Dil |
|----------|------|----------------|-----------------|-----|
| `react-vite` | React + Vite (TypeScript) | Vitest | npm/pnpm | TS |
| `nextjs` | Next.js (TypeScript) | Jest | npm/pnpm | TS |
| `vue-vite` | Vue + Vite (TypeScript) | Vitest | npm/pnpm | TS |

### DevOps (2 stack)

| Stack ID | İsim | Test Framework | Package Manager | Dil |
|----------|------|----------------|-----------------|-----|
| `devops-docker` | Docker + Docker Compose | - | - | YAML |
| `ci-github-actions` | GitHub Actions CI/CD | - | - | YAML |

---

## ✨ Özellikler

### Phase A: Stack Specifications
- ✅ **StackSpec**: Her stack için teknik spesifikasyonlar
- ✅ **ProjectType**: `api`, `webapp`, `fullstack`, `devops`
- ✅ **OutputMode**: `generate_new`, `patch_existing`
- ✅ **Automatic Stack Inference**: Görev açıklamasından stack tahmin etme

### Phase B: JSON Input Contract
- ✅ **Structured Input**: JSON dosyasından görev yükleme
- ✅ **Constraints**: Ek kısıtlamalar tanımlama
- ✅ **Plain Text Fallback**: Normal metin görev desteği devam ediyor

### Phase C: Stack-Aware Actions
- ✅ **AnalyzeTask**: Karmaşıklık + önerilen stack + dosya manifest + test stratejisi
- ✅ **DraftPlan**: Stack bilgisini içeren plan
- ✅ **WriteCode**: Multi-language + FILE manifest format
- ✅ **WriteTest**: Stack'e özgü test framework (Jest/Vitest/PHPUnit/Pytest)
- ✅ **ReviewCode**: Stack-specific best practices kontrolü

### Phase D: Guardrails
- ✅ **Output Validation**: Stack yapısına uygunluk kontrolü
- ✅ **FILE Manifest Parser**: Çoklu dosya desteği
- ✅ **Safe File Writer**: Otomatik `.bak` yedekleme
- ✅ **Patch Mode**: Mevcut projelere güvenli değişiklik

### Phase E: Tests
- ✅ **28+ Integration Tests**: Stack specs, file utils, validation testleri

---

## 🚀 Kullanım

### 1. JSON Dosyasından Görev Yükleme

```bash
python -m mgx_agent.cli --json examples/express_api_task.json
```

### 2. Normal Metin Görev (Otomatik Stack Inference)

```bash
python -m mgx_agent.cli --task "Create a Next.js dashboard with user management"
```

### 3. Python API Kullanımı

```python
from mgx_agent.team import MGXStyleTeam
from mgx_agent.config import TeamConfig

# Stack-aware config
config = TeamConfig(
    target_stack="fastapi",
    project_type="api",
    output_mode="generate_new",
    strict_requirements=True,
    constraints=["Use Pydantic", "Add authentication"]
)

team = MGXStyleTeam(config=config)

# Görev çalıştır
await team.analyze_and_plan("Create user management API")
team.approve_plan()
await team.execute()
```

---

## 📄 JSON Task Format

### Minimal Format

```json
{
  "task": "Create a REST API for user management"
}
```

### Full Format

```json
{
  "task": "Create a REST API for user management",
  "target_stack": "fastapi",
  "project_type": "api",
  "output_mode": "generate_new",
  "strict_requirements": true,
  "constraints": [
    "Use Pydantic models",
    "Add JWT authentication",
    "Include .env configuration"
  ],
  "existing_project_path": "./my-project"
}
```

### Alan Açıklamaları

| Alan | Tip | Zorunlu | Açıklama |
|------|-----|---------|----------|
| `task` | string | ✅ | Görev açıklaması |
| `target_stack` | string | ❌ | Stack ID (otomatik tahmin edilir) |
| `project_type` | string | ❌ | `api`, `webapp`, `fullstack`, `devops` |
| `output_mode` | string | ❌ | `generate_new` (default) veya `patch_existing` |
| `strict_requirements` | boolean | ❌ | FILE manifest formatı zorunlu (default: false) |
| `constraints` | array | ❌ | Ek kısıtlamalar listesi |
| `existing_project_path` | string | ❌ | Patch mode için proje yolu |

---

## 📚 Örnekler

### Örnek 1: Express TypeScript API

**Dosya:** `examples/express_api_task.json`

```json
{
  "task": "Create a simple Express TypeScript REST API with user CRUD endpoints",
  "target_stack": "express-ts",
  "project_type": "api",
  "constraints": [
    "Use TypeScript",
    "Include error handling middleware",
    "Add input validation"
  ]
}
```

**Çalıştırma:**

```bash
python -m mgx_agent.cli --json examples/express_api_task.json
```

**Beklenen Çıktı:**

```
FILE: package.json
{
  "name": "express-api",
  "scripts": {
    "dev": "ts-node-dev src/server.ts",
    "build": "tsc",
    "start": "node dist/server.js"
  },
  "dependencies": {
    "express": "^4.18.0",
    "dotenv": "^16.0.0"
  }
}

FILE: src/server.ts
import express from 'express';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
app.use(express.json());

// User routes
app.get('/users', (req, res) => {
  res.json({ users: [] });
});

export default app;

FILE: tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "outDir": "./dist"
  }
}
```

---

### Örnek 2: FastAPI Backend

**Dosya:** `examples/fastapi_task.json`

```json
{
  "task": "Build a FastAPI application for user management",
  "target_stack": "fastapi",
  "project_type": "api",
  "strict_requirements": true,
  "constraints": [
    "Use Pydantic models",
    "Implement JWT authentication"
  ]
}
```

**Çalıştırma:**

```bash
python -m mgx_agent.cli --json examples/fastapi_task.json
```

**Beklenen Çıktı:**

```
FILE: app/main.py
from fastapi import FastAPI
from app.routers import users

app = FastAPI(title="User Management API")
app.include_router(users.router)

FILE: app/models.py
from pydantic import BaseModel, EmailStr

class User(BaseModel):
    id: int
    email: EmailStr
    username: str

FILE: app/routers/users.py
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
async def get_users():
    return {"users": []}

FILE: requirements.txt
fastapi
uvicorn[standard]
pydantic[email]
python-jose[cryptography]
```

---

### Örnek 3: Next.js Dashboard

**Dosya:** `examples/nextjs_task.json`

```json
{
  "task": "Create a Next.js admin dashboard with user list page",
  "target_stack": "nextjs",
  "project_type": "webapp",
  "constraints": [
    "Use App Router (Next.js 13+)",
    "Server-side rendering"
  ]
}
```

**Beklenen Dosya Yapısı:**

```
app/
  page.tsx          # Ana sayfa
  users/
    page.tsx        # Kullanıcı listesi
  api/
    users/
      route.ts      # API endpoint
components/
  UserTable.tsx
package.json
next.config.js
tsconfig.json
```

---

### Örnek 4: Docker Setup

**Dosya:** `examples/docker_task.json`

```json
{
  "task": "Create Docker setup for Node.js API with PostgreSQL",
  "target_stack": "devops-docker",
  "project_type": "devops",
  "constraints": [
    "Multi-stage build",
    "Health checks"
  ]
}
```

**Beklenen Çıktı:**

```
FILE: Dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:18-alpine
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY package*.json ./
RUN npm ci --only=production
CMD ["node", "dist/server.js"]

FILE: docker-compose.yml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "3000:3000"
    depends_on:
      - postgres
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
  
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: mydb
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

### Örnek 5: Laravel Module (Patch Mode)

**Dosya:** `examples/laravel_task.json`

```json
{
  "task": "Add blog module to Laravel project",
  "target_stack": "laravel",
  "project_type": "api",
  "output_mode": "patch_existing",
  "existing_project_path": "./my-laravel-project",
  "constraints": [
    "Use Eloquent ORM",
    "Create migration files"
  ]
}
```

**Beklenen Değişiklikler:**

```
FILE: app/Models/Post.php
<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Post extends Model
{
    protected $fillable = ['title', 'content', 'author_id'];
}

FILE: app/Http/Controllers/PostController.php
<?php

namespace App\Http\Controllers;

class PostController extends Controller
{
    public function index()
    {
        return Post::all();
    }
}

FILE: database/migrations/2024_01_01_000000_create_posts_table.php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;

class CreatePostsTable extends Migration
{
    public function up()
    {
        Schema::create('posts', function (Blueprint $table) {
            $table->id();
            $table->string('title');
            $table->text('content');
            $table->timestamps();
        });
    }
}
```

---

## 🧠 Stack-Aware Actions

### AnalyzeTask Çıktısı

```
KARMAŞIKLIK: M
ÖNERİLEN_STACK: fastapi - Python REST API için optimal, async desteği
DOSYA_MANİFESTO:
- app/main.py: FastAPI app instance
- app/routers/users.py: User endpoints
- app/models.py: Pydantic models
- requirements.txt: Dependencies
- .env.example: Configuration template
TEST_STRATEJİSİ: pytest ile 5 adet test (CRUD operations + auth)
```

### WriteCode FILE Manifest Format

**Strict Mode (strict_requirements=true):**

```
FILE: src/server.ts
import express from 'express';
const app = express();

FILE: src/routes/users.ts
export const userRoutes = router();
```

**Normal Mode:**

```typescript
// Tek dosya için
import express from 'express';
const app = express();
```

### WriteTest Stack-Aware

**FastAPI (Pytest):**

```python
import pytest
from fastapi.testclient import TestClient

def test_create_user():
    client = TestClient(app)
    response = client.post("/users")
    assert response.status_code == 201
```

**Express-TS (Jest):**

```typescript
import { describe, it, expect } from '@jest/globals';
import request from 'supertest';

describe('User API', () => {
  it('should create user', async () => {
    const response = await request(app).post('/users');
    expect(response.status).toBe(201);
  });
});
```

---

## ✅ Output Validation

### Stack Structure Validation

```python
from mgx_agent.file_utils import validate_stack_structure

is_valid, warnings = validate_stack_structure("./my-project", "fastapi")

if not is_valid:
    print("⚠️ Uyarılar:", warnings)
```

### Constraint Validation

```python
from mgx_agent.file_utils import validate_output_constraints

files = {
    "package.json": '{"scripts": {"dev": "pnpm dev"}}',
    ".env.example": "DATABASE_URL=",
}

is_valid, errors = validate_output_constraints(
    files,
    stack_id="express-ts",
    constraints=["Use pnpm", "Include env vars"]
)
```

**Constraint Kuralları:**

| Constraint | Kontrol |
|------------|---------|
| "Use pnpm" | package.json'da `pnpm` aranır |
| "No extra libraries" | Bağımlılık sayısı kontrolü |
| "Must include env vars" | `.env.example` dosyası varlığı |
| "Use minimal dependencies" | Toplam dependency sayısı < 20 |

---

## 🛡️ Safe File Operations

### Otomatik Backup

```python
from mgx_agent.file_utils import safe_write_file

# Mevcut dosyayı yedekler ve yazar
safe_write_file("src/main.py", "# New code", create_backup_flag=True)

# Yedek: src/main.py.20240101_120000.bak
```

### FILE Manifest Parser

```python
from mgx_agent.file_utils import parse_file_manifest

manifest = """
FILE: package.json
{"name": "test"}

FILE: src/index.ts
console.log("hello");
"""

files = parse_file_manifest(manifest)
# {'package.json': '{"name": "test"}', 'src/index.ts': 'console.log("hello");'}
```

---

## 🔧 TeamConfig Stack Ayarları

```python
from mgx_agent.config import TeamConfig

config = TeamConfig(
    # Stack ayarları
    target_stack="nextjs",           # Stack seçimi
    project_type="webapp",           # Proje tipi
    output_mode="generate_new",      # Mod
    strict_requirements=True,        # FILE manifest zorunlu
    constraints=["Use App Router"],  # Kısıtlamalar
    existing_project_path="./app",   # Patch mode için
    
    # Mevcut ayarlar (hala destekleniyor)
    max_rounds=5,
    human_reviewer=False,
    enable_caching=True,
)
```

---

## ⚠️ Sınırlamalar

### Şu An Desteklenmeyen
- ❌ Multi-tenant SaaS özellikleri
- ❌ Kubernetes configuration (istenirse eklenebilir)
- ❌ Her dil/framework (sadece liste alındaki stack'ler)
- ❌ Otomatik patch conflict resolution

### Bilinen Sorunlar
- **Patch Mode**: Unified diff desteği için `patch_ng` kütüphanesi gerekli
  - Yoksa `.mgx_new` dosyası oluşturulur (manuel merge gerekir)
- **Large Projects**: Çok büyük projelerde dosya sayısı sınırı olabilir
- **LLM Output**: Bazen FILE manifest formatına uyulmayabilir
  - Validation ve retry mekanizması devreye girer

---

## 🧪 Test Çalıştırma

### Tüm Web Stack Testleri

```bash
pytest tests/test_web_stack_support.py -v
```

### Spesifik Test Grubu

```bash
# Stack specs testleri
pytest tests/test_web_stack_support.py::TestStackSpecs -v

# File manifest testleri
pytest tests/test_web_stack_support.py::TestFileManifestParser -v

# Validation testleri
pytest tests/test_web_stack_support.py::TestOutputValidation -v
```

---

## 📊 Başarı Metrikleri

### Hedefler ✅

- ✅ 10 stack desteği (5 backend, 3 frontend, 2 devops)
- ✅ JSON input contract
- ✅ Stack-aware actions (5 action güncellendi)
- ✅ Output validation + guardrails
- ✅ 28+ integration test
- ✅ FILE manifest parser
- ✅ Safe file writer with backup
- ✅ Backward compatibility

### Test Coverage

```
tests/test_web_stack_support.py::TestStackSpecs                 PASSED [ 10%]
tests/test_web_stack_support.py::TestFileManifestParser         PASSED [ 20%]
tests/test_web_stack_support.py::TestOutputValidation           PASSED [ 40%]
tests/test_web_stack_support.py::TestSafeFileWriter             PASSED [ 60%]
tests/test_web_stack_support.py::TestStackStructureValidation   PASSED [ 70%]
tests/test_web_stack_support.py::TestTeamConfigStackSupport     PASSED [ 80%]
tests/test_web_stack_support.py::TestJSONInputParsing           PASSED [ 90%]
tests/test_web_stack_support.py::TestBackwardCompatibility      PASSED [100%]
```

---

## 🚀 Gelecek Geliştirmeler

### v2.0 (Planlanıyor)
- [ ] Vue 2 backward compatibility
- [ ] Ruby on Rails stack
- [ ] Go (Gin/Echo) stack
- [ ] Rust (Actix/Rocket) stack
- [ ] Automatic conflict resolution (patch mode)
- [ ] Multi-file diff preview
- [ ] Stack migration tools (örn: Express → NestJS)

### v2.1 (Planlanıyor)
- [ ] Kubernetes manifests (Helm charts)
- [ ] Terraform templates
- [ ] AWS CDK templates
- [ ] CI/CD: GitLab CI, CircleCI, Jenkins

---

## 📞 Destek

Sorunlar için GitHub Issues açabilir veya [IMPROVEMENT_GUIDE.md](../IMPROVEMENT_GUIDE.md) dökümanına bakabilirsiniz.

---

**Web Stack Support - Production Ready! 🎉**
