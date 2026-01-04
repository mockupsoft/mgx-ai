# Production Deployment Checklist (Green First)

This checklist is executed for each production release.

## 1) Build

- [ ] Build Docker image with immutable version tag
- [ ] Generate changelog / release notes
- [ ] Verify SBOM generated (see `docs/security/SBOM.md`)

## 2) Deploy to Green

- [ ] Apply manifests to green namespace
- [ ] Validate config/secrets mounted
- [ ] Ensure DB migrations are backward compatible

## 3) Smoke Tests

- [ ] Run smoke suite against green
- [ ] Validate critical endpoints
- [ ] Validate background jobs

Reference: `tests/smoke-tests/production-validation.yaml`

## 4) Observability

- [ ] Logs flowing (structured)
- [ ] Metrics flowing
- [ ] Traces flowing
- [ ] Alerts enabled

## 5) Security

- [ ] SAST checks clean (Bandit)
- [ ] Dependency scan complete (pip-audit / safety)
- [ ] No critical vulnerabilities

## 6) Switch

- [ ] Switch traffic blue → green
- [ ] Confirm within < 1 second

## 7) Monitor

- [ ] Tight monitoring first 1 hour
- [ ] Monitor first 24 hours

See: `docs/monitoring-during-switch.md`
