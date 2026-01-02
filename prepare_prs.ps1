# PR Hazırlama Scripti (PowerShell)

Write-Host "🧪 Test Infrastructure PR hazırlanıyor..." -ForegroundColor Cyan

# Test Infrastructure PR için dosyaları ekle
git add backend/tests/integration/test_*.py
git add backend/tests/e2e/test_*.py
git add backend/tests/docker/
git add backend/tests/fixtures/
git add backend/scripts/run_*_tests.*
git add .github/workflows/*-tests.yml
git add pytest.ini
git add backend/pytest.ini
git add TEST_RUNNING_GUIDE.md
git add backend/docs/TESTING.md

# Bug fixes (testlerin çalışması için gerekli)
git add mgx_agent/performance/profiler.py
git add backend/mgx_agent/performance/profiler.py
git add backend/db/models/entities.py
git add backend/db/models/entities_evaluation.py
git add backend/migrations/versions/ai_evaluation_framework_001.py

Write-Host "✅ Test Infrastructure PR hazırlandı!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Commit mesajı:" -ForegroundColor Yellow
Write-Host "feat: Add comprehensive test infrastructure"
Write-Host ""
Write-Host "Sonraki adım: git commit -m 'feat: Add comprehensive test infrastructure'"

