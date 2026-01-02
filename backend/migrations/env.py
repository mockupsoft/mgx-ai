# -*- coding: utf-8 -*-
"""
Alembic configuration for database migrations.
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Add the parent directory to the Python path for imports
import sys
import os
# Add backend directory to path
backend_dir = os.path.dirname(os.path.dirname(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
# Also add parent directory (project root) to path
project_root = os.path.dirname(backend_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import our models and settings
from backend.config import settings
from backend.db.models import Base
from backend.db.models.entities import *  # Import all models for metadata

# Alembic Config object
config = context.config

# Set the database URL from our settings
# Alembic requires sync connection (not async)
# Use DATABASE_URL environment variable if set, otherwise use sync database_url
# If DATABASE_URL contains asyncpg, convert it to sync psycopg2
database_url = os.getenv("DATABASE_URL", settings.database_url)
# Convert async URL to sync if needed
if database_url and "asyncpg" in database_url:
    database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
elif database_url and "+" in database_url and "asyncpg" not in database_url:
    # Remove any other async driver prefix
    database_url = database_url.split("+", 1)[1] if "+" in database_url else database_url
    if not database_url.startswith("postgresql://"):
        database_url = "postgresql://" + database_url.split("://", 1)[1] if "://" in database_url else database_url
config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the target metadata for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # For async mode, we need to use the async engine
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()