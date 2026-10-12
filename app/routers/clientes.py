from fastapi import APIRouter, Depends, status

from app.db.base import Database
from app.deps import get_db
from app.models import (
    Cliente,
    ClienteCreate,
    ClienteUpdate,
    Projeto,
    ServicoContratadoCreate,
    TipoServico,
    TipoServicoCreate,
)
from app.services import ClienteService, ProjetoService, TipoServicoService

router = APIRouter(tags=["Clientes"])


@router.get("/tipos-servico", response_model=list[TipoServico])
def listar_tipos_servico(db: Database = Depends(get_db)):
    return TipoServicoService(db).listar()


@router.post("/tipos-servico", response_model=TipoServico, status_code=status.HTTP_201_CREATED)
def criar_tipo_servico(dados: TipoServicoCreate, db: Database = Depends(get_db)):
    return TipoServicoService(db).criar(dados)


@router.get("/clientes", response_model=list[Cliente])
def listar_clientes(ativo: bool | None = None, db: Database = Depends(get_db)):
    return ClienteService(db).listar(ativo)


@router.post("/clientes", response_model=Cliente, status_code=status.HTTP_201_CREATED)
def criar_cliente(dados: ClienteCreate, db: Database = Depends(get_db)):
    return ClienteService(db).criar(dados)


@router.get("/clientes/{cliente_id}", response_model=Cliente)
def obter_cliente(cliente_id: str, db: Database = Depends(get_db)):
    return ClienteService(db).obter(cliente_id)


@router.patch("/clientes/{cliente_id}", response_model=Cliente)
def atualizar_cliente(cliente_id: str, dados: ClienteUpdate, db: Database = Depends(get_db)):
    return ClienteService(db).atualizar(cliente_id, dados)


@router.post("/clientes/{cliente_id}/servicos", response_model=Cliente, status_code=status.HTTP_201_CREATED)
def adicionar_servico(cliente_id: str, dados: ServicoContratadoCreate, db: Database = Depends(get_db)):
    return ClienteService(db).adicionar_servico(cliente_id, dados)


@router.delete("/clientes/{cliente_id}/servicos/{servico_id}", response_model=Cliente)
def encerrar_servico(cliente_id: str, servico_id: str, db: Database = Depends(get_db)):
    """Encerra (inativa) um serviço contratado, mantendo o histórico."""
    return ClienteService(db).encerrar_servico(cliente_id, servico_id)


@router.get("/clientes/{cliente_id}/projetos", response_model=list[Projeto])
def listar_projetos_do_cliente(cliente_id: str, db: Database = Depends(get_db)):
    ClienteService(db).obter(cliente_id)
    return ProjetoService(db).listar(cliente_id=cliente_id)
