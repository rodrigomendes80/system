import sqlite3
import threading
import uuid
from datetime import date, datetime, timezone
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
            self._migrar_remocao_de_projetos()

    def on_startup(self) -> None:
        # Em SQLite o esquema é criado/migrado automaticamente ao iniciar a aplicação
        self.create_schema()

    def _tabela_existe(self, nome: str) -> bool:
        return bool(
            self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (nome,)
            ).fetchone()
        )

    def _migrar_remocao_de_projetos(self) -> None:
        """Bases criadas quando o sistema tinha projetos: a tarefa passa a ser só do cliente.

        O vínculo com o projeto é registrado no histórico da tarefa antes de a tabela
        de projetos ser removida, para não perder essa informação.
        """
        colunas = {r["name"] for r in self._conn.execute("PRAGMA table_info(tarefas)")}
        if "projeto_id" not in colunas and "cliente_id" in colunas:
            if self._tabela_existe("projetos"):
                self._conn.execute("DROP TABLE projetos")
                self._conn.commit()
            return

        tem_projetos = self._tabela_existe("projetos") and "projeto_id" in colunas
        cliente = "t.cliente_id" if "cliente_id" in colunas else "NULL"
        if tem_projetos:
            cliente = f"COALESCE({cliente}, p.cliente_id)"
        juncao = "LEFT JOIN projetos p ON p.id = t.projeto_id" if tem_projetos else ""

        self._conn.commit()
        self._conn.execute("PRAGMA foreign_keys = OFF")
        # Renomear sem reescrever as referências de outras tabelas (tarefa_historico → tarefas)
        self._conn.execute("PRAGMA legacy_alter_table = ON")
        self._conn.execute("BEGIN")  # tudo ou nada
        try:
            self._conn.execute(
                """
                CREATE TABLE tarefas_nova (
                  id                TEXT PRIMARY KEY,
                  cliente_id        TEXT NOT NULL REFERENCES clientes(id),
                  titulo            TEXT NOT NULL,
                  descricao         TEXT,
                  status            TEXT NOT NULL CHECK (status IN ('A_FAZER', 'EM_ANDAMENTO', 'BLOQUEADA', 'FINALIZADA')),
                  prioridade        TEXT NOT NULL CHECK (prioridade IN ('BAIXA', 'MEDIA', 'ALTA', 'URGENTE')),
                  data_criacao      TEXT NOT NULL,
                  data_prazo        TEXT,
                  data_finalizacao  TEXT
                )
                """
            )
            self._conn.execute(
                f"""
                INSERT INTO tarefas_nova (id, cliente_id, titulo, descricao, status, prioridade,
                                          data_criacao, data_prazo, data_finalizacao)
                SELECT t.id, {cliente}, t.titulo, t.descricao, t.status, t.prioridade,
                       t.data_criacao, t.data_prazo, t.data_finalizacao
                FROM tarefas t {juncao}
                WHERE {cliente} IS NOT NULL
                """
            )
            if tem_projetos:
                agora = datetime.now(timezone.utc).isoformat()
                vinculos = self._conn.execute(
                    "SELECT t.id, p.nome FROM tarefas t JOIN projetos p ON p.id = t.projeto_id"
                ).fetchall()
                self._conn.executemany(
                    "INSERT INTO tarefa_historico (id, tarefa_id, tipo, texto, autor, data_criacao) "
                    "VALUES (?, ?, 'SISTEMA', ?, NULL, ?)",
                    [
                        (
                            str(uuid.uuid4()),
                            v["id"],
                            f'Projetos foram removidos do sistema. Esta tarefa fazia parte do projeto "{v["nome"]}".',
                            agora,
                        )
                        for v in vinculos
                    ],
                )
            self._conn.execute("DROP TABLE tarefas")
            self._conn.execute("ALTER TABLE tarefas_nova RENAME TO tarefas")
            self._conn.execute("DROP TABLE IF EXISTS projetos")
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            self._conn.execute("PRAGMA legacy_alter_table = OFF")
            self._conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self._conn.close()
