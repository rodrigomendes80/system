"use strict";

// ---------- Rótulos e formatação ----------

const STATUS_PROJETO = {
  PLANEJAMENTO: ["Planejamento", "b-info"],
  EM_ANDAMENTO: ["Em andamento", "b-warn"],
  FINALIZADO: ["Finalizado", "b-ok"],
};
const STATUS_TAREFA = {
  A_FAZER: ["A fazer", ""],
  EM_ANDAMENTO: ["Em andamento", "b-warn"],
  BLOQUEADA: ["Bloqueada", "b-danger"],
  FINALIZADA: ["Finalizada", "b-ok"],
};
const PRIORIDADE = {
  URGENTE: ["Urgente", "b-danger"],
  ALTA: ["Alta", "b-warn"],
  MEDIA: ["Média", "b-info"],
  BAIXA: ["Baixa", ""],
};

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const badge = (map, key) => `<span class="badge ${map[key]?.[1] ?? ""}">${esc(map[key]?.[0] ?? key)}</span>`;
const fmtData = (d) => (d ? d.slice(0, 10).split("-").reverse().join("/") : "—");
const fmtDataHora = (d) =>
  d ? new Date(d).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";
const hoje = () => new Date().toLocaleDateString("sv-SE"); // AAAA-MM-DD no fuso local
const atrasada = (prazo, finalizado) => prazo && !finalizado && prazo < hoje();
const options = (map, selected) =>
  Object.entries(map)
    .map(([k, [label]]) => `<option value="${k}" ${k === selected ? "selected" : ""}>${label}</option>`)
    .join("");

// ---------- API ----------

async function api(path, { method = "GET", body } = {}) {
  const resp = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (resp.status === 204) return null;
  const data = await resp.json().catch(() => null);
  if (!resp.ok) {
    let msg = data?.detail;
    if (Array.isArray(msg)) msg = msg.map((e) => `${e.loc.at(-1)}: ${e.msg}`).join("; ");
    throw new Error(msg || `Erro ${resp.status}`);
  }
  return data;
}

// ---------- UI utilitária ----------

const $app = document.getElementById("app");
let toastTimer;

function toast(msg, ok = false) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = "toast" + (ok ? " ok" : "");
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 5000);
}

async function acao(fn, sucesso) {
  try {
    await fn();
    if (sucesso) toast(sucesso, true);
    await render();
  } catch (e) {
    toast(e.message);
  }
}

/** Abre um formulário em modal. onSubmit(dados, form) deve lançar erro para manter o modal aberto. */
function abrirFormulario(titulo, corpoHtml, onSubmit, aoAbrir) {
  const dialog = document.getElementById("modal");
  const form = document.getElementById("modal-form");
  document.getElementById("modal-title").textContent = titulo;
  document.getElementById("modal-body").innerHTML = corpoHtml;
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const dados = Object.fromEntries(new FormData(form));
    for (const k of Object.keys(dados)) if (dados[k] === "") dados[k] = null;
    try {
      await onSubmit(dados, form);
      dialog.close();
      await render();
    } catch (e) {
      toast(e.message);
    }
  };
  document.getElementById("modal-cancel").onclick = () => dialog.close();
  aoAbrir?.(form);
  dialog.showModal();
}

const campo = (label, input) => `<div class="field"><label>${label}</label>${input}</div>`;

// ---------- Projetos ----------

const filtros = { cliente_id: "", status: "" };

function cardProjeto(p, nomeCliente) {
  const finalizado = p.status === "FINALIZADO";
  return `
    <a class="card" href="#/projetos/${p.id}">
      <div class="top"><h3>${esc(p.nome)}</h3>${badge(STATUS_PROJETO, p.status)}</div>
      <div class="sub">${esc(nomeCliente ?? "")}</div>
      <div class="progress ${finalizado ? "done" : ""}"><span style="width:${p.percentual_concluido}%"></span></div>
      <div class="foot">
        <span>${p.tarefas_finalizadas}/${p.total_tarefas} tarefas · ${p.percentual_concluido}%</span>
        <span class="${atrasada(p.data_prazo, finalizado) ? "late" : ""}">Prazo: ${fmtData(p.data_prazo)}</span>
      </div>
    </a>`;
}

