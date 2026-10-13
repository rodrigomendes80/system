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


def test_listagem_geral_de_tarefas_com_projeto_e_cliente(client, cliente_id, projeto_id):
    outro = client.post("/clientes", json={"nome": "Outro"}).json()["id"]
    outro_proj = client.post("/projetos", json={"cliente_id": outro, "nome": "P2"}).json()["id"]
    client.post(f"/projetos/{projeto_id}/tarefas", json={"titulo": "A", "prioridade": "BAIXA"})
    client.post(f"/projetos/{outro_proj}/tarefas", json={"titulo": "B", "prioridade": "URGENTE"})

    todas = client.get("/tarefas").json()
    assert [t["titulo"] for t in todas] == ["B", "A"]
    assert todas[1]["cliente_nome"] == "Loja Exemplo"
    assert todas[1]["projeto_nome"] == "Black Friday"

    so_cliente = client.get(f"/tarefas?cliente_id={cliente_id}").json()
    assert [t["titulo"] for t in so_cliente] == ["A"]
    assert len(client.get("/tarefas?prioridade=URGENTE").json()) == 1


def test_tarefa_sem_projeto(client, cliente_id, projeto_id):
    resp = client.post("/tarefas", json={"cliente_id": cliente_id, "titulo": "Avulsa", "prioridade": "ALTA"})
    assert resp.status_code == 201
    avulsa = resp.json()
    assert avulsa["projeto_id"] is None
    assert avulsa["cliente_id"] == cliente_id

    listada = next(t for t in client.get("/tarefas").json() if t["id"] == avulsa["id"])
    assert listada["projeto_nome"] is None
    assert listada["cliente_nome"] == "Loja Exemplo"
    assert [t["titulo"] for t in client.get("/tarefas?sem_projeto=true").json()] == ["Avulsa"]

    # Não entra na contagem de nenhum projeto
    assert client.get(f"/projetos/{projeto_id}").json()["total_tarefas"] == 0

    # Depois pode ser alocada em um projeto do mesmo cliente...
    alocada = client.patch(f"/tarefas/{avulsa['id']}", json={"projeto_id": projeto_id}).json()
    assert alocada["projeto_id"] == projeto_id
    assert client.get(f"/projetos/{projeto_id}").json()["total_tarefas"] == 1
    # ...e removida dele
    assert client.patch(f"/tarefas/{avulsa['id']}", json={"projeto_id": None}).json()["projeto_id"] is None


def test_tarefa_com_projeto_de_outro_cliente_e_recusada(client, projeto_id):
    outro = client.post("/clientes", json={"nome": "Outro"}).json()["id"]
    resp = client.post("/tarefas", json={"cliente_id": outro, "projeto_id": projeto_id, "titulo": "X"})
    assert resp.status_code == 409


def test_nao_aloca_tarefa_em_projeto_finalizado(client, cliente_id, projeto_id):
    client.post(f"/projetos/{projeto_id}/tarefas", json={"titulo": "T", "status": "FINALIZADA"})
    client.post(f"/projetos/{projeto_id}/finalizar")
    resp = client.post("/tarefas", json={"cliente_id": cliente_id, "projeto_id": projeto_id, "titulo": "X"})
    assert resp.status_code == 409
    avulsa = client.post("/tarefas", json={"cliente_id": cliente_id, "titulo": "Y"}).json()
    assert client.patch(f"/tarefas/{avulsa['id']}", json={"projeto_id": projeto_id}).status_code == 409


def test_migracao_de_base_antiga(tmp_path):
    """Bases criadas quando a tarefa exigia projeto são migradas sem perder dados."""
    import sqlite3

    from app.db.sqlite import SQLiteDatabase

    caminho = tmp_path / "antiga.db"
    con = sqlite3.connect(caminho)
    con.executescript(
        """
        CREATE TABLE clientes (id TEXT PRIMARY KEY, nome TEXT NOT NULL, documento TEXT, email TEXT,
          telefone TEXT, data_cadastro TEXT NOT NULL, ativo INTEGER NOT NULL);
        CREATE TABLE projetos (id TEXT PRIMARY KEY, cliente_id TEXT NOT NULL, nome TEXT NOT NULL,
          descricao TEXT, status TEXT NOT NULL, data_criacao TEXT NOT NULL, data_prazo TEXT,
          data_finalizacao TEXT);
        CREATE TABLE tarefas (id TEXT PRIMARY KEY, projeto_id TEXT NOT NULL, titulo TEXT NOT NULL,
          descricao TEXT, status TEXT NOT NULL, prioridade TEXT NOT NULL, data_criacao TEXT NOT NULL,
          data_prazo TEXT, data_finalizacao TEXT);
        INSERT INTO clientes VALUES ('c1', 'Cliente', NULL, NULL, NULL, '2026-01-01T00:00:00+00:00', 1);
        INSERT INTO projetos VALUES ('p1', 'c1', 'Proj', NULL, 'EM_ANDAMENTO', '2026-01-01T00:00:00+00:00', NULL, NULL);
        INSERT INTO tarefas VALUES ('t1', 'p1', 'Antiga', NULL, 'A_FAZER', 'MEDIA', '2026-01-01T00:00:00+00:00', NULL, NULL);
        """
    )
    con.close()

    db = SQLiteDatabase(str(caminho))
    db.create_schema()
    db.create_schema()  # idempotente
    tarefa = db.fetch_one("SELECT * FROM tarefas WHERE id = 't1'")
    assert tarefa["cliente_id"] == "c1" and tarefa["projeto_id"] == "p1"
    db.execute(
        "INSERT INTO tarefas (id, cliente_id, projeto_id, titulo, status, prioridade, data_criacao) "
        "VALUES ('t2', 'c1', NULL, 'Sem projeto', 'A_FAZER', 'BAIXA', '2026-01-02T00:00:00+00:00')"
    )
    db.close()


