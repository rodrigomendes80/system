from abc import ABC, abstractmethod
from typing import Any

Row = dict[str, Any]


class Database(ABC):
    """Interface mínima de acesso ao banco, comum ao Databricks e ao SQLite.

    As consultas usam parâmetros nomeados no formato `:nome`, suportado pelos dois backends.
    """

    @abstractmethod
    def table(self, name: str) -> str:
        """Nome totalmente qualificado da tabela (ex.: `main`.`gestao_projetos`.`clientes`)."""

    @abstractmethod
    def _run(self, sql: str, params: dict[str, Any], fetch: bool) -> list[Row]: ...

    @abstractmethod
    def create_schema(self) -> None: ...

    def close(self) -> None:
        pass

    def on_startup(self) -> None:
        """Executado quando a aplicação inicia (ex.: criar esquema local)."""

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> None:
        self._run(sql, params or {}, fetch=False)

    def fetch_all(self, sql: str, params: dict[str, Any] | None = None) -> list[Row]:
        return self._run(sql, params or {}, fetch=True)

    def fetch_one(self, sql: str, params: dict[str, Any] | None = None) -> Row | None:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def insert(self, table: str, values: dict[str, Any]) -> None:
        cols = ", ".join(values)
        placeholders = ", ".join(f":{c}" for c in values)
        self.execute(f"INSERT INTO {self.table(table)} ({cols}) VALUES ({placeholders})", values)

    def update(self, table: str, id_: str, values: dict[str, Any]) -> None:
        if not values:
            return
        sets = ", ".join(f"{c} = :{c}" for c in values)
        self.execute(f"UPDATE {self.table(table)} SET {sets} WHERE id = :id", {**values, "id": id_})