function formProjeto(clientes, p = {}) {
  const opcoesCliente = clientes
    .filter((c) => c.ativo || c.id === p.cliente_id)
    .map((c) => `<option value="${c.id}" ${c.id === p.cliente_id ? "selected" : ""}>${esc(c.nome)}</option>`)
    .join("");
  const statusEditaveis = { PLANEJAMENTO: STATUS_PROJETO.PLANEJAMENTO, EM_ANDAMENTO: STATUS_PROJETO.EM_ANDAMENTO };
  return (
    (p.id ? "" : campo("Cliente", `<select name="cliente_id" required>${opcoesCliente}</select>`)) +
    campo("Nome", `<input name="nome" required value="${esc(p.nome)}">`) +
    campo("Descrição", `<textarea name="descricao">${esc(p.descricao)}</textarea>`) +
    `<div class="row-2">` +
    campo("Prazo", `<input type="date" name="data_prazo" value="${esc(p.data_prazo)}">`) +
    campo("Status", `<select name="status">${options(statusEditaveis, p.status ?? "PLANEJAMENTO")}</select>`) +
    `</div>`
  );
}

async function viewProjetos() {
  const qs = new URLSearchParams(Object.entries(filtros).filter(([, v]) => v)).toString();
  const [clientes, projetos, todos] = await Promise.all([
    api("/clientes"),
    api("/projetos" + (qs ? `?${qs}` : "")),
    api("/projetos"),
  ]);
  const nomes = Object.fromEntries(clientes.map((c) => [c.id, c.nome]));
  const ativos = clientes.filter((c) => c.ativo);
  const receita = ativos.reduce((s, c) => s + Number(c.valor_total_servicos), 0);
  const abertos = todos.filter((p) => p.status !== "FINALIZADO");

  $app.innerHTML = `
    <div class="page-head">
      <h1>Projetos</h1>
      <div class="toolbar">
        <select id="f-cliente"><option value="">Todos os clientes</option>${clientes
          .map((c) => `<option value="${c.id}" ${c.id === filtros.cliente_id ? "selected" : ""}>${esc(c.nome)}</option>`)
          .join("")}</select>
        <select id="f-status"><option value="">Todos os status</option>${options(STATUS_PROJETO, filtros.status)}</select>
        <button class="btn primary" id="novo-projeto" ${ativos.length ? "" : "disabled title='Cadastre um cliente primeiro'"}>+ Novo projeto</button>
      </div>
    </div>
    <div class="kpis">
      <div class="kpi"><div class="label">Clientes ativos</div><div class="value">${ativos.length}</div></div>
      <div class="kpi"><div class="label">Receita contratada</div><div class="value">${brl.format(receita)}</div></div>
      <div class="kpi"><div class="label">Projetos em aberto</div><div class="value">${abertos.length}</div></div>
      <div class="kpi"><div class="label">Projetos atrasados</div><div class="value">${
        abertos.filter((p) => atrasada(p.data_prazo, false)).length
      }</div></div>
    </div>
    ${
      projetos.length
        ? `<div class="grid">${projetos.map((p) => cardProjeto(p, nomes[p.cliente_id])).join("")}</div>`
        : `<div class="panel empty">Nenhum projeto encontrado.</div>`
    }`;

  document.getElementById("f-cliente").onchange = (e) => ((filtros.cliente_id = e.target.value), render());
  document.getElementById("f-status").onchange = (e) => ((filtros.status = e.target.value), render());
  document.getElementById("novo-projeto").onclick = () =>
    abrirFormulario("Novo projeto", formProjeto(clientes), async (d) => {
      const p = await api("/projetos", { method: "POST", body: d });
      location.hash = `#/projetos/${p.id}`;
    });
}

function cardTarefa(t, bloqueado) {
  const finalizada = t.status === "FINALIZADA";
  return `
    <div class="task" data-id="${t.id}" draggable="${!bloqueado}">
      ${badge(PRIORIDADE, t.prioridade)}
      <div class="title">${esc(t.titulo)}</div>
      ${t.descricao ? `<div class="desc">${esc(t.descricao)}</div>` : ""}
      <div class="dates">
        Criada: ${fmtDataHora(t.data_criacao)}<br>
        <span class="${atrasada(t.data_prazo, finalizada) ? "late" : ""}">Prazo: ${fmtData(t.data_prazo)}</span>
        ${finalizada ? `<br>Finalizada: ${fmtDataHora(t.data_finalizacao)}` : ""}
      </div>
      <div class="row">
        <select data-status="${t.id}" ${bloqueado ? "disabled" : ""}>${options(STATUS_TAREFA, t.status)}</select>
        <button class="btn sm" data-editar="${t.id}" ${bloqueado ? "disabled" : ""}>Editar</button>
        <button class="btn sm danger" data-excluir="${t.id}" ${bloqueado ? "disabled" : ""}>Excluir</button>
      </div>
    </div>`;
}

