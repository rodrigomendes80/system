"use strict";

// ---------- Rótulos e formatação ----------

// Cores do status da tarefa: A fazer = vermelho, Em andamento = azul, Bloqueada = laranja, Finalizada = verde
const STATUS_TAREFA = {
  A_FAZER: ["A fazer", "b-danger"],
  EM_ANDAMENTO: ["Em andamento", "b-info"],
  BLOQUEADA: ["Bloqueada", "b-warn"],
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
const vazio = (texto) => `<option value="" selected disabled hidden>${texto}</option>`;
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
function abrirFormulario(titulo, corpoHtml, onSubmit, aoAbrir, { botao = "Salvar", perigo = false } = {}) {
  const dialog = document.getElementById("modal");
  const form = document.getElementById("modal-form");
  const submit = document.getElementById("modal-submit");
  submit.textContent = botao;
  submit.className = `btn ${perigo ? "danger-solid" : "primary"}`;
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

// ---------- Visualização: lista/kanban e agrupamento ----------

const pref = (chave, padrao) => {
  try {
    return localStorage.getItem(chave) ?? padrao;
  } catch {
    return padrao;
  }
};
const salvarPref = (chave, valor) => {
  try {
    localStorage.setItem(chave, valor);
  } catch {}
};

function seletorVisao(atual) {
  return `<div class="segmented" role="group" aria-label="Visualização">
    <button class="${atual === "lista" ? "on" : ""}" data-visao="lista">☰ Lista</button>
    <button class="${atual === "kanban" ? "on" : ""}" data-visao="kanban">▦ Kanban</button>
  </div>`;
}

function seletorAgrupar(atual, opcoes) {
  return `<select id="agrupar" title="Agrupar">
    <option value="">Sem agrupamento</option>
    ${Object.entries(opcoes)
      .map(([v, rotulo]) => `<option value="${v}" ${v === atual ? "selected" : ""}>${rotulo}</option>`)
      .join("")}
  </select>`;
}

/** Liga os controles de visão e agrupamento, salvando a escolha no navegador. */
function ligarVisao(prefVisao, prefAgrupar, aoMudar) {
  $app.querySelectorAll("[data-visao]").forEach(
    (el) => (el.onclick = () => (salvarPref(prefVisao, el.dataset.visao), aoMudar()))
  );
  const agrupar = document.getElementById("agrupar");
  if (agrupar) agrupar.onchange = () => (salvarPref(prefAgrupar, agrupar.value), aoMudar());
}

/** Agrupa itens por chave; grupos em ordem alfabética, com os "sem grupo" por último. */
function agrupar(itens, chave, titulo, link) {
  const grupos = new Map();
  for (const item of itens) {
    const k = chave(item) ?? "";
    if (!grupos.has(k)) grupos.set(k, { chave: k, titulo: titulo(item), link: link(item), itens: [] });
    grupos.get(k).itens.push(item);
  }
  return [...grupos.values()].sort((a, b) =>
    !a.chave ? 1 : !b.chave ? -1 : a.titulo.localeCompare(b.titulo, "pt-BR")
  );
}

const tituloGrupo = (g) =>
  `${g.link ? `<a href="${g.link}">${esc(g.titulo)}</a>` : esc(g.titulo)} <span class="muted">· ${g.itens.length}</span>`;

/** Linhas de tabela com cabeçalho por grupo (ou sem grupos). */
function linhasAgrupadas(grupos, colunas, linha) {
  return grupos
    .map(
      (g) =>
        (g.titulo !== null ? `<tr class="grupo"><td colspan="${colunas}">${tituloGrupo(g)}</td></tr>` : "") +
        g.itens.map(linha).join("")
    )
    .join("");
}

/** Um quadro kanban por grupo. */
function quadrosAgrupados(grupos, quadro) {
  return grupos
    .map((g) =>
      g.titulo !== null
        ? `<section class="grupo-kanban"><h3>${tituloGrupo(g)}</h3>${quadro(g.itens)}</section>`
        : quadro(g.itens)
    )
    .join("");
}

const semGrupo = (itens) => [{ chave: "", titulo: null, link: null, itens }];

/** Arrastar cartões entre colunas do kanban; aoSoltar(id, colunaDestino). */
function ligarArrastar(aoSoltar) {
  $app.querySelectorAll('[draggable="true"][data-id]').forEach(
    (el) => (el.ondragstart = (e) => e.dataTransfer.setData("text/plain", el.dataset.id))
  );
  $app.querySelectorAll("[data-coluna]").forEach((col) => {
    col.ondragover = (e) => (e.preventDefault(), col.classList.add("drop"));
    col.ondragleave = () => col.classList.remove("drop");
    col.ondrop = (e) => {
      e.preventDefault();
      col.classList.remove("drop");
      const id = e.dataTransfer.getData("text/plain");
      if (id) aoSoltar(id, col.dataset.coluna);
    };
  });
}

/** Arrastar tarefas muda o status. */
function arrastarTarefas(porId) {
  ligarArrastar((tid, status) => {
    if (porId[tid] && porId[tid].status !== status)
      acao(() => api(`/tarefas/${tid}`, { method: "PATCH", body: { status } }));
  });
}

// ---------- Tarefas: componentes ----------

function cardTarefa(t, comCliente = false) {
  const finalizada = t.status === "FINALIZADA";
  return `
    <div class="task" data-id="${t.id}" draggable="true">
      ${badge(PRIORIDADE, t.prioridade)}
      <div class="title"><a class="link-tarefa" href="#/tarefas/${t.id}">${esc(t.titulo)}</a>
        ${t.total_comentarios ? `<span class="coments" title="Comentários">💬 ${t.total_comentarios}</span>` : ""}</div>
      ${comCliente ? `<div class="origem"><a href="#/clientes/${t.cliente_id}">${esc(t.cliente_nome)}</a></div>` : ""}
      ${t.descricao ? `<div class="desc">${esc(t.descricao)}</div>` : ""}
      <div class="dates">
        Criada: ${fmtDataHora(t.data_criacao)}<br>
        <span class="${atrasada(t.data_prazo, finalizada) ? "late" : ""}">Prazo: ${fmtData(t.data_prazo)}</span>
        ${finalizada ? `<br>Finalizada: ${fmtDataHora(t.data_finalizacao)}` : ""}
      </div>
      <div class="row">
        <select class="status-sel st-${t.status}" data-status="${t.id}">${options(STATUS_TAREFA, t.status)}</select>
        <button class="btn sm" data-editar="${t.id}">Editar</button>
        <button class="btn sm danger" data-excluir="${t.id}">Excluir</button>
      </div>
    </div>`;
}

function formTarefa(t = {}) {
  return (
    campo("Título", `<input name="titulo" required value="${esc(t.titulo)}">`) +
    campo("Descrição", `<textarea name="descricao">${esc(t.descricao)}</textarea>`) +
    `<div class="row-2">` +
    campo(
      "Prioridade",
      `<select name="prioridade" required>${t.id ? "" : vazio("Selecione")}${options(PRIORIDADE, t.prioridade)}</select>`
    ) +
    campo("Status", `<select name="status">${options(STATUS_TAREFA, t.status ?? "A_FAZER")}</select>`) +
    `</div>` +
    campo("Prazo", `<input type="date" name="data_prazo" value="${esc(t.data_prazo)}">`)
  );
}

/** Nova tarefa: escolhe o cliente (ou já vem com ele, a partir da tela do cliente). */
async function abrirNovaTarefa(pre = {}) {
  const clientes = await api("/clientes");
  const ativos = clientes.filter((c) => c.ativo || c.id === pre.cliente_id);
  if (!ativos.length) {
    toast("Cadastre um cliente antes de criar tarefas.");
    return;
  }
  const clienteInicial = ativos.some((c) => c.id === pre.cliente_id) ? pre.cliente_id : "";

  abrirFormulario(
    "Nova tarefa",
    campo(
      "Cliente",
      `<select name="cliente_id" required>${clienteInicial ? "" : vazio("Selecione o cliente")}${ativos
        .map((c) => `<option value="${c.id}" ${c.id === clienteInicial ? "selected" : ""}>${esc(c.nome)}</option>`)
        .join("")}</select>`
    ) + formTarefa(),
    async (dados) => {
      await api("/tarefas", { method: "POST", body: dados });
      toast("Tarefa criada", true);
    }
  );
}

function abrirEdicaoTarefa(t) {
  abrirFormulario("Editar tarefa", formTarefa(t), (dados) =>
    api(`/tarefas/${t.id}`, { method: "PATCH", body: dados })
  );
}

/** Linha da tabela de tarefas. */
function linhaTarefa(t, comCliente = true) {
  const atrasadaT = atrasada(t.data_prazo, t.status === "FINALIZADA");
  return `<tr>
    <td><a class="link-tarefa" href="#/tarefas/${t.id}"><strong>${esc(t.titulo)}</strong></a>
      ${t.total_comentarios ? `<span class="coments" title="Comentários">💬 ${t.total_comentarios}</span>` : ""}
      ${t.descricao ? `<div class="small muted">${esc(t.descricao)}</div>` : ""}</td>
    ${comCliente ? `<td class="nowrap"><a href="#/clientes/${t.cliente_id}">${esc(t.cliente_nome)}</a></td>` : ""}
    <td>${badge(PRIORIDADE, t.prioridade)}</td>
    <td><select class="status-sel st-${t.status}" data-status="${t.id}">${options(STATUS_TAREFA, t.status)}</select></td>
    <td class="nowrap ${atrasadaT ? "late" : ""}">${fmtData(t.data_prazo)}</td>
    <td class="nowrap small">${fmtDataHora(t.data_criacao)}</td>
    <td class="nowrap small">${fmtDataHora(t.data_finalizacao)}</td>
    <td class="nowrap">
      <button class="btn sm" data-editar="${t.id}">Editar</button>
      <button class="btn sm danger" data-excluir="${t.id}">Excluir</button>
    </td>
  </tr>`;
}

const cabecalhoTarefas = (comCliente = true) =>
  `<thead><tr><th>Tarefa</th>${comCliente ? "<th>Cliente</th>" : ""}<th>Prioridade</th><th>Status</th>
   <th>Prazo</th><th>Criada</th><th>Finalizada</th><th></th></tr></thead>`;

/** Quadro kanban: uma coluna por status. */
function quadroTarefas(tarefas, comCliente = false) {
  return `<div class="board">${Object.entries(STATUS_TAREFA)
    .map(([status, [label]]) => {
      const doStatus = tarefas.filter((t) => t.status === status);
      return `<div class="column" data-coluna="${status}">
        <h3><span>${label}</span><span>${doStatus.length}</span></h3>
        ${doStatus.map((t) => cardTarefa(t, comCliente)).join("") || '<p class="small muted" style="padding:0 4px">Nenhuma tarefa</p>'}
      </div>`;
    })
    .join("")}</div>`;
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
      (el.onclick = () => abrirEdicaoTarefa(porId[el.dataset.editar]))
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

/** Exclui o cliente. Com tarefas, mostra o que será apagado e pede o nome como confirmação. */
async function excluirCliente(c) {
  const v = await api(`/clientes/${c.id}/vinculos`);
  const sair = () => {
    toast(`Cliente "${c.nome}" excluído`, true);
    if (location.hash === "#/clientes") render();
    else location.hash = "#/clientes";
  };
  if (!v.tarefas) {
    if (!confirm(`Excluir o cliente "${c.nome}"${v.servicos ? ` e seus ${v.servicos} serviço(s)` : ""}? Esta ação não pode ser desfeita.`))
      return;
    await api(`/clientes/${c.id}`, { method: "DELETE" });
    return sair();
  }
  const item = (n, txt) => (n ? `<li><strong>${n}</strong> ${txt}</li>` : "");
  abrirFormulario(
    "Excluir cliente",
    `<div class="alerta">
       <p><strong>Esta ação não pode ser desfeita.</strong> Junto com <strong>${esc(c.nome)}</strong> serão apagados:</p>
       <ul>
         ${item(v.servicos, "serviço(s) contratado(s)")}
         ${item(v.tarefas, "tarefa(s)")}
         ${item(v.comentarios, "comentário(s) do histórico")}
       </ul>
       <p class="small">Para manter o histórico, use <strong>Inativar</strong> em vez de excluir.</p>
     </div>` +
      campo(
        `Digite <strong>${esc(c.nome)}</strong> para confirmar`,
        `<input name="confirmacao" required autocomplete="off">`
      ),
    async ({ confirmacao }) => {
      if ((confirmacao || "").trim() !== c.nome.trim()) throw new Error("O nome digitado não confere com o do cliente.");
      await api(`/clientes/${c.id}?cascata=true`, { method: "DELETE" });
      toast(`Cliente "${c.nome}" e seus dados foram excluídos`, true);
      if (location.hash !== "#/clientes") location.hash = "#/clientes";
    },
    null,
    { botao: "Excluir definitivamente", perigo: true }
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
        <thead><tr><th>Cliente</th><th>Cadastro</th><th>Serviços contratados</th><th class="num">Valor total</th><th>Status</th><th></th></tr></thead>
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
            <td class="num"><button class="btn sm danger" data-excluir-cliente="${c.id}">Excluir</button></td>
          </tr>`
              )
              .join("") || `<tr><td colspan="6" class="empty">Nenhum cliente cadastrado.</td></tr>`
          }
        </tbody>
        ${
          clientes.length
            ? `<tfoot><tr><th colspan="3">Total — clientes ativos</th><th class="num">${brl.format(total)}</th><th colspan="2"></th></tr></tfoot>`
            : ""
        }
      </table>
    </div>`;
  document.getElementById("novo-cliente").onclick = novoCliente;
  document.getElementById("novo-tipo").onclick = novoTipoServico;
  $app.querySelectorAll("tr[data-id]").forEach((tr) => (tr.onclick = () => (location.hash = `#/clientes/${tr.dataset.id}`)));
  $app.querySelectorAll("[data-excluir-cliente]").forEach(
    (el) =>
      (el.onclick = (e) => {
        e.stopPropagation(); // não abrir o cliente ao clicar em Excluir
        const c = clientes.find((x) => x.id === el.dataset.excluirCliente);
        excluirCliente(c).catch((err) => toast(err.message));
      })
  );
}

async function viewCliente(id) {
  const [c, tarefas, tipos] = await Promise.all([
    api(`/clientes/${id}`),
    api(`/tarefas?cliente_id=${encodeURIComponent(id)}`),
    api("/tipos-servico"),
  ]);
  const abertas = tarefas.filter((t) => t.status !== "FINALIZADA");
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
        <button class="btn danger" id="excluir-cliente">Excluir</button>
      </div>
    </div>
    <div class="kpis">
      <div class="kpi"><div class="label">Valor total contratado</div><div class="value">${brl.format(c.valor_total_servicos)}</div></div>
      <div class="kpi"><div class="label">Tarefas em aberto</div><div class="value">${abertas.length}</div></div>
      <div class="kpi"><div class="label">Tarefas atrasadas</div><div class="value ${
        abertas.some((t) => atrasada(t.data_prazo, false)) ? "late" : ""
      }">${abertas.filter((t) => atrasada(t.data_prazo, false)).length}</div></div>
      <div class="kpi"><div class="label">Tarefas finalizadas</div><div class="value">${
        tarefas.length - abertas.length
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
    <div class="page-head"><h2>Tarefas</h2>
      <button class="btn primary" id="nova-tarefa" ${c.ativo ? "" : "disabled"}>+ Nova tarefa</button></div>
    ${
      tarefas.length
        ? `<div class="panel table-wrap" style="padding:0"><table>${cabecalhoTarefas(false)}
            <tbody>${tarefas.map((t) => linhaTarefa(t, false)).join("")}</tbody></table></div>`
        : `<div class="panel empty">Nenhuma tarefa para este cliente.</div>`
    }`;

  document.getElementById("editar").onclick = () =>
    abrirFormulario("Editar cliente", formCliente(c), (d) => api(`/clientes/${id}`, { method: "PATCH", body: d }));
  document.getElementById("excluir-cliente").onclick = () => excluirCliente(c).catch((e) => toast(e.message));
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
  document.getElementById("nova-tarefa").onclick = () => abrirNovaTarefa({ cliente_id: id });
  ligarAcoesTarefas(tarefas);
  $app.querySelectorAll("[data-encerrar]").forEach(
    (el) =>
      (el.onclick = () => {
        if (confirm("Encerrar este serviço? Ele sai do valor total, mas fica no histórico."))
          acao(() => api(`/clientes/${id}/servicos/${el.dataset.encerrar}`, { method: "DELETE" }), "Serviço encerrado");
      })
  );
}

// ---------- Tarefas ----------

const filtrosTarefas = { cliente_id: "", status: "", prioridade: "", prazo: "" };
const PRAZOS = { hoje: ["Para hoje"], atrasadas: ["Atrasadas"], semana: ["Próximos 7 dias"] };


function somarDias(dias) {
  const d = new Date();
  d.setDate(d.getDate() + dias);
  return d.toLocaleDateString("sv-SE");
}

async function viewTarefas() {
  const visaoTarefas = pref("visaoTarefas", "lista");
  const agruparPor = pref("agruparTarefas", "");
  const f = filtrosTarefas;
  const qs = new URLSearchParams(Object.entries(f).filter(([k, v]) => v && k !== "prazo")).toString();
  const [clientes, todas] = await Promise.all([api("/clientes"), api("/tarefas" + (qs ? `?${qs}` : ""))]);
  const estaAtrasada = (t) => atrasada(t.data_prazo, t.status === "FINALIZADA");
  const paraHoje = (t) => t.data_prazo === hoje() && t.status !== "FINALIZADA";
  const naSemana = (t) =>
    t.data_prazo && t.status !== "FINALIZADA" && t.data_prazo >= hoje() && t.data_prazo <= somarDias(7);
  const filtroPrazo = { hoje: paraHoje, atrasadas: estaAtrasada, semana: naSemana }[f.prazo];
  const tarefas = filtroPrazo ? todas.filter(filtroPrazo) : todas;
  const conta = (status) => todas.filter((t) => t.status === status).length;
  const opt = (lista, sel) =>
    lista.map((x) => `<option value="${x.id}" ${x.id === sel ? "selected" : ""}>${esc(x.nome)}</option>`).join("");
  const grupos =
    agruparPor === "cliente"
      ? agrupar(tarefas, (t) => t.cliente_id, (t) => t.cliente_nome, (t) => `#/clientes/${t.cliente_id}`)
      : semGrupo(tarefas);

  $app.innerHTML = `
    <div class="page-head">
      <h1>Tarefas</h1>
      <div class="toolbar">
        ${seletorVisao(visaoTarefas)}
        <button class="btn primary" id="nova-tarefa">+ Nova tarefa</button>
      </div>
    </div>
    <div class="kpis">
      <a class="kpi clickable ${f.prazo === "hoje" ? "on" : ""}" href="javascript:void 0" data-prazo="hoje"><div class="label">Para hoje</div>
        <div class="value">${todas.filter(paraHoje).length}</div></a>
      <div class="kpi"><div class="label">A fazer</div><div class="value">${conta("A_FAZER")}</div></div>
      <div class="kpi"><div class="label">Em andamento</div><div class="value">${conta("EM_ANDAMENTO")}</div></div>
      <div class="kpi"><div class="label">Bloqueadas</div><div class="value">${conta("BLOQUEADA")}</div></div>
      <a class="kpi clickable ${f.prazo === "atrasadas" ? "on" : ""}" href="javascript:void 0" data-prazo="atrasadas"><div class="label">Atrasadas</div>
        <div class="value ${todas.some(estaAtrasada) ? "late" : ""}">${todas.filter(estaAtrasada).length}</div></a>
      <div class="kpi"><div class="label">Finalizadas</div><div class="value">${conta("FINALIZADA")}</div></div>
    </div>
    <div class="filters">
      <select id="ft-cliente"><option value="">Todos os clientes</option>${opt(clientes, f.cliente_id)}</select>
      <select id="ft-status"><option value="">Todos os status</option>${options(STATUS_TAREFA, f.status)}</select>
      <select id="ft-prioridade"><option value="">Todas as prioridades</option>${options(PRIORIDADE, f.prioridade)}</select>
      <select id="ft-prazo"><option value="">Todos os prazos</option>${options(PRAZOS, f.prazo)}</select>
      ${seletorAgrupar(agruparPor, { cliente: "Agrupar por cliente" })}
      ${Object.values(f).some(Boolean) ? '<button class="btn ghost sm" id="ft-limpar">Limpar filtros</button>' : ""}
    </div>
    ${
      visaoTarefas === "kanban"
        ? quadrosAgrupados(grupos, (itens) => quadroTarefas(itens, true))
        : `<div class="panel table-wrap" style="padding:0">
      <table>
        ${cabecalhoTarefas()}
        <tbody>${
          linhasAgrupadas(grupos, 8, (t) => linhaTarefa(t)) ||
          `<tr><td colspan="8" class="empty">Nenhuma tarefa encontrada.</td></tr>`
        }</tbody>
      </table>
    </div>`
    }`;

  const filtro = (campo, el) => (el.onchange = () => ((f[campo] = el.type === "checkbox" ? el.checked : el.value), render()));
  filtro("cliente_id", document.getElementById("ft-cliente"));
  filtro("status", document.getElementById("ft-status"));
  filtro("prioridade", document.getElementById("ft-prioridade"));
  filtro("prazo", document.getElementById("ft-prazo"));
  document.getElementById("ft-limpar")?.addEventListener("click", () => {
    Object.keys(f).forEach((k) => (f[k] = ""));
    render();
  });
  $app.querySelectorAll("[data-prazo]").forEach(
    (el) => (el.onclick = () => ((f.prazo = f.prazo === el.dataset.prazo ? "" : el.dataset.prazo), render()))
  );
  ligarVisao("visaoTarefas", "agruparTarefas", render);
  document.getElementById("nova-tarefa").onclick = () => abrirNovaTarefa();
  arrastarTarefas(ligarAcoesTarefas(tarefas));
}

// ---------- Detalhe da tarefa e histórico ----------

let filtroHistorico = "todos";

const iniciais = (texto) =>
  (texto || "?")
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("");

function itemHistorico(r) {
  const quando = fmtDataHora(r.data_criacao);
  if (r.tipo === "SISTEMA") {
    return `<li class="hist sistema">
      <span class="hist-ponto"></span>
      <div><span>${esc(r.texto)}</span>
        <div class="small muted">${quando}${r.autor ? ` · ${esc(r.autor)}` : ""}</div></div>
    </li>`;
  }
  return `<li class="hist comentario">
    <span class="avatar">${r.autor ? esc(iniciais(r.autor)) : "💬"}</span>
    <div class="balao">
      <div class="balao-topo">
        <strong>${esc(r.autor || "Comentário")}</strong>
        <span class="small muted">${quando}</span>
        <button class="btn sm ghost danger" data-excluir-comentario="${r.id}" title="Excluir comentário">Excluir</button>
      </div>
      <div class="texto">${esc(r.texto)}</div>
    </div>
  </li>`;
}

async function viewTarefa(id) {
  const t = await api(`/tarefas/${id}`);
  const [cliente, historico] = await Promise.all([api(`/clientes/${t.cliente_id}`), api(`/tarefas/${id}/historico`)]);
  const finalizada = t.status === "FINALIZADA";
  const comentarios = historico.filter((r) => r.tipo === "COMENTARIO");
  const exibidos = (filtroHistorico === "comentarios" ? comentarios : historico).slice().reverse();

  $app.innerHTML = `
    <p><a href="#/tarefas">← Tarefas</a></p>
    <div class="page-head">
      <div>
        <h1>${esc(t.titulo)} ${badge(STATUS_TAREFA, t.status)} ${badge(PRIORIDADE, t.prioridade)}</h1>
        <div class="meta muted small">
          <span>Cliente: <a href="#/clientes/${t.cliente_id}">${esc(cliente.nome)}</a></span>
          <span>Criada: ${fmtDataHora(t.data_criacao)}</span>
          <span class="${atrasada(t.data_prazo, finalizada) ? "late" : ""}">Prazo: ${fmtData(t.data_prazo)}</span>
          ${finalizada ? `<span>Finalizada: ${fmtDataHora(t.data_finalizacao)}</span>` : ""}
        </div>
      </div>
      <div class="toolbar">
        <select class="status-sel st-${t.status}" data-status="${t.id}">${options(STATUS_TAREFA, t.status)}</select>
        <button class="btn" data-editar="${t.id}">Editar</button>
        <button class="btn danger" id="excluir-tarefa">Excluir</button>
      </div>
    </div>
    <div class="panel">
      <h2>Descrição</h2>
      ${t.descricao ? `<div class="texto">${esc(t.descricao)}</div>` : '<p class="muted">Sem descrição.</p>'}
    </div>
    <div class="panel">
      <div class="page-head" style="margin-bottom:12px">
        <h2 style="margin:0">Histórico</h2>
        <div class="segmented" role="group" aria-label="Filtrar histórico">
          <button class="${filtroHistorico === "todos" ? "on" : ""}" data-hist="todos">Tudo (${historico.length})</button>
          <button class="${filtroHistorico === "comentarios" ? "on" : ""}" data-hist="comentarios">Comentários (${comentarios.length})</button>
        </div>
      </div>
      <form id="form-comentario" class="novo-comentario">
        <textarea name="texto" required placeholder="Escreva um comentário para documentar esta tarefa…"></textarea>
        <div class="actions" style="margin-top:8px">
          <span class="small muted">Ctrl + Enter para enviar</span>
          <button type="submit" class="btn primary">Adicionar comentário</button>
        </div>
      </form>
      ${
        exibidos.length
          ? `<ul class="timeline">${exibidos.map(itemHistorico).join("")}</ul>`
          : `<p class="muted">Nenhum comentário ainda.</p>`
      }
    </div>`;

  ligarAcoesTarefas([t]);
  document.getElementById("excluir-tarefa").onclick = async () => {
    if (!confirm(`Excluir a tarefa "${t.titulo}" e todo o seu histórico?`)) return;
    try {
      await api(`/tarefas/${id}`, { method: "DELETE" });
      toast("Tarefa excluída", true);
      location.hash = "#/tarefas";
    } catch (e) {
      toast(e.message);
    }
  };
  $app.querySelectorAll("[data-hist]").forEach(
    (el) => (el.onclick = () => ((filtroHistorico = el.dataset.hist), render()))
  );
  const form = document.getElementById("form-comentario");
  const enviar = async () => {
    const texto = form.texto.value.trim();
    if (!texto) return form.texto.focus();
    await acao(() => api(`/tarefas/${id}/comentarios`, { method: "POST", body: { texto } }), "Comentário adicionado");
  };
  form.onsubmit = (e) => (e.preventDefault(), enviar());
  form.texto.onkeydown = (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) (e.preventDefault(), enviar());
  };
  $app.querySelectorAll("[data-excluir-comentario]").forEach(
    (el) =>
      (el.onclick = () => {
        if (confirm("Excluir este comentário?"))
          acao(
            () => api(`/tarefas/${id}/comentarios/${el.dataset.excluirComentario}`, { method: "DELETE" }),
            "Comentário excluído"
          );
      })
  );
}

// ---------- Roteamento ----------

async function render() {
  const [, secao, id] = (location.hash || "#/tarefas").split("/");
  document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("active", a.dataset.nav === secao));
  try {
    if (secao === "clientes") await (id ? viewCliente(id) : viewClientes());
    else await (id && secao === "tarefas" ? viewTarefa(id) : viewTarefas());
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
