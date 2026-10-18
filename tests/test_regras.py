from decimal import Decimal


# ---------- Clientes ----------

def test_cliente_com_servicos_e_valor_total(client, tipo_servico_id):
    seo = client.post("/tipos-servico", json={"nome": "SEO"}).json()["id"]
    resp = client.post(
        "/clientes",
        json={
            "nome": "Cliente A",
            "servicos": [
                {"tipo_servico_id": tipo_servico_id, "valor": "1500.00"},
                {"tipo_servico_id": seo, "valor": "800.50"},
            ],
        },
    )
    assert resp.status_code == 201
    cliente = resp.json()
    assert cliente["data_cadastro"]
    assert len(cliente["servicos"]) == 2
    assert Decimal(cliente["valor_total_servicos"]) == Decimal("2300.50")

    # Serviço encerrado deixa de compor o valor total, mas permanece no histórico
    servico_id = next(s["id"] for s in cliente["servicos"] if s["tipo_servico_nome"] == "SEO")
    cliente = client.delete(f"/clientes/{cliente['id']}/servicos/{servico_id}").json()
    assert Decimal(cliente["valor_total_servicos"]) == Decimal("1500")
    assert len(cliente["servicos"]) == 2


def test_cliente_com_tipo_servico_inexistente(client):
    resp = client.post(
        "/clientes", json={"nome": "X", "servicos": [{"tipo_servico_id": "nao-existe", "valor": "10"}]}
    )
    assert resp.status_code == 404


def test_rotas_de_projetos_nao_existem_mais(client):
    assert client.get("/projetos").status_code == 404
    assert all("projeto" not in caminho for caminho in client.get("/openapi.json").json()["paths"])


# ---------- Tarefas ----------

def test_tarefa_pertence_a_cliente_existente(client):
    resp = client.post("/tarefas", json={"cliente_id": "nao-existe", "titulo": "T"})
    assert resp.status_code == 404


def test_tarefa_tem_datas_status_e_prioridade(client, cliente_id, nova_tarefa):
    tarefa = nova_tarefa("Criar campanha", prioridade="ALTA")
    assert tarefa["cliente_id"] == cliente_id
    assert "projeto_id" not in tarefa
    assert tarefa["status"] == "A_FAZER"
    assert tarefa["prioridade"] == "ALTA"
    assert tarefa["data_criacao"]
    assert tarefa["data_finalizacao"] is None

    tarefa = client.patch(f"/tarefas/{tarefa['id']}", json={"status": "FINALIZADA"}).json()
    assert tarefa["data_finalizacao"] is not None

    # Reabrir a tarefa limpa a data de finalização
    tarefa = client.patch(f"/tarefas/{tarefa['id']}", json={"status": "EM_ANDAMENTO"}).json()
    assert tarefa["data_finalizacao"] is None


def test_listagem_geral_e_filtros(client, cliente_id, nova_tarefa):
    outro = client.post("/clientes", json={"nome": "Outro"}).json()["id"]
    nova_tarefa("Baixa", prioridade="BAIXA")
    client.post("/tarefas", json={"cliente_id": outro, "titulo": "Urgente", "prioridade": "URGENTE"})

    todas = client.get("/tarefas").json()
    assert [t["titulo"] for t in todas] == ["Urgente", "Baixa"]  # ordenado por prioridade
    assert todas[1]["cliente_nome"] == "Loja Exemplo"
    assert [t["titulo"] for t in client.get(f"/tarefas?cliente_id={cliente_id}").json()] == ["Baixa"]
    assert len(client.get("/tarefas?prioridade=URGENTE").json()) == 1
    assert len(client.get("/tarefas?status=FINALIZADA").json()) == 0


def test_patch_com_null_em_campo_obrigatorio_e_ignorado(client, nova_tarefa):
    t = nova_tarefa("T")
    resp = client.patch(f"/tarefas/{t['id']}", json={"titulo": None, "descricao": "nova"})
    assert resp.status_code == 200
    assert resp.json()["titulo"] == "T"


# ---------- Histórico ----------

def test_historico_registra_criacao_e_mudancas(client, nova_tarefa):
    t = nova_tarefa("T", prioridade="ALTA")
    client.patch(f"/tarefas/{t['id']}", json={"status": "EM_ANDAMENTO", "data_prazo": "2026-11-20"})
    client.patch(f"/tarefas/{t['id']}", json={"status": "EM_ANDAMENTO"})  # sem mudança: não registra

    textos = [r["texto"] for r in client.get(f"/tarefas/{t['id']}/historico").json()]
    assert textos == [
        "Tarefa criada com status A fazer e prioridade Alta",
        "Status alterado de A fazer para Em andamento",
        "Prazo alterado de sem prazo para 20/11/2026",
    ]


