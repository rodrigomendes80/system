"""Bases SQLite criadas em versões anteriores são atualizadas sem perder tarefas."""
import sqlite3

from app.db.sqlite import SQLiteDatabase

CLIENTES_E_PROJETOS = """
CREATE TABLE clientes (id TEXT PRIMARY KEY, nome TEXT NOT NULL, documento TEXT, email TEXT,
  telefone TEXT, data_cadastro TEXT NOT NULL, ativo INTEGER NOT NULL);
CREATE TABLE projetos (id TEXT PRIMARY KEY, cliente_id TEXT NOT NULL REFERENCES clientes(id),
  nome TEXT NOT NULL, descricao TEXT, status TEXT NOT NULL, data_criacao TEXT NOT NULL,
  data_prazo TEXT, data_finalizacao TEXT);
INSERT INTO clientes VALUES ('c1', 'Cliente', NULL, NULL, NULL, '2026-01-01T00:00:00+00:00', 1);
INSERT INTO projetos VALUES ('p1', 'c1', 'Site novo', NULL, 'EM_ANDAMENTO', '2026-01-01T00:00:00+00:00', NULL, NULL);
"""


def _abrir(caminho):
    db = SQLiteDatabase(str(caminho))
    db.create_schema()
    db.create_schema()  # idempotente
    return db


def test_migra_base_com_projeto_opcional_e_historico(tmp_path):
    caminho = tmp_path / "v2.db"
    con = sqlite3.connect(caminho)
    con.executescript(
        CLIENTES_E_PROJETOS
        + """
        CREATE TABLE tarefas (id TEXT PRIMARY KEY, cliente_id TEXT NOT NULL REFERENCES clientes(id),
          projeto_id TEXT REFERENCES projetos(id), titulo TEXT NOT NULL, descricao TEXT,
          status TEXT NOT NULL, prioridade TEXT NOT NULL, data_criacao TEXT NOT NULL,
          data_prazo TEXT, data_finalizacao TEXT);
        CREATE TABLE tarefa_historico (id TEXT PRIMARY KEY, tarefa_id TEXT NOT NULL REFERENCES tarefas(id),
          tipo TEXT NOT NULL, texto TEXT NOT NULL, autor TEXT, data_criacao TEXT NOT NULL);
        INSERT INTO tarefas VALUES ('t1', 'c1', 'p1', 'No projeto', NULL, 'A_FAZER', 'MEDIA', '2026-01-02T00:00:00+00:00', NULL, NULL);
        INSERT INTO tarefas VALUES ('t2', 'c1', NULL, 'Avulsa', NULL, 'A_FAZER', 'BAIXA', '2026-01-02T00:00:00+00:00', NULL, NULL);
        INSERT INTO tarefa_historico VALUES ('h1', 't1', 'COMENTARIO', 'comentário antigo', NULL, '2026-01-03T00:00:00+00:00');
        """
    )
    con.close()

    db = _abrir(caminho)
    tarefas = db.fetch_all("SELECT * FROM tarefas ORDER BY id")
    assert [(t["id"], t["cliente_id"]) for t in tarefas] == [("t1", "c1"), ("t2", "c1")]
    assert "projeto_id" not in tarefas[0]
    assert db.fetch_one("SELECT name FROM sqlite_master WHERE name = 'projetos'") is None

    # Comentário antigo preservado e vínculo com o projeto registrado no histórico
    historico = db.fetch_all("SELECT tipo, texto FROM tarefa_historico WHERE tarefa_id = 't1' ORDER BY data_criacao")
    assert historico[0] == {"tipo": "COMENTARIO", "texto": "comentário antigo"}
    assert 'projeto "Site novo"' in historico[1]["texto"]
    assert db.fetch_all("SELECT * FROM tarefa_historico WHERE tarefa_id = 't2'") == []

    # Chaves estrangeiras continuam válidas
    assert db.fetch_all("PRAGMA foreign_key_check") == []
    db.close()


def test_migra_base_mais_antiga_sem_cliente_na_tarefa(tmp_path):
    caminho = tmp_path / "v1.db"
    con = sqlite3.connect(caminho)
    con.executescript(
        CLIENTES_E_PROJETOS
        + """
        CREATE TABLE tarefas (id TEXT PRIMARY KEY, projeto_id TEXT NOT NULL, titulo TEXT NOT NULL,
          descricao TEXT, status TEXT NOT NULL, prioridade TEXT NOT NULL, data_criacao TEXT NOT NULL,
          data_prazo TEXT, data_finalizacao TEXT);
        INSERT INTO tarefas VALUES ('t1', 'p1', 'Antiga', NULL, 'A_FAZER', 'MEDIA', '2026-01-01T00:00:00+00:00', NULL, NULL);
        """
    )
    con.close()

    db = _abrir(caminho)
    tarefa = db.fetch_one("SELECT * FROM tarefas WHERE id = 't1'")
    assert tarefa["cliente_id"] == "c1"
    assert db.fetch_one("SELECT name FROM sqlite_master WHERE name = 'projetos'") is None
    db.execute(
        "INSERT INTO tarefas (id, cliente_id, titulo, status, prioridade, data_criacao) "
        "VALUES ('t2', 'c1', 'Nova', 'A_FAZER', 'BAIXA', '2026-01-02T00:00:00+00:00')"
    )
    db.close()
