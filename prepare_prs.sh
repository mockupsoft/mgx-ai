#!/bin/bash
# PR Hazırlama Scripti

echo "🧪 Test Infrastructure PR hazırlanıyor..."

# Test Infrastructure PR için dosyaları ekle
git add backend/tests/integration/test_*.py
git add backend/tests/e2e/test_*.py
git add backend/tests/docker/
git add backend/tests/fixtures/
git add backend/scripts/run_*_tests.*
git add .github/workflows/*-tests.yml
git add pytest.ini backend/pytest.ini
git add TEST_RUNNING_GUIDE.md
git add backend/docs/TESTING.md

# Bug fixes (testlerin çalışması için gerekli)
git add mgx_agent/performance/profiler.py
git add backend/mgx_agent/performance/profiler.py
git add backend/db/models/entities.py
git add backend/db/models/entities_evaluation.py
git add backend/migrations/versions/ai_evaluation_framework_001.py

echo "✅ Test Infrastructure PR hazırlandı!"
echo ""
echo "📝 Commit mesajı:"
echo "feat: Add comprehensive test infrastructure"
echo ""
echo "- Add integration tests (18 files)"
echo "- Add E2E tests (6 files)"
echo "- Add Docker tests (4 files)"
echo "- Add test fixtures and scripts"
echo "- Add CI/CD workflows"
echo "- Fix Windows compatibility (resource module)"
echo "- Fix SQLAlchemy relationship warnings"
echo "- Fix metadata reserved name conflict"
echo "- Update pytest.ini configuration"
echo "- Add test running guide"

