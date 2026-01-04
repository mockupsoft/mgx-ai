#!/usr/bin/env bash
set -euo pipefail

# Dependency scanning helper.
# Runs tools that detect known vulnerabilities.

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

cd "${ROOT_DIR}"

echo "Running pip-audit (if installed)..."
if command -v pip-audit >/dev/null 2>&1; then
  pip-audit || true
else
  echo "pip-audit not installed"
fi

echo "Running safety check (if installed)..."
if command -v safety >/dev/null 2>&1; then
  safety check || true
else
  echo "safety not installed"
fi
