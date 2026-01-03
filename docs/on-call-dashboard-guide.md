# On-Call Dashboard Guide

## Dashboard Location

- Dashboard JSON: `/monitoring/dashboards/on-call-dashboard.json`
- Alert rules: `/monitoring/alerts/on-call-alerts.yaml`

## How to Interpret Key Metrics

1. **System Health**
   - Uptime: sustained dips indicate restarts or outages
   - Error rate: watch for sustained > 5%
   - Latency (P99): watch for sustained > 5s
   - Queue depth: backlog indicates throughput issues

2. **Provider Status**
   - Success rate: identify provider-specific degradation
   - 429s: provider rate limiting
   - Failover status: whether routing has moved to a secondary provider

3. **Resources**
   - CPU/memory: saturation indicates scaling or leak needs
   - DB connections: pool saturation and slow queries
   - Cache hit rate: a drop may increase DB load

4. **Error Analysis**
   - Error by type/provider
   - DLQ size: indicates persistent failures or poison messages

5. **Performance**
   - P50/P95/P99 request latency
   - Throughput and query latency

## Common Alert Patterns

- **P0: Memory > 90%** → see runbook `memory-exhaustion.md`
- **P1: Provider 429** → see runbook `rate-limit-429.md`
- **P1: Error rate > 5%** → see runbook `task-failure.md`
- **P1: DB connections > 90%** → see runbook `db-connection-pool.md`

## Troubleshooting Links

See `/monitoring/dashboard-links.yaml` for quick navigation.