def test_historico_registra_criacao_e_mudancas(client, cliente_id, projeto_id):
    t = client.post(f"/projetos/{projeto_id}/tarefas", json={"titulo": "T", "prioridade": "ALTA"}).json()
    client.patch(f"/tarefas/{t['id']}", json={"status": "EM_ANDAMENTO", "data_prazo": "2026-11-20"})
    client.patch(f"/tarefas/{t['id']}", json={"projeto_id": None})
    client.patch(f"/tarefas/{t['id']}", json={"status": "EM_ANDAMENTO"})  # sem mudança: não registra

    textos = [r["texto"] for r in client.get(f"/tarefas/{t['id']}/historico").json()]
    assert textos == [
        "Tarefa criada com status A fazer e prioridade Alta",
        "Status alterado de A fazer para Em andamento",
        "Prazo alterado de sem prazo para 20/11/2026",
        "Projeto alterado de Black Friday para Sem projeto",
    ]


def test_comentarios_da_tarefa(client, projeto_id):
    t = client.post(f"/projetos/{projeto_id}/tarefas", json={"titulo": "T"}).json()
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

    # Comentário em branco é recusado
    assert client.post(f"/tarefas/{t['id']}/comentarios", json={"texto": "   "}).status_code == 409
    # Comentário pode ser excluído; registro do sistema não
    assert client.delete(f"/tarefas/{t['id']}/comentarios/{comentario['id']}").status_code == 204
    assert client.delete(f"/tarefas/{t['id']}/comentarios/{historico[0]['id']}").status_code == 409
    assert client.get(f"/tarefas/{t['id']}").json()["total_comentarios"] == 1


def test_comentar_em_tarefa_de_projeto_finalizado(client, projeto_id):
    t = client.post(f"/projetos/{projeto_id}/tarefas", json={"titulo": "T", "status": "FINALIZADA"}).json()
    client.post(f"/projetos/{projeto_id}/finalizar")
    resp = client.post(f"/tarefas/{t['id']}/comentarios", json={"texto": "Documentação pós-entrega"})
    assert resp.status_code == 201


def test_excluir_tarefa_remove_historico(client, projeto_id):
    t = client.post(f"/projetos/{projeto_id}/tarefas", json={"titulo": "T"}).json()
    client.post(f"/tarefas/{t['id']}/comentarios", json={"texto": "x"})
    assert client.delete(f"/tarefas/{t['id']}").status_code == 204
    assert client.get(f"/tarefas/{t['id']}/historico").status_code == 404


def test_excluir_cliente_sem_vinculos(client, tipo_servico_id):
    c = client.post(
        "/clientes", json={"nome": "Só serviço", "servicos": [{"tipo_servico_id": tipo_servico_id, "valor": "10"}]}
    ).json()
    assert client.get(f"/clientes/{c['id']}/vinculos").json() == {
        "servicos": 1, "projetos": 0, "tarefas": 0, "comentarios": 0
    }
    assert client.delete(f"/clientes/{c['id']}").status_code == 204
    assert client.get(f"/clientes/{c['id']}").status_code == 404


def test_excluir_cliente_com_vinculos_exige_cascata(client, cliente_id, projeto_id):
    t = client.post(f"/projetos/{projeto_id}/tarefas", json={"titulo": "T"}).json()
    client.post("/tarefas", json={"cliente_id": cliente_id, "titulo": "Avulsa"})
    client.post(f"/tarefas/{t['id']}/comentarios", json={"texto": "nota"})
    assert client.get(f"/clientes/{cliente_id}/vinculos").json() == {
        "servicos": 1, "projetos": 1, "tarefas": 2, "comentarios": 1
    }

    resp = client.delete(f"/clientes/{cliente_id}")
    assert resp.status_code == 409
    assert "1 projeto(s) e 2 tarefa(s)" in resp.json()["detail"]
    assert client.get(f"/clientes/{cliente_id}").status_code == 200  # nada foi apagado

    assert client.delete(f"/clientes/{cliente_id}?cascata=true").status_code == 204
    assert client.get(f"/clientes/{cliente_id}").status_code == 404
    assert client.get(f"/projetos/{projeto_id}").status_code == 404
    assert client.get(f"/tarefas/{t['id']}").status_code == 404
    assert client.get("/tarefas").json() == []


def test_excluir_cliente_nao_afeta_outros(client, cliente_id):
    outro = client.post("/clientes", json={"nome": "Outro"}).json()["id"]
    p = client.post("/projetos", json={"cliente_id": outro, "nome": "P"}).json()["id"]
    client.post(f"/projetos/{p}/tarefas", json={"titulo": "Fica"})
    client.delete(f"/clientes/{cliente_id}?cascata=true")
    assert [t["titulo"] for t in client.get("/tarefas").json()] == ["Fica"]


def test_interface_nao_fica_em_cache(client):
    for caminho in ("/", "/static/app.js", "/static/styles.css"):
        resp = client.get(caminho)
        assert resp.status_code == 200
        assert resp.headers["cache-control"] == "no-cache"
    assert "status-sel" in client.get("/static/app.js").text
