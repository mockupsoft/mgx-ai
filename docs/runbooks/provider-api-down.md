# Runbook: Provider API Down

## Detection

Signals:
- All requests to a provider failing (5xx/timeouts)
- Provider success rate drops to near 0%

## Response

1. **Fail over (immediately)**
   - Route requests to an alternative provider
   - Disable the failing provider via configuration/feature flag

2. **Escalation (within 5 minutes)**
   - Check provider status page
   - Contact provider support
   - Notify stakeholders in `#incidents` and update status page for P0

## Recovery

1. **Verify provider is stable**
   - Success rate recovered and latency is normal

2. **Gradual traffic re-routing**
   - Route 10% traffic back for 24–48 hours
   - Increase to 50% if stable
   - Return to 100% after validation

3. **Keep fallback enabled for 1 week**
   - Maintain the ability to switch back quickly
