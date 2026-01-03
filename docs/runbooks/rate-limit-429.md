# Runbook: Provider Rate Limiting (HTTP 429)

## Detection

**Alert**: `Provider 429 rate limit`

Typical signals:
- Spike in HTTP 429 responses from the LLM provider
- Increased retries / backoff time
- Queue depth increasing while throughput decreases

## Investigation

1. **Confirm the spike**
   - Check provider request rate and 429 count
   - Check error logs for `429`, `rate_limit`, `Too Many Requests`

2. **Check queue depth / backlog**
   - Is work accumulating faster than workers can complete?
   - Is there a sudden increase in inbound tasks or retries?

3. **Check provider budget / quotas**
   - Daily/monthly quota exhausted?
   - Per-minute or per-tenant limit hit?

4. **Check workload patterns**
   - Recent deploy or feature flag change increasing call volume?
   - Large batch job or automation started?

## Response

1. **Reduce submission rate (lowest risk)**
   - Temporarily slow task submission / concurrency
   - Increase backoff on retries

2. **Fail over to an alternative provider**
   - Switch routing strategy to a secondary provider
   - If using feature flags, disable the new provider rollout and force stable provider

3. **Stabilize the queue**
   - Pause non-critical tasks
   - Drain dead-letter queue (DLQ) after root cause is addressed

4. **Communicate**
   - For P1/P0 incidents, update `#incidents` and status page per the on-call guide

## Prevention

- Implement a rate-limiting queue / token bucket per provider
- Add cost + quota monitoring (budget, requests/min, 429 rate)
- Provider-aware load shedding (reject low-priority requests)
- Automatic failover on sustained 429s (circuit breaker)
- Validate rollout changes via gradual rollout (10% → 50% → 100%)
