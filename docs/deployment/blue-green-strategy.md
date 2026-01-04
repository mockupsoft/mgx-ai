# Blue-Green Deployment Strategy

This document defines the production blue-green strategy for **instant (<1s) traffic switching**, safe validation, and **one-click rollback**.

## Environments

- **Blue**: Current production (stable).
- **Green**: New release candidate (staging-equivalent, production-grade infrastructure).

Both environments are expected to be **fully capable** of handling 100% of production traffic.

## Goals

- Zero-downtime deployments.
- Instant traffic cutover (target: < 1 second).
- Fast rollback with no data loss.
- Clear health gating and validation steps.

## High-level Flow

1. Deploy new version to **green**.
2. Run smoke + critical-path validation against green.
3. Verify metrics/logs/traces for green.
4. Switch traffic from blue → green at the load balancer (or service selector).
5. Monitor for anomalies; automatically rollback if error budget is exceeded.

## Traffic Switching Model

### Load Balancer / Service Selector Switching (Primary)

Preferred mechanism is a **single stable frontend** (LB / Ingress / Service) that routes to a backend pool labeled:

- `color=blue`
- `color=green`

Traffic is switched by updating a selector/weight (depending on platform):

- Kubernetes Service selector patch (simple)
- Ingress backend switch
- Service mesh routing (Istio / Linkerd)

**Target**: the update must be atomic and completed within < 1 second.

### DNS Switching (Secondary)

DNS switching is **not the primary** mechanism due to TTL and cache uncertainty. It is reserved for:

- disaster recovery
- regional failover

## Health Gating

### Required Health Checks

Before switching traffic to green, all must be healthy:

- `/health/ready` returns 200
- DB connectivity OK
- Redis connectivity OK (if enabled)
- Background workers running
- External providers used in critical paths reachable

### Switching Gate

Traffic switch is only allowed when:

- green is healthy for >= 5 minutes
- p95 latency within baseline tolerance
- error rate < 0.5% (pre-switch)

## Rollback

Rollback is always:

- switch traffic from green → blue
- keep green running for post-mortem (unless it is causing impact)

See: [`rollback-procedure.md`](./rollback-procedure.md)

## Parallel Maintenance

- Blue and green must be patched for security updates.
- Secrets/config drift must be prevented:
  - use a single source of truth (GitOps)
  - use sealed secrets / external secret store

## Data Safety

To avoid data loss:

- Database schema changes must be backward compatible.
- Prefer expand/contract migrations.
- Feature flags should guard new behavior.

## Observability Requirements

During green validation and the cutover window:

- logs: structured + correlation IDs
- metrics: request rate, error rate, latency, saturation
- traces: end-to-end for key endpoints

See: `docs/monitoring-during-switch.md`
