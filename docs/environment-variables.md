# Environment Variables

This document describes key environment variables used by MGX-AI.

> Secrets must be supplied via a secret manager / Kubernetes Secret. Do **not** commit real values.

## Core

| Variable | Purpose | Default | Security |
|---|---|---:|---|
| `MGX_ENV` | Environment selector (`development`, `staging`, `production`) | `development` | Public |
| `LOG_LEVEL` | Logging verbosity | `INFO` | Public |
| `API_HOST` | Bind host | `127.0.0.1` | Public |
| `API_PORT` | Bind port | `8000` | Public |

## Database

| Variable | Purpose | Default | Security |
|---|---|---:|---|
| `DB_HOST` | PostgreSQL hostname | `localhost` | Public |
| `DB_PORT` | PostgreSQL port | `5432` | Public |
| `DB_NAME` | Database name | `mgx_agent` | Public |
| `DB_USER` | Database user | `postgres` | Secret |
| `DB_PASSWORD` | Database password | `postgres` | Secret |
| `DB_POOL_SIZE` | Connection pool size | `10` | Public |
| `DB_MAX_OVERFLOW` | Max overflow connections | `20` | Public |

## Cache

| Variable | Purpose | Default | Security |
|---|---|---:|---|
| `REDIS_URL` | Redis URL | unset | Public/Secret (depends on auth) |

## LLM Providers (Secrets)

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | OpenAI key |
| `ANTHROPIC_API_KEY` | Anthropic key |
| `MISTRAL_API_KEY` | Mistral key |
| `TOGETHER_API_KEY` | Together key |
| `OPENROUTER_API_KEY` | OpenRouter key |

## Feature Flags

| Variable | Purpose | Default |
|---|---|---:|
| `FEATURE_FLAGS_CONFIG_PATH` | Path to `feature_flags.yaml` | `config/feature_flags.yaml` |
| `FEATURE_FLAGS_CACHE_TTL_SECONDS` | Decision cache TTL | `60` |
| `FEATURE_FLAGS_CONFIG_RELOAD_TTL_SECONDS` | How often to check config changes | `30` |

## Observability

| Variable | Purpose |
|---|---|
| `OTEL_ENABLED` | Enable OpenTelemetry |
| `OTEL_SERVICE_NAME` | Service name |
| `OTEL_OTLP_ENDPOINT` | OTLP collector endpoint |

## Environment Files

- Dev: `/config/environments/dev.yaml`
- Staging: `/config/environments/staging.yaml`
- Prod: `/config/environments/prod.yaml`