function formTarefa(t = {}) {
  return (
    campo("Título", `<input name="titulo" required value="${esc(t.titulo)}">`) +
    campo("Descrição", `<textarea name="descricao">${esc(t.descricao)}</textarea>`) +
    `<div class="row-2">` +
    campo("Prioridade", `<select name="prioridade">${options(PRIORIDADE, t.prioridade ?? "MEDIA")}</select>`) +
    campo("Status", `<select name="status">${options(STATUS_TAREFA, t.status ?? "A_FAZER")}</select>`) +
    `</div>` +
    campo("Prazo", `<input type="date" name="data_prazo" value="${esc(t.data_prazo)}">`)
  );
}

/** Nova tarefa escolhendo cliente e projeto (somente projetos não finalizados). */
async function abrirNovaTarefa(pre = {}) {
  const [clientes, projetos] = await Promise.all([api("/clientes"), api("/projetos")]);
  const abertos = projetos.filter((p) => p.status !== "FINALIZADO");
  const comProjeto = clientes.filter((c) => abertos.some((p) => p.cliente_id === c.id));
  if (!comProjeto.length) {
    toast("Não há projetos em aberto. Crie um projeto antes de cadastrar tarefas.");
    return;
  }
  const clienteInicial = comProjeto.some((c) => c.id === pre.cliente_id) ? pre.cliente_id : comProjeto[0].id;
  const opcoesProjeto = (clienteId, selecionado) =>
    abertos
      .filter((p) => p.cliente_id === clienteId)
      .map((p) => `<option value="${p.id}" ${p.id === selecionado ? "selected" : ""}>${esc(p.nome)}</option>`)
      .join("");

  abrirFormulario(
    "Nova tarefa",
    `<div class="row-2">` +
      campo(
        "Cliente",
        `<select name="cliente_id" required>${comProjeto
          .map((c) => `<option value="${c.id}" ${c.id === clienteInicial ? "selected" : ""}>${esc(c.nome)}</option>`)
          .join("")}</select>`
      ) +
      campo("Projeto", `<select name="projeto_id" required>${opcoesProjeto(clienteInicial, pre.projeto_id)}</select>`) +
      `</div>` +
      formTarefa(),
    async ({ cliente_id, projeto_id, ...dados }) => {
      await api(`/projetos/${projeto_id}/tarefas`, { method: "POST", body: dados });
      toast("Tarefa criada", true);
    },
    (form) => {
      const projeto = form.elements.namedItem("projeto_id");
      form.elements.namedItem("cliente_id").onchange = (e) => (projeto.innerHTML = opcoesProjeto(e.target.value));
    }
  );
}

/** Liga os botões/seletores de status, edição e exclusão de tarefas na tela atual. */
function ligarAcoesTarefas(tarefas) {
  const porId = Object.fromEntries(tarefas.map((t) => [t.id, t]));
  $app.querySelectorAll("[data-status]").forEach(
    (el) =>
      (el.onchange = () =>
        acao(() => api(`/tarefas/${el.dataset.status}`, { method: "PATCH", body: { status: el.value } })))
  );
  $app.querySelectorAll("[data-editar]").forEach(
    (el) =>
      (el.onclick = () =>
        abrirFormulario("Editar tarefa", formTarefa(porId[el.dataset.editar]), (d) =>
          api(`/tarefas/${el.dataset.editar}`, { method: "PATCH", body: d })
        ))
  );
  $app.querySelectorAll("[data-excluir]").forEach(
    (el) =>
      (el.onclick = () => {
        if (confirm(`Excluir a tarefa "${porId[el.dataset.excluir].titulo}"?`))
          acao(() => api(`/tarefas/${el.dataset.excluir}`, { method: "DELETE" }), "Tarefa excluída");
      })
  );
  return porId;
}

