# Traffic Switching Procedure

This document describes how to switch traffic between **blue** and **green** environments.

## Mechanism

Primary switching mechanism:

- Kubernetes Service selector update (atomic patch)
- or load balancer target-group swap

Tooling:

- `backend/app/deployment/traffic_switcher.py`
- `k8s/services/traffic-switcher-service.yaml`

## Safety Gates

Before switching:

- green health: `/health/ready` 200 for >= 5 minutes
- error rate < 1%
- p95 latency within acceptable range

## Switch Steps

1. Start an observation window (dashboards open).
2. Execute switch:
   - `python -m backend.app.deployment.traffic_switcher switch --target green`
3. Watch error rate + latency for 5-15 minutes.
4. If anomalies exceed threshold, rollback:
   - `scripts/rollback-production.sh`

## Automatic Rollback Policy

- rollback if error rate > 1% for 60 seconds
- rollback if readiness probe fails for 2 consecutive checks

## Post-switch

- keep blue warm for at least 24 hours
- keep a rollback window open
- generate a post-deploy report
