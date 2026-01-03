# Environment Guide: Dev

## Purpose

Fast local iteration with minimal guardrails.

## Local Setup

- Use Docker Compose for Postgres/Redis
- Set `MGX_ENV=development` and `LOG_LEVEL=DEBUG`

## Debug Mode

- Increase logging verbosity
- Enable all feature flags for experimentation

## Resetting Dev Database

- Drop and recreate schema (see project database docs)

## Testing Feature Flags

- Edit `config/feature_flags.yaml`
- Use deterministic user IDs to validate rollout decisions
