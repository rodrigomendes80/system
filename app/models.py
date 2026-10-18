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


class StatusTarefa(str, Enum):
    A_FAZER = "A_FAZER"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    BLOQUEADA = "BLOQUEADA"
    FINALIZADA = "FINALIZADA"


class TipoHistorico(str, Enum):
    COMENTARIO = "COMENTARIO"
    SISTEMA = "SISTEMA"


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


class VinculosCliente(BaseModel):
    """O que será apagado junto com o cliente."""

    servicos: int
    tarefas: int
    comentarios: int


class Cliente(ClienteBase):
    id: str
    data_cadastro: DataHora
    ativo: bool
    servicos: list[ServicoContratado] = []
    valor_total_servicos: Decimal = Decimal("0")


# ---------- Tarefas ----------

class TarefaCreate(BaseModel):
    cliente_id: str
    titulo: str = Field(min_length=1, max_length=200)
    descricao: str | None = None
    status: StatusTarefa = StatusTarefa.A_FAZER
    prioridade: Prioridade = Prioridade.MEDIA
    data_prazo: date | None = None


class TarefaUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    descricao: str | None = None
    status: StatusTarefa | None = None
    prioridade: Prioridade | None = None
    data_prazo: date | None = None


class Tarefa(BaseModel):
    id: str
    cliente_id: str
    titulo: str
    descricao: str | None
    status: StatusTarefa
    prioridade: Prioridade
    data_criacao: DataHora
    data_prazo: date | None
    data_finalizacao: DataHora | None
    total_comentarios: int = 0


class ComentarioCreate(BaseModel):
    texto: str = Field(min_length=1, max_length=10000)


class RegistroHistorico(BaseModel):
    id: str
    tarefa_id: str
    tipo: TipoHistorico
    texto: str
    autor: str | None
    data_criacao: DataHora


class TarefaDetalhada(Tarefa):
    """Tarefa com o nome do cliente (listagem geral)."""

    cliente_nome: str
