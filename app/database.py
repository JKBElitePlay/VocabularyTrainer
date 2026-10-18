"""Database configuration and session dependencies."""

import os
from collections.abc import Generator
from pathlib import Path

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for all database models."""


def create_database(database_url: str | None = None):
    """Create an engine and session factory for the configured database."""
    url = database_url or os.getenv(
        "VOCABULARY_DATABASE_URL",
        f"sqlite:///{Path('data') / 'vokabeltrainer.db'}",
    )
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    if url.startswith("sqlite:///") and ":memory:" not in url:
        db_path = Path(url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args=connect_args)
    return engine, sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request) -> Generator[Session, None, None]:
    """Yield the current application's database session."""
    with request.app.state.session_factory() as session:
        yield session
