# Runbook: High Task Error Rate

## Detection

**Alert**: `High task error rate` (> 5%)

Symptoms:
- Elevated 5xx responses
- Increased failed task runs
- DLQ growth

## Investigation

1. **Triage scope**
   - Is this limited to one endpoint, workspace, or provider?
   - Did it start after a deploy or config change?

2. **Check logs and traces**
   - Search for the top exception types (timeouts, auth errors, validation errors)
   - Confirm whether failures correlate with a single provider or dependency

3. **Check DLQ / retries**
   - Are tasks failing repeatedly due to a deterministic bug?
   - Is the retry policy too aggressive, increasing load?

4. **Classify likely root cause**
   - **Provider issue**: 5xx/429/timeouts from upstream
   - **Code bug**: new exception type, stack trace after deploy
   - **Resource issue**: CPU/memory pressure, connection pool exhaustion

## Response

1. **If provider-related**
   - Fail over to a healthy provider
   - Reduce concurrency and enable backoff

2. **If code-related**
   - Roll back the last deployment
   - Disable the feature flag that introduced the failure

3. **If resource-related**
   - Scale up/out (replicas, CPU/memory)
   - Identify and fix the bottleneck (DB pool, Redis, external API)

4. **Manual intervention**
   - Pause the queue if failures are causing cascading overload
   - Reprocess DLQ only after the incident is stabilized

## Post-mortem

- Create an incident document using `/docs/incident-postmortem-template.md`
- Record a timeline, impact, and contributing factors
- Add action items:
  - Better alerting or dashboards
  - Guardrails (rate limits, circuit breakers)
  - Test coverage / canary improvements
