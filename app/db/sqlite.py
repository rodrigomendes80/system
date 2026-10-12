import sqlite3
import threading
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.db.base import Database, Row

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "sql" / "sqlite" / "001_schema.sql"

sqlite3.register_adapter(Decimal, str)
sqlite3.register_adapter(datetime, lambda v: v.isoformat())
sqlite3.register_adapter(date, lambda v: v.isoformat())


class SQLiteDatabase(Database):
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.Lock()

    def table(self, name: str) -> str:
        return name

    def _run(self, sql: str, params: dict[str, Any], fetch: bool) -> list[Row]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()] if fetch else []
            self._conn.commit()
            return rows

    def create_schema(self) -> None:
        with self._lock:
            self._conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))

    def close(self) -> None:
        self._conn.close()
