#!/usr/bin/env bash
set -euo pipefail

# Deploy the current version to the green environment.
#
# This script is intentionally conservative and uses placeholders.
# Adapt image tag, namespace, and manifest locations for your infra.

IMAGE_TAG=${IMAGE_TAG:-"latest"}
NAMESPACE_GREEN=${NAMESPACE_GREEN:-"production-green"}

echo "Deploying image tag: ${IMAGE_TAG} to namespace: ${NAMESPACE_GREEN}"

# 1) Build & tag (example)
# docker build -t "mgx-agent:${IMAGE_TAG}" .

# 2) Apply manifests
# kubectl apply -n "${NAMESPACE_GREEN}" -f k8s/production/

# 3) Run smoke tests
# kubectl run -n "${NAMESPACE_GREEN}" smoke --rm -i --restart=Never --image=curlimages/curl -- \
#   curl -fsS "http://mgx-agent/health/ready"

echo "Green deploy completed (placeholder)."
