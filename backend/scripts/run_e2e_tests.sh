#!/bin/bash
# -*- coding: utf-8 -*-
"""
Run E2E Tests

Executes all end-to-end tests with proper environment setup.
"""

set -e

echo "=========================================="
echo "Running E2E Tests"
echo "=========================================="

# Set test environment variables
export TESTING=true
export DATABASE_URL="sqlite+aiosqlite:///:memory:"
export REDIS_URL="redis://localhost:6379/15"
export S3_ENDPOINT_URL="http://localhost:9000"

# Run E2E tests
pytest -m e2e \
    backend/tests/e2e/ \
    -v \
    --tb=short \
    --maxfail=5 \
    --durations=10

echo "=========================================="
echo "E2E Tests Completed"
echo "=========================================="

