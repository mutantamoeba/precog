"""
Alembic Environment Configuration for Precog Database Migrations.

This module configures Alembic to connect to PostgreSQL using the
environment-aware prefixed variable resolution (e.g., DEV_DB_NAME
when PRECOG_ENV=dev). Falls back to flat DB_* vars for CI.

Environment Variables:
    PRECOG_ENV: Environment prefix selector (dev/test/staging/prod)
    {PREFIX}_DB_HOST: Database hostname (default: localhost)
    {PREFIX}_DB_PORT: Database port (default: 5432)
    {PREFIX}_DB_NAME: Database name (derived from PRECOG_ENV if not set)
    {PREFIX}_DB_USER: Database username (default: postgres)
    {PREFIX}_DB_PASSWORD: Database password (REQUIRED)

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
"""

from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

# Load environment variables from .env file
# This allows local development without setting system env vars
load_dotenv()

# Import environment-aware resolution after load_dotenv()
from precog.config.environment import get_database_name, get_prefixed_env  # noqa: E402

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
    host = get_prefixed_env("DB_HOST", "localhost")
    port = get_prefixed_env("DB_PORT", "5432")
    database = get_database_name()
    user = get_prefixed_env("DB_USER", "postgres")
    password = get_prefixed_env("DB_PASSWORD")

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
