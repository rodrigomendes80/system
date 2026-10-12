# Gestão de Projetos e Tarefas

Sistema para gerenciar **Clientes → Projetos → Tarefas**, com persistência em **Databricks**
(Delta Tables via SQL Warehouse). Backend em Python/FastAPI + interface web, pronto para
desenvolver no VS Code e publicar como **Databricks App**.

## Telas

| Endereço | O que mostra |
|---|---|
| `/` → **Projetos** | Indicadores (clientes ativos, receita contratada, projetos em aberto/atrasados), filtros por cliente e status, cards com % de conclusão |
| **Projeto** | Quadro (kanban) com as tarefas por status — arraste entre colunas ou troque no seletor —, prioridade, datas, botões Finalizar/Reabrir |
| **Clientes** | Totalizador (valor contratado, ticket médio, clientes e serviços ativos), valor por tipo de serviço, lista com total; cadastro com vários serviços |
| **Tarefa** (clique no título) | Dados da tarefa e **histórico**: comentários para documentar o andamento + registros automáticos de mudanças (status, prioridade, prazo, projeto) |
| **Tarefas** | Todas as tarefas em **lista ou kanban**, indicadores (para hoje, por status, atrasadas), filtros por cliente, projeto, status, prioridade e prazo (para hoje, atrasadas, próximos 7 dias); nova tarefa escolhendo cliente e projeto |
| **Cliente** | Dados, serviços (contratar/encerrar) e projetos do cliente |
| `/docs` | Documentação e testes da API |

## Modelo de dados

```
tipos_servico 1───N cliente_servicos N───1 clientes 1───N projetos 1───N tarefas
                                              clientes 1───N tarefas   (o projeto da tarefa é opcional)
```

| Entidade | Campos principais |
|---|---|
| **Cliente** | nome, documento (CPF/CNPJ), e-mail, telefone, **data de cadastro**, ativo |
| **Serviço contratado** | cliente, **tipo de serviço**, **valor**, data de início, ativo |
| **Tipo de serviço** | catálogo (Tráfego Pago, SEO, Social Media, …) |
| **Projeto** | cliente, nome, descrição, status, data de criação, prazo, data de finalização |
| **Tarefa** | cliente, projeto (opcional), título, descrição, **status**, **prioridade**, **data de criação**, prazo, **data de finalização** |

- Status do projeto: `PLANEJAMENTO`, `EM_ANDAMENTO`, `FINALIZADO`
- Status da tarefa: `A_FAZER`, `EM_ANDAMENTO`, `BLOQUEADA`, `FINALIZADA`
- Prioridade: `BAIXA`, `MEDIA`, `ALTA`, `URGENTE`

O cliente retorna também `valor_total_servicos` (soma dos serviços ativos) e o projeto retorna
`total_tarefas`, `tarefas_finalizadas` e `percentual_concluido`.

## Regras de negócio

1. Projeto pertence a um cliente existente e ativo. Tarefa pertence a um cliente e pode ou não
   estar alocada em um projeto **desse mesmo cliente** (pode ser alocada/removida depois).
2. **Projeto só é finalizado quando todas as suas tarefas estão `FINALIZADA`**
   (projeto sem tarefas também não finaliza). Caso contrário, a API responde `409` informando
   quantas tarefas estão pendentes.
3. Projeto finalizado fica bloqueado: não aceita criar, alterar, mover ou excluir tarefas.
   Para mexer, use `POST /projetos/{id}/reabrir`.
4. A **data de finalização da tarefa** é preenchida automaticamente ao mudar o status para
   `FINALIZADA` e limpa se a tarefa for reaberta. O mesmo vale para o projeto.
5. Cada tarefa tem um **histórico**: os comentários do usuário e os registros automáticos de
   criação e mudanças. Registros automáticos não podem ser excluídos; comentários podem. Comentários
   são permitidos mesmo em tarefas de projeto finalizado. No Databricks App o autor é preenchido
   com o e-mail do usuário logado.
6. Serviços contratados não são apagados: ao encerrar, ficam inativos (histórico preservado)
   e saem do valor total.

As regras ficam em [`app/services.py`](app/services.py).

