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
            self._migrar_tarefa_sem_projeto()
            self._conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
            if self._tabela_existe("tarefas_antiga"):
                # Copia as tarefas antigas, herdando o cliente do projeto
                self._conn.executescript(
                    """
                    INSERT INTO tarefas (id, cliente_id, projeto_id, titulo, descricao, status,
                                         prioridade, data_criacao, data_prazo, data_finalizacao)
                    SELECT t.id, p.cliente_id, t.projeto_id, t.titulo, t.descricao, t.status,
                           t.prioridade, t.data_criacao, t.data_prazo, t.data_finalizacao
                    FROM tarefas_antiga t JOIN projetos p ON p.id = t.projeto_id;
                    DROP TABLE tarefas_antiga;
                    """
                )

    def on_startup(self) -> None:
        # Em SQLite o esquema é criado/migrado automaticamente ao iniciar a aplicação
        self.create_schema()

    def _tabela_existe(self, nome: str) -> bool:
        return bool(
            self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (nome,)
            ).fetchone()
        )

    def _migrar_tarefa_sem_projeto(self) -> None:
        if not self._tabela_existe("tarefas"):
            return
        colunas = {r["name"] for r in self._conn.execute("PRAGMA table_info(tarefas)")}
        if "cliente_id" not in colunas:
            self._conn.execute("ALTER TABLE tarefas RENAME TO tarefas_antiga")

    def close(self) -> None:
        self._conn.close()
