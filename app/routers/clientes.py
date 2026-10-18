from fastapi import APIRouter, Depends, Response, status

from app.db.base import Database
from app.deps import get_db
from app.models import (
    Cliente,
    ClienteCreate,
    ClienteUpdate,
    ServicoContratadoCreate,
    TipoServico,
    TipoServicoCreate,
    VinculosCliente,
)
from app.services import ClienteService, TipoServicoService

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


@router.get("/clientes/{cliente_id}/vinculos", response_model=VinculosCliente)
def vinculos_cliente(cliente_id: str, db: Database = Depends(get_db)):
    """Quantos serviços, tarefas e comentários seriam apagados com o cliente."""
    return ClienteService(db).vinculos(cliente_id)


@router.delete("/clientes/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_cliente(cliente_id: str, cascata: bool = False, db: Database = Depends(get_db)):
    """Exclui o cliente de forma definitiva. Com tarefas, exige `cascata=true`."""
    ClienteService(db).excluir(cliente_id, cascata)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/clientes/{cliente_id}/servicos/{servico_id}", response_model=Cliente)
def encerrar_servico(cliente_id: str, servico_id: str, db: Database = Depends(get_db)):
    """Encerra (inativa) um serviço contratado, mantendo o histórico."""
    return ClienteService(db).encerrar_servico(cliente_id, servico_id)
