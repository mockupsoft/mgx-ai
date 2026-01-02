# -*- coding: utf-8 -*-
# Run E2E Tests (PowerShell)

Write-Host "=========================================="
Write-Host "Running E2E Tests"
Write-Host "=========================================="

# Set test environment variables
$env:TESTING = "true"
$env:DATABASE_URL = "sqlite+aiosqlite:///:memory:"
$env:REDIS_URL = "redis://localhost:6379/15"
$env:S3_ENDPOINT_URL = "http://localhost:9000"

# Run E2E tests
pytest -m e2e `
    backend/tests/e2e/ `
    -v `
    --tb=short `
    --maxfail=5 `
    --durations=10

Write-Host "=========================================="
Write-Host "E2E Tests Completed"
Write-Host "=========================================="




