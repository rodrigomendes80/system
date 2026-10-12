from fastapi import APIRouter, Depends, Response, status

from app.db.base import Database
from app.deps import get_db
from app.models import Tarefa, TarefaUpdate
from app.services import TarefaService

router = APIRouter(prefix="/tarefas", tags=["Tarefas"])


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
