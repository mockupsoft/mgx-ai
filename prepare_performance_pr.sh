#!/bin/bash
# Performance Benchmarks PR Hazırlama Scripti

echo "⚡ Performance Benchmarks PR hazırlanıyor..."

# Performance PR için dosyaları ekle
git add backend/tests/performance/
git add backend/services/llm/prompt_optimizer.py
git add backend/routers/performance.py
git add backend/scripts/test_performance_optimizations.py
git add backend/migrations/versions/performance_optimization_001.py
git add backend/PERFORMANCE_OPTIMIZATION_SUMMARY.md

echo "✅ Performance Benchmarks PR hazırlandı!"
echo ""
echo "📝 Commit mesajı:"
echo "feat: Add performance benchmarks and optimizations"
echo ""
echo "- Add LLM performance benchmarks"
echo "- Add cache performance tests"
echo "- Add system performance tests"
echo "- Add LLM prompt optimizer"
echo "- Add performance API endpoints"
echo "- Add performance metrics tracking"

