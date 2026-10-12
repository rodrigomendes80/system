import logging
import threading
from pathlib import Path
from typing import Any

from app.db.base import Database, Row

log = logging.getLogger(__name__)

SQL_DIR = Path(__file__).resolve().parents[2] / "sql" / "databricks"


class DatabricksDatabase(Database):
    """Acesso às Delta Tables via SQL Warehouse (databricks-sql-connector)."""

    def __init__(
        self,
        server_hostname: str,
        http_path: str,
        catalog: str,
        schema: str,
        access_token: str = "",
    ):
        if not server_hostname or not http_path:
            raise ValueError(
                "Configure DATABRICKS_SERVER_HOSTNAME e DATABRICKS_HTTP_PATH no arquivo .env"
            )
        self._server_hostname = server_hostname
        self._http_path = http_path
        self._access_token = access_token
        self._fq_schema = f"`{catalog}`.`{schema}`"
        self._conn = None
        self._lock = threading.Lock()

    def _connect(self):
        from databricks import sql

        kwargs: dict[str, Any] = {
            "server_hostname": self._server_hostname,
            "http_path": self._http_path,
        }
        if self._access_token:
            kwargs["access_token"] = self._access_token
        else:
            # Sem token: login OAuth pelo navegador (ideal para desenvolvimento no VS Code)
            kwargs["auth_type"] = "databricks-oauth"
        return sql.connect(**kwargs)

    def table(self, name: str) -> str:
        return f"{self._fq_schema}.`{name}`"

    def _run(self, sql: str, params: dict[str, Any], fetch: bool) -> list[Row]:
        with self._lock:
            if self._conn is None:
                self._conn = self._connect()
            try:
                with self._conn.cursor() as cur:
                    cur.execute(sql, params)
                    if not fetch:
                        return []
                    cols = [d[0] for d in cur.description]
                    return [dict(zip(cols, r)) for r in cur.fetchall()]
            except Exception:
                # Descarta a conexão para reconectar na próxima chamada (ex.: sessão expirada)
                self._discard_connection()
                raise

    def _discard_connection(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def create_schema(self) -> None:
        for file in sorted(SQL_DIR.glob("*.sql")):
            for statement in _split_statements(file.read_text(encoding="utf-8")):
                statement = statement.replace("{fq}", self._fq_schema)
                try:
                    self.execute(statement)
                except Exception as exc:
                    # Permite reexecutar o script: constraints já criadas são ignoradas
                    if "ALREADY_EXISTS" in str(exc).upper() or "already exists" in str(exc):
                        log.info("Ignorando (já existe): %s", statement.splitlines()[0])
                        continue
                    raise

    def close(self) -> None:
        with self._lock:
            self._discard_connection()


def _split_statements(script: str) -> list[str]:
    lines = [line for line in script.splitlines() if not line.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]
