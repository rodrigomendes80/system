# Gestão de Projetos e Tarefas

API para gerenciar **Clientes → Projetos → Tarefas**, com persistência em **Databricks**
(Delta Tables via SQL Warehouse). Feita em Python/FastAPI, pronta para desenvolver no VS Code.

## Modelo de dados

```
tipos_servico 1───N cliente_servicos N───1 clientes 1───N projetos 1───N tarefas
```

| Entidade | Campos principais |
|---|---|
| **Cliente** | nome, documento (CPF/CNPJ), e-mail, telefone, **data de cadastro**, ativo |
| **Serviço contratado** | cliente, **tipo de serviço**, **valor**, data de início, ativo |
| **Tipo de serviço** | catálogo (Tráfego Pago, SEO, Social Media, …) |
| **Projeto** | cliente, nome, descrição, status, data de criação, prazo, data de finalização |
| **Tarefa** | projeto, título, descrição, **status**, **prioridade**, **data de criação**, prazo, **data de finalização** |

- Status do projeto: `PLANEJAMENTO`, `EM_ANDAMENTO`, `FINALIZADO`
- Status da tarefa: `A_FAZER`, `EM_ANDAMENTO`, `BLOQUEADA`, `FINALIZADA`
- Prioridade: `BAIXA`, `MEDIA`, `ALTA`, `URGENTE`

O cliente retorna também `valor_total_servicos` (soma dos serviços ativos) e o projeto retorna
`total_tarefas`, `tarefas_finalizadas` e `percentual_concluido`.

## Regras de negócio

1. Projeto pertence a um cliente existente e ativo; tarefa pertence a um projeto existente.
2. **Projeto só é finalizado quando todas as suas tarefas estão `FINALIZADA`**
   (projeto sem tarefas também não finaliza). Caso contrário, a API responde `409` informando
   quantas tarefas estão pendentes.
3. Projeto finalizado fica bloqueado: não aceita criar, alterar ou excluir tarefas.
   Para mexer, use `POST /projetos/{id}/reabrir`.
4. A **data de finalização da tarefa** é preenchida automaticamente ao mudar o status para
   `FINALIZADA` e limpa se a tarefa for reaberta. O mesmo vale para o projeto.
5. Serviços contratados não são apagados: ao encerrar, ficam inativos (histórico preservado)
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

Abra http://localhost:8000/docs para testar todos os endpoints pelo navegador (Swagger).
No VS Code também há as configurações de execução **"API (uvicorn)"** e **"Inicializar banco"**
(aba Run and Debug), e exemplos de chamadas em [`requests.http`](requests.http).

### Desenvolvimento local x Databricks

- `DB_BACKEND=sqlite` → usa um arquivo SQLite local (rápido para desenvolver, sem custo de warehouse).
- `DB_BACKEND=databricks` → usa o Databricks. Preencha no `.env`:
  - `DATABRICKS_SERVER_HOSTNAME` e `DATABRICKS_HTTP_PATH`: em *SQL Warehouses → seu warehouse → Connection details*
  - `DATABRICKS_TOKEN`: token pessoal (PAT). Se ficar vazio, abre o login OAuth no navegador.
  - `DATABRICKS_CATALOG` / `DATABRICKS_SCHEMA`: onde as tabelas serão criadas (o schema é criado se não existir).

O DDL do Databricks está em [`sql/databricks/`](sql/databricks/) e pode também ser executado
manualmente no SQL Editor (substituindo `{fq}` por `catalogo.schema`).

> **Sobre o Databricks:** em Delta Tables, `PRIMARY KEY` e `FOREIGN KEY` são apenas informativas
> (exigem Unity Catalog e não bloqueiam dados inválidos); por isso a integridade é garantida pela
> aplicação. As `CHECK` constraints de status, prioridade e valor **são** validadas pelo Delta.

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
| GET/PATCH/DELETE | `/tarefas/{id}` | Consulta / altera / exclui tarefa |

## Estrutura

```
app/
  main.py          # aplicação FastAPI
  models.py        # entidades, enums e validações
  services.py      # regras de negócio
  repositories.py  # SQL
  db/              # conexão Databricks e SQLite
  routers/         # endpoints
sql/databricks/    # DDL Delta (tabelas + constraints)
sql/sqlite/        # DDL local
scripts/init_db.py # cria tabelas e dados iniciais
tests/             # testes automatizados
```