async function viewProjeto(id) {
  const [p, tarefas, clientes] = await Promise.all([
    api(`/projetos/${id}`),
    api(`/projetos/${id}/tarefas`),
    api("/clientes"),
  ]);
  const cliente = clientes.find((c) => c.id === p.cliente_id);
  const finalizado = p.status === "FINALIZADO";
  const pendentes = p.total_tarefas - p.tarefas_finalizadas;

  $app.innerHTML = `
    <p><a href="#/projetos">← Projetos</a></p>
    <div class="page-head">
      <div>
        <h1>${esc(p.nome)} ${badge(STATUS_PROJETO, p.status)}</h1>
        <div class="meta muted small">
          <span>Cliente: <a href="#/clientes/${p.cliente_id}">${esc(cliente?.nome)}</a></span>
          <span>Criado: ${fmtDataHora(p.data_criacao)}</span>
          <span class="${atrasada(p.data_prazo, finalizado) ? "late" : ""}">Prazo: ${fmtData(p.data_prazo)}</span>
          ${finalizado ? `<span>Finalizado: ${fmtDataHora(p.data_finalizacao)}</span>` : ""}
        </div>
        ${p.descricao ? `<p class="muted">${esc(p.descricao)}</p>` : ""}
      </div>
      <div class="toolbar">
        ${
          finalizado
            ? `<button class="btn" id="reabrir">Reabrir projeto</button>`
            : `<button class="btn" id="editar">Editar</button>
               <button class="btn" id="nova-tarefa">+ Nova tarefa</button>
               <button class="btn primary" id="finalizar" title="${
                 pendentes ? `${pendentes} tarefa(s) pendente(s)` : ""
               }">Finalizar projeto</button>`
        }
      </div>
    </div>
    <div class="panel">
      <div class="page-head" style="margin-bottom:8px">
        <strong>${p.tarefas_finalizadas} de ${p.total_tarefas} tarefas finalizadas</strong>
        <span class="muted">${p.percentual_concluido}%</span>
      </div>
      <div class="progress big ${finalizado ? "done" : ""}"><span style="width:${p.percentual_concluido}%"></span></div>
      ${finalizado ? `<p class="small muted">Projeto finalizado: as tarefas ficam bloqueadas até ele ser reaberto.</p>` : ""}
    </div>
    <div class="board">
      ${Object.entries(STATUS_TAREFA)
        .map(([status, [label]]) => {
          const doStatus = tarefas.filter((t) => t.status === status);
          return `<div class="column" data-coluna="${status}">
            <h3><span>${label}</span><span>${doStatus.length}</span></h3>
            ${doStatus.map((t) => cardTarefa(t, finalizado)).join("")}
          </div>`;
        })
        .join("")}
    </div>`;

  const porId = ligarAcoesTarefas(tarefas);
  const mudarStatus = (tid, status) =>
    acao(() => api(`/tarefas/${tid}`, { method: "PATCH", body: { status } }));

  if (finalizado) {
    document.getElementById("reabrir").onclick = () =>
      acao(() => api(`/projetos/${id}/reabrir`, { method: "POST" }), "Projeto reaberto");
  } else {
    document.getElementById("finalizar").onclick = () =>
      acao(() => api(`/projetos/${id}/finalizar`, { method: "POST" }), "Projeto finalizado!");
    document.getElementById("nova-tarefa").onclick = () =>
      abrirNovaTarefa({ cliente_id: p.cliente_id, projeto_id: id });
    document.getElementById("editar").onclick = () =>
      abrirFormulario("Editar projeto", formProjeto(clientes, p), (d) =>
        api(`/projetos/${id}`, { method: "PATCH", body: d })
      );
  }

  // Arrastar e soltar entre colunas
  $app.querySelectorAll('.task[draggable="true"]').forEach(
    (el) => (el.ondragstart = (e) => e.dataTransfer.setData("text/plain", el.dataset.id))
  );
  $app.querySelectorAll("[data-coluna]").forEach((col) => {
    col.ondragover = (e) => (e.preventDefault(), col.classList.add("drop"));
    col.ondragleave = () => col.classList.remove("drop");
    col.ondrop = (e) => {
      e.preventDefault();
      col.classList.remove("drop");
      const tid = e.dataTransfer.getData("text/plain");
      if (tid && porId[tid] && porId[tid].status !== col.dataset.coluna) mudarStatus(tid, col.dataset.coluna);
    };
  });
}

// ---------- Clientes ----------

function linhaServico(tipos, s = {}) {
  return `<div class="svc-row">
    <select name="svc_tipo">${tipos.map((t) => `<option value="${t.id}">${esc(t.nome)}</option>`).join("")}</select>
    <input name="svc_valor" type="number" step="0.01" min="0" placeholder="Valor (R$)" required value="${esc(s.valor)}">
    <input name="svc_inicio" type="date" title="Data de início">
    <button type="button" class="btn sm ghost" onclick="this.parentElement.remove()">✕</button>
  </div>`;
}

function formCliente(c = {}) {
  return (
    campo("Nome", `<input name="nome" required value="${esc(c.nome)}">`) +
    `<div class="row-2">` +
    campo("CPF / CNPJ", `<input name="documento" value="${esc(c.documento)}">`) +
    campo("Telefone", `<input name="telefone" value="${esc(c.telefone)}">`) +
    `</div>` +
    campo("E-mail", `<input name="email" type="email" value="${esc(c.email)}">`)
  );
}

async function novoCliente() {
  const tipos = await api("/tipos-servico");
  abrirFormulario(
    "Novo cliente",
    formCliente() +
      `<div class="field"><label>Serviços contratados</label><div id="svcs"></div>
       <button type="button" class="btn sm" id="add-svc">+ Adicionar serviço</button></div>`,
    async (d, form) => {
      const tiposSel = [...form.querySelectorAll('[name="svc_tipo"]')];
      const valores = [...form.querySelectorAll('[name="svc_valor"]')];
      const inicios = [...form.querySelectorAll('[name="svc_inicio"]')];
      const servicos = tiposSel.map((el, i) => ({
        tipo_servico_id: el.value,
        valor: valores[i].value,
        data_inicio: inicios[i].value || null,
      }));
      const { nome, documento, telefone, email } = d;
      const c = await api("/clientes", { method: "POST", body: { nome, documento, telefone, email, servicos } });
      location.hash = `#/clientes/${c.id}`;
    },
    (form) => {
      const add = () => form.querySelector("#svcs").insertAdjacentHTML("beforeend", linhaServico(tipos));
      form.querySelector("#add-svc").onclick = add;
      add();
    }
  );
}

