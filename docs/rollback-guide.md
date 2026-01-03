# Rollback Guide

## Automatic Rollback Triggers

- Error rate > 10%
- Latency P99 > 10x baseline
- Service unavailable
- Health checks failing

## Manual Rollback Steps

1. Identify the previous known-good version (image tag / commit SHA).
2. Alert the team in `#incidents`.
3. Update the deployment to the previous version.
4. Monitor dashboards until metrics stabilize.
5. Document the rollback in the incident timeline.
