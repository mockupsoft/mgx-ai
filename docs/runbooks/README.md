# Incident Response Runbooks

This directory contains incident response runbooks for MGX-AI.

## Runbook Index

- [Provider Rate Limiting (HTTP 429)](./rate-limit-429.md)
- [High Task Failure Rate](./task-failure.md)
- [Memory Exhaustion / OOM](./memory-exhaustion.md)
- [Provider API Down](./provider-api-down.md)
- [DB Connection Pool Exhaustion](./db-connection-pool.md)

## Usage

1. Start from the **Detection** section to confirm the alert is real.
2. Follow **Investigation** to narrow scope and identify the blast radius.
3. Execute **Response** steps in order of lowest-risk to highest-risk.
4. Capture findings and actions for the post-mortem.

## Common Links

- On-call guide: [`/docs/on-call-guide.md`](../on-call-guide.md)
- Dashboard guide: [`/docs/on-call-dashboard-guide.md`](../on-call-dashboard-guide.md)
- Post-mortem template: [`/docs/incident-postmortem-template.md`](../incident-postmortem-template.md)
