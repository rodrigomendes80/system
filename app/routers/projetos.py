from fastapi import APIRouter, Depends, status

from app.db.base import Database
from app.deps import get_db, get_usuario
from app.models import (
    Prioridade,
    Projeto,
    ProjetoCreate,
    ProjetoUpdate,
    StatusProjeto,
    StatusTarefa,
    Tarefa,
    TarefaCreate,
)
from app.services import ProjetoService, TarefaService

router = APIRouter(prefix="/projetos")


@router.get("", response_model=list[Projeto], tags=["Projetos"])
def listar_projetos(
    cliente_id: str | None = None,
    status: StatusProjeto | None = None,
    db: Database = Depends(get_db),
):
    return ProjetoService(db).listar(cliente_id, status)


@router.post("", response_model=Projeto, status_code=status.HTTP_201_CREATED, tags=["Projetos"])
def criar_projeto(dados: ProjetoCreate, db: Database = Depends(get_db)):
    return ProjetoService(db).criar(dados)


@router.get("/{projeto_id}", response_model=Projeto, tags=["Projetos"])
def obter_projeto(projeto_id: str, db: Database = Depends(get_db)):
    return ProjetoService(db).obter(projeto_id)


@router.patch("/{projeto_id}", response_model=Projeto, tags=["Projetos"])
def atualizar_projeto(projeto_id: str, dados: ProjetoUpdate, db: Database = Depends(get_db)):
    return ProjetoService(db).atualizar(projeto_id, dados)


@router.post("/{projeto_id}/finalizar", response_model=Projeto, tags=["Projetos"])
def finalizar_projeto(projeto_id: str, db: Database = Depends(get_db)):
    """Finaliza o projeto. Retorna 409 se houver alguma tarefa não finalizada."""
    return ProjetoService(db).finalizar(projeto_id)


@router.post("/{projeto_id}/reabrir", response_model=Projeto, tags=["Projetos"])
def reabrir_projeto(projeto_id: str, db: Database = Depends(get_db)):
    return ProjetoService(db).reabrir(projeto_id)


@router.get("/{projeto_id}/tarefas", response_model=list[Tarefa], tags=["Tarefas"])
def listar_tarefas(
    projeto_id: str,
    status: StatusTarefa | None = None,
    prioridade: Prioridade | None = None,
    db: Database = Depends(get_db),
):
    return TarefaService(db).listar(projeto_id, status, prioridade)


@router.post(
    "/{projeto_id}/tarefas",
    response_model=Tarefa,
    status_code=status.HTTP_201_CREATED,
    tags=["Tarefas"],
)
def criar_tarefa(
    projeto_id: str,
    dados: TarefaCreate,
    db: Database = Depends(get_db),
    usuario: str | None = Depends(get_usuario),
):
    return TarefaService(db).criar(projeto_id, dados, usuario)
