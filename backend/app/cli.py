"""CLI entry-point for operational commands.

Usage (via Docker):
    docker compose run --rm api python -m app.cli seed-superuser
"""
import asyncio
import sys

import typer
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.user import User

app = typer.Typer(help="batmonai operational CLI")
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def _seed(settings) -> None:  # type: ignore[no-untyped-def]
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        result = await session.execute(
            select(User).where(User.email == settings.superuser_email)
        )
        existing = result.scalar_one_or_none()
        if existing:
            typer.echo(f"Superuser {settings.superuser_email!r} already exists — skipping.")
        else:
            su = User(
                email=settings.superuser_email,
                password_hash=pwd_ctx.hash(settings.superuser_password),
                role="superuser",
                client_id=None,
                must_change_password=False,
                is_active=True,
            )
            session.add(su)
            await session.commit()
            typer.echo(f"Superuser {settings.superuser_email!r} created.")

    await engine.dispose()


@app.command("seed-superuser")
def seed_superuser() -> None:
    """Seed the superuser from SUPERUSER_EMAIL / SUPERUSER_PASSWORD env vars."""
    settings = get_settings()
    asyncio.run(_seed(settings))


if __name__ == "__main__":
    app()
