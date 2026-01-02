# 🚀 PR Hazırlama Rehberi

Bu rehber, projenin son halini PR olarak göndermek için gerekli adımları içerir.

## 📋 PR Organizasyonu

### 1. 🧪 Test Infrastructure PR (Önerilen: Bug Fix'ler Dahil)
**Branch**: `feat/test-infrastructure`
**PR Body**: `PR_TEST_INFRASTRUCTURE.md`

### 2. ⚡ Performance Benchmarks PR
**Branch**: `feat/performance-benchmarks`
**PR Body**: `PR_PERFORMANCE_BENCHMARKS.md`

### 3. 🎨 Frontend PR (Ayrı Repo)
**Repo**: `ai-front`
**Branch**: `feat/github-integration`
**PR Body**: `FRONTEND_PR_BODY.md`

---

## 🔧 Adım Adım PR Hazırlama

### Adım 1: Test Infrastructure PR

```powershell
# Branch'e geç
git checkout feat/test-infrastructure

# Dosyaları ekle (PowerShell script kullanarak)
.\prepare_prs.ps1

# Veya manuel olarak:
git add backend/tests/integration/test_*.py
git add backend/tests/e2e/test_*.py
git add backend/tests/docker/
git add backend/tests/fixtures/
git add backend/scripts/run_*_tests.*
git add .github/workflows/*-tests.yml
git add pytest.ini backend/pytest.ini
git add TEST_RUNNING_GUIDE.md
git add backend/docs/TESTING.md

# Bug fixes
git add mgx_agent/performance/profiler.py
git add backend/mgx_agent/performance/profiler.py
git add backend/db/models/entities.py
git add backend/db/models/entities_evaluation.py
git add backend/migrations/versions/ai_evaluation_framework_001.py

# Commit
git commit -m "feat: Add comprehensive test infrastructure

- Add integration tests (18 files)
- Add E2E tests (6 files)
- Add Docker tests (4 files)
- Add test fixtures and scripts
- Add CI/CD workflows
- Fix Windows compatibility (resource module)
- Fix SQLAlchemy relationship warnings
- Fix metadata reserved name conflict
- Update pytest.ini configuration
- Add test running guide"

# Push
git push origin feat/test-infrastructure
```

**GitHub'da PR oluştur**:
- Base: `main`
- Compare: `feat/test-infrastructure`
- Title: `🧪 Test Infrastructure: Integration, E2E ve Docker Tests`
- Body: `PR_TEST_INFRASTRUCTURE.md` içeriğini kopyala

---

### Adım 2: Performance Benchmarks PR

```powershell
# Main'e dön
git checkout main

# Performance branch'e geç
git checkout feat/performance-benchmarks

# Dosyaları ekle
git add backend/tests/performance/
git add backend/services/llm/prompt_optimizer.py
git add backend/routers/performance.py
git add backend/scripts/test_performance_optimizations.py
git add backend/migrations/versions/performance_optimization_001.py
git add backend/PERFORMANCE_OPTIMIZATION_SUMMARY.md

# Commit
git commit -m "feat: Add performance benchmarks and optimizations

- Add LLM performance benchmarks
- Add cache performance tests
- Add system performance tests
- Add LLM prompt optimizer
- Add performance API endpoints
- Add performance metrics tracking"

# Push
git push origin feat/performance-benchmarks
```

**GitHub'da PR oluştur**:
- Base: `main`
- Compare: `feat/performance-benchmarks`
- Title: `⚡ Performance Benchmarks ve Optimizasyonlar`
- Body: `PR_PERFORMANCE_BENCHMARKS.md` içeriğini kopyala

---

### Adım 3: Frontend PR (Ayrı Repo)

```powershell
# Frontend repo'ya git
cd ../ai-front

# Branch oluştur
git checkout -b feat/github-integration

# Frontend değişikliklerini commit et
git add .
git commit -m "feat: Add GitHub integration frontend components

- Add PR management components
- Add Issues management components
- Add Activity feed components
- Add Branch management components
- Add Diff viewer components
- Add React hooks for GitHub API
- Add test files"

# Push
git push origin feat/github-integration
```

**GitHub'da PR oluştur**:
- Repo: `ai-front`
- Base: `main`
- Compare: `feat/github-integration`
- Title: `🎨 GitHub Entegrasyonu Frontend Bileşenleri`
- Body: `FRONTEND_PR_BODY.md` içeriğini kopyala

---

## 📝 PR Body Dosyaları

1. **PR_TEST_INFRASTRUCTURE.md** - Test Infrastructure PR body
2. **PR_PERFORMANCE_BENCHMARKS.md** - Performance Benchmarks PR body
3. **PR_BUG_FIXES.md** - Bug Fixes PR body (opsiyonel, Test Infrastructure'a dahil)
4. **FRONTEND_PR_BODY.md** - Frontend PR body

---

## ✅ Checklist

### Test Infrastructure PR
- [x] Branch oluşturuldu: `feat/test-infrastructure`
- [x] Test dosyaları eklendi
- [x] Test fixtures eklendi
- [x] Test scriptleri eklendi
- [x] CI/CD workflows eklendi
- [x] Bug fix'ler eklendi
- [x] PR body hazırlandı
- [ ] Commit yapıldı
- [ ] Push yapıldı
- [ ] GitHub'da PR oluşturuldu

### Performance Benchmarks PR
- [x] Branch oluşturuldu: `feat/performance-benchmarks`
- [x] Performance test dosyaları eklendi
- [x] Performance services eklendi
- [x] Performance API eklendi
- [x] PR body hazırlandı
- [ ] Commit yapıldı
- [ ] Push yapıldı
- [ ] GitHub'da PR oluşturuldu

### Frontend PR
- [ ] Branch oluşturuldu: `feat/github-integration` (ai-front repo'da)
- [ ] Frontend değişiklikleri commit edildi
- [ ] Push yapıldı
- [ ] GitHub'da PR oluşturuldu

---

## 🎯 Önerilen Sıra

1. **Test Infrastructure PR** (en önemli, diğer PR'lar buna bağımlı olabilir)
2. **Performance Benchmarks PR** (bağımsız)
3. **Frontend PR** (ayrı repo, bağımsız)

---

## 📊 PR İstatistikleri

### Test Infrastructure PR
- **Dosya Sayısı**: 50+ dosya
- **Test Dosyaları**: 28 dosya
- **Test Fixtures**: 5 dosya
- **Test Scripts**: 8 dosya
- **CI/CD Workflows**: 3 dosya

### Performance Benchmarks PR
- **Dosya Sayısı**: 7 dosya
- **Test Dosyaları**: 3 dosya
- **Services**: 1 dosya
- **API**: 1 dosya

---

## 🔗 GitHub PR Linkleri

PR'lar oluşturulduktan sonra buraya linkler eklenecek:
- Test Infrastructure PR: [Link eklenecek]
- Performance Benchmarks PR: [Link eklenecek]
- Frontend PR: [Link eklenecek]

---

## 💡 Notlar

- Test Infrastructure PR'ına bug fix'ler dahil edildi çünkü testlerin çalışması için gerekli
- Performance Benchmarks PR bağımsız olarak gönderilebilir
- Frontend PR ayrı repo'da olduğu için bağımsız

