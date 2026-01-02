#!/bin/bash
# PostgreSQL pg_hba.conf configuration for Docker network access
# This script configures PostgreSQL to allow connections from Docker network

set -e

# Wait for PostgreSQL to be ready
until pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do
  sleep 1
done

# Configure pg_hba.conf to allow connections from Docker network (172.x.x.x)
# This allows backend containers to connect without SSL
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
  -- Allow connections from Docker network (172.16.0.0/12 covers most Docker networks)
  ALTER SYSTEM SET listen_addresses = '*';
  
  -- Reload configuration
  SELECT pg_reload_conf();
EOSQL

# Update pg_hba.conf directly
cat >> /var/lib/postgresql/data/pg_hba.conf <<-EOF

# Docker network access (added by init script)
host    all             all             172.16.0.0/12           md5
host    all             all             172.17.0.0/16           md5
host    all             all             172.18.0.0/16           md5
host    all             all             172.19.0.0/16           md5
host    all             all             172.20.0.0/16           md5
host    all             all             172.21.0.0/16           md5
host    all             all             172.22.0.0/16           md5
host    all             all             172.23.0.0/16           md5
host    all             all             172.24.0.0/16           md5
host    all             all             172.25.0.0/16           md5
host    all             all             172.26.0.0/16           md5
host    all             all             172.27.0.0/16           md5
host    all             all             172.28.0.0/16           md5
host    all             all             172.29.0.0/16           md5
host    all             all             172.30.0.0/16           md5
host    all             all             172.31.0.0/16           md5
# Allow all Docker networks (172.0.0.0/8)
host    all             all             172.0.0.0/8             md5
EOF

# Reload PostgreSQL configuration
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT pg_reload_conf();"

echo "PostgreSQL pg_hba.conf configured for Docker network access"

