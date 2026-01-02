#!/bin/bash
# -*- coding: utf-8 -*-
"""
Run Docker Compose Tests

Executes all Docker compose tests.
Requires Docker and docker-compose to be available.
"""

set -e

echo "=========================================="
echo "Running Docker Compose Tests"
echo "=========================================="

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH"
    exit 1
fi

# Check if docker compose is available
if ! docker compose version &> /dev/null; then
    echo "Error: Docker Compose is not installed or not in PATH"
    exit 1
fi

# Run Docker tests
pytest -m docker \
    backend/tests/docker/ \
    -v \
    --tb=short \
    --maxfail=5 \
    --durations=10

echo "=========================================="
echo "Docker Compose Tests Completed"
echo "=========================================="




