"""Regras de negócio do sistema."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.db.base import Database, Row
from app.models import (
    Cliente,
    ClienteCreate,
    ClienteUpdate,
    Projeto,
    ProjetoCreate,
    ProjetoUpdate,
    ServicoContratado,
    ServicoContratadoCreate,
    StatusProjeto,
    StatusTarefa,
    Tarefa,
    TarefaCreate,
    TarefaDetalhada,
    TarefaUpdate,
    TipoServico,
    TipoServicoCreate,
)
from app.repositories import (
    ClienteRepository,
    ProjetoRepository,
    TarefaRepository,
    TipoServicoRepository,
)


class NaoEncontrado(Exception):
    """Recurso inexistente (HTTP 404)."""


class RegraDeNegocioViolada(Exception):
    """Operação não permitida pelas regras do sistema (HTTP 409)."""


def _novo_id() -> str:
    return str(uuid.uuid4())


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


_CAMPOS_OBRIGATORIOS = {"nome", "titulo", "status", "prioridade", "ativo"}


def _campos_alterados(dados) -> dict:
    """Campos enviados no PATCH; `null` em campo obrigatório é tratado como "não enviado"."""
    return {
        k: v
        for k, v in dados.model_dump(exclude_unset=True).items()
        if v is not None or k not in _CAMPOS_OBRIGATORIOS
    }


class TipoServicoService:
    def __init__(self, db: Database):
        self.repo = TipoServicoRepository(db)

    def listar(self) -> list[TipoServico]:
        return [TipoServico(**r) for r in self.repo.listar()]

    def criar(self, dados: TipoServicoCreate) -> TipoServico:
        values = {"id": _novo_id(), **dados.model_dump(), "ativo": True}
        self.repo.inserir(values)
        return TipoServico(**values)


class ClienteService:
    def __init__(self, db: Database):
        self.repo = ClienteRepository(db)
        self.tipos = TipoServicoRepository(db)

    def _montar(self, rows: list[Row]) -> list[Cliente]:
        servicos = self.repo.listar_servicos([r["id"] for r in rows])
        clientes = []
        for row in rows:
            do_cliente = [ServicoContratado(**s) for s in servicos if s["cliente_id"] == row["id"]]
            total = sum((s.valor for s in do_cliente if s.ativo), Decimal("0"))
            clientes.append(Cliente(**row, servicos=do_cliente, valor_total_servicos=total))
        return clientes

    def listar(self, ativo: bool | None = None) -> list[Cliente]:
        return self._montar(self.repo.listar(ativo))

    def obter(self, cliente_id: str) -> Cliente:
        row = self.repo.obter(cliente_id)
        if not row:
            raise NaoEncontrado(f"Cliente {cliente_id} não encontrado")
        return self._montar([row])[0]

    def criar(self, dados: ClienteCreate) -> Cliente:
        for servico in dados.servicos:
            self._validar_tipo_servico(servico.tipo_servico_id)
        cliente_id = _novo_id()
        self.repo.inserir(
            {
                "id": cliente_id,
                **dados.model_dump(exclude={"servicos"}),
                "data_cadastro": _agora(),
                "ativo": True,
            }
        )
        for servico in dados.servicos:
            self._inserir_servico(cliente_id, servico)
        return self.obter(cliente_id)

    def atualizar(self, cliente_id: str, dados: ClienteUpdate) -> Cliente:
        self.obter(cliente_id)
        self.repo.atualizar(cliente_id, _campos_alterados(dados))
        return self.obter(cliente_id)

    def adicionar_servico(self, cliente_id: str, dados: ServicoContratadoCreate) -> Cliente:
        self.obter(cliente_id)
        self._validar_tipo_servico(dados.tipo_servico_id)
        self._inserir_servico(cliente_id, dados)
        return self.obter(cliente_id)

    def encerrar_servico(self, cliente_id: str, servico_id: str) -> Cliente:
        servico = self.repo.obter_servico(servico_id)
        if not servico or servico["cliente_id"] != cliente_id:
            raise NaoEncontrado(f"Serviço {servico_id} não encontrado para este cliente")
        self.repo.atualizar_servico(servico_id, {"ativo": False})
        return self.obter(cliente_id)

    def _validar_tipo_servico(self, tipo_servico_id: str) -> None:
        tipo = self.tipos.obter(tipo_servico_id)
        if not tipo or not tipo["ativo"]:
            raise NaoEncontrado(f"Tipo de serviço {tipo_servico_id} não encontrado")

    def _inserir_servico(self, cliente_id: str, dados: ServicoContratadoCreate) -> None:
        self.repo.inserir_servico(
            {"id": _novo_id(), "cliente_id": cliente_id, **dados.model_dump(), "ativo": True}
        )


class ProjetoService:
    def __init__(self, db: Database):
        self.repo = ProjetoRepository(db)
        self.clientes = ClienteRepository(db)

    @staticmethod
    def _montar(row: Row) -> Projeto:
        total = int(row["total_tarefas"] or 0)
        finalizadas = int(row["tarefas_finalizadas"] or 0)
        percentual = round(100 * finalizadas / total, 1) if total else 0.0
        return Projeto(
            **{**row, "total_tarefas": total, "tarefas_finalizadas": finalizadas},
            percentual_concluido=percentual,
        )

    def listar(self, cliente_id: str | None = None, status: StatusProjeto | None = None) -> list[Projeto]:
        rows = self.repo.listar(cliente_id, status.value if status else None)
        return [self._montar(r) for r in rows]

    def obter(self, projeto_id: str) -> Projeto:
        row = self.repo.obter(projeto_id)
        if not row:
            raise NaoEncontrado(f"Projeto {projeto_id} não encontrado")
        return self._montar(row)

    def criar(self, dados: ProjetoCreate) -> Projeto:
        cliente = self.clientes.obter(dados.cliente_id)
        if not cliente:
            raise NaoEncontrado(f"Cliente {dados.cliente_id} não encontrado")
        if not cliente["ativo"]:
            raise RegraDeNegocioViolada("Não é possível criar projeto para cliente inativo")
        if dados.status == StatusProjeto.FINALIZADO:
            raise RegraDeNegocioViolada("Um projeto novo não pode nascer finalizado (não possui tarefas)")
        projeto_id = _novo_id()
        self.repo.inserir(
            {
                "id": projeto_id,
                **dados.model_dump(),
                "status": dados.status.value,
                "data_criacao": _agora(),
                "data_finalizacao": None,
            }
        )
        return self.obter(projeto_id)

    def atualizar(self, projeto_id: str, dados: ProjetoUpdate) -> Projeto:
        projeto = self.obter(projeto_id)
        valores = _campos_alterados(dados)
        novo_status = valores.pop("status", None)

        if valores and projeto.status == StatusProjeto.FINALIZADO:
            raise RegraDeNegocioViolada("Projeto finalizado não pode ser alterado; reabra-o primeiro")
        self.repo.atualizar(projeto_id, valores)

        if novo_status == StatusProjeto.FINALIZADO:
            return self.finalizar(projeto_id)
        if novo_status is not None and novo_status != projeto.status:
            self.repo.atualizar(
                projeto_id, {"status": novo_status.value, "data_finalizacao": None}
            )
        return self.obter(projeto_id)

    def finalizar(self, projeto_id: str) -> Projeto:
        """REGRA: o projeto só finaliza quando TODAS as suas tarefas estão finalizadas."""
        projeto = self.obter(projeto_id)
        if projeto.status == StatusProjeto.FINALIZADO:
            return projeto
        if projeto.total_tarefas == 0:
            raise RegraDeNegocioViolada("Projeto sem tarefas não pode ser finalizado")
        pendentes = projeto.total_tarefas - projeto.tarefas_finalizadas
        if pendentes > 0:
            raise RegraDeNegocioViolada(
                f"Projeto possui {pendentes} tarefa(s) não finalizada(s) "
                f"de um total de {projeto.total_tarefas}"
            )
        self.repo.atualizar(
            projeto_id, {"status": StatusProjeto.FINALIZADO.value, "data_finalizacao": _agora()}
        )
        return self.obter(projeto_id)

    def reabrir(self, projeto_id: str) -> Projeto:
        projeto = self.obter(projeto_id)
        if projeto.status != StatusProjeto.FINALIZADO:
            raise RegraDeNegocioViolada("Somente projetos finalizados podem ser reabertos")
        self.repo.atualizar(
            projeto_id, {"status": StatusProjeto.EM_ANDAMENTO.value, "data_finalizacao": None}
        )
        return self.obter(projeto_id)


class TarefaService:
    def __init__(self, db: Database):
        self.repo = TarefaRepository(db)
        self.projetos = ProjetoService(db)

    def _projeto_editavel(self, projeto_id: str) -> Projeto:
        projeto = self.projetos.obter(projeto_id)
        if projeto.status == StatusProjeto.FINALIZADO:
            raise RegraDeNegocioViolada(
                "Projeto finalizado: suas tarefas não podem ser criadas, alteradas ou excluídas. "
                "Reabra o projeto primeiro."
            )
        return projeto

    def listar_todas(
        self, cliente_id=None, projeto_id=None, status=None, prioridade=None
    ) -> list[TarefaDetalhada]:
        rows = self.repo.listar_todas(
            cliente_id,
            projeto_id,
            status.value if status else None,
            prioridade.value if prioridade else None,
        )
        return [TarefaDetalhada(**r) for r in rows]

    def listar(self, projeto_id: str, status=None, prioridade=None) -> list[Tarefa]:
        self.projetos.obter(projeto_id)
        rows = self.repo.listar(
            projeto_id, status.value if status else None, prioridade.value if prioridade else None
        )
        return [Tarefa(**r) for r in rows]

    def obter(self, tarefa_id: str) -> Tarefa:
        row = self.repo.obter(tarefa_id)
        if not row:
            raise NaoEncontrado(f"Tarefa {tarefa_id} não encontrada")
        return Tarefa(**row)

    def criar(self, projeto_id: str, dados: TarefaCreate) -> Tarefa:
        self._projeto_editavel(projeto_id)
        agora = _agora()
        tarefa_id = _novo_id()
        self.repo.inserir(
            {
                "id": tarefa_id,
                "projeto_id": projeto_id,
                **dados.model_dump(),
                "status": dados.status.value,
                "prioridade": dados.prioridade.value,
                "data_criacao": agora,
                "data_finalizacao": agora if dados.status == StatusTarefa.FINALIZADA else None,
            }
        )
        return self.obter(tarefa_id)

    def atualizar(self, tarefa_id: str, dados: TarefaUpdate) -> Tarefa:
        tarefa = self.obter(tarefa_id)
        self._projeto_editavel(tarefa.projeto_id)
        valores = _campos_alterados(dados)

        if "prioridade" in valores:
            valores["prioridade"] = valores["prioridade"].value
        novo_status = valores.get("status")
        if novo_status is not None:
            valores["status"] = novo_status.value
            # Data de finalização é controlada pelo sistema
            if novo_status == StatusTarefa.FINALIZADA and tarefa.status != StatusTarefa.FINALIZADA:
                valores["data_finalizacao"] = _agora()
            elif novo_status != StatusTarefa.FINALIZADA:
                valores["data_finalizacao"] = None

        self.repo.atualizar(tarefa_id, valores)
        return self.obter(tarefa_id)

    def excluir(self, tarefa_id: str) -> None:
        tarefa = self.obter(tarefa_id)
        self._projeto_editavel(tarefa.projeto_id)
        self.repo.excluir(tarefa_id)
