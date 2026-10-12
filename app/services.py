"""Regras de negócio do sistema."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.db.base import Database, Row
from app.models import (
    Cliente,
    ClienteCreate,
    ClienteUpdate,
    ComentarioCreate,
    RegistroHistorico,
    Projeto,
    ProjetoCreate,
    ProjetoUpdate,
    ServicoContratado,
    ServicoContratadoCreate,
    StatusProjeto,
    StatusTarefa,
    Tarefa,
    TarefaAvulsaCreate,
    TarefaCreate,
    TarefaDetalhada,
    TarefaUpdate,
    TipoServico,
    TipoServicoCreate,
    TipoHistorico,
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


_ROTULO_STATUS = {
    StatusTarefa.A_FAZER: "A fazer",
    StatusTarefa.EM_ANDAMENTO: "Em andamento",
    StatusTarefa.BLOQUEADA: "Bloqueada",
    StatusTarefa.FINALIZADA: "Finalizada",
}
_ROTULO_PRIORIDADE = {"BAIXA": "Baixa", "MEDIA": "Média", "ALTA": "Alta", "URGENTE": "Urgente"}


def _data_br(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "sem prazo"


class TarefaService:
    def __init__(self, db: Database):
        self.repo = TarefaRepository(db)
        self.projetos = ProjetoService(db)
        self.clientes = ClienteRepository(db)

    # ----- Histórico -----

    def _registrar(self, tarefa_id: str, tipo: TipoHistorico, texto: str, autor: str | None) -> str:
        registro_id = _novo_id()
        self.repo.inserir_registro(
            {
                "id": registro_id,
                "tarefa_id": tarefa_id,
                "tipo": tipo.value,
                "texto": texto,
                "autor": autor,
                # precisão de microssegundos para manter a ordem dos registros
                "data_criacao": datetime.now(timezone.utc),
            }
        )
        return registro_id

    def historico(self, tarefa_id: str) -> list[RegistroHistorico]:
        self.obter(tarefa_id)
        return [RegistroHistorico(**r) for r in self.repo.listar_historico(tarefa_id)]

    def comentar(self, tarefa_id: str, dados: ComentarioCreate, autor: str | None = None) -> RegistroHistorico:
        """Comentários documentam a tarefa e são permitidos mesmo com o projeto finalizado."""
        self.obter(tarefa_id)
        texto = dados.texto.strip()
        if not texto:
            raise RegraDeNegocioViolada("O comentário não pode ficar em branco")
        registro_id = self._registrar(tarefa_id, TipoHistorico.COMENTARIO, texto, autor)
        return RegistroHistorico(**self.repo.obter_registro(registro_id))

    def excluir_comentario(self, tarefa_id: str, registro_id: str) -> None:
        registro = self.repo.obter_registro(registro_id)
        if not registro or registro["tarefa_id"] != tarefa_id:
            raise NaoEncontrado("Comentário não encontrado")
        if registro["tipo"] != TipoHistorico.COMENTARIO.value:
            raise RegraDeNegocioViolada("Registros automáticos do histórico não podem ser excluídos")
        self.repo.excluir_registro(registro_id)

    def _descrever_mudancas(self, antes: Tarefa, depois: Tarefa) -> list[str]:
        mudancas = []
        if antes.status != depois.status:
            mudancas.append(
                f"Status alterado de {_ROTULO_STATUS[antes.status]} para {_ROTULO_STATUS[depois.status]}"
            )
        if antes.prioridade != depois.prioridade:
            mudancas.append(
                f"Prioridade alterada de {_ROTULO_PRIORIDADE[antes.prioridade.value]} "
                f"para {_ROTULO_PRIORIDADE[depois.prioridade.value]}"
            )
        if antes.data_prazo != depois.data_prazo:
            mudancas.append(f"Prazo alterado de {_data_br(antes.data_prazo)} para {_data_br(depois.data_prazo)}")
        if antes.projeto_id != depois.projeto_id:
            nome = lambda pid: self.projetos.obter(pid).nome if pid else "Sem projeto"  # noqa: E731
            mudancas.append(f"Projeto alterado de {nome(antes.projeto_id)} para {nome(depois.projeto_id)}")
        if antes.titulo != depois.titulo:
            mudancas.append(f"Título alterado de \"{antes.titulo}\" para \"{depois.titulo}\"")
        if (antes.descricao or "") != (depois.descricao or ""):
            mudancas.append("Descrição atualizada")
        return mudancas

    def _projeto_editavel(self, projeto_id: str | None) -> Projeto | None:
        """Projeto finalizado bloqueia criar, alterar, mover ou excluir suas tarefas."""
        if projeto_id is None:
            return None
        projeto = self.projetos.obter(projeto_id)
        if projeto.status == StatusProjeto.FINALIZADO:
            raise RegraDeNegocioViolada(
                f"O projeto \"{projeto.nome}\" está finalizado: suas tarefas não podem ser criadas, "
                "alteradas, movidas ou excluídas. Reabra o projeto primeiro."
            )
        return projeto

    def _projeto_do_cliente(self, projeto_id: str | None, cliente_id: str) -> None:
        projeto = self._projeto_editavel(projeto_id)
        if projeto and projeto.cliente_id != cliente_id:
            raise RegraDeNegocioViolada("O projeto escolhido pertence a outro cliente")

    def listar_todas(
        self, cliente_id=None, projeto_id=None, status=None, prioridade=None, sem_projeto=False
    ) -> list[TarefaDetalhada]:
        rows = self.repo.listar_todas(
            cliente_id,
            projeto_id,
            status.value if status else None,
            prioridade.value if prioridade else None,
            sem_projeto,
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

    def criar(self, projeto_id: str, dados: TarefaCreate, autor: str | None = None) -> Tarefa:
        """Cria a tarefa dentro de um projeto (o cliente é o do projeto)."""
        projeto = self._projeto_editavel(projeto_id)
        return self._inserir(projeto.cliente_id, projeto_id, dados, autor)

    def criar_avulsa(self, dados: TarefaAvulsaCreate, autor: str | None = None) -> Tarefa:
        """Cria a tarefa a partir do cliente, com ou sem projeto."""
        cliente = self.clientes.obter(dados.cliente_id)
        if not cliente:
            raise NaoEncontrado(f"Cliente {dados.cliente_id} não encontrado")
        self._projeto_do_cliente(dados.projeto_id, dados.cliente_id)
        return self._inserir(
            dados.cliente_id,
            dados.projeto_id,
            TarefaCreate(**dados.model_dump(exclude={"cliente_id", "projeto_id"})),
            autor,
        )

    def _inserir(
        self, cliente_id: str, projeto_id: str | None, dados: TarefaCreate, autor: str | None = None
    ) -> Tarefa:
        agora = _agora()
        tarefa_id = _novo_id()
        self.repo.inserir(
            {
                "id": tarefa_id,
                "cliente_id": cliente_id,
                "projeto_id": projeto_id,
                **dados.model_dump(),
                "status": dados.status.value,
                "prioridade": dados.prioridade.value,
                "data_criacao": agora,
                "data_finalizacao": agora if dados.status == StatusTarefa.FINALIZADA else None,
            }
        )
        self._registrar(
            tarefa_id,
            TipoHistorico.SISTEMA,
            f"Tarefa criada com status {_ROTULO_STATUS[dados.status]} "
            f"e prioridade {_ROTULO_PRIORIDADE[dados.prioridade.value]}",
            autor,
        )
        return self.obter(tarefa_id)

    def atualizar(self, tarefa_id: str, dados: TarefaUpdate, autor: str | None = None) -> Tarefa:
        tarefa = self.obter(tarefa_id)
        self._projeto_editavel(tarefa.projeto_id)
        valores = _campos_alterados(dados)

        if "projeto_id" in valores and valores["projeto_id"] != tarefa.projeto_id:
            self._projeto_do_cliente(valores["projeto_id"], tarefa.cliente_id)
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
        atualizada = self.obter(tarefa_id)
        for mudanca in self._descrever_mudancas(tarefa, atualizada):
            self._registrar(tarefa_id, TipoHistorico.SISTEMA, mudanca, autor)
        return atualizada

    def excluir(self, tarefa_id: str) -> None:
        tarefa = self.obter(tarefa_id)
        self._projeto_editavel(tarefa.projeto_id)
        self.repo.excluir(tarefa_id)
