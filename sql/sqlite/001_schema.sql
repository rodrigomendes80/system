-- Esquema equivalente em SQLite, usado em desenvolvimento local e nos testes.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tipos_servico (
  id         TEXT PRIMARY KEY,
  nome       TEXT NOT NULL,
  descricao  TEXT,
  ativo      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS clientes (
  id             TEXT PRIMARY KEY,
  nome           TEXT NOT NULL,
  documento      TEXT,
  email          TEXT,
  telefone       TEXT,
  data_cadastro  TEXT NOT NULL,
  ativo          INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cliente_servicos (
  id               TEXT PRIMARY KEY,
  cliente_id       TEXT NOT NULL REFERENCES clientes(id),
  tipo_servico_id  TEXT NOT NULL REFERENCES tipos_servico(id),
  valor            NUMERIC NOT NULL CHECK (valor >= 0),
  data_inicio      TEXT,
  ativo            INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS projetos (
  id                TEXT PRIMARY KEY,
  cliente_id        TEXT NOT NULL REFERENCES clientes(id),
  nome              TEXT NOT NULL,
  descricao         TEXT,
  status            TEXT NOT NULL CHECK (status IN ('PLANEJAMENTO', 'EM_ANDAMENTO', 'FINALIZADO')),
  data_criacao      TEXT NOT NULL,
  data_prazo        TEXT,
  data_finalizacao  TEXT
);

-- A tarefa pertence a um cliente; o projeto é opcional.
CREATE TABLE IF NOT EXISTS tarefas (
  id                TEXT PRIMARY KEY,
  cliente_id        TEXT NOT NULL REFERENCES clientes(id),
  projeto_id        TEXT REFERENCES projetos(id),
  titulo            TEXT NOT NULL,
  descricao         TEXT,
  status            TEXT NOT NULL CHECK (status IN ('A_FAZER', 'EM_ANDAMENTO', 'BLOQUEADA', 'FINALIZADA')),
  prioridade        TEXT NOT NULL CHECK (prioridade IN ('BAIXA', 'MEDIA', 'ALTA', 'URGENTE')),
  data_criacao      TEXT NOT NULL,
  data_prazo        TEXT,
  data_finalizacao  TEXT
);

-- Histórico da tarefa: comentários do usuário e registros automáticos do sistema
CREATE TABLE IF NOT EXISTS tarefa_historico (
  id            TEXT PRIMARY KEY,
  tarefa_id     TEXT NOT NULL REFERENCES tarefas(id),
  tipo          TEXT NOT NULL CHECK (tipo IN ('COMENTARIO', 'SISTEMA')),
  texto         TEXT NOT NULL,
  autor         TEXT,
  data_criacao  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tarefa_historico_tarefa ON tarefa_historico (tarefa_id, data_criacao);
