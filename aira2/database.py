"""Talk to the same PostgreSQL database the C# AIRA app uses.

EF Core stored mixed-case column names, so every column is quoted:
    SELECT "Id", "Title" FROM incidents

If you write SELECT id FROM incidents, Postgres will look for a lowercase
column named id and fail.
"""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

import psycopg
from psycopg.rows import dict_row

from aira2.config import settings


def connect() -> psycopg.Connection:
    """Open one connection. Caller must close it (or use get_connection)."""
    return psycopg.connect(
        settings.database_url,
        row_factory=dict_row,
        connect_timeout=8,
    )


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """with get_connection() as conn:  → auto-commit or rollback, then close."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
