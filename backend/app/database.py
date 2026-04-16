from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import DATABASE_URL, DB_PATH

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover - optional dependency for Postgres mode
    psycopg = None
    dict_row = None


POSTGRES_PREFIXES = ("postgres://", "postgresql://")
USE_POSTGRES = DATABASE_URL.lower().startswith(POSTGRES_PREFIXES)
QMARK_PATTERN = re.compile(r"\?")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect_sqlite(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _to_postgres_sql(query: str) -> str:
    # The codebase uses sqlite-style `?` placeholders.
    return QMARK_PATTERN.sub("%s", query)


class PostgresCursorAdapter:
    def __init__(self, cursor: Any):
        self._cursor = cursor

    def execute(self, query: str, params: tuple[Any, ...] | list[Any] | None = None):
        self._cursor.execute(_to_postgres_sql(query), tuple(params or ()))
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()


class PostgresConnectionAdapter:
    def __init__(self, conn: Any):
        self._conn = conn

    def execute(self, query: str, params: tuple[Any, ...] | list[Any] | None = None):
        cursor = self._conn.cursor()
        cursor.execute(_to_postgres_sql(query), tuple(params or ()))
        return PostgresCursorAdapter(cursor)

    def cursor(self):
        return PostgresCursorAdapter(self._conn.cursor())

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


def _connect_postgres() -> PostgresConnectionAdapter:
    if psycopg is None or dict_row is None:
        raise RuntimeError(
            "APPEALS_DATABASE_URL is set, but psycopg is not installed. "
            "Install backend dependencies (including psycopg[binary])."
        )
    raw_conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return PostgresConnectionAdapter(raw_conn)


def _connect(db_path: Path | str = DB_PATH):
    if USE_POSTGRES:
        return _connect_postgres()
    return _connect_sqlite(db_path)


@contextmanager
def get_conn() -> Iterator[Any]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_case_extractions_mode_column(conn: Any) -> None:
    if USE_POSTGRES:
        row = conn.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'case_extractions'
              AND column_name = 'mode'
              AND table_schema = ANY (current_schemas(false))
            LIMIT 1
            """
        ).fetchone()
        has_mode = bool(row)
    else:
        extraction_columns = {row[1] for row in conn.execute("PRAGMA table_info(case_extractions)").fetchall()}
        has_mode = "mode" in extraction_columns

    if not has_mode:
        conn.execute("ALTER TABLE case_extractions ADD COLUMN mode TEXT NOT NULL DEFAULT 'rule_based';")


def init_db() -> None:
    with get_conn() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                type TEXT NOT NULL,
                filename TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                processed_status TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS doc_pages (
                document_id TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                text TEXT NOT NULL,
                confidence REAL,
                extraction_method TEXT,
                PRIMARY KEY (document_id, page_number),
                FOREIGN KEY(document_id) REFERENCES documents(document_id) ON DELETE CASCADE
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                page_number INTEGER,
                text TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
                FOREIGN KEY(document_id) REFERENCES documents(document_id) ON DELETE CASCADE
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS case_extractions (
                extraction_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                case_json TEXT NOT NULL,
                warnings TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                owner TEXT NOT NULL,
                due_date TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                type TEXT NOT NULL,
                version INTEGER NOT NULL,
                storage_path TEXT NOT NULL,
                metadata TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                notes TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS appealability_cache (
                case_id TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                result_json TEXT NOT NULL,
                computed_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_session_usage (
                session_id TEXT PRIMARY KEY,
                request_count INTEGER NOT NULL,
                first_request_at TEXT NOT NULL,
                last_request_at TEXT NOT NULL,
                last_request_epoch REAL NOT NULL
            );
            """
        )

        cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_case_id ON documents(case_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_case_id ON chunks(case_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_case_id ON tasks(case_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_case_id ON events(case_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_appealability_cache_computed_at ON appealability_cache(computed_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_session_last_epoch ON chat_session_usage(last_request_epoch);")
        _ensure_case_extractions_mode_column(conn)
