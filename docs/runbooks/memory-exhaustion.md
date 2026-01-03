# Runbook: Memory Exhaustion / OOM

## Detection

**Alerts**:
- `Memory > 90%`
- OOM killer events / container restarts

Symptoms:
- Sudden increase in latency
- Worker crashes/restarts
- Increased GC time

## Investigation

1. **Confirm memory pressure**
   - Node and pod/container memory usage
   - RSS vs cache/buffers

2. **Identify leak vs workload**
   - Did memory grow steadily (leak) or spike (large payload)?
   - Check recent deploys and feature flags

3. **Profile / inspect**
   - Use heap profiling if available
   - Check for unbounded caches, large in-memory artifacts, or retained prompts

## Response

1. **Stabilize service**
   - Restart pods to clear memory (short-term)
   - Scale out to distribute load

2. **Reduce memory usage**
   - Reduce concurrency (fewer simultaneous tasks)
   - Enable pruning for large artifacts and caches

3. **Increase resources (last resort)**
   - Increase memory requests/limits
   - Move to larger instance type

## Prevention

- Set memory requests/limits and enforce quotas
- Add leak detection to CI and regression tests
- Monitor memory trends and GC time
- Avoid unbounded caches; enforce TTL + max size