function novoTipoServico() {
  abrirFormulario(
    "Novo tipo de serviço",
    campo("Nome", `<input name="nome" required>`) + campo("Descrição", `<textarea name="descricao"></textarea>`),
    (d) => api("/tipos-servico", { method: "POST", body: d }).then(() => toast("Tipo de serviço criado", true))
  );
}

async function viewClientes() {
  const clientes = await api("/clientes");
  const ativos = clientes.filter((c) => c.ativo);
  const total = ativos.reduce((soma, c) => soma + Number(c.valor_total_servicos), 0);
  const servicosAtivos = ativos.flatMap((c) => c.servicos.filter((s) => s.ativo));
  const porTipo = {};
  for (const s of servicosAtivos) {
    porTipo[s.tipo_servico_nome] ??= { valor: 0, qtd: 0 };
    porTipo[s.tipo_servico_nome].valor += Number(s.valor);
    porTipo[s.tipo_servico_nome].qtd += 1;
  }
  const tipos = Object.entries(porTipo).sort((a, b) => b[1].valor - a[1].valor);
  const maiorValor = Math.max(1, ...tipos.map(([, v]) => v.valor));

  $app.innerHTML = `
    <div class="page-head">
      <h1>Clientes</h1>
      <div class="toolbar">
        <button class="btn" id="novo-tipo">+ Tipo de serviço</button>
        <button class="btn primary" id="novo-cliente">+ Novo cliente</button>
      </div>
    </div>
    <div class="kpis">
      <div class="kpi"><div class="label">Valor total contratado</div><div class="value">${brl.format(total)}</div>
        <div class="small muted">soma dos serviços ativos</div></div>
      <div class="kpi"><div class="label">Ticket médio por cliente</div>
        <div class="value">${brl.format(ativos.length ? total / ativos.length : 0)}</div>
        <div class="small muted">valor total ÷ clientes ativos</div></div>
      <div class="kpi"><div class="label">Clientes ativos</div><div class="value">${ativos.length}</div>
        <div class="small muted">${clientes.length - ativos.length} inativo(s)</div></div>
      <div class="kpi"><div class="label">Serviços ativos</div><div class="value">${servicosAtivos.length}</div>
        <div class="small muted">${tipos.length} tipo(s) de serviço</div></div>
    </div>
    ${
      tipos.length
        ? `<div class="panel"><h2>Valor contratado por tipo de serviço</h2><div class="bars">${tipos
            .map(
              ([nome, v]) => `<div class="bar-row">
                <span>${esc(nome)} <span class="muted small">· ${v.qtd} cliente(s)</span></span>
                <div class="bar-track"><span style="width:${(100 * v.valor) / maiorValor}%"></span></div>
                <span class="num"><strong>${brl.format(v.valor)}</strong>
                  <span class="muted small">${total ? Math.round((100 * v.valor) / total) : 0}%</span></span>
              </div>`
            )
            .join("")}</div></div>`
        : ""
    }
    <div class="panel table-wrap" style="padding:0">
      <table>
        <thead><tr><th>Cliente</th><th>Cadastro</th><th>Serviços contratados</th><th class="num">Valor total</th><th>Status</th></tr></thead>
        <tbody>
          ${
            clientes
              .map(
                (c) => `<tr class="clickable" data-id="${c.id}">
            <td><strong>${esc(c.nome)}</strong><div class="small muted">${esc(c.documento ?? "")} ${esc(c.email ?? "")}</div></td>
            <td>${fmtDataHora(c.data_cadastro)}</td>
            <td><div class="chips">${
              c.servicos
                .filter((s) => s.ativo)
                .map((s) => `<span class="badge b-info">${esc(s.tipo_servico_nome)} · ${brl.format(s.valor)}</span>`)
                .join("") || '<span class="muted">—</span>'
            }</div></td>
            <td class="num"><strong>${brl.format(c.valor_total_servicos)}</strong></td>
            <td>${c.ativo ? '<span class="badge b-ok">Ativo</span>' : '<span class="badge">Inativo</span>'}</td>
          </tr>`
              )
              .join("") || `<tr><td colspan="5" class="empty">Nenhum cliente cadastrado.</td></tr>`
          }
        </tbody>
        ${
          clientes.length
            ? `<tfoot><tr><th colspan="3">Total — clientes ativos</th><th class="num">${brl.format(total)}</th><th></th></tr></tfoot>`
            : ""
        }
      </table>
    </div>`;
  document.getElementById("novo-cliente").onclick = novoCliente;
  document.getElementById("novo-tipo").onclick = novoTipoServico;
  $app.querySelectorAll("tr[data-id]").forEach((tr) => (tr.onclick = () => (location.hash = `#/clientes/${tr.dataset.id}`)));
}

