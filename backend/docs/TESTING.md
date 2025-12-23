# Testing Guide

Bu dokümantasyon, proje için test yürütme, test yazma ve test altyapısı hakkında bilgi sağlar.

## Test Kategorileri

### Unit Tests
- **Konum**: `backend/tests/unit/`
- **Amaç**: Bireysel fonksiyon ve sınıfların izole testleri
- **Çalıştırma**: `pytest -m unit backend/tests/unit/`

### Integration Tests
- **Konum**: `backend/tests/integration/`
- **Amaç**: Sistem bileşenlerinin birlikte çalışmasını test eder
- **Kapsam**:
  - Backend-DB entegrasyon testleri
  - Backend-Redis entegrasyon testleri
  - Backend-MinIO entegrasyon testleri
  - Backend API entegrasyon testleri
  - Multi-agent workflow entegrasyon testleri
- **Çalıştırma**: `pytest -m integration backend/tests/integration/`

### E2E Tests
- **Konum**: `backend/tests/e2e/`
- **Amaç**: Tam workflow'ların baştan sona çalışmasını test eder
- **Kapsam**:
  - API E2E testleri
  - Frontend-Backend E2E testleri
  - CLI E2E testleri
  - Complete workflow E2E testleri
- **Çalıştırma**: `pytest -m e2e backend/tests/e2e/`

### Docker Tests
- **Konum**: `backend/tests/docker/`
- **Amaç**: Docker Compose deployment'ının doğru çalıştığını test eder
- **Kapsam**:
  - Service health check testleri
  - Service integration testleri
  - Data persistence testleri
  - Network connectivity testleri
- **Çalıştırma**: `pytest -m docker backend/tests/docker/`
- **Gereksinimler**: Docker ve docker-compose

## Test Çalıştırma

### Tüm Testleri Çalıştırma

**Linux/Mac:**
```bash
./backend/scripts/run_all_tests.sh
```

**Windows (PowerShell):**
```powershell
.\backend\scripts\run_all_tests.ps1
```

**Manuel:**
```bash
pytest backend/tests/ -v
```

### Belirli Test Kategorisini Çalıştırma

**Integration Tests:**
```bash
pytest -m integration backend/tests/integration/ -v
```

**E2E Tests:**
```bash
pytest -m e2e backend/tests/e2e/ -v
```

**Docker Tests:**
```bash
pytest -m docker backend/tests/docker/ -v
```

### Belirli Test Dosyasını Çalıştırma

```bash
pytest backend/tests/integration/test_database_integration.py -v
```

### Belirli Test Fonksiyonunu Çalıştırma

```bash
pytest backend/tests/integration/test_database_integration.py::TestModelCRUD::test_workspace_create -v
```

## Test Markers

Testler aşağıdaki marker'lar ile kategorize edilmiştir:

- `@pytest.mark.unit`: Unit testler
- `@pytest.mark.integration`: Integration testler
- `@pytest.mark.e2e`: E2E testler
- `@pytest.mark.docker`: Docker testler
- `@pytest.mark.slow`: Yavaş çalışan testler
- `@pytest.mark.performance`: Performance testler (varsayılan olarak hariç)

### Marker Kullanımı

```python
import pytest

@pytest.mark.integration
class TestDatabaseIntegration:
    """Database integration tests."""
    
    async def test_workspace_create(self):
        """Test creating a workspace."""
        pass
```

## Test Fixtures

### Database Fixtures

`backend/tests/fixtures/database.py` dosyasında:
- `test_db_engine`: Test database engine
- `test_db_session`: Test database session
- `test_workspace`: Test workspace
- `test_project`: Test project
- `test_task`: Test task
- `test_agent_definition`: Test agent definition
- `test_agent_instance`: Test agent instance

### Redis Fixtures

`backend/tests/fixtures/redis.py` dosyasında:
- `mock_redis_client`: Mock Redis client
- `redis_cache_fixture`: Redis cache fixture

### Storage Fixtures

`backend/tests/fixtures/storage.py` dosyasında:
- `mock_s3_client`: Mock S3 client
- `test_bucket`: Test bucket

### API Fixtures

`backend/tests/fixtures/api.py` dosyasında:
- `test_app`: Test FastAPI app
- `api_client`: Test HTTP client
- `authenticated_client`: Authenticated test client

### LLM Fixtures

`backend/tests/fixtures/llm.py` dosyasında:
- `mock_llm_provider`: Mock LLM provider
- `mock_llm_response`: Mock LLM response
- `mock_llm_cost_tracker`: Mock LLM cost tracker

## Test Environment Variables

Testler aşağıdaki environment variable'ları kullanır:

```bash
TESTING=true
DATABASE_URL=sqlite+aiosqlite:///:memory:
REDIS_URL=redis://localhost:6379/15
S3_ENDPOINT_URL=http://localhost:9000
```

## CI/CD Integration

### GitHub Actions Workflows

- **Integration Tests**: `.github/workflows/integration-tests.yml`
- **E2E Tests**: `.github/workflows/e2e-tests.yml`
- **Docker Tests**: `.github/workflows/docker-tests.yml`

### Workflow Triggering

Testler şu durumlarda otomatik çalışır:
- `main` veya `develop` branch'ine push
- Pull request açıldığında
- Manuel olarak `workflow_dispatch` ile

## Test Coverage

Test coverage raporu oluşturmak için:

```bash
pytest --cov=backend --cov-report=html backend/tests/
```

Coverage raporu `htmlcov/index.html` dosyasında görüntülenebilir.

## Troubleshooting

### Test Başarısız Oluyor

1. **Database Connection Errors**: Test database URL'ini kontrol edin
2. **Redis Connection Errors**: Redis'in çalıştığından emin olun
3. **Import Errors**: Python path'in doğru ayarlandığından emin olun
4. **Async Errors**: `pytest-asyncio` plugin'inin yüklü olduğundan emin olun

### Docker Testleri Çalışmıyor

1. Docker'ın çalıştığından emin olun: `docker ps`
2. Docker Compose'un yüklü olduğundan emin olun: `docker compose version`
3. Port çakışmalarını kontrol edin
4. Container loglarını kontrol edin: `docker compose logs`

### Test Timeout

Yavaş testler için timeout süresini artırın:

```bash
pytest --timeout=300 backend/tests/
```

## Best Practices

1. **Test Isolation**: Her test bağımsız olmalı
2. **Test Data**: Test verileri her test için ayrı oluşturulmalı
3. **Cleanup**: Test sonrası temizlik yapılmalı
4. **Naming**: Test isimleri açıklayıcı olmalı
5. **Documentation**: Test dokümantasyonu güncel tutulmalı

## Test Execution Scripts

### Linux/Mac Scripts

- `backend/scripts/run_integration_tests.sh`
- `backend/scripts/run_e2e_tests.sh`
- `backend/scripts/run_docker_tests.sh`
- `backend/scripts/run_all_tests.sh`

### Windows Scripts (PowerShell)

- `backend/scripts/run_integration_tests.ps1`
- `backend/scripts/run_e2e_tests.ps1`
- `backend/scripts/run_all_tests.ps1`

## Daha Fazla Bilgi

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-Asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
