from fastapi import APIRouter, Depends, Response, status

from app.db.base import Database
from app.deps import get_db
from app.models import (
    Prioridade,
    StatusTarefa,
    Tarefa,
    TarefaAvulsaCreate,
    TarefaDetalhada,
    TarefaUpdate,
)
from app.services import TarefaService

router = APIRouter(prefix="/tarefas", tags=["Tarefas"])


@router.get("", response_model=list[TarefaDetalhada])
def listar_todas_tarefas(
    cliente_id: str | None = None,
    projeto_id: str | None = None,
    status: StatusTarefa | None = None,
    prioridade: Prioridade | None = None,
    sem_projeto: bool = False,
    db: Database = Depends(get_db),
):
    """Todas as tarefas, com projeto e cliente, ordenadas por prioridade e prazo."""
    return TarefaService(db).listar_todas(cliente_id, projeto_id, status, prioridade, sem_projeto)


@router.post("", response_model=Tarefa, status_code=status.HTTP_201_CREATED)
def criar_tarefa(dados: TarefaAvulsaCreate, db: Database = Depends(get_db)):
    """Cria uma tarefa para um cliente, alocada ou não em um projeto."""
    return TarefaService(db).criar_avulsa(dados)


@router.get("/{tarefa_id}", response_model=Tarefa)
def obter_tarefa(tarefa_id: str, db: Database = Depends(get_db)):
    return TarefaService(db).obter(tarefa_id)


@router.patch("/{tarefa_id}", response_model=Tarefa)
def atualizar_tarefa(tarefa_id: str, dados: TarefaUpdate, db: Database = Depends(get_db)):
    return TarefaService(db).atualizar(tarefa_id, dados)


@router.delete("/{tarefa_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_tarefa(tarefa_id: str, db: Database = Depends(get_db)):
    TarefaService(db).excluir(tarefa_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
