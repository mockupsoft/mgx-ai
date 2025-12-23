# -*- coding: utf-8 -*-
# Run All Tests (PowerShell)

Write-Host "=========================================="
Write-Host "Running All Tests"
Write-Host "=========================================="

# Set test environment variables
$env:TESTING = "true"
$env:DATABASE_URL = "sqlite+aiosqlite:///:memory:"
$env:REDIS_URL = "redis://localhost:6379/15"
$env:S3_ENDPOINT_URL = "http://localhost:9000"

$ExitCode = 0

# Run unit tests
Write-Host ""
Write-Host "--- Running Unit Tests ---"
pytest -m "unit and not slow" `
    backend/tests/unit/ `
    -v `
    --tb=short `
    --maxfail=10
if ($LASTEXITCODE -ne 0) { $ExitCode = $LASTEXITCODE }

# Run integration tests
Write-Host ""
Write-Host "--- Running Integration Tests ---"
pytest -m integration `
    backend/tests/integration/ `
    -v `
    --tb=short `
    --maxfail=5
if ($LASTEXITCODE -ne 0) { $ExitCode = $LASTEXITCODE }

# Run E2E tests
Write-Host ""
Write-Host "--- Running E2E Tests ---"
pytest -m e2e `
    backend/tests/e2e/ `
    -v `
    --tb=short `
    --maxfail=5
if ($LASTEXITCODE -ne 0) { $ExitCode = $LASTEXITCODE }

# Run Docker tests (if Docker is available)
if (Get-Command docker -ErrorAction SilentlyContinue) {
    if (docker compose version 2>&1 | Out-Null) {
        Write-Host ""
        Write-Host "--- Running Docker Tests ---"
        pytest -m docker `
            backend/tests/docker/ `
            -v `
            --tb=short `
            --maxfail=5
        if ($LASTEXITCODE -ne 0) { $ExitCode = $LASTEXITCODE }
    } else {
        Write-Host ""
        Write-Host "--- Skipping Docker Tests (Docker Compose not available) ---"
    }
} else {
    Write-Host ""
    Write-Host "--- Skipping Docker Tests (Docker not available) ---"
}

Write-Host ""
Write-Host "=========================================="
if ($ExitCode -eq 0) {
    Write-Host "All Tests Passed!"
} else {
    Write-Host "Some Tests Failed (exit code: $ExitCode)"
}
Write-Host "=========================================="

exit $ExitCode

