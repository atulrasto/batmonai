"""Alembic env — synchronous runner connecting directly to postgres (not pgbouncer).

Responsibilities:
  1. Create TimescaleDB + btree_gist extensions (autocommit, idempotent).
  2. Create / update the non-superuser app role.
  3. Run DDL migrations inside a transaction.
  4. Grant table/sequence privileges to the app role after migrations complete.
"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Register all models so autogenerate can see them
from app.models.base import Base  # noqa: E402
import app.models  # noqa: E402, F401

target_metadata = Base.metadata


def _get_url() -> str:
    # migrations connect directly to postgres (bypasses pgbouncer)
    return os.environ["DATABASE_URL_SYNC"]


def _q(s: str) -> str:
    """Double-quote a SQL identifier."""
    return '"' + s.replace('"', '""') + '"'


def _l(s: str) -> str:
    """Single-quote a SQL string literal, escaping embedded quotes."""
    return "'" + s.replace("'", "''") + "'"


def _setup_extensions_and_role(url: str) -> None:
    app_user = os.environ.get("APP_DB_USER", "batmonai_app")
    app_password = os.environ.get("APP_DB_PASSWORD", "")
    db_name = os.environ.get("POSTGRES_DB", "batmonai")

    engine = engine_from_config(
        {"sqlalchemy.url": url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        isolation_level="AUTOCOMMIT",
    )
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        conn.execute(text(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT FROM pg_catalog.pg_roles WHERE rolname = {_l(app_user)}
                ) THEN
                    CREATE ROLE {_q(app_user)}
                        WITH LOGIN PASSWORD {_l(app_password)} NOINHERIT;
                ELSE
                    ALTER ROLE {_q(app_user)} WITH PASSWORD {_l(app_password)};
                END IF;
            END
            $$
        """))
        conn.execute(text(
            f"GRANT CONNECT ON DATABASE {_q(db_name)} TO {_q(app_user)}"
        ))
        conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {_q(app_user)}"))
    engine.dispose()


def _grant_permissions(url: str) -> None:
    app_user = os.environ.get("APP_DB_USER", "batmonai_app")
    engine = engine_from_config(
        {"sqlalchemy.url": url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        isolation_level="AUTOCOMMIT",
    )
    with engine.connect() as conn:
        conn.execute(text(
            f"GRANT SELECT, INSERT, UPDATE, DELETE "
            f"ON ALL TABLES IN SCHEMA public TO {_q(app_user)}"
        ))
        conn.execute(text(
            f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {_q(app_user)}"
        ))
        conn.execute(text(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {_q(app_user)}"
        ))
        conn.execute(text(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT USAGE, SELECT ON SEQUENCES TO {_q(app_user)}"
        ))
    engine.dispose()


def run_migrations_offline() -> None:
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _get_url()

    _setup_extensions_and_role(url)

    connectable = engine_from_config(
        {"sqlalchemy.url": url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()

    _grant_permissions(url)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
