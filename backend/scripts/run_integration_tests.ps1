# -*- coding: utf-8 -*-
# Run Integration Tests (PowerShell)

Write-Host "=========================================="
Write-Host "Running Integration Tests"
Write-Host "=========================================="

# Set test environment variables
$env:TESTING = "true"
$env:DATABASE_URL = "sqlite+aiosqlite:///:memory:"
$env:REDIS_URL = "redis://localhost:6379/15"
$env:S3_ENDPOINT_URL = "http://localhost:9000"

# Run integration tests
pytest -m integration `
    backend/tests/integration/ `
    -v `
    --tb=short `
    --maxfail=5 `
    --durations=10

Write-Host "=========================================="
Write-Host "Integration Tests Completed"
Write-Host "=========================================="

