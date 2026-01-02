# PR Organizasyon Planı

## 📋 PR'lar ve Dosyaları

### 1. 🧪 Test Infrastructure PR
**Branch**: `feat/test-infrastructure`
**Dosyalar**:

#### Test Dosyaları
- `backend/tests/integration/test_database_integration.py`
- `backend/tests/integration/test_redis_integration.py`
- `backend/tests/integration/test_storage_integration.py`
- `backend/tests/integration/test_api_integration.py`
- `backend/tests/integration/test_workflow_integration.py`
- `backend/tests/e2e/test_api_e2e.py`
- `backend/tests/e2e/test_complete_workflow_e2e.py`
- `backend/tests/e2e/test_frontend_backend_e2e.py`
- `backend/tests/docker/test_service_health.py`
- `backend/tests/docker/test_service_integration.py`
- `backend/tests/docker/test_data_persistence.py`
- `backend/tests/docker/test_network.py`
- `backend/tests/docker/conftest.py`

#### Test Fixtures
- `backend/tests/fixtures/api.py`
- `backend/tests/fixtures/database.py`
- `backend/tests/fixtures/llm.py`
- `backend/tests/fixtures/redis.py`
- `backend/tests/fixtures/storage.py`

#### Test Scripts
- `backend/scripts/run_all_tests.sh`
- `backend/scripts/run_all_tests.ps1`
- `backend/scripts/run_integration_tests.sh`
- `backend/scripts/run_integration_tests.ps1`
- `backend/scripts/run_e2e_tests.sh`
- `backend/scripts/run_e2e_tests.ps1`
- `backend/scripts/run_docker_tests.sh`

#### CI/CD Workflows
- `.github/workflows/integration-tests.yml`
- `.github/workflows/e2e-tests.yml`
- `.github/workflows/docker-tests.yml`

#### Config & Docs
- `pytest.ini` (docker marker eklendi, testpaths güncellendi)
- `backend/pytest.ini` (docker marker eklendi, testpaths güncellendi)
- `TEST_RUNNING_GUIDE.md`
- `backend/docs/TESTING.md` (güncellendi)

#### Bug Fixes (Test Infrastructure için gerekli)
- `mgx_agent/performance/profiler.py` (Windows uyumluluğu)
- `backend/mgx_agent/performance/profiler.py` (Windows uyumluluğu)
- `backend/db/models/entities.py` (SQLAlchemy overlaps)
- `backend/db/models/entities_evaluation.py` (metadata → alert_metadata)
- `backend/migrations/versions/ai_evaluation_framework_001.py` (metadata → alert_metadata)

---

### 2. ⚡ Performance Benchmarks PR
**Branch**: `feat/performance-benchmarks`
**Dosyalar**:

#### Performance Tests
- `backend/tests/performance/test_benchmarks.py`
- `backend/tests/performance/test_optimizations.py`
- `backend/tests/performance/benchmarks.py`

#### Performance Services
- `backend/services/llm/prompt_optimizer.py`

#### Performance API
- `backend/routers/performance.py`

#### Performance Scripts
- `backend/scripts/test_performance_optimizations.py`

#### Performance Migrations
- `backend/migrations/versions/performance_optimization_001.py`

#### Performance Docs
- `backend/PERFORMANCE_OPTIMIZATION_SUMMARY.md`

---

### 3. 🐛 Bug Fixes PR (Eğer ayrı göndermek isterseniz)
**Branch**: `fix/windows-compatibility-sqlalchemy`
**Dosyalar**:

#### Windows Uyumluluğu
- `mgx_agent/performance/profiler.py`
- `backend/mgx_agent/performance/profiler.py`

#### SQLAlchemy Düzeltmeleri
- `backend/db/models/entities.py` (overlaps parametreleri)
- `backend/db/models/entities_evaluation.py` (metadata → alert_metadata)
- `backend/migrations/versions/ai_evaluation_framework_001.py` (metadata → alert_metadata)

**Not**: Bu dosyalar Test Infrastructure PR'ında da var. Eğer ayrı PR istemiyorsanız, bunlar Test Infrastructure PR'ına dahil edilebilir.

---

### 4. 🎨 Frontend PR (Ayrı Repo: ai-front)
**Branch**: `feat/github-integration` (ai-front repo'da)
**Dosyalar**: Frontend submodule değişiklikleri

---

## 🔄 Alternatif Organizasyon

### Seçenek 1: Test Infrastructure + Bug Fixes (Önerilen)
Test Infrastructure PR'ına bug fix'leri de dahil edelim çünkü:
- Testlerin çalışması için bu düzeltmeler gerekli
- Ayrı PR oluşturmak gereksiz karmaşıklık yaratır
- Test Infrastructure PR'ı zaten kapsamlı

### Seçenek 2: Ayrı PR'lar
- Test Infrastructure PR (sadece test dosyaları)
- Bug Fixes PR (Windows + SQLAlchemy)
- Performance Benchmarks PR
- Frontend PR

---

## 📝 Commit Mesajları

### Test Infrastructure PR
```
feat: Add comprehensive test infrastructure

- Add integration tests (18 files)
- Add E2E tests (6 files)
- Add Docker tests (4 files)
- Add test fixtures and scripts
- Add CI/CD workflows
- Fix Windows compatibility (resource module)
- Fix SQLAlchemy relationship warnings
- Fix metadata reserved name conflict
- Update pytest.ini configuration
- Add test running guide
```

### Performance Benchmarks PR
```
feat: Add performance benchmarks and optimizations

- Add LLM performance benchmarks
- Add cache performance tests
- Add system performance tests
- Add LLM prompt optimizer
- Add performance API endpoints
- Add performance metrics tracking
```

### Bug Fixes PR (Eğer ayrı)
```
fix: Windows compatibility and SQLAlchemy fixes

- Fix resource module import for Windows
- Fix SQLAlchemy relationship overlaps
- Fix metadata reserved name conflict
```

---

## ✅ Önerilen Yaklaşım

**Test Infrastructure PR**'ına bug fix'leri dahil edelim çünkü:
1. Testlerin çalışması için bu düzeltmeler gerekli
2. Daha mantıklı bir gruplama
3. Daha az PR sayısı = daha kolay review

**Son PR Listesi**:
1. 🧪 Test Infrastructure PR (bug fix'ler dahil)
2. ⚡ Performance Benchmarks PR
3. 🎨 Frontend PR (ayrı repo)

