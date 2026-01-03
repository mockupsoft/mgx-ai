# Runbook: DB Connection Pool Exhaustion

## Detection

**Alert**: `DB connection pool exhausted`

Symptoms:
- Increased 5xx responses from DB-related endpoints
- Errors such as `too many clients`, `pool timeout`, `connection refused`
- Latency spikes due to waiting for a connection

## Investigation

1. **Check pool utilization**
   - Current active connections vs pool size
   - Connection acquisition timeouts

2. **Find slow queries**
   - Identify slow query patterns (> 1s)
   - Check for missing indexes or N+1 query patterns

3. **Check for connection leaks**
   - Connections not returned to pool
   - Long-running transactions

## Response

1. **Immediate mitigation**
   - Scale application replicas to distribute pool pressure
   - Increase DB pool size (carefully) and validate DB max connections

2. **Reduce pressure**
   - Kill long-running queries
   - Enable query timeouts

3. **If leak suspected**
   - Restart the application to release leaked connections
   - Roll back recent changes that touched DB session handling

## Prevention

- Set sane pool configuration and enforce query timeouts
- Add connection leak detection
- Monitor pool saturation and slow queries
- Load test before rollout