async function viewCliente(id) {
  const [c, projetos, tipos] = await Promise.all([
    api(`/clientes/${id}`),
    api(`/clientes/${id}/projetos`),
    api("/tipos-servico"),
  ]);
  $app.innerHTML = `
    <p><a href="#/clientes">← Clientes</a></p>
    <div class="page-head">
      <div>
        <h1>${esc(c.nome)} ${c.ativo ? '<span class="badge b-ok">Ativo</span>' : '<span class="badge">Inativo</span>'}</h1>
        <div class="meta muted small">
          <span>Cadastro: ${fmtDataHora(c.data_cadastro)}</span>
          ${c.documento ? `<span>Doc.: ${esc(c.documento)}</span>` : ""}
          ${c.email ? `<span>${esc(c.email)}</span>` : ""}
          ${c.telefone ? `<span>${esc(c.telefone)}</span>` : ""}
        </div>
      </div>
      <div class="toolbar">
        <button class="btn" id="editar">Editar</button>
        <button class="btn" id="ativo">${c.ativo ? "Inativar" : "Reativar"}</button>
      </div>
    </div>
    <div class="kpis">
      <div class="kpi"><div class="label">Valor total contratado</div><div class="value">${brl.format(c.valor_total_servicos)}</div></div>
      <div class="kpi"><div class="label">Projetos</div><div class="value">${projetos.length}</div></div>
      <div class="kpi"><div class="label">Projetos finalizados</div><div class="value">${
        projetos.filter((p) => p.status === "FINALIZADO").length
      }</div></div>
    </div>
    <div class="panel">
      <div class="page-head" style="margin-bottom:8px"><h2>Serviços contratados</h2>
        <button class="btn sm" id="add-servico">+ Contratar serviço</button></div>
      <div class="table-wrap"><table>
        <thead><tr><th>Serviço</th><th>Início</th><th class="num">Valor</th><th>Situação</th><th></th></tr></thead>
        <tbody>${
          c.servicos
            .map(
              (s) => `<tr>
            <td>${esc(s.tipo_servico_nome)}</td><td>${fmtData(s.data_inicio)}</td>
            <td class="num">${brl.format(s.valor)}</td>
            <td>${s.ativo ? '<span class="badge b-ok">Ativo</span>' : '<span class="badge">Encerrado</span>'}</td>
            <td class="num">${s.ativo ? `<button class="btn sm danger" data-encerrar="${s.id}">Encerrar</button>` : ""}</td>
          </tr>`
            )
            .join("") || `<tr><td colspan="5" class="empty">Nenhum serviço contratado.</td></tr>`
        }</tbody>
      </table></div>
    </div>
    <div class="page-head"><h2>Projetos</h2>
      <button class="btn primary" id="novo-projeto" ${c.ativo ? "" : "disabled"}>+ Novo projeto</button></div>
    ${
      projetos.length
        ? `<div class="grid">${projetos.map((p) => cardProjeto(p, c.nome)).join("")}</div>`
        : `<div class="panel empty">Nenhum projeto para este cliente.</div>`
    }`;

  document.getElementById("editar").onclick = () =>
    abrirFormulario("Editar cliente", formCliente(c), (d) => api(`/clientes/${id}`, { method: "PATCH", body: d }));
  document.getElementById("ativo").onclick = () =>
    acao(() => api(`/clientes/${id}`, { method: "PATCH", body: { ativo: !c.ativo } }));
  document.getElementById("add-servico").onclick = () =>
    abrirFormulario(
      "Contratar serviço",
      campo("Tipo de serviço", `<select name="tipo_servico_id">${tipos.map((t) => `<option value="${t.id}">${esc(t.nome)}</option>`).join("")}</select>`) +
        `<div class="row-2">` +
        campo("Valor (R$)", `<input name="valor" type="number" step="0.01" min="0" required>`) +
        campo("Início", `<input name="data_inicio" type="date">`) +
        `</div>`,
      (d) => api(`/clientes/${id}/servicos`, { method: "POST", body: d })
    );
  document.getElementById("novo-projeto").onclick = () =>
    abrirFormulario("Novo projeto", formProjeto([c], { cliente_id: c.id }), async (d) => {
      const p = await api("/projetos", { method: "POST", body: { ...d, cliente_id: id } });
      location.hash = `#/projetos/${p.id}`;
    });
  $app.querySelectorAll("[data-encerrar]").forEach(
    (el) =>
      (el.onclick = () => {
        if (confirm("Encerrar este serviço? Ele sai do valor total, mas fica no histórico."))
          acao(() => api(`/clientes/${id}/servicos/${el.dataset.encerrar}`, { method: "DELETE" }), "Serviço encerrado");
      })
  );
}

