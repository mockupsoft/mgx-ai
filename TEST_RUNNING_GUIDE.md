# Test Çalıştırma Kılavuzu

Bu dokümantasyon, projede oluşturulan tüm test dosyalarını çalıştırmak için gereken adımları içerir.

## Test Dosyaları Özeti

### Integration Tests (18 dosya)
- `test_database_integration.py` - DB entegrasyon testleri
- `test_redis_integration.py` - Redis entegrasyon testleri
- `test_storage_integration.py` - MinIO/S3 entegrasyon testleri
- `test_api_integration.py` - API entegrasyon testleri
- `test_workflow_integration.py` - Workflow entegrasyon testleri
- + 13 mevcut integration test dosyası

**Konum**: `backend/tests/integration/`

### E2E Tests (6 dosya)
- `test_api_e2e.py` - API E2E testleri
- `test_frontend_backend_e2e.py` - Frontend-Backend E2E testleri
- `test_complete_workflow_e2e.py` - Complete workflow E2E testleri
- + 3 mevcut E2E test dosyası

**Konum**: `backend/tests/e2e/`

### Docker Tests (4 dosya)
- `test_service_health.py` - Service health check testleri
- `test_service_integration.py` - Service integration testleri
- `test_data_persistence.py` - Data persistence testleri
- `test_network.py` - Network connectivity testleri

**Konum**: `backend/tests/docker/`

## Kurulum

### 1. Bağımlılıkları Yükleyin

```bash
# Ana bağımlılıklar
pip install -r requirements.txt

# Test bağımlılıkları
pip install -r requirements-dev.txt
```

### 2. Ortam Değişkenlerini Ayarlayın

Testler için gerekli ortam değişkenlerini `.env` dosyasında ayarlayın:

```bash
# .env dosyası örneği
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/test_db
REDIS_URL=redis://localhost:6379/0
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

## Test Çalıştırma

### Tüm Testleri Çalıştırma

```bash
# Tüm testler
pytest tests/ backend/tests/ -v

# Veya sadece backend testleri
pytest backend/tests/ -v
```

### Kategoriye Göre Test Çalıştırma

#### Integration Tests

```bash
# Integration testleri
pytest -m integration backend/tests/integration/ -v

# Belirli bir integration test dosyası
pytest -m integration backend/tests/integration/test_database_integration.py -v
```

#### E2E Tests

```bash
# E2E testleri
pytest -m e2e backend/tests/e2e/ -v

# Belirli bir E2E test dosyası
pytest -m e2e backend/tests/e2e/test_api_e2e.py -v
```

#### Docker Tests

**Not**: Docker testleri çalıştırmak için Docker ve docker-compose'un çalışır durumda olması gerekir.

```bash
# Önce Docker servislerini başlatın
docker compose up -d

# Docker testleri
pytest -m docker backend/tests/docker/ -v

# Belirli bir Docker test dosyası
pytest -m docker backend/tests/docker/test_service_health.py -v
```

### Unit Tests

```bash
# Unit testleri
pytest -m unit tests/unit/ backend/tests/unit/ -v
```

## Test Seçenekleri

### Verbose Mod

```bash
pytest -v  # Detaylı çıktı
pytest -vv  # Daha detaylı çıktı
```

### Belirli Test Fonksiyonu

```bash
# Belirli bir test fonksiyonunu çalıştırma
pytest backend/tests/integration/test_database_integration.py::test_create_workspace -v
```

### İlk Hatada Durdur

```bash
pytest -x  # İlk hata durumunda durur
pytest --maxfail=3  # 3 hata sonrası durur
```

### Coverage Raporu

```bash
# Coverage ile test çalıştırma
pytest --cov=backend --cov-report=html --cov-report=term-missing

# HTML raporunu görüntüleme
# htmlcov/index.html dosyasını tarayıcıda açın
```

### Paralel Çalıştırma

```bash
# Tüm CPU çekirdeklerini kullanarak paralel çalıştırma
pytest -n auto

# Belirli sayıda worker ile
pytest -n 4
```

## Test Marker'ları

Projede kullanılan test marker'ları:

- `@pytest.mark.unit` - Unit testler
- `@pytest.mark.integration` - Integration testler
- `@pytest.mark.e2e` - End-to-end testler
- `@pytest.mark.docker` - Docker testleri
- `@pytest.mark.performance` - Performans testleri (varsayılan olarak hariç)
- `@pytest.mark.asyncio` - Async testler
- `@pytest.mark.slow` - Yavaş testler

### Marker ile Filtreleme

```bash
# Sadece integration testleri
pytest -m integration

# Integration ve e2e testleri
pytest -m "integration or e2e"

# Yavaş testleri hariç tut
pytest -m "not slow"

# Performance testleri dahil et
pytest -m "integration or performance"
```

## Sorun Giderme

### Import Hataları

Eğer import hataları alıyorsanız:

```bash
# Python path'i kontrol edin
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Windows için
set PYTHONPATH=%PYTHONPATH%;%CD%
```

### Veritabanı Bağlantı Hataları

Integration testleri için test veritabanının çalışır durumda olduğundan emin olun:

```bash
# PostgreSQL kontrolü
psql -U postgres -c "SELECT 1"

# Veya Docker ile
docker compose ps postgres
```

### Redis Bağlantı Hataları

```bash
# Redis kontrolü
redis-cli ping

# Veya Docker ile
docker compose ps redis
```

### MinIO Bağlantı Hataları

```bash
# MinIO kontrolü
curl http://localhost:9000/minio/health/live

# Veya Docker ile
docker compose ps minio
```

## CI/CD Entegrasyonu

GitHub Actions veya diğer CI/CD sistemlerinde test çalıştırmak için:

```yaml
# .github/workflows/tests.yml örneği
- name: Run Integration Tests
  run: |
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    pytest -m integration backend/tests/integration/ -v

- name: Run E2E Tests
  run: |
    pytest -m e2e backend/tests/e2e/ -v

- name: Run Docker Tests
  run: |
    docker compose up -d
    pytest -m docker backend/tests/docker/ -v
```

## Daha Fazla Bilgi

- Detaylı test dokümantasyonu: `docs/TESTING.md`
- Backend test dokümantasyonu: `backend/docs/TESTING.md`
- Workflow test dokümantasyonu: `docs/WORKFLOW_TESTING.md`