def test_comentarios_da_tarefa(client, nova_tarefa):
    t = nova_tarefa("T")
    resp = client.post(
        f"/tarefas/{t['id']}/comentarios",
        json={"texto": "Cliente aprovou o criativo"},
        headers={"X-Forwarded-Email": "rodrigo@empresa.com"},
    )
    assert resp.status_code == 201
    comentario = resp.json()
    assert comentario["tipo"] == "COMENTARIO"
    assert comentario["autor"] == "rodrigo@empresa.com"
    client.post(f"/tarefas/{t['id']}/comentarios", json={"texto": "Segundo comentário"})

    historico = client.get(f"/tarefas/{t['id']}/historico").json()
    assert [r["tipo"] for r in historico] == ["SISTEMA", "COMENTARIO", "COMENTARIO"]
    assert client.get(f"/tarefas/{t['id']}").json()["total_comentarios"] == 2
    assert client.get("/tarefas").json()[0]["total_comentarios"] == 2

    assert client.post(f"/tarefas/{t['id']}/comentarios", json={"texto": "   "}).status_code == 409
    assert client.delete(f"/tarefas/{t['id']}/comentarios/{comentario['id']}").status_code == 204
    assert client.delete(f"/tarefas/{t['id']}/comentarios/{historico[0]['id']}").status_code == 409
    assert client.get(f"/tarefas/{t['id']}").json()["total_comentarios"] == 1


def test_excluir_tarefa_remove_historico(client, nova_tarefa):
    t = nova_tarefa("T")
    client.post(f"/tarefas/{t['id']}/comentarios", json={"texto": "x"})
    assert client.delete(f"/tarefas/{t['id']}").status_code == 204
    assert client.get(f"/tarefas/{t['id']}/historico").status_code == 404


# ---------- Exclusão de cliente ----------

def test_excluir_cliente_sem_tarefas(client, tipo_servico_id):
    c = client.post(
        "/clientes", json={"nome": "Só serviço", "servicos": [{"tipo_servico_id": tipo_servico_id, "valor": "10"}]}
    ).json()
    assert client.get(f"/clientes/{c['id']}/vinculos").json() == {"servicos": 1, "tarefas": 0, "comentarios": 0}
    assert client.delete(f"/clientes/{c['id']}").status_code == 204
    assert client.get(f"/clientes/{c['id']}").status_code == 404


def test_excluir_cliente_com_tarefas_exige_cascata(client, cliente_id, nova_tarefa):
    t = nova_tarefa("T")
    nova_tarefa("Outra")
    client.post(f"/tarefas/{t['id']}/comentarios", json={"texto": "nota"})
    assert client.get(f"/clientes/{cliente_id}/vinculos").json() == {"servicos": 1, "tarefas": 2, "comentarios": 1}

    resp = client.delete(f"/clientes/{cliente_id}")
    assert resp.status_code == 409
    assert "2 tarefa(s)" in resp.json()["detail"]
    assert client.get(f"/clientes/{cliente_id}").status_code == 200  # nada foi apagado

    assert client.delete(f"/clientes/{cliente_id}?cascata=true").status_code == 204
    assert client.get(f"/clientes/{cliente_id}").status_code == 404
    assert client.get(f"/tarefas/{t['id']}").status_code == 404
    assert client.get("/tarefas").json() == []


def test_excluir_cliente_nao_afeta_outros(client, cliente_id):
    outro = client.post("/clientes", json={"nome": "Outro"}).json()["id"]
    client.post("/tarefas", json={"cliente_id": outro, "titulo": "Fica"})
    client.delete(f"/clientes/{cliente_id}?cascata=true")
    assert [t["titulo"] for t in client.get("/tarefas").json()] == ["Fica"]


# ---------- Interface ----------

def test_interface_nao_fica_em_cache(client):
    for caminho in ("/", "/static/app.js", "/static/styles.css"):
        resp = client.get(caminho)
        assert resp.status_code == 200
        assert resp.headers["cache-control"] == "no-cache"
    assert "status-sel" in client.get("/static/app.js").text
