from decimal import Decimal


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


def test_projeto_pertence_a_cliente_existente(client):
    resp = client.post("/projetos", json={"cliente_id": "nao-existe", "nome": "P"})
    assert resp.status_code == 404


def test_tarefa_tem_datas_status_e_prioridade(client, projeto_id):
    tarefa = client.post(
        f"/projetos/{projeto_id}/tarefas", json={"titulo": "Criar campanha", "prioridade": "ALTA"}
    ).json()
    assert tarefa["status"] == "A_FAZER"
    assert tarefa["prioridade"] == "ALTA"
    assert tarefa["data_criacao"]
    assert tarefa["data_finalizacao"] is None

    tarefa = client.patch(f"/tarefas/{tarefa['id']}", json={"status": "FINALIZADA"}).json()
    assert tarefa["data_finalizacao"] is not None

    # Reabrir a tarefa limpa a data de finalização
    tarefa = client.patch(f"/tarefas/{tarefa['id']}", json={"status": "EM_ANDAMENTO"}).json()
    assert tarefa["data_finalizacao"] is None


def test_projeto_so_finaliza_com_todas_tarefas_finalizadas(client, projeto_id):
    # Sem tarefas: não finaliza
    assert client.post(f"/projetos/{projeto_id}/finalizar").status_code == 409

    t1 = client.post(f"/projetos/{projeto_id}/tarefas", json={"titulo": "T1"}).json()
    t2 = client.post(f"/projetos/{projeto_id}/tarefas", json={"titulo": "T2"}).json()
    client.patch(f"/tarefas/{t1['id']}", json={"status": "FINALIZADA"})

    # 1 de 2 finalizadas: não finaliza
    resp = client.post(f"/projetos/{projeto_id}/finalizar")
    assert resp.status_code == 409
    assert "1 tarefa(s) não finalizada(s)" in resp.json()["detail"]

    # Também não finaliza via PATCH de status
    assert client.patch(f"/projetos/{projeto_id}", json={"status": "FINALIZADO"}).status_code == 409

    projeto = client.get(f"/projetos/{projeto_id}").json()
    assert projeto["percentual_concluido"] == 50.0

    client.patch(f"/tarefas/{t2['id']}", json={"status": "FINALIZADA"})
    projeto = client.post(f"/projetos/{projeto_id}/finalizar").json()
    assert projeto["status"] == "FINALIZADO"
    assert projeto["data_finalizacao"] is not None
    assert projeto["percentual_concluido"] == 100.0


def test_projeto_finalizado_bloqueia_tarefas_ate_reabrir(client, projeto_id):
    t = client.post(f"/projetos/{projeto_id}/tarefas", json={"titulo": "T", "status": "FINALIZADA"}).json()
    client.post(f"/projetos/{projeto_id}/finalizar")

    assert client.post(f"/projetos/{projeto_id}/tarefas", json={"titulo": "Nova"}).status_code == 409
    assert client.patch(f"/tarefas/{t['id']}", json={"status": "A_FAZER"}).status_code == 409
    assert client.delete(f"/tarefas/{t['id']}").status_code == 409

    projeto = client.post(f"/projetos/{projeto_id}/reabrir").json()
    assert projeto["status"] == "EM_ANDAMENTO"
    assert projeto["data_finalizacao"] is None
    assert client.post(f"/projetos/{projeto_id}/tarefas", json={"titulo": "Nova"}).status_code == 201


def test_listagens_e_filtros(client, cliente_id, projeto_id):
    client.post(f"/projetos/{projeto_id}/tarefas", json={"titulo": "Baixa", "prioridade": "BAIXA"})
    client.post(f"/projetos/{projeto_id}/tarefas", json={"titulo": "Urgente", "prioridade": "URGENTE"})

    tarefas = client.get(f"/projetos/{projeto_id}/tarefas").json()
    assert [t["titulo"] for t in tarefas] == ["Urgente", "Baixa"]  # ordenado por prioridade
    assert len(client.get(f"/projetos/{projeto_id}/tarefas?prioridade=BAIXA").json()) == 1

    assert len(client.get(f"/clientes/{cliente_id}/projetos").json()) == 1
    assert len(client.get("/projetos?status=FINALIZADO").json()) == 0


def test_cliente_inativo_nao_recebe_projeto(client, cliente_id):
    client.patch(f"/clientes/{cliente_id}", json={"ativo": False})
    resp = client.post("/projetos", json={"cliente_id": cliente_id, "nome": "P"})
    assert resp.status_code == 409


def test_patch_com_null_em_campo_obrigatorio_e_ignorado(client, projeto_id):
    t = client.post(f"/projetos/{projeto_id}/tarefas", json={"titulo": "T"}).json()
    resp = client.patch(f"/tarefas/{t['id']}", json={"titulo": None, "descricao": "nova"})
    assert resp.status_code == 200
    assert resp.json()["titulo"] == "T"
