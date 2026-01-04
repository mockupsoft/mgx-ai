# Rollback Emergency Runbook

## When to Run

- Sustained error rate increase after deploy
- Readiness failures
- Elevated latency beyond SLO

## Immediate Actions

1. Confirm impact (dashboard + alerts).
2. Execute rollback:
   - `scripts/rollback-production.sh`
3. Verify recovery:
   - `/health/ready` 200
   - error rate back to baseline
4. Capture evidence for post-mortem.

## Communication

- Notify on-call channel
- Update status page (if applicable)
- Record start/end times
