# Threat Model (Phase 3A)

## Scope

- Public API endpoints (FastAPI)
- Background execution / tool sandbox
- Git/GitHub integrations
- Secret management
- Observability pipeline

## Assets

- secrets (API keys, tokens)
- repositories and generated artifacts
- workspace data isolation
- audit logs

## Entry Points

- HTTP API
- Webhooks
- WebSocket endpoints
- Outbound HTTP integrations (LLM providers, Git providers)

## Trust Boundaries

- client ↔ API
- API ↔ database
- API ↔ Redis
- API ↔ outbound providers

## Key Threats & Mitigations

### Broken access control

- Mitigation: enforce authenticated identity; enforce workspace boundary on all operations.

### SSRF

- Mitigation: validate outbound URLs; block internal networks; restrict schemes.

### Secret leakage

- Mitigation: do not log secrets; encrypt at rest; integrate detect-secrets.

### Supply chain

- Mitigation: dependency audits; SBOM generation; pinned versions for production.

## Open Items

- Production auth integration (token verification)
- mTLS/service-to-service policy (if deployed with service mesh)
