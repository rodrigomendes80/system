from fastapi import APIRouter, Depends, Response, status

from app.db.base import Database
from app.deps import get_db
from app.models import Prioridade, StatusTarefa, Tarefa, TarefaDetalhada, TarefaUpdate
from app.services import TarefaService

router = APIRouter(prefix="/tarefas", tags=["Tarefas"])


@router.get("", response_model=list[TarefaDetalhada])
def listar_todas_tarefas(
    cliente_id: str | None = None,
    projeto_id: str | None = None,
    status: StatusTarefa | None = None,
    prioridade: Prioridade | None = None,
    db: Database = Depends(get_db),
):
    """Todas as tarefas, com projeto e cliente, ordenadas por prioridade e prazo."""
    return TarefaService(db).listar_todas(cliente_id, projeto_id, status, prioridade)


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
