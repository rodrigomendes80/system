"""Acesso a dados (SQL). Sem regras de negócio — elas ficam em services.py."""
from typing import Any

from app.db.base import Database, Row


class TipoServicoRepository:
    def __init__(self, db: Database):
        self.db = db

    def listar(self, somente_ativos: bool = True) -> list[Row]:
        where = "WHERE ativo = :ativo" if somente_ativos else ""
        return self.db.fetch_all(
            f"SELECT * FROM {self.db.table('tipos_servico')} {where} ORDER BY nome",
            {"ativo": True} if somente_ativos else {},
        )

    def obter(self, id_: str) -> Row | None:
        return self.db.fetch_one(
            f"SELECT * FROM {self.db.table('tipos_servico')} WHERE id = :id", {"id": id_}
        )

    def inserir(self, values: dict[str, Any]) -> None:
        self.db.insert("tipos_servico", values)


class ClienteRepository:
    def __init__(self, db: Database):
        self.db = db

    def listar(self, ativo: bool | None = None) -> list[Row]:
        where = "WHERE ativo = :ativo" if ativo is not None else ""
        return self.db.fetch_all(
            f"SELECT * FROM {self.db.table('clientes')} {where} ORDER BY nome",
            {"ativo": ativo} if ativo is not None else {},
        )

    def obter(self, id_: str) -> Row | None:
        return self.db.fetch_one(
            f"SELECT * FROM {self.db.table('clientes')} WHERE id = :id", {"id": id_}
        )

    def inserir(self, values: dict[str, Any]) -> None:
        self.db.insert("clientes", values)

    def atualizar(self, id_: str, values: dict[str, Any]) -> None:
        self.db.update("clientes", id_, values)

    def listar_servicos(self, cliente_ids: list[str]) -> list[Row]:
        if not cliente_ids:
            return []
        params = {f"c{i}": cid for i, cid in enumerate(cliente_ids)}
        in_list = ", ".join(f":{k}" for k in params)
        return self.db.fetch_all(
            f"""
            SELECT cs.*, ts.nome AS tipo_servico_nome
            FROM {self.db.table('cliente_servicos')} cs
            JOIN {self.db.table('tipos_servico')} ts ON ts.id = cs.tipo_servico_id
            WHERE cs.cliente_id IN ({in_list})
            ORDER BY ts.nome
            """,
            params,
        )

    def obter_servico(self, servico_id: str) -> Row | None:
        return self.db.fetch_one(
            f"SELECT * FROM {self.db.table('cliente_servicos')} WHERE id = :id", {"id": servico_id}
        )

    def inserir_servico(self, values: dict[str, Any]) -> None:
        self.db.insert("cliente_servicos", values)

    def atualizar_servico(self, servico_id: str, values: dict[str, Any]) -> None:
        self.db.update("cliente_servicos", servico_id, values)


class ProjetoRepository:
    def __init__(self, db: Database):
        self.db = db

    def _select(self) -> str:
        # Projeto + contagem de tarefas (para progresso e regra de finalização)
        return f"""
            SELECT p.*,
                   COALESCE(t.total, 0) AS total_tarefas,
                   COALESCE(t.finalizadas, 0) AS tarefas_finalizadas
            FROM {self.db.table('projetos')} p
            LEFT JOIN (
                SELECT projeto_id,
                       COUNT(*) AS total,
                       SUM(CASE WHEN status = 'FINALIZADA' THEN 1 ELSE 0 END) AS finalizadas
                FROM {self.db.table('tarefas')}
                GROUP BY projeto_id
            ) t ON t.projeto_id = p.id
        """

    def listar(self, cliente_id: str | None = None, status: str | None = None) -> list[Row]:
        filtros, params = [], {}
        if cliente_id:
            filtros.append("p.cliente_id = :cliente_id")
            params["cliente_id"] = cliente_id
        if status:
            filtros.append("p.status = :status")
            params["status"] = status
        where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
        return self.db.fetch_all(f"{self._select()} {where} ORDER BY p.data_criacao DESC", params)

    def obter(self, id_: str) -> Row | None:
        return self.db.fetch_one(f"{self._select()} WHERE p.id = :id", {"id": id_})

    def inserir(self, values: dict[str, Any]) -> None:
        self.db.insert("projetos", values)

    def atualizar(self, id_: str, values: dict[str, Any]) -> None:
        self.db.update("projetos", id_, values)


_ORDEM_PRIORIDADE = (
    "CASE {col} WHEN 'URGENTE' THEN 1 WHEN 'ALTA' THEN 2 WHEN 'MEDIA' THEN 3 ELSE 4 END"
)


class TarefaRepository:
    def __init__(self, db: Database):
        self.db = db

    def listar_todas(
        self,
        cliente_id: str | None = None,
        projeto_id: str | None = None,
        status: str | None = None,
        prioridade: str | None = None,
    ) -> list[Row]:
        filtros, params = [], {}
        for coluna, valor in (
            ("p.cliente_id", cliente_id),
            ("t.projeto_id", projeto_id),
            ("t.status", status),
            ("t.prioridade", prioridade),
        ):
            if valor:
                nome = coluna.split(".")[1]
                filtros.append(f"{coluna} = :{nome}")
                params[nome] = valor
        where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
        return self.db.fetch_all(
            f"""
            SELECT t.*, p.nome AS projeto_nome, p.status AS projeto_status,
                   c.id AS cliente_id, c.nome AS cliente_nome
            FROM {self.db.table('tarefas')} t
            JOIN {self.db.table('projetos')} p ON p.id = t.projeto_id
            JOIN {self.db.table('clientes')} c ON c.id = p.cliente_id
            {where}
            ORDER BY {_ORDEM_PRIORIDADE.format(col='t.prioridade')}, t.data_prazo, t.data_criacao
            """,
            params,
        )

    def listar(
        self, projeto_id: str, status: str | None = None, prioridade: str | None = None
    ) -> list[Row]:
        filtros, params = ["projeto_id = :projeto_id"], {"projeto_id": projeto_id}
        if status:
            filtros.append("status = :status")
            params["status"] = status
        if prioridade:
            filtros.append("prioridade = :prioridade")
            params["prioridade"] = prioridade
        return self.db.fetch_all(
            f"SELECT * FROM {self.db.table('tarefas')} WHERE {' AND '.join(filtros)} "
            f"ORDER BY {_ORDEM_PRIORIDADE.format(col='prioridade')}, data_criacao",
            params,
        )

    def obter(self, id_: str) -> Row | None:
        return self.db.fetch_one(
            f"SELECT * FROM {self.db.table('tarefas')} WHERE id = :id", {"id": id_}
        )

    def inserir(self, values: dict[str, Any]) -> None:
        self.db.insert("tarefas", values)

    def atualizar(self, id_: str, values: dict[str, Any]) -> None:
        self.db.update("tarefas", id_, values)

    def excluir(self, id_: str) -> None:
        self.db.execute(f"DELETE FROM {self.db.table('tarefas')} WHERE id = :id", {"id": id_})