## Como rodar no VS Code

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env               # e ajuste as variáveis
python -m scripts.init_db          # cria as tabelas e os tipos de serviço iniciais
uvicorn app.main:app --reload
```

Abra **http://localhost:8000** para usar o sistema, ou http://localhost:8000/docs para a API.
No VS Code também há as configurações de execução **"API (uvicorn)"** e **"Inicializar banco"**
(aba Run and Debug), e exemplos de chamadas em [`requests.http`](requests.http).

### Configuração do banco (`.env`)

- `DB_BACKEND=databricks` (padrão) → usa o Databricks. Preencha:
  - `DATABRICKS_SERVER_HOSTNAME` e `DATABRICKS_HTTP_PATH`: em *SQL Warehouses → seu warehouse → Connection details*
  - `DATABRICKS_TOKEN`: token pessoal (PAT). Se ficar vazio, abre o login OAuth no navegador.
  - `DATABRICKS_CATALOG` / `DATABRICKS_SCHEMA`: onde as tabelas serão criadas (o schema é criado se não existir).

- `DB_BACKEND=sqlite` → arquivo SQLite local, útil só para testar sem consumir o warehouse.

O DDL do Databricks está em [`sql/databricks/`](sql/databricks/) e pode também ser executado
manualmente no SQL Editor (substituindo `{fq}` por `catalogo.schema`).

> **Sobre o Databricks:** em Delta Tables, `PRIMARY KEY` e `FOREIGN KEY` são apenas informativas
> (exigem Unity Catalog e não bloqueiam dados inválidos); por isso a integridade é garantida pela
> aplicação. As `CHECK` constraints de status, prioridade e valor **são** validadas pelo Delta.

## Publicar como Databricks App

O sistema roda dentro do Databricks, acessível pelo navegador para quem tem acesso ao workspace
(login do próprio Databricks). A configuração está em [`app.yaml`](app.yaml).

1. **Crie as tabelas** uma vez, a partir do VS Code, com o `.env` apontando para o Databricks:
   `python -m scripts.init_db`
2. **Crie o app** no workspace: *Compute → Apps → Create app → Custom*. Em *App resources*,
   adicione um **SQL warehouse** com a chave `sql-warehouse` e permissão **Can use**.
3. **Dê acesso às tabelas** ao service principal do app (o ID aparece na página do app), no SQL Editor:
   ```sql
   GRANT USE CATALOG ON CATALOG main TO `<id-do-service-principal>`;
   GRANT USE SCHEMA, SELECT, MODIFY ON SCHEMA main.gestao_projetos TO `<id-do-service-principal>`;
   ```
4. **Envie o código e publique** (Databricks CLI):
   ```bash
   databricks sync . /Workspace/Users/<seu-email>/gestao-projetos
   databricks apps deploy <nome-do-app> --source-code-path /Workspace/Users/<seu-email>/gestao-projetos
   ```
5. Abra a URL exibida na página do app.

Se usar outro catálogo/schema, ajuste `DATABRICKS_CATALOG` e `DATABRICKS_SCHEMA` no `app.yaml`
e nos comandos `GRANT`.

## Testes

```bash
pytest
```

Os testes usam SQLite em memória e cobrem as regras acima.

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET/POST | `/tipos-servico` | Catálogo de tipos de serviço |
| GET/POST | `/clientes` | Lista (filtro `ativo`) / cadastra cliente (com serviços) |
| GET/PATCH | `/clientes/{id}` | Consulta / altera cliente (inclusive inativar) |
| POST | `/clientes/{id}/servicos` | Contrata novo serviço |
| DELETE | `/clientes/{id}/servicos/{servico_id}` | Encerra serviço (mantém histórico) |
| GET | `/clientes/{id}/projetos` | Projetos do cliente |
| GET/POST | `/projetos` | Lista (filtros `cliente_id`, `status`) / cria projeto |
| GET/PATCH | `/projetos/{id}` | Consulta / altera projeto |
| POST | `/projetos/{id}/finalizar` | Finaliza (só se todas as tarefas estiverem finalizadas) |
| POST | `/projetos/{id}/reabrir` | Reabre projeto finalizado |
| GET/POST | `/projetos/{id}/tarefas` | Lista (filtros `status`, `prioridade`) / cria tarefa |
| GET | `/tarefas` | Todas as tarefas com projeto e cliente (filtros `cliente_id`, `projeto_id`, `sem_projeto`, `status`, `prioridade`) |
| POST | `/tarefas` | Cria tarefa para um cliente, com ou sem `projeto_id` |
| GET | `/tarefas/{id}/historico` | Comentários e registros automáticos da tarefa |
| POST | `/tarefas/{id}/comentarios` | Adiciona comentário |
| DELETE | `/tarefas/{id}/comentarios/{comentario_id}` | Exclui comentário |
| GET/PATCH/DELETE | `/tarefas/{id}` | Consulta / altera / exclui tarefa |

## Estrutura

```
app/
  main.py          # aplicação FastAPI
  static/          # interface web (HTML, CSS, JS)
  models.py        # entidades, enums e validações
  services.py      # regras de negócio
  repositories.py  # SQL
  db/              # conexão Databricks e SQLite
  routers/         # endpoints
sql/databricks/    # DDL Delta (tabelas + constraints)
sql/sqlite/        # DDL local
scripts/init_db.py # cria tabelas e dados iniciais
app.yaml           # configuração do Databricks App
tests/             # testes automatizados
```