// ---------- Tarefas ----------

const filtrosTarefas = { cliente_id: "", projeto_id: "", status: "", prioridade: "", atrasadas: false };

async function viewTarefas() {
  const f = filtrosTarefas;
  const qs = new URLSearchParams(Object.entries(f).filter(([k, v]) => v && k !== "atrasadas")).toString();
  const [clientes, projetos, todas] = await Promise.all([
    api("/clientes"),
    api("/projetos"),
    api("/tarefas" + (qs ? `?${qs}` : "")),
  ]);
  const estaAtrasada = (t) => atrasada(t.data_prazo, t.status === "FINALIZADA");
  const tarefas = f.atrasadas ? todas.filter(estaAtrasada) : todas;
  const conta = (status) => todas.filter((t) => t.status === status).length;
  const projetosFiltro = projetos.filter((p) => !f.cliente_id || p.cliente_id === f.cliente_id);
  const opt = (lista, sel) =>
    lista.map((x) => `<option value="${x.id}" ${x.id === sel ? "selected" : ""}>${esc(x.nome)}</option>`).join("");

  $app.innerHTML = `
    <div class="page-head">
      <h1>Tarefas</h1>
      <div class="toolbar"><button class="btn primary" id="nova-tarefa">+ Nova tarefa</button></div>
    </div>
    <div class="kpis">
      <div class="kpi"><div class="label">A fazer</div><div class="value">${conta("A_FAZER")}</div></div>
      <div class="kpi"><div class="label">Em andamento</div><div class="value">${conta("EM_ANDAMENTO")}</div></div>
      <div class="kpi"><div class="label">Bloqueadas</div><div class="value">${conta("BLOQUEADA")}</div></div>
      <div class="kpi"><div class="label">Atrasadas</div><div class="value ${todas.some(estaAtrasada) ? "late" : ""}">${
        todas.filter(estaAtrasada).length
      }</div></div>
      <div class="kpi"><div class="label">Finalizadas</div><div class="value">${conta("FINALIZADA")}</div></div>
    </div>
    <div class="filters">
      <select id="ft-cliente"><option value="">Todos os clientes</option>${opt(clientes, f.cliente_id)}</select>
      <select id="ft-projeto"><option value="">Todos os projetos</option>${opt(projetosFiltro, f.projeto_id)}</select>
      <select id="ft-status"><option value="">Todos os status</option>${options(STATUS_TAREFA, f.status)}</select>
      <select id="ft-prioridade"><option value="">Todas as prioridades</option>${options(PRIORIDADE, f.prioridade)}</select>
      <label class="check"><input type="checkbox" id="ft-atrasadas" ${f.atrasadas ? "checked" : ""}> Somente atrasadas</label>
    </div>
    <div class="panel table-wrap" style="padding:0">
      <table>
        <thead><tr>
          <th>Tarefa</th><th>Cliente</th><th>Projeto</th><th>Prioridade</th><th>Status</th>
          <th>Prazo</th><th>Criada</th><th>Finalizada</th><th></th>
        </tr></thead>
        <tbody>${
          tarefas
            .map((t) => {
              const bloqueada = t.projeto_status === "FINALIZADO";
              return `<tr>
              <td><strong>${esc(t.titulo)}</strong>${t.descricao ? `<div class="small muted">${esc(t.descricao)}</div>` : ""}</td>
              <td class="nowrap"><a href="#/clientes/${t.cliente_id}">${esc(t.cliente_nome)}</a></td>
              <td><a href="#/projetos/${t.projeto_id}">${esc(t.projeto_nome)}</a></td>
              <td>${badge(PRIORIDADE, t.prioridade)}</td>
              <td><select data-status="${t.id}" ${bloqueada ? "disabled title='Projeto finalizado'" : ""}>${options(STATUS_TAREFA, t.status)}</select></td>
              <td class="nowrap ${estaAtrasada(t) ? "late" : ""}">${fmtData(t.data_prazo)}</td>
              <td class="nowrap small">${fmtDataHora(t.data_criacao)}</td>
              <td class="nowrap small">${fmtDataHora(t.data_finalizacao)}</td>
              <td class="nowrap">
                <button class="btn sm" data-editar="${t.id}" ${bloqueada ? "disabled" : ""}>Editar</button>
                <button class="btn sm danger" data-excluir="${t.id}" ${bloqueada ? "disabled" : ""}>Excluir</button>
              </td>
            </tr>`;
            })
            .join("") || `<tr><td colspan="9" class="empty">Nenhuma tarefa encontrada.</td></tr>`
        }</tbody>
      </table>
    </div>`;

  const filtro = (campo, el) => (el.onchange = () => ((f[campo] = el.type === "checkbox" ? el.checked : el.value), render()));
  document.getElementById("ft-cliente").onchange = (e) => {
    f.cliente_id = e.target.value;
    const projeto = projetos.find((p) => p.id === f.projeto_id);
    if (projeto && f.cliente_id && projeto.cliente_id !== f.cliente_id) f.projeto_id = "";
    render();
  };
  filtro("projeto_id", document.getElementById("ft-projeto"));
  filtro("status", document.getElementById("ft-status"));
  filtro("prioridade", document.getElementById("ft-prioridade"));
  filtro("atrasadas", document.getElementById("ft-atrasadas"));
  document.getElementById("nova-tarefa").onclick = () =>
    abrirNovaTarefa({ cliente_id: f.cliente_id, projeto_id: f.projeto_id });
  ligarAcoesTarefas(tarefas);
}

// ---------- Roteamento ----------

async function render() {
  const [, secao, id] = (location.hash || "#/projetos").split("/");
  document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("active", a.dataset.nav === secao));
  try {
    if (secao === "clientes") await (id ? viewCliente(id) : viewClientes());
    else if (secao === "tarefas") await viewTarefas();
    else await (id ? viewProjeto(id) : viewProjetos());
  } catch (e) {
    $app.innerHTML = `<div class="panel empty">Não foi possível carregar: ${esc(e.message)}</div>`;
  }
}

// Menu lateral no celular
const sidebar = document.getElementById("sidebar");
const backdrop = document.getElementById("backdrop");
const menu = (aberto) => (sidebar.classList.toggle("open", aberto), backdrop.classList.toggle("open", aberto));
document.getElementById("menu-btn").onclick = () => menu(true);
backdrop.onclick = () => menu(false);

window.addEventListener("hashchange", () => {
  document.getElementById("toast").hidden = true;
  menu(false);
  render();
});
render();
