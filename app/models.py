from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

# O Databricks devolve TIMESTAMP sem fuso (em UTC); marcamos como UTC para a
# interface converter corretamente para o horário local.
DataHora = Annotated[
    datetime, AfterValidator(lambda v: v if v.tzinfo else v.replace(tzinfo=timezone.utc))
]


class StatusProjeto(str, Enum):
    PLANEJAMENTO = "PLANEJAMENTO"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    FINALIZADO = "FINALIZADO"


class StatusTarefa(str, Enum):
    A_FAZER = "A_FAZER"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    BLOQUEADA = "BLOQUEADA"
    FINALIZADA = "FINALIZADA"


class Prioridade(str, Enum):
    BAIXA = "BAIXA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"
    URGENTE = "URGENTE"


# ---------- Tipos de serviço ----------

class TipoServicoCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    descricao: str | None = None


class TipoServico(TipoServicoCreate):
    id: str
    ativo: bool


# ---------- Clientes ----------

class ServicoContratadoCreate(BaseModel):
    tipo_servico_id: str
    valor: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    data_inicio: date | None = None


class ServicoContratado(ServicoContratadoCreate):
    id: str
    cliente_id: str
    tipo_servico_nome: str
    ativo: bool


class ClienteBase(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    documento: str | None = Field(default=None, description="CPF ou CNPJ")
    email: str | None = None
    telefone: str | None = None


class ClienteCreate(ClienteBase):
    servicos: list[ServicoContratadoCreate] = []


class ClienteUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    documento: str | None = None
    email: str | None = None
    telefone: str | None = None
    ativo: bool | None = None


class Cliente(ClienteBase):
    id: str
    data_cadastro: DataHora
    ativo: bool
    servicos: list[ServicoContratado] = []
    valor_total_servicos: Decimal = Decimal("0")


# ---------- Projetos ----------

class ProjetoCreate(BaseModel):
    cliente_id: str
    nome: str = Field(min_length=1, max_length=200)
    descricao: str | None = None
    data_prazo: date | None = None
    status: StatusProjeto = StatusProjeto.PLANEJAMENTO


class ProjetoUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    descricao: str | None = None
    data_prazo: date | None = None
    status: StatusProjeto | None = None


class Projeto(BaseModel):
    id: str
    cliente_id: str
    nome: str
    descricao: str | None
    status: StatusProjeto
    data_criacao: DataHora
    data_prazo: date | None
    data_finalizacao: DataHora | None
    total_tarefas: int = 0
    tarefas_finalizadas: int = 0
    percentual_concluido: float = 0.0


# ---------- Tarefas ----------

class TarefaCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    descricao: str | None = None
    status: StatusTarefa = StatusTarefa.A_FAZER
    prioridade: Prioridade = Prioridade.MEDIA
    data_prazo: date | None = None


class TarefaAvulsaCreate(TarefaCreate):
    """Tarefa criada a partir do cliente; o projeto é opcional."""

    cliente_id: str
    projeto_id: str | None = None


class TarefaUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    descricao: str | None = None
    status: StatusTarefa | None = None
    prioridade: Prioridade | None = None
    data_prazo: date | None = None
    projeto_id: str | None = Field(
        default=None, description="Aloca a tarefa em um projeto do mesmo cliente; null remove do projeto"
    )


class Tarefa(BaseModel):
    id: str
    cliente_id: str
    projeto_id: str | None
    titulo: str
    descricao: str | None
    status: StatusTarefa
    prioridade: Prioridade
    data_criacao: DataHora
    data_prazo: date | None
    data_finalizacao: DataHora | None


class TarefaDetalhada(Tarefa):
    """Tarefa com o projeto e o cliente a que pertence (listagem geral)."""

    projeto_nome: str | None
    projeto_status: StatusProjeto | None
    cliente_nome: str
