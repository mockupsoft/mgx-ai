#!/bin/bash
# -*- coding: utf-8 -*-
"""
Run Integration Tests

Executes all integration tests with proper environment setup.
"""

set -e

echo "=========================================="
echo "Running Integration Tests"
echo "=========================================="

# Set test environment variables
export TESTING=true
export DATABASE_URL="sqlite+aiosqlite:///:memory:"
export REDIS_URL="redis://localhost:6379/15"
export S3_ENDPOINT_URL="http://localhost:9000"

# Run integration tests
pytest -m integration \
    backend/tests/integration/ \
    -v \
    --tb=short \
    --maxfail=5 \
    --durations=10

echo "=========================================="
echo "Integration Tests Completed"
echo "=========================================="




