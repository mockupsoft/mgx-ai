#!/usr/bin/env bash
set -euo pipefail

# One-click rollback by switching the stable service selector back to blue.

NAMESPACE=${NAMESPACE:-"production"}
SERVICE_NAME=${SERVICE_NAME:-"mgx-agent-lb"}

echo "Rolling back: switching ${SERVICE_NAME} selector color=blue in namespace ${NAMESPACE}"

# Example (Kubernetes Service selector patch)
# kubectl patch service "${SERVICE_NAME}" -n "${NAMESPACE}" --type merge -p '{"spec":{"selector":{"app":"mgx-agent","color":"blue"}}}'

echo "Rollback completed (placeholder). Verify /health/ready and error rate."
