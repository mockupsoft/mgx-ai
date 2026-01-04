#!/usr/bin/env bash
set -euo pipefail

# Security code review helper.
# Runs SAST tools and produces human-readable output.

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

cd "${ROOT_DIR}"

echo "Running bandit..."
if command -v bandit >/dev/null 2>&1; then
  bandit -r backend -c backend/.bandit.yaml || true
else
  echo "bandit not installed"
fi
