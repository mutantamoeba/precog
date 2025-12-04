"""
Alembic Environment Configuration for Precog Database Migrations.

This module configures Alembic to connect to PostgreSQL using environment
variables, following Pattern 4 (Security - No Credentials in Code).

Environment Variables Required:
    DB_HOST: Database hostname (default: localhost)
    DB_PORT: Database port (default: 5432)
    DB_NAME: Database name (default: precog_dev)
    DB_USER: Database username (default: postgres)
    DB_PASSWORD: Database password (REQUIRED)

Usage:
    # Run migrations
    cd src/precog/database
    alembic upgrade head

    # Create new migration
    alembic revision -m "description"

    # Show current version
    alembic current

References:
    - ADR-030: Alembic Migration Framework
    - Pattern 4: Security (No Credentials in Code)
    - docs/utility/SCHEMA_MIGRATION_WORKFLOW_V1.1.md
"""

import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

# Load environment variables from .env file
# This allows local development without setting system env vars
load_dotenv()

# Alembic Config object - provides access to .ini file values
config = context.config

# Set up Python logging from the config file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
# TODO: Import SQLAlchemy models when we add them
# from precog.database.models import Base
# target_metadata = Base.metadata
target_metadata = None


def get_database_url() -> str:
    """
    Build PostgreSQL connection URL from environment variables.

    Returns:
        PostgreSQL connection URL string

    Raises:
        ValueError: If DB_PASSWORD is not set

    Security Note:
        Password is read from environment variable, never hardcoded.
        See Pattern 4 in DEVELOPMENT_PATTERNS_V1.5.md
    """
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    database = os.getenv("DB_NAME", "precog_dev")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD")

    if not password:
        raise ValueError(
            "DB_PASSWORD environment variable is required. "
            "Set it in .env file or system environment."
        )

    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This generates SQL scripts without connecting to the database.
    Useful for generating migration scripts to run manually.

    Usage:
        alembic upgrade head --sql > migration.sql
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    This connects to the database and applies migrations directly.
    Uses NullPool to avoid connection pooling issues in migration context.
    """
    # Build connection URL from environment variables
    url = get_database_url()

    # Create engine with URL (not from config file)
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


# Execute the appropriate migration mode
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
