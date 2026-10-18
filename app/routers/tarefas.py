from fastapi import APIRouter, Depends, Response, status

from app.db.base import Database
from app.deps import get_db, get_usuario
from app.models import (
    ComentarioCreate,
    Prioridade,
    RegistroHistorico,
    StatusTarefa,
    Tarefa,
    TarefaCreate,
    TarefaDetalhada,
    TarefaUpdate,
)
from app.services import TarefaService

router = APIRouter(prefix="/tarefas", tags=["Tarefas"])


@router.get("", response_model=list[TarefaDetalhada])
def listar_todas_tarefas(
    cliente_id: str | None = None,
    status: StatusTarefa | None = None,
    prioridade: Prioridade | None = None,
    db: Database = Depends(get_db),
):
    """Todas as tarefas, com o nome do cliente, ordenadas por prioridade e prazo."""
    return TarefaService(db).listar_todas(cliente_id, status, prioridade)


@router.post("", response_model=Tarefa, status_code=status.HTTP_201_CREATED)
def criar_tarefa(
    dados: TarefaCreate, db: Database = Depends(get_db), usuario: str | None = Depends(get_usuario)
):
    """Cria uma tarefa para um cliente."""
    return TarefaService(db).criar(dados, usuario)


@router.get("/{tarefa_id}", response_model=Tarefa)
def obter_tarefa(tarefa_id: str, db: Database = Depends(get_db)):
    return TarefaService(db).obter(tarefa_id)


@router.patch("/{tarefa_id}", response_model=Tarefa)
def atualizar_tarefa(
    tarefa_id: str,
    dados: TarefaUpdate,
    db: Database = Depends(get_db),
    usuario: str | None = Depends(get_usuario),
):
    return TarefaService(db).atualizar(tarefa_id, dados, usuario)


@router.delete("/{tarefa_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_tarefa(tarefa_id: str, db: Database = Depends(get_db)):
    TarefaService(db).excluir(tarefa_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{tarefa_id}/historico", response_model=list[RegistroHistorico], tags=["Histórico"])
def historico_tarefa(tarefa_id: str, db: Database = Depends(get_db)):
    """Comentários e registros automáticos da tarefa, do mais antigo ao mais recente."""
    return TarefaService(db).historico(tarefa_id)


@router.post(
    "/{tarefa_id}/comentarios",
    response_model=RegistroHistorico,
    status_code=status.HTTP_201_CREATED,
    tags=["Histórico"],
)
def comentar_tarefa(
    tarefa_id: str,
    dados: ComentarioCreate,
    db: Database = Depends(get_db),
    usuario: str | None = Depends(get_usuario),
):
    return TarefaService(db).comentar(tarefa_id, dados, usuario)


@router.delete(
    "/{tarefa_id}/comentarios/{comentario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Histórico"],
)
def excluir_comentario(tarefa_id: str, comentario_id: str, db: Database = Depends(get_db)):
    TarefaService(db).excluir_comentario(tarefa_id, comentario_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
