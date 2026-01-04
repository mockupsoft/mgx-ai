# SBOM (Software Bill of Materials)

## Goal

Maintain an auditable inventory of third-party components.

## Generation

Use `scripts/security/dependency-audit.sh` to generate:

- `docs/security/SBOM.json` (machine-readable)
- `docs/security/vulnerability-report.md` (human-readable)

## Notes

For production builds, prefer a standardized SBOM format (CycloneDX/SPDX) produced during CI.
