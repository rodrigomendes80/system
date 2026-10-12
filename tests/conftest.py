import pytest
from fastapi.testclient import TestClient

from app.db.sqlite import SQLiteDatabase
from app.main import create_app


@pytest.fixture
def client():
    db = SQLiteDatabase(":memory:")
    db.create_schema()
    with TestClient(create_app(db)) as c:
        yield c


@pytest.fixture
def tipo_servico_id(client):
    return client.post("/tipos-servico", json={"nome": "Tráfego Pago"}).json()["id"]


@pytest.fixture
def cliente_id(client, tipo_servico_id):
    resp = client.post(
        "/clientes",
        json={"nome": "Loja Exemplo", "servicos": [{"tipo_servico_id": tipo_servico_id, "valor": "1500.00"}]},
    )
    return resp.json()["id"]


@pytest.fixture
def projeto_id(client, cliente_id):
    return client.post("/projetos", json={"cliente_id": cliente_id, "nome": "Black Friday"}).json()["id"]
