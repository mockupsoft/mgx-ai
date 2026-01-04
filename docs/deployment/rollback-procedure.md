# Rollback Procedure (Blue-Green)

This runbook describes the production rollback procedure for a blue-green deployment.

## Objective

- Restore stable service within **< 1 minute**.
- Minimize user impact.
- Ensure **no data loss** (requires compatible schema changes).

## One-click Rollback

Rollback is implemented by switching traffic back to the blue environment:

- Kubernetes Service selector: `color=blue`
- Ingress backend switch
- Load balancer target group swap

Script: `scripts/rollback-production.sh`

## Preconditions

- Blue is running and healthy.
- Blue has access to all required dependencies (DB/Redis/etc).
- Database schema is backward compatible.

## Rollback Steps

1. **Announce rollback** in incident channel.
2. Switch traffic green → blue.
3. Verify:
   - `/health/ready` is 200
   - key API endpoints are responding
   - errors return to baseline
4. Keep green running for investigation.
5. Capture:
   - deployment version identifiers
   - logs, traces, metrics snapshots

## Verification Checklist

- ✅ error rate recovered
- ✅ latency recovered
- ✅ no data corruption
- ✅ no stuck jobs / queue backlogs

## Rollback Drill

Run at least quarterly:

- execute rollback in a controlled window
- record time-to-recovery and any manual steps

## Post-rollback Actions

- open incident report
- add a regression test or alert for the triggering condition
- create follow-up ticket to fix root cause before re-attempting green cutover
