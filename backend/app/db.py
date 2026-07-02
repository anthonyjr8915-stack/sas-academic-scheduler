"""
Database bootstrap.

Uses SQLite for local dev (zero-setup) and PostgreSQL in production — set
`SAS_DATABASE_URL` to switch, e.g. postgresql+psycopg://user:pw@host/db. The rest
of the app only touches `get_session()` / `init_db()`, so the backend is
DB-portable by design.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

_DEFAULT_SQLITE = f"sqlite:///{Path(__file__).resolve().parents[1] / 'sas.db'}"
DATABASE_URL = os.getenv("SAS_DATABASE_URL", _DEFAULT_SQLITE)

# check_same_thread is a SQLite-only quirk; harmless to gate on the scheme.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=_connect_args)


def init_db() -> None:
    # Import models so their tables register on SQLModel.metadata before create_all.
    from app.models import tables  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
