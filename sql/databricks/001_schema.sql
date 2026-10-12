-- Esquema do sistema de gestão de projetos em Databricks (Delta Lake + Unity Catalog).
-- {fq} é substituído pelo script de inicialização por `catalogo`.`schema`.
--
-- Observação: no Delta, PRIMARY KEY / FOREIGN KEY são *informativas* (não bloqueiam
-- dados inválidos). A integridade referencial e as regras de negócio são garantidas
-- pela aplicação (app/services.py). Já as CHECK constraints (002) SÃO validadas.

CREATE SCHEMA IF NOT EXISTS {fq};

CREATE TABLE IF NOT EXISTS {fq}.tipos_servico (
  id          STRING  NOT NULL,
  nome        STRING  NOT NULL,
  descricao   STRING,
  ativo       BOOLEAN NOT NULL,
  CONSTRAINT pk_tipos_servico PRIMARY KEY (id)
) USING DELTA
COMMENT 'Catálogo de tipos de serviço que podem ser contratados (ex.: Tráfego Pago, SEO)';

CREATE TABLE IF NOT EXISTS {fq}.clientes (
  id             STRING    NOT NULL,
  nome           STRING    NOT NULL,
  documento      STRING    COMMENT 'CPF ou CNPJ',
  email          STRING,
  telefone       STRING,
  data_cadastro  TIMESTAMP NOT NULL,
  ativo          BOOLEAN   NOT NULL,
  CONSTRAINT pk_clientes PRIMARY KEY (id)
) USING DELTA
COMMENT 'Clientes da empresa';

CREATE TABLE IF NOT EXISTS {fq}.cliente_servicos (
  id               STRING        NOT NULL,
  cliente_id       STRING        NOT NULL,
  tipo_servico_id  STRING        NOT NULL,
  valor            DECIMAL(12,2) NOT NULL COMMENT 'Valor contratado do serviço',
  data_inicio      DATE,
  ativo            BOOLEAN       NOT NULL,
  CONSTRAINT pk_cliente_servicos PRIMARY KEY (id),
  CONSTRAINT fk_cliente_servicos_cliente FOREIGN KEY (cliente_id) REFERENCES {fq}.clientes,
  CONSTRAINT fk_cliente_servicos_tipo FOREIGN KEY (tipo_servico_id) REFERENCES {fq}.tipos_servico
) USING DELTA
COMMENT 'Serviços contratados por cada cliente e seus valores';

CREATE TABLE IF NOT EXISTS {fq}.projetos (
  id                STRING    NOT NULL,
  cliente_id        STRING    NOT NULL,
  nome              STRING    NOT NULL,
  descricao         STRING,
  status            STRING    NOT NULL,
  data_criacao      TIMESTAMP NOT NULL,
  data_prazo        DATE,
  data_finalizacao  TIMESTAMP,
  CONSTRAINT pk_projetos PRIMARY KEY (id),
  CONSTRAINT fk_projetos_cliente FOREIGN KEY (cliente_id) REFERENCES {fq}.clientes
) USING DELTA
COMMENT 'Projetos (cada projeto pertence a um cliente)';

CREATE TABLE IF NOT EXISTS {fq}.tarefas (
  id                STRING    NOT NULL,
  cliente_id        STRING    NOT NULL,
  projeto_id        STRING    COMMENT 'Opcional: tarefa pode não estar alocada em projeto',
  titulo            STRING    NOT NULL,
  descricao         STRING,
  status            STRING    NOT NULL,
  prioridade        STRING    NOT NULL,
  data_criacao      TIMESTAMP NOT NULL,
  data_prazo        DATE,
  data_finalizacao  TIMESTAMP,
  CONSTRAINT pk_tarefas PRIMARY KEY (id),
  CONSTRAINT fk_tarefas_cliente FOREIGN KEY (cliente_id) REFERENCES {fq}.clientes,
  CONSTRAINT fk_tarefas_projeto FOREIGN KEY (projeto_id) REFERENCES {fq}.projetos
) USING DELTA
COMMENT 'Tarefas (pertencem a um cliente; o projeto é opcional)';

CREATE TABLE IF NOT EXISTS {fq}.tarefa_historico (
  id            STRING    NOT NULL,
  tarefa_id     STRING    NOT NULL,
  tipo          STRING    NOT NULL COMMENT 'COMENTARIO (escrito pelo usuário) ou SISTEMA (registro automático)',
  texto         STRING    NOT NULL,
  autor         STRING    COMMENT 'E-mail do usuário (preenchido automaticamente no Databricks App)',
  data_criacao  TIMESTAMP NOT NULL,
  CONSTRAINT pk_tarefa_historico PRIMARY KEY (id),
  CONSTRAINT fk_tarefa_historico_tarefa FOREIGN KEY (tarefa_id) REFERENCES {fq}.tarefas
) USING DELTA
COMMENT 'Histórico/documentação de cada tarefa: comentários e mudanças registradas pelo sistema';
