# Local Development Setup

## Prerequisites

- Python environment for the backend
- Docker + Docker Compose for local Postgres/Redis

## .env Setup

1. Copy the example file:

```bash
cp .env.example .env
```

2. Set provider keys (use sandbox keys only).

## Start Local Dependencies

```bash
docker compose up -d postgres redis
```

## Run the API (Dev Environment)

- Set environment variables:

```bash
export MGX_ENV=development
export LOG_LEVEL=DEBUG
export FEATURE_FLAGS_CONFIG_PATH=config/feature_flags.yaml
```

- Start the server (see project README for the exact command).

## Overriding Variables

- Use `.env` for local dev.
- In Kubernetes, use ConfigMaps + Secrets.

## Common Issues

- **DB connection errors**: verify Postgres is running and `DB_HOST` matches the docker compose service name.
- **Redis not configured**: `REDIS_URL` can be left unset; the service should degrade gracefully.
