# On-Call Guide (MGX-AI)

## Severity Levels and SLAs

- **P0 (Critical)**: Provider down, database unreachable, application down
  - **Response**: < 5 minutes
- **P1 (High)**: Error rate > 5%, severe performance degradation
  - **Response**: < 15 minutes
- **P2 (Medium)**: Minor features broken, non-critical degradation
  - **Response**: < 2 business hours

## Escalation Chain

1. Alert triggered → **On-call engineer (Level 1)**
2. Not resolved in **10 min** → Escalate to **Tech Lead (Level 2)**
3. Not resolved in **30 min** → Escalate to **CTO (Level 3)**
4. **P0 incidents** → CTO contacted immediately

## Incident Communication

- **Status page**: Update within **2 minutes** of a P0 incident
- **Slack `#incidents`**: Post with severity level and impact summary
- **Updates**: Every **15 minutes** during an active incident
- **Post-mortem**: Schedule within **24 hours**

## First 5 Minutes Checklist

1. Acknowledge the alert.
2. Confirm the incident is real (dashboards + logs).
3. Determine severity (P0/P1/P2).
4. Start an incident thread in `#incidents`.
5. Pick the relevant runbook in `/docs/runbooks/`.

## Runbooks

See [`/docs/runbooks/README.md`](./runbooks/README.md).
