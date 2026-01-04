# Monitoring During Production Switch

## Goal

Detect regressions quickly and rollback within minutes.

## Dashboards

- request rate (RPS)
- error rate (4xx/5xx)
- latency p50/p95/p99
- saturation (CPU/memory)
- dependency health (DB, Redis)

Dashboard file: `monitoring/production-switch-dashboard.json`

## Alerts

- switch anomaly alerts: `monitoring/production-switch-alerts.yaml`
- traffic switcher alerts: `monitoring/traffic-switch-alerts.yaml`

## Timeline

### During Switch (seconds)

- watch immediate increase in 5xx
- verify readiness continues to pass

### First 1 hour

- check rolling error rate and latency
- validate queues/backlogs

### First 24 hours

- validate steady state
- track SLO (99.95% uptime target)

## Rollback Criteria

Rollback if any condition holds:

- error rate > 1% for 60 seconds
- p95 latency regressions exceed baseline tolerance
- repeated readiness failures

Rollback: `scripts/rollback-production.sh`
