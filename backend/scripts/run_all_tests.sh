#!/bin/bash
# -*- coding: utf-8 -*-
"""
Run All Tests

Executes all test suites: unit, integration, E2E, and Docker tests.
"""

set -e

echo "=========================================="
echo "Running All Tests"
echo "=========================================="

# Set test environment variables
export TESTING=true
export DATABASE_URL="sqlite+aiosqlite:///:memory:"
export REDIS_URL="redis://localhost:6379/15"
export S3_ENDPOINT_URL="http://localhost:9000"

# Track test results
EXIT_CODE=0

# Run unit tests
echo ""
echo "--- Running Unit Tests ---"
pytest -m "unit and not slow" \
    backend/tests/unit/ \
    -v \
    --tb=short \
    --maxfail=10 \
    || EXIT_CODE=$?

# Run integration tests
echo ""
echo "--- Running Integration Tests ---"
pytest -m integration \
    backend/tests/integration/ \
    -v \
    --tb=short \
    --maxfail=5 \
    || EXIT_CODE=$?

# Run E2E tests
echo ""
echo "--- Running E2E Tests ---"
pytest -m e2e \
    backend/tests/e2e/ \
    -v \
    --tb=short \
    --maxfail=5 \
    || EXIT_CODE=$?

# Run Docker tests (if Docker is available)
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    echo ""
    echo "--- Running Docker Tests ---"
    pytest -m docker \
        backend/tests/docker/ \
        -v \
        --tb=short \
        --maxfail=5 \
        || EXIT_CODE=$?
else
    echo ""
    echo "--- Skipping Docker Tests (Docker not available) ---"
fi

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "All Tests Passed!"
else
    echo "Some Tests Failed (exit code: $EXIT_CODE)"
fi
echo "=========================================="

exit $EXIT_CODE




