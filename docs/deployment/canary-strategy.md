# Canary Deployment Strategy (Optional / Future)

Canary deployments gradually shift traffic to a new version, allowing early detection of issues with minimal user impact.

## Traffic Plan

- 5% → 25% → 50% → 100%

Advance only when:

- error rate <= 0.5%
- p95 latency within baseline tolerance
- no sustained increase in resource utilization

## Automatic Rollback

Rollback triggers:

- error rate > 0.5% for 5 minutes (or > 1% for 1 minute)
- elevated 5xx or timeouts
- saturation (CPU throttling, OOM, queue backlogs)

## Implementation (Istio Example)

Use an Istio `VirtualService` with weighted routing:

- stable (blue) subset weight
- canary (green) subset weight

A rollout controller (or automation script) updates weights.

## Operational Notes

- Ensure both versions share compatible database schema.
- Use feature flags to decouple deploy from release.
- Ensure metrics are labeled by version/subset.
