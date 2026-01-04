# OWASP Top 10 Security Hardening Audit (Phase 3A)

This document captures the current state and remediation actions mapped to OWASP Top 10.

> Note: This repository includes development defaults (e.g. local DB credentials). Production safety gates must enforce non-default credentials and secure configuration.

## A1: Broken Access Control

### Controls

- RBAC service: `backend/services/auth/rbac.py`
- Permission dependency helper: `require_permission(resource, action)`

### Gaps / Actions

- Enforce authentication/identity in production (do not rely on unauthenticated headers).
- Ensure workspace isolation by requiring `X-Workspace-ID` (or token-embedded workspace) on all endpoints.

### Tests

- `tests/security/test_access_control.py`

## A2: Cryptographic Failures

### Controls

- Secret encryption service supports:
  - Fernet (dev)
  - AWS KMS (prod)
  - Vault (prod)

File: `backend/services/secrets/encryption.py`

### Actions

- Ensure no hardcoded keys.
- Ensure production deployments use KMS/Vault or configured Fernet key.

### Tests

- `tests/security/test_cryptography.py`

## A3: Injection

### Controls

- SSRF-safe outbound URL validation utility: `backend/services/security/ssrf.py`

### Actions

- Apply SSRF guard to any outbound HTTP integrations.
- Ensure subprocess calls (if any) use argument lists (no shell=True).

### Tests

- `tests/security/test_injection.py`

## A4: Insecure Design

### Deliverable

- Threat model: `docs/security/threat-model.md`

## A5: Security Misconfiguration

### Controls

- Security headers middleware: `backend/middleware/security_headers.py`
- Production-only restrictive error CORS headers (avoid `Access-Control-Allow-Origin: *` in prod)

### Tests

- `tests/security/test_configuration.py`

## A6: Vulnerable and Outdated Components

### Controls

- Dependency audit scripts:
  - `scripts/security/dependency-audit.sh`
  - `scripts/security/dependency-scan.sh`

### Deliverables

- SBOM docs: `docs/security/SBOM.md`
- SBOM artifact: `docs/security/SBOM.json`
- Vulnerability report template: `docs/security/vulnerability-report.md`

## A7: Identification & Authentication Failures

### Controls

- RBAC permission enforcement available via `require_permission`.

### Actions

- Production deployments must enforce authenticated identity (token-based).

### Tests

- `tests/security/test_auth.py`

## A8: Software & Data Integrity Failures

### Controls

- CI quality gates + pre-commit checks

### Deliverable

- CI/CD security notes: `docs/security/ci-cd-security.md`

## A9: Logging & Monitoring Failures

### Controls

- Structured logging middleware with correlation IDs
- Security event logger: `backend/services/security_logging.py`

## A10: SSRF

### Controls

- Outbound URL validation rejects:
  - localhost
  - RFC1918 / link-local / metadata IPs
  - non-http(s) schemes

File: `backend/services/security/ssrf.py`

### Tests

- `tests/security/test_ssrf.py`
