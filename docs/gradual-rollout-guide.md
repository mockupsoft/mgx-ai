# Gradual Rollout Guide (Feature Flags)

Feature flags enable controlled rollout and quick rollback without redeploying.

## Phase 1: 10% (24–48 hours)

- Canary release
- Monitor error rate and latency
- Expected: < 1% additional errors vs baseline

## Phase 2: 50% (24–48 hours)

- Expand to half of users
- Compare treatment vs control metrics
- Expected: performance parity

## Phase 3: 100%

- Enable for all users
- Monitor for 24 hours
- Keep fallback for 1 week
- Abort if error rate increases by > 2%

## Notes

- Rollout is **deterministic** per user/workspace.
- Prefer feature-flag rollback over redeploy when safe.
