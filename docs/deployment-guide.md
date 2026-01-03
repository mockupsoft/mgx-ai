# Deployment Guide

## Overview

MGX-AI supports three environments:

- **Dev**: fast iteration, single replica
- **Staging**: production-like validation
- **Production**: blue-green deployment, strict gates

Kubernetes templates:
- `/k8s/deployments/dev-deployment.yaml`
- `/k8s/deployments/staging-deployment.yaml`
- `/k8s/deployments/prod-deployment.yaml`

## Per-Environment Checklist

### Dev (< 5 minutes)

- Build succeeds
- Unit tests pass
- Basic lint check

### Staging (< 30 minutes)

- All tests pass (unit + integration)
- No critical vulnerabilities
- Coverage > 80%
- Full lint + type checks
- Monitoring enabled

### Production (< 45 minutes)

- All staging gates pass
- Manual review approved
- Deployment window confirmed
- Rollback plan documented

## Deployment Steps (High Level)

1. Apply ConfigMap + Secret for the environment.
2. Deploy the new image.
3. Watch `/health/ready` and error/latency dashboards.
4. For production, shift traffic gradually (blue-green) and keep rollback ready.

## Monitoring During Deployment

- Use the on-call dashboard: `/monitoring/dashboards/on-call-dashboard.json`
- Verify:
  - Error rate stays below 2% baseline drift
  - P99 latency stays within 2x baseline

## Rollback

See `/docs/rollback-guide.md`.
