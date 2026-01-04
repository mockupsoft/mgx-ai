# CI/CD Security Notes

## Controls

- Pre-commit hooks:
  - Ruff + formatting
  - MyPy type checks
  - Bandit (SAST)
  - detect-secrets
  - safety / pip-audit checks

## Recommendations

- Protect main branch with required checks
- Require signed commits/tags for production releases
- Pin production dependencies (lockfile) and build with SBOM
