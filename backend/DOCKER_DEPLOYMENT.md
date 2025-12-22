# Docker Deployment Guide - MGX Agent Self-Hosted

Complete guide for deploying MGX Agent with Docker Compose, including PostgreSQL, Redis, MinIO (S3-compatible storage), and optional Kafka.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Prerequisites](#prerequisites)
3. [Architecture Overview](#architecture-overview)
4. [Initial Setup](#initial-setup)
5. [Services Overview](#services-overview)
6. [Data Persistence & Backups](#data-persistence--backups)
7. [Database Migrations](#database-migrations)
8. [Monitoring & Logs](#monitoring--logs)
9. [Troubleshooting](#troubleshooting)
10. [Security Best Practices](#security-best-practices)
11. [Performance Tuning](#performance-tuning)
12. [External Integrations](#external-integrations)
13. [Scaling & High Availability](#scaling--high-availability)

---

## Quick Start

### 1. Clone and Configure

```bash
git clone https://github.com/your-org/mgx-agent.git
cd mgx-agent
cp .env.example .env
```

### 2. Generate Secure Secrets (Production)

```bash
# Generate secure secrets
JWT_SECRET=$(openssl rand -hex 32)
API_KEY=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -hex 16)
S3_SECRET=$(openssl rand -base64 32)

# Update .env file with generated secrets
sed -i "s/change-me-in-production-use-openssl-rand-hex-32/$JWT_SECRET/g" .env
sed -i "s/S3_SECRET_ACCESS_KEY=minioadmin/S3_SECRET_ACCESS_KEY=$S3_SECRET/g" .env
# ... manually update DB_PASSWORD and other values
```

Or manually edit `.env`:
```bash
nano .env
```

### 3. Start Services

```bash
# Build and start all services in background
docker compose up -d --build

# Wait for services to become healthy
docker compose ps

# Expected output (all healthy):
# NAME                 IMAGE               STATUS
# mgx-postgres         postgres:16-alpine  Up 2m (healthy)
# mgx-redis            redis:7-alpine      Up 2m (healthy)
# mgx-minio            minio:latest        Up 2m (healthy)
# mgx-minio-init       minio/mc:latest     Exited 0
# mgx-migrate          mgx-agent:latest    Exited 0
# mgx-ai               mgx-agent:latest    Up 1m (healthy)
```

### 4. Verify API Health

```bash
# Check API health endpoint
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "timestamp": "2024-01-01T12:00:00Z"}

# View API documentation
# Open http://localhost:8000/docs in browser
```

### 5. Access MinIO Console (Optional)

```bash
# MinIO web console
# Open http://localhost:9001 in browser
# Username: minioadmin
# Password: minioadmin (from .env S3_SECRET_ACCESS_KEY)
```

---

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU Cores | 2 | 4+ |
| RAM | 4 GB | 8+ GB |
| Disk Space | 20 GB | 50+ GB SSD |
| Docker Version | 20.10 | 24.0+ |
| Docker Compose | v2.0 | v2.20+ |
| OS | Linux/Mac | Linux (recommended) |

### Install Docker & Docker Compose

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

**macOS:**
```bash
# Install Docker Desktop from https://www.docker.com/products/docker-desktop
# Includes Docker and Docker Compose v2
```

**Verify Installation:**
```bash
docker --version      # Docker version 20.10+
docker compose version  # Docker Compose version v2.0+
```

### Required Ports

| Port | Service | Purpose |
|------|---------|---------|
| 8000 | FastAPI | API HTTP |
| 5432 | PostgreSQL | Database |
| 6379 | Redis | Cache |
| 9000 | MinIO | S3 API |
| 9001 | MinIO | Web Console |
| 9092 | Kafka | Event Stream (optional) |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Network (mgx-net)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │              │    │              │    │              │       │
│  │  mgx-ai      │◄───┤  postgres    │    │  redis       │       │
│  │  (FastAPI)   │    │  (DB)        │    │  (Cache)     │       │
│  │              │    │              │    │              │       │
│  │ Port 8000    │    │ Port 5432    │    │ Port 6379    │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│        ▲                                                          │
│        │                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │              │    │              │    │              │       │
│  │  minio       │    │ minio-init   │    │  mgx-migrate │       │
│  │  (S3 Compat) │◄───┤  (Bucket     │    │  (Alembic)   │       │
│  │              │    │   Init)      │    │              │       │
│  │ Port 9000/01 │    │              │    │              │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐                           │
│  │              │    │              │ (Optional Profile)         │
│  │  kafka       │    │  zookeeper   │                           │
│  │  (Events)    │◄───┤ (Kafka Coord)│                           │
│  │              │    │              │                           │
│  │ Port 9092    │    │ Port 2181    │                           │
│  └──────────────┘    └──────────────┘                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

Data Flow:
1. Client requests → mgx-ai (FastAPI)
2. mgx-ai queries → postgres (database)
3. mgx-ai caches → redis (cache)
4. mgx-ai stores → minio (S3 artifacts)
5. mgx-ai emits → kafka (optional events)
```

### Service Dependencies

```
minio ──┐
        ├─► minio-init (bucket creation)
postgres ──┐
           ├─► mgx-migrate (run migrations)
           │   │
           │   ├─► mgx-ai (API)
           │
redis ─────┘
```

---

## Initial Setup

### 1. Prepare Configuration

```bash
# Copy example environment
cp .env.example .env

# Edit for your deployment
# Critical settings to change:
# - JWT_SECRET (use: openssl rand -hex 32)
# - API_KEY (use: openssl rand -hex 32)
# - DB_PASSWORD (use: openssl rand -hex 16)
# - S3_ACCESS_KEY_ID & S3_SECRET_ACCESS_KEY
# - MGX_BASE_URL (change from localhost if needed)
```

### 2. Build Docker Image

```bash
# Build the MGX Agent image
docker compose build

# Force rebuild if needed
docker compose build --no-cache
```

### 3. Create .env for your environment

```bash
# Development (auto-applied if docker-compose.override.yml exists)
# Sets: MGX_ENV=development, MGX_LOG_LEVEL=DEBUG

# Production (specify explicitly)
docker compose -f docker-compose.yml up -d

# Or unset override:
MGX_ENV=production docker compose --no-project-directory up -d
```

### 4. Start Services

```bash
# Start all services in background
docker compose up -d --build

# Follow startup logs
docker compose logs -f mgx-ai

# Wait for healthy status
docker compose ps
```

---

## Services Overview

### PostgreSQL 16 (postgres)

**Purpose:** Primary relational database for all application data

**Configuration:**
- Image: `postgres:16-alpine` (lightweight)
- Port: 5432 (internal only)
- Volume: `pg_data` (persistent)
- Health Check: `pg_isready`

**Initialization:**
- Executes `init-db.sql` on first run
- Creates tables: workspaces, projects, repositories, tasks, runs, metrics, artifacts
- Idempotent (safe to re-run)

**Performance Settings:**
- `shared_buffers=256MB` (1/4 of RAM)
- `effective_cache_size=1GB`
- `max_connections=200`

**Connect directly (development):**
```bash
docker compose exec postgres psql -U mgx -d mgx
```

### Redis 7 (redis)

**Purpose:** In-memory cache and distributed session store

**Configuration:**
- Image: `redis:7-alpine` (lightweight)
- Port: 6379 (internal only)
- Volume: `redis_data` (persistent AOF)
- Health Check: `redis-cli ping`
- Persistence: AOF enabled (`--appendonly yes`)

**Features:**
- LRU eviction for automatic cache cleanup
- AOF durability for data recovery
- Performance optimized: `appendfsync everysec` (balance)

**Monitoring:**
```bash
# Check Redis stats
docker compose exec redis redis-cli info stats

# Monitor commands
docker compose exec redis redis-cli monitor

# Check memory usage
docker compose exec redis redis-cli info memory
```

### MinIO (minio)

**Purpose:** S3-compatible object storage for artifacts

**Configuration:**
- Image: `minio/latest` (latest stable)
- Ports: 9000 (API), 9001 (console)
- Volume: `minio_data` (persistent)
- Health Check: `curl minio/health/live`

**Console Access:**
- URL: http://localhost:9001
- Username: minioadmin
- Password: From `S3_SECRET_ACCESS_KEY` in `.env`

**Bucket Initialization:**
- Service: `minio-init` (runs once after minio is healthy)
- Creates bucket: `mgx-artifacts` (configurable)
- Enables versioning for data recovery
- Idempotent: Safe to re-run

### MinIO Init (minio-init)

**Purpose:** One-time bucket creation and versioning

**Execution:**
- Depends: minio service healthy
- Runs: `minio/mc` (MinIO client)
- Commands:
  1. Connect to MinIO
  2. Create bucket (ignore if exists)
  3. Enable versioning
  4. Exit (doesn't keep running)

**Inspect Results:**
```bash
# View service status (exits after completion)
docker compose ps | grep minio-init

# View logs if creation failed
docker compose logs minio-init
```

### Database Migrations (mgx-migrate)

**Purpose:** Run Alembic migrations before API starts

**Execution:**
- Depends: postgres service healthy
- Runs: `alembic upgrade head`
- Command: `bash -c "alembic upgrade head && echo 'Migrations completed'"`
- Exit: After migrations complete (doesn't keep running)

**Check Status:**
```bash
# View migration logs
docker compose logs mgx-migrate

# Expected success message:
# INFO [alembic.runtime.migration] Context impl PostgresqlImpl.
# INFO [alembic.runtime.migration] Will assume transactional DDL.
# INFO [alembic.runtime.migration] Running upgrade (initial) -> (version), (version) -> ...
```

**Manually Run Migrations:**
```bash
# If you need to re-run migrations
docker compose run --rm mgx-migrate alembic upgrade head

# Or in running container
docker compose exec mgx-ai alembic upgrade head
```

### FastAPI Application (mgx-ai)

**Purpose:** Main application server

**Configuration:**
- Image: `mgx-agent:latest` (built from ./Dockerfile)
- Port: 8000
- Workers: `MGX_WORKERS` (default: 4)
- Health Check: GET `/health` endpoint

**Startup Process:**
1. Waits for: postgres, redis, minio healthy
2. Waits for: mgx-migrate completed
3. Runs: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
4. WebSocket support via uvicorn

**API Endpoints:**
- Docs: http://localhost:8000/docs (Swagger UI)
- ReDoc: http://localhost:8000/redoc
- OpenAPI: http://localhost:8000/openapi.json
- Health: http://localhost:8000/health

**View Logs:**
```bash
# Recent logs
docker compose logs mgx-ai

# Follow logs in real-time
docker compose logs -f mgx-ai

# Last 100 lines with timestamps
docker compose logs --tail 100 --timestamps mgx-ai
```

### Apache Kafka (kafka) - Optional

**Purpose:** Distributed event streaming (optional, enable with profile)

**Start with Kafka:**
```bash
docker compose --profile kafka up -d
```

**Configuration:**
- Image: `confluentinc/cp-kafka:7.5.0`
- Port: 9092 (external), 29092 (internal)
- Volume: `kafka_data` (persistent)
- Broker ID: 1 (single broker for dev/small deployments)

**Features:**
- Auto-create topics
- 24-hour retention
- 1GB size-based retention

**Monitor Kafka:**
```bash
# Check broker status
docker compose exec kafka kafka-broker-api-versions.sh --bootstrap-server kafka:9092

# List topics
docker compose exec kafka kafka-topics.sh --bootstrap-server kafka:9092 --list

# Create topic
docker compose exec kafka kafka-topics.sh --bootstrap-server kafka:9092 \
  --create --topic mgx-events --partitions 1 --replication-factor 1
```

### Zookeeper (zookeeper) - Optional

**Purpose:** Kafka cluster coordination (required for Kafka)

**Configuration:**
- Image: `confluentinc/cp-zookeeper:7.5.0`
- Port: 2181
- Volumes: `zookeeper_data`, `zookeeper_logs`

---

## Data Persistence & Backups

### Volume Structure

| Volume | Service | Path | Purpose |
|--------|---------|------|---------|
| `pg_data` | postgres | `/var/lib/postgresql/data` | Database files |
| `redis_data` | redis | `/data` | Redis AOF persistence |
| `minio_data` | minio | `/data` | Object storage |
| `kafka_data` | kafka | `/var/lib/kafka/data` | Event streams (optional) |
| `zookeeper_data` | zookeeper | `/var/lib/zookeeper/data` | Zookeeper state (optional) |

### List Volumes

```bash
# Show all MGX volumes
docker volume ls | grep mgx

# Inspect specific volume
docker volume inspect project_pg_data

# Volume location on host
docker volume inspect --format '{{.Mountpoint}}' project_pg_data
```

### PostgreSQL Backups

#### Full Database Dump

```bash
# Backup to SQL file
docker compose exec -T postgres pg_dump -U mgx -d mgx > backup-$(date +%Y%m%d-%H%M%S).sql

# Backup to compressed archive (recommended)
docker compose exec -T postgres pg_dump -U mgx -d mgx | gzip > backup-$(date +%Y%m%d-%H%M%S).sql.gz

# Size estimate
docker compose exec postgres du -sh /var/lib/postgresql/data
```

#### Restore from Backup

```bash
# From uncompressed dump
docker compose exec -T postgres psql -U mgx -d mgx < backup-20240101-120000.sql

# From compressed backup
gunzip < backup-20240101-120000.sql.gz | \
  docker compose exec -T postgres psql -U mgx -d mgx

# Verify restoration
docker compose exec postgres psql -U mgx -d mgx -c "SELECT COUNT(*) FROM workspaces;"
```

#### Scheduled Backups (Cron)

```bash
#!/bin/bash
# /usr/local/bin/mgx-backup.sh

BACKUP_DIR="/backups/mgx"
RETENTION_DAYS=30

mkdir -p $BACKUP_DIR

# Create backup
BACKUP_FILE="$BACKUP_DIR/mgx-db-$(date +%Y%m%d-%H%M%S).sql.gz"
docker compose -f /opt/mgx/docker-compose.yml exec -T postgres \
  pg_dump -U mgx -d mgx | gzip > $BACKUP_FILE

# Remove old backups (keep last 30 days)
find $BACKUP_DIR -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup created: $BACKUP_FILE"
```

Add to crontab (daily at 2 AM):
```bash
0 2 * * * /usr/local/bin/mgx-backup.sh >> /var/log/mgx-backup.log 2>&1
```

### MinIO Backups

#### Using mc (MinIO Client)

```bash
# Mirror entire bucket to local directory
docker run --rm -v /backups/minio:/export minio/mc:latest \
  sh -c "mc alias set myminio http://minio:9000 minioadmin minioadmin && \
         mc mirror myminio/mgx-artifacts /export"

# Restore from backup
docker run --rm -v /backups/minio:/export minio/mc:latest \
  sh -c "mc alias set myminio http://minio:9000 minioadmin minioadmin && \
         mc mirror /export myminio/mgx-artifacts"
```

#### Using S3 CLI

```bash
# If using AWS S3 as backup target
aws s3 sync s3://minio-local/mgx-artifacts s3://backup-bucket/mgx-artifacts/

# Or use AWS DataSync for automated backups
```

### Disk Space Management

```bash
# Check volume sizes
docker system df

# Prune unused data
docker system prune -a

# Check container logs size
docker exec mgx-ai du -sh /app/logs

# Rotate logs (in docker-compose.yml)
# logging:
#   driver: "json-file"
#   options:
#     max-size: "100m"
#     max-file: "10"
```

---

## Database Migrations

### Understanding Alembic

Alembic is the SQL Alchemy migration tool used for schema changes.

**Migration Files:**
```
backend/migrations/
├── env.py           # Alembic environment configuration
├── script.py.mako   # Migration template
└── versions/        # Migration files
    ├── 001_initial.py
    ├── 002_add_git_metadata.py
    └── ...
```

### Running Migrations

#### Automatic (default)

Migrations run automatically when services start:
1. `mgx-migrate` service checks for pending migrations
2. Runs `alembic upgrade head`
3. Exits after completion
4. `mgx-ai` waits for `mgx-migrate` to complete

#### Manual (if needed)

```bash
# Apply all pending migrations
docker compose exec mgx-ai alembic upgrade head

# Apply specific migration
docker compose exec mgx-ai alembic upgrade 002_add_git_metadata

# Downgrade to previous version
docker compose exec mgx-ai alembic downgrade -1

# View migration history
docker compose exec mgx-ai alembic current
docker compose exec mgx-ai alembic history
```

### Creating New Migrations

```bash
# Generate new migration (detects schema changes)
docker compose exec mgx-ai alembic revision --autogenerate -m "description of changes"

# Edit generated migration file: backend/migrations/versions/XXX_description.py

# Apply new migration
docker compose exec mgx-ai alembic upgrade head

# Test with rollback
docker compose exec mgx-ai alembic downgrade -1
docker compose exec mgx-ai alembic upgrade head
```

### Troubleshooting Migrations

#### Migration fails to apply

```bash
# Check error logs
docker compose logs mgx-migrate

# Check database state
docker compose exec postgres psql -U mgx -d mgx -c \
  "SELECT * FROM alembic_version;"

# Mark migration as complete (use with caution!)
docker compose exec postgres psql -U mgx -d mgx -c \
  "INSERT INTO alembic_version (version_num) VALUES ('migration_id');"
```

#### Database schema out of sync

```bash
# Check current version
docker compose exec mgx-ai alembic current

# View pending migrations
docker compose exec mgx-ai alembic upgrade head --sql

# Downgrade all (dangerous!)
docker compose exec mgx-ai alembic downgrade base

# Re-apply all
docker compose exec mgx-ai alembic upgrade head
```

---

## Monitoring & Logs

### Service Status

```bash
# View all services and health status
docker compose ps

# Expected healthy output:
# NAME               STATUS
# mgx-postgres       Up 5 minutes (healthy)
# mgx-redis          Up 5 minutes (healthy)
# mgx-minio          Up 5 minutes (healthy)
# mgx-ai             Up 3 minutes (healthy)

# Watch status updates
watch docker compose ps

# Get detailed stats
docker compose stats
```

### View Logs

```bash
# View logs for specific service
docker compose logs mgx-ai
docker compose logs postgres
docker compose logs redis

# Follow logs in real-time
docker compose logs -f mgx-ai

# View last N lines
docker compose logs --tail 50 mgx-ai

# With timestamps
docker compose logs --timestamps mgx-ai

# All services
docker compose logs

# Filter by time
docker compose logs --since 2024-01-01T12:00:00 mgx-ai
docker compose logs --until 2024-01-01T13:00:00 mgx-ai
```

### API Health Check

```bash
# Health endpoint
curl http://localhost:8000/health

# Response (healthy):
# {
#   "status": "healthy",
#   "timestamp": "2024-01-01T12:00:00Z",
#   "version": "0.1.0"
# }

# Root endpoint
curl http://localhost:8000/

# API documentation
curl http://localhost:8000/openapi.json
```

### Database Health

```bash
# Check connection
docker compose exec postgres psql -U mgx -d mgx -c "SELECT 1"

# View database size
docker compose exec postgres psql -U mgx -d mgx -c \
  "SELECT pg_size_pretty(pg_database_size('mgx'))"

# Check table sizes
docker compose exec postgres psql -U mgx -d mgx -c \
  "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) \
   FROM pg_tables ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC"

# View active connections
docker compose exec postgres psql -U mgx -d mgx -c \
  "SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname"
```

### Resource Monitoring

```bash
# Memory, CPU, network usage
docker compose stats

# Disk usage per volume
docker volume ls | awk '{print $2}' | xargs -I {} docker volume inspect {} \
  --format '{{.Name}}: {{.Mountpoint}}'

# Container resource limits (if set)
docker inspect mgx-ai | grep -A 20 "HostConfig"
```

### Application Metrics

```bash
# View recent API requests (from logs)
docker compose logs mgx-ai | grep "GET\|POST\|PUT\|DELETE"

# Track error rates
docker compose logs mgx-ai | grep ERROR | wc -l

# Monitor task execution
docker compose logs mgx-ai | grep "task_run\|status"
```

---

## Troubleshooting

### Common Issues and Solutions

#### ❌ "API not healthy" / Port 8000 not responding

**Symptoms:**
```bash
curl http://localhost:8000/health
# curl: (7) Failed to connect
# OR
# HTTP 503 Service Unavailable
```

**Diagnosis:**
```bash
# Check service status
docker compose ps mgx-ai

# View logs
docker compose logs mgx-ai

# Check port is exposed
docker compose port mgx-ai 8000
```

**Solutions:**

1. **Service not started:**
   ```bash
   # Restart service
   docker compose restart mgx-ai
   
   # Check dependencies
   docker compose ps
   ```

2. **Database not healthy:**
   ```bash
   # Check PostgreSQL
   docker compose logs postgres
   docker compose ps postgres
   
   # Reconnect if needed
   docker compose restart postgres
   ```

3. **Check dependencies:**
   ```bash
   # Verify all required services are healthy
   docker compose ps
   
   # All should show "Up X minutes (healthy)"
   # If not, troubleshoot that service
   ```

---

#### ❌ Database connection errors

**Symptoms:**
```
FATAL: database "mgx" does not exist
FATAL: role "mgx" does not exist
```

**Diagnosis:**
```bash
# Check PostgreSQL logs
docker compose logs postgres

# Check if initialization ran
docker compose exec postgres psql -U postgres -c "\\l"
```

**Solutions:**

1. **Database not initialized:**
   ```bash
   # Remove volume and restart
   docker compose down -v postgres
   docker compose up -d postgres
   
   # Wait for initialization
   docker compose ps postgres  # Watch for (healthy)
   ```

2. **Check init-db.sql exists:**
   ```bash
   ls -la init-db.sql
   
   # Should be readable
   head -20 init-db.sql
   ```

3. **Manual database creation:**
   ```bash
   docker compose exec postgres psql -U postgres -c \
     "CREATE USER mgx WITH PASSWORD 'mgx' CREATEDB;"
   
   docker compose exec postgres psql -U postgres -c \
     "CREATE DATABASE mgx OWNER mgx;"
   
   # Re-run migrations
   docker compose restart mgx-migrate
   ```

---

#### ❌ Migration failures

**Symptoms:**
```bash
docker compose logs mgx-migrate
# ERROR: Tables already exist
# ERROR: Invalid migration
# ERROR: Rollback failed
```

**Diagnosis:**
```bash
# Check migration status
docker compose exec postgres psql -U mgx -d mgx -c \
  "SELECT * FROM alembic_version;"

# View pending migrations
docker compose exec mgx-ai alembic current
docker compose exec mgx-ai alembic heads
```

**Solutions:**

1. **Tables already exist from init-db.sql:**
   ```bash
   # Check if alembic_version exists
   docker compose exec postgres psql -U mgx -d mgx -c \
     "SELECT * FROM alembic_version;"
   
   # If empty, mark initial as applied
   docker compose exec postgres psql -U mgx -d mgx -c \
     "INSERT INTO alembic_version (version_num) VALUES ('initial');"
   ```

2. **Invalid SQL in migration:**
   ```bash
   # Check migration file syntax
   cat backend/migrations/versions/XXX_description.py
   
   # Check for errors
   docker compose exec mgx-ai python -m py_compile \
     backend/migrations/versions/XXX_description.py
   ```

3. **Downgrade and retry:**
   ```bash
   docker compose exec mgx-ai alembic downgrade -1
   docker compose exec mgx-ai alembic upgrade head
   ```

---

#### ❌ MinIO bucket not created

**Symptoms:**
```bash
docker compose ps minio-init
# Exited with error code 1

# S3 operations fail in application
```

**Diagnosis:**
```bash
# Check minio-init logs
docker compose logs minio-init

# Check MinIO is healthy
docker compose ps minio

# Manually check bucket
docker compose exec minio mc ls myminio/
```

**Solutions:**

1. **MinIO endpoint not accessible:**
   ```bash
   # Test connectivity from init container
   docker compose exec minio-init curl http://minio:9000/minio/health/live
   
   # If fails, restart MinIO
   docker compose restart minio
   docker compose up -d minio-init
   ```

2. **Credentials incorrect:**
   ```bash
   # Verify in .env
   grep "S3_" .env
   
   # Restart minio-init with correct creds
   docker compose restart minio-init
   ```

3. **Bucket already exists:**
   ```bash
   # Check existing buckets
   docker compose exec minio mc ls myminio/
   
   # If exists, mark init as complete
   # minio-init uses --ignore-existing flag, should be OK
   ```

4. **Manual bucket creation:**
   ```bash
   docker compose exec minio mc mb myminio/mgx-artifacts
   docker compose exec minio mc version enable myminio/mgx-artifacts
   ```

---

#### ❌ Permission/Disk errors

**Symptoms:**
```
permission denied: /var/lib/postgresql/data
disk quota exceeded
no space left on device
```

**Diagnosis:**
```bash
# Check volume permissions
docker volume inspect project_pg_data | grep Mountpoint
ls -la /var/lib/docker/volumes/project_pg_data/_data/

# Check disk usage
docker system df
df -h

# Check container permissions
docker compose exec postgres id
docker compose exec postgres ls -la /var/lib/postgresql/data
```

**Solutions:**

1. **Fix volume permissions:**
   ```bash
   # Find volume path
   VOLUME_PATH=$(docker volume inspect --format '{{.Mountpoint}}' project_pg_data)
   
   # Fix permissions
   sudo chown 999:999 $VOLUME_PATH
   sudo chmod 700 $VOLUME_PATH
   
   # Restart service
   docker compose restart postgres
   ```

2. **Free disk space:**
   ```bash
   # Remove old images
   docker image prune -a
   
   # Remove stopped containers
   docker container prune
   
   # Remove unused volumes
   docker volume prune
   
   # Check what's using space
   du -sh /var/lib/docker
   ```

3. **Increase disk allocation:**
   ```bash
   # Docker Desktop: Settings > Resources > Disk image size
   # Linux: Extend LVM or add more storage
   ```

---

#### ❌ High CPU/Memory usage

**Symptoms:**
```bash
docker compose stats
# mgx-ai: CPU 80%, MEM 3.5GB / 4GB
```

**Diagnosis:**
```bash
# View resource limits
docker inspect mgx-ai | grep -A 20 "HostConfig"

# Monitor in real-time
docker stats --no-stream mgx-ai

# Check for memory leaks
docker compose logs mgx-ai | grep -i "memory\|gc"
```

**Solutions:**

1. **Reduce worker count:**
   ```bash
   # Edit .env
   MGX_WORKERS=2

   # Restart
   docker compose restart mgx-ai
   ```

2. **Reduce cache size:**
   ```bash
   # Edit .env
   MGX_CACHE_MAX_ENTRIES=1000
   MGX_CACHE_TTL_SECONDS=1800

   # Restart
   docker compose restart mgx-ai
   ```

3. **Set resource limits:**
   ```yaml
   # In docker-compose.yml
   mgx-ai:
     deploy:
       resources:
         limits:
           cpus: '2'
           memory: 2G
         reservations:
           cpus: '1'
           memory: 1G
   ```

---

#### ❌ Redis connection refused

**Symptoms:**
```
redis.exceptions.ConnectionError: Error 111 connecting to redis:6379
REDIS_URL not set or invalid
```

**Diagnosis:**
```bash
# Check Redis status
docker compose ps redis

# Test connectivity
docker compose exec mgx-ai redis-cli -h redis ping

# Check configuration
grep REDIS .env
```

**Solutions:**

1. **Start Redis:**
   ```bash
   docker compose up -d redis
   docker compose ps redis  # Wait for (healthy)
   ```

2. **Verify REDIS_URL:**
   ```bash
   # Should be redis://redis:6379/0 (or your custom port)
   grep REDIS_URL .env
   
   # Restart services
   docker compose restart mgx-ai
   ```

3. **Clear Redis and restart:**
   ```bash
   docker compose down -v redis
   docker compose up -d redis
   ```

---

### Debugging Checklist

Use this checklist when troubleshooting:

- [ ] All services healthy: `docker compose ps`
- [ ] No error logs: `docker compose logs | grep -i error`
- [ ] Ports accessible: `docker compose port` for each service
- [ ] Network reachable: `docker network inspect project_mgx-net`
- [ ] Volumes mounted: `docker volume ls | grep project`
- [ ] .env file loaded: `docker compose config | head -50`
- [ ] Dependencies met: Check `depends_on` for each service
- [ ] No port conflicts: `netstat -tlnp | grep 8000`
- [ ] Sufficient resources: `docker system df`
- [ ] Logs reviewed: `docker compose logs -f <service>`

---

## Security Best Practices

### 1. Change Default Secrets

**❌ Never leave default values in production:**

```bash
# INSECURE - DO NOT USE IN PRODUCTION
JWT_SECRET=change-me-in-production
S3_SECRET_ACCESS_KEY=minioadmin
DB_PASSWORD=mgx
```

**✅ Generate strong, random secrets:**

```bash
# Generate 32-character hex string
JWT_SECRET=$(openssl rand -hex 32)

# Generate base64 string
S3_SECRET=$(openssl rand -base64 32)

# Generate 16-character hex string
DB_PASSWORD=$(openssl rand -hex 16)

# Update .env file
sed -i "s/change-me-in-production-use-openssl-rand-hex-32/$JWT_SECRET/" .env
sed -i "s/S3_SECRET_ACCESS_KEY=minioadmin/S3_SECRET_ACCESS_KEY=$S3_SECRET/" .env
```

### 2. Use Environment Secrets

**Development:**
```bash
# Plain .env file is OK for local development
cp .env.example .env
```

**Production:**
```bash
# Use Docker secrets (Swarm mode)
echo "my-jwt-secret-value" | docker secret create jwt_secret -

# Or use Docker compose secrets syntax
docker compose -f docker-compose.prod.yml up

# In docker-compose.prod.yml:
# services:
#   mgx-ai:
#     secrets:
#       - jwt_secret
# secrets:
#   jwt_secret:
#     external: true
```

### 3. Implement Reverse Proxy (TLS)

**Nginx with Let's Encrypt:**

```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

server {
    listen 80;
    server_name api.example.com;
    return 301 https://$server_name$request_uri;
}
```

### 4. Restrict Port Access

```bash
# Close unnecessary ports from public internet
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 80/tcp  # HTTP (nginx)
sudo ufw allow 443/tcp # HTTPS (nginx)

# Database access only from internal network
# MinIO console only from trusted IPs
# Redis only from containers
```

### 5. Regular Updates

```bash
# Update base images monthly
docker compose pull
docker compose up -d

# Update dependencies
# Rebuild with latest Python packages in next build
docker compose build --no-cache

# Monitor security advisories
# Set up Dependabot notifications on GitHub
```

### 6. Audit Access

```bash
# Enable PostgreSQL logging
# Add to docker-compose.yml environment:
# POSTGRES_INITDB_ARGS: "-c log_statement=all"

# Monitor authentication
docker compose logs postgres | grep "authentication"

# Review API access logs
docker compose logs mgx-ai | grep "GET\|POST\|DELETE"
```

### 7. Backup Security

```bash
# Encrypt backups
docker compose exec -T postgres pg_dump -U mgx -d mgx | \
  openssl enc -aes-256-cbc -salt -in backup.sql.enc

# Store off-site
# Consider: AWS S3 with encryption, Azure Blob, Google Cloud Storage

# Test restore procedure monthly
```

---

## Performance Tuning

### 1. FastAPI Workers

```bash
# .env
# CPU cores - 1 = optimal workers
# 4 cores → 3 workers
# 8 cores → 7 workers
MGX_WORKERS=4
```

### 2. Database Connection Pool

```bash
# .env
# Pool size per worker
# workers × 2 = adequate for most uses
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
```

### 3. PostgreSQL Performance

```sql
-- Adjust in docker-compose.yml POSTGRES_INITDB_ARGS:
-c shared_buffers=512MB         # For 8GB RAM
-c effective_cache_size=2GB     # 1/4 of total RAM
-c work_mem=32MB                # Memory per operation
-c maintenance_work_mem=256MB   # For backups/index

-- Check current settings
docker compose exec postgres psql -U mgx -d mgx -c "SHOW shared_buffers;"
```

### 4. Redis Performance

```bash
# Monitor hit rate
docker compose exec redis redis-cli info stats | grep hits_ratio

# Clear old entries if needed
docker compose exec redis redis-cli FLUSHDB

# Increase maxmemory policy
# In docker-compose.yml command:
# redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
```

### 5. Caching Strategy

```bash
# .env
MGX_ENABLE_CACHING=true
MGX_CACHE_BACKEND=redis          # Use redis for multi-worker
MGX_CACHE_TTL_SECONDS=3600       # 1 hour
MGX_CACHE_MAX_ENTRIES=50000      # Increase for more data

# Monitor cache effectiveness
curl http://localhost:8000/metrics | grep cache_hits
```

### 6. Load Balancing

```nginx
# Nginx upstream for multiple workers
upstream mgx_api {
    server localhost:8000;
    server localhost:8001;  # Scale to multiple containers
    server localhost:8002;
    keepalive 32;
}

server {
    listen 80;
    location / {
        proxy_pass http://mgx_api;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 7. Disk I/O Optimization

```bash
# Use SSD for data volumes
# Check mount options
df -T | grep mgx

# Increase journal size for MinIO
# In docker-compose.yml MinIO volumes:
# - minio_data:/data:rw,sync=false

# Enable write-back caching for Redis
# In docker-compose.yml Redis command:
# redis-server --appendonly yes --appendfsync no
```

### 8. Memory Optimization

```bash
# Monitor memory usage
docker compose stats mgx-ai

# Reduce cache size if memory is limited
MGX_CACHE_MAX_ENTRIES=1000

# Limit container memory
# In docker-compose.yml:
# deploy:
#   resources:
#     limits:
#       memory: 2G
```

---

## External Integrations

### AWS S3 (Instead of MinIO)

```bash
# .env
S3_ENDPOINT_URL=https://s3.us-west-2.amazonaws.com
S3_REGION=us-west-2
S3_BUCKET=my-mgx-artifacts
S3_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
S3_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
S3_SECURE=true

# Create IAM user with S3 access
# Create bucket
# Update environment variables
# Restart services
docker compose restart mgx-ai
```

### Managed PostgreSQL (AWS RDS)

```bash
# .env
DB_HOST=mydb.c9akciq32.us-east-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=mgx
DB_USER=admin
DB_PASSWORD=strong-password

# Run migrations against RDS
docker compose exec mgx-ai alembic upgrade head

# Test connection
docker compose exec mgx-ai python -c \
  "from backend.config import settings; print(settings.async_database_url)"
```

### Enable Kafka for Event Streaming

```bash
# Start with Kafka profile
docker compose --profile kafka up -d

# Configure in .env
KAFKA_ENABLED=true
KAFKA_BROKERS=kafka:29092
KAFKA_TOPIC_EVENTS=mgx-events

# Verify Kafka is running
docker compose ps kafka
docker compose ps zookeeper

# Test topic creation
docker compose exec kafka kafka-topics.sh \
  --bootstrap-server kafka:29092 \
  --create --topic mgx-events --if-not-exists

# Consume events (development only)
docker compose exec kafka kafka-console-consumer.sh \
  --bootstrap-server kafka:29092 \
  --topic mgx-events \
  --from-beginning
```

### OpenTelemetry Observability

```bash
# Add Jaeger for distributed tracing
# Add Prometheus for metrics
# Add Grafana for visualization

# In .env
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

# Extend docker-compose.yml with:
# jaeger:
#   image: jaegertracing/all-in-one:latest
#   ports: ["6831:6831/udp", "16686:16686"]
```

### GitHub Integration

See [Ticket #5: Git-Aware Execution](docs/GIT_AWARE_EXECUTION.md) for complete GitHub App setup.

```bash
# GitHub App authentication (recommended)
GITHUB_APP_ID=123456
GITHUB_CLIENT_ID=Iv1.abcdef123456
GITHUB_PRIVATE_KEY_PATH=/run/secrets/github_app_private_key.pem

# Or Personal Access Token (fallback)
GITHUB_PAT=ghp_xxxxxxxxxxxx
```

---

## Scaling & High Availability

### Horizontal Scaling (Multiple API Servers)

```yaml
# docker-compose.scale.yml
version: '3.8'

services:
  mgx-ai-1:
    build: .
    ports: ["8001:8000"]
    depends_on: [postgres, redis, minio]

  mgx-ai-2:
    build: .
    ports: ["8002:8000"]
    depends_on: [postgres, redis, minio]

  mgx-ai-3:
    build: .
    ports: ["8003:8000"]
    depends_on: [postgres, redis, minio]

  # Nginx load balancer
  nginx:
    image: nginx:alpine
    ports: ["80:80"]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on: [mgx-ai-1, mgx-ai-2, mgx-ai-3]
```

### Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mgx-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mgx-api
  template:
    metadata:
      labels:
        app: mgx-api
    spec:
      containers:
      - name: mgx-api
        image: mgx-agent:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: mgx-secrets
              key: database-url
        - name: REDIS_URL
          value: redis://redis:6379/0
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
```

### Database Replication

```bash
# PostgreSQL streaming replication
# Set up primary-replica configuration
# Consider managed services: AWS RDS, Google Cloud SQL, Azure Database

# For high availability:
# - Use PostgreSQL with replicas
# - Enable automatic failover with Patroni
# - Monitor with Prometheus + Grafana
```

### Backup Strategy

```bash
# Automated daily backups
# Off-site replication (S3, Azure Blob, GCS)
# Weekly full backups to separate storage
# Monthly archival retention

# 3-2-1 rule:
# - 3 copies of data
# - 2 different storage media
# - 1 off-site copy
```

---

## Summary

This Docker Compose setup provides:

✅ **Production-Ready:**
- All critical services with health checks
- Proper startup ordering and dependencies
- Data persistence with volumes
- Comprehensive logging and monitoring

✅ **Secure:**
- Environment variable management
- Secret rotation guidance
- TLS/HTTPS support via reverse proxy
- Network isolation

✅ **Scalable:**
- Redis for distributed caching
- PostgreSQL connection pooling
- Kafka for event streaming (optional)
- Horizontal scaling with load balancing

✅ **Recoverable:**
- Automated backups procedures
- Volume management and recovery
- Migration tracking and rollback

✅ **Observable:**
- Health endpoints for all services
- Comprehensive logging
- Resource monitoring
- Performance metrics

For questions or issues, refer to:
- [GitHub Issues](https://github.com/your-org/mgx-agent/issues)
- [Community Slack](#)
- [Email Support](mailto:support@example.com)
