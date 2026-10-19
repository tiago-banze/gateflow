/**
 * organizador_event_detail.js
 * Página do evento do Organizador: Resumo, Convidados, Convites e Definições.
 * Os números atualizam sozinhos (polling) enquanto a página está visível.
 */

const EVENT_ID = document.body.getAttribute("data-event-id");
const EVENT_ENDED = document.body.getAttribute("data-event-ended") === "true";
const POLL_INTERVAL_MS = 10000;

const state = { guests: [], rsvp: null, stats: null, channels: null, filter: "all", search: "", actionGuest: null };
let pollTimer = null;
let searchTimer = null;

const RSVP_BADGE = {
  confirmed: `<span class="badge badge-success">${icon("check", 13)} Confirmou</span>`,
  declined: `<span class="badge badge-danger">${icon("x", 13)} Recusou</span>`,
  pending: `<span class="badge badge-muted">${icon("clock", 13)} Sem resposta</span>`,
};
const CHANNEL_LABEL = { whatsapp: "WhatsApp", sms: "SMS", email: "e-mail" };

document.addEventListener("DOMContentLoaded", () => {
  const dateEl = document.getElementById("event-date-display");
  if (dateEl) dateEl.textContent = formatDateTime(dateEl.textContent.trim());

  initTabs("resumo");
  bindAddSheet();
  bindForms();
  bindSending();

  document.getElementById("detail-search").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.search = e.target.value.trim().toLowerCase(); renderGuests(); }, 200);
  });
  document.querySelectorAll("#guest-filters [data-filter]").forEach((btn) => {
    btn.addEventListener("click", () => setFilter(btn.getAttribute("data-filter")));
  });
  document.addEventListener("gf:setfilter", (e) => setFilter(e.detail.filter));
  document.addEventListener("gf:tabchange", (e) => {
    const fab = document.getElementById("fab-add-guest");
    if (fab && !EVENT_ENDED) fab.hidden = !["resumo", "convidados"].includes(e.detail.tab);
  });

  refreshAll();
  startPolling();
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) { clearInterval(pollTimer); } else { refreshAll(); startPolling(); }
  });

  // Acabou de criar o evento: leva logo a adicionar convidados.
  if (new URLSearchParams(window.location.search).get("novo") === "1" && !EVENT_ENDED) {
    window.history.replaceState(null, "", window.location.pathname + window.location.hash);
    showToast("Evento criado! Agora adicione os convidados.", "success");
    setTimeout(() => openSheet("add-guests-sheet"), 400);
  }
});

function startPolling() {
  clearInterval(pollTimer);
  pollTimer = setInterval(refreshAll, POLL_INTERVAL_MS);
}

async function refreshAll() {
  const [guestsRes, rsvpRes] = await Promise.all([
    apiRequest(`/api/organizador/events/${EVENT_ID}/guests`),
    apiRequest(`/api/organizador/events/${EVENT_ID}/rsvp-summary`),
  ]);
  if (guestsRes.success) { state.guests = guestsRes.data || []; state.stats = guestsRes.stats || null; }
  if (rsvpRes.success) state.rsvp = rsvpRes.data;
  renderSummary();
  renderGuests();
  renderSendCards();
}

// ---------------------------------------------------------------- Resumo ----
function renderSummary() {
  const total = state.guests.length;
  const r = state.rsvp || { confirmed: 0, declined: 0, pending: total, total_companions: 0 };
  const stats = state.stats || { checked_in: 0 };
  const set = (key, value) => document.querySelectorAll(`[data-kpi="${key}"]`).forEach((el) => { el.textContent = value; });
  set("total", total);
  set("confirmed", r.confirmed);
  set("pending", r.pending);
  set("declined", r.declined);
  set("checked_in", stats.checked_in ?? 0);
  set("not_in", Math.max(0, total - (stats.checked_in ?? 0)));

  const answered = total ? Math.round(((r.confirmed + r.declined) / total) * 100) : 0;
  document.getElementById("progress-answered").textContent = `${answered}%`;
  document.getElementById("progress-ok").style.width = `${total ? (r.confirmed / total) * 100 : 0}%`;
  document.getElementById("progress-no").style.width = `${total ? (r.declined / total) * 100 : 0}%`;
  document.getElementById("legend-companions").textContent = r.total_companions ? `+ ${r.total_companions} acompanhantes confirmados` : "";

  document.getElementById("tab-count-guests").textContent = total;
  const pendingInvites = state.guests.filter((g) => !g.invite_sent_at).length;
  document.getElementById("next-invites-sub").textContent =
    total === 0 ? "Adicione convidados primeiro" : pendingInvites ? `${pendingInvites} convite(s) por enviar` : "Todos os convites foram enviados";
  document.getElementById("next-pending-sub").textContent = r.pending ? `${r.pending} sem resposta` : "Todos responderam";
  const badge = document.getElementById("tab-count-invites");
  badge.textContent = pendingInvites;
  badge.classList.toggle("hidden", pendingInvites === 0);
}

// ------------------------------------------------------------- Convidados ----
function setFilter(name) {
  state.filter = name;
  document.querySelectorAll("#guest-filters [data-filter]").forEach((btn) => {
    btn.setAttribute("aria-pressed", btn.getAttribute("data-filter") === name ? "true" : "false");
  });
  renderGuests();
}

function guestMatchesFilter(g, filter) {
  if (filter === "all") return true;
  if (filter === "present") return Boolean(g.checked_in);
  return (g.rsvp_status || "pending") === filter;
}

function deliveryNote(g) {
  if (g.notify_error && !g.invite_sent_at) return `<div class="guest-note is-error">${icon("alert", 13)} Não enviado: ${escapeHtml(g.notify_error)}</div>`;
  if (g.invite_sent_at) {
    const via = (g.notify_channels || "").split(",").filter(Boolean).map((c) => CHANNEL_LABEL[c] || c).join(" + ");
    return `<div class="guest-note">${icon("check", 13)} Convite enviado${via ? ` por ${escapeHtml(via)}` : ""}</div>`;
  }
  return `<div class="guest-note">Convite ainda não enviado</div>`;
}

function renderGuests() {
  const box = document.getElementById("detail-guests");
  document.querySelectorAll("#guest-filters [data-count]").forEach((el) => {
    el.textContent = state.guests.filter((g) => guestMatchesFilter(g, el.getAttribute("data-count"))).length;
  });

  if (state.guests.length === 0) {
    box.className = "";
    box.innerHTML = `
      <div class="empty-card">
        <span class="empty-icon">${icon("users")}</span>
        <strong>Sem convidados</strong>
        <p>Adicione a sua lista: um a um ou importando uma planilha.</p>
        ${EVENT_ENDED ? "" : `<button class="btn btn-primary" type="button" data-sheet-open="add-guests-sheet">${icon("user-plus")} Adicionar convidados</button>`}
      </div>`;
    return;
  }

  const items = state.guests.filter((g) => guestMatchesFilter(g, state.filter))
    .filter((g) => !state.search || `${g.full_name} ${g.phone || ""} ${g.email || ""}`.toLowerCase().includes(state.search));

  box.className = "guest-list";
  if (items.length === 0) {
    box.innerHTML = `<div class="empty-card" style="grid-column:1/-1"><strong>Ninguém encontrado</strong><p>Experimente outro nome ou filtro.</p></div>`;
    return;
  }

  box.innerHTML = items.map((g) => `
    <div class="guest-row ${g.checked_in ? "is-present" : ""}">
      <span class="guest-avatar" aria-hidden="true">${escapeHtml((g.full_name || "?").trim().charAt(0).toUpperCase())}</span>
      <div class="guest-main">
        <div class="guest-name">${escapeHtml(g.full_name)}</div>
        <div class="guest-sub">
          ${RSVP_BADGE[g.rsvp_status] || RSVP_BADGE.pending}
          ${g.checked_in ? `<span class="badge badge-success">${icon("check", 13)} Presente</span>` : ""}
          ${g.table_number && g.table_number !== "Não definida" ? `<span>Mesa ${escapeHtml(g.table_number.replace(/^mesa\s*/i, ""))}</span>` : ""}
          ${g.rsvp_status === "confirmed" && g.companions_confirmed ? `<span>+${g.companions_confirmed}</span>` : ""}
        </div>
        ${deliveryNote(g)}
      </div>
      <button class="icon-btn" type="button" data-guest-menu="${g.id}" aria-label="Ações para ${escapeHtml(g.full_name)}">${icon("more-vertical")}</button>
    </div>`).join("");

  box.querySelectorAll("[data-guest-menu]").forEach((btn) => {
    btn.addEventListener("click", () => openGuestActions(btn.getAttribute("data-guest-menu")));
  });
}

function openGuestActions(guestId) {
  const g = state.guests.find((x) => x.id === guestId);
  if (!g) return;
  state.actionGuest = g;
  document.getElementById("guest-actions-title").textContent = g.full_name;
  document.getElementById("guest-actions-info").textContent = [g.phone, g.email].filter(Boolean).join(" · ") || "Sem contacto registado";
  document.getElementById("act-invite-sub").textContent = g.invite_sent_at ? "Reenviar o convite" : "Link para confirmar presença";
  document.getElementById("act-reminder").hidden = g.rsvp_status !== "confirmed";
  openSheet("guest-actions-sheet");
}

// ------------------------------------------------------------------ Envio ----
async function loadChannels() {
  const res = await apiRequest("/api/organizador/notifications/status");
  if (res.success) state.channels = res.data;
  renderChannels();
}

function renderChannels() {
  const box = document.getElementById("channels-box");
  const ch = state.channels;
  if (!ch) { box.innerHTML = ""; return; }
  const defs = [["whatsapp", "WhatsApp", "message"], ["sms", "SMS", "phone"], ["email", "E-mail", "mail"]];
  const any = defs.some(([k]) => ch[k].configured);
  box.innerHTML = `
    ${any ? "" : `<div class="notice is-warning">${icon("alert")}<div><strong>Envio ainda não ativo.</strong> O servidor não tem nenhum canal (WhatsApp, SMS ou e-mail) configurado. Peça ao administrador para configurar — enquanto isso, pode copiar o link de cada convidado e enviar à mão.</div></div>`}
    <div class="channel-grid">
      ${defs.map(([k, label, ico]) => `
        <div class="channel ${ch[k].configured ? "is-on" : "is-off"}">
          ${icon(ico)}<span>${label}</span><small>${ch[k].configured ? "Ativo" : "Não configurado"}</small>
        </div>`).join("")}
    </div>`;
  document.getElementById("btn-send-invites-bulk").disabled = !any || EVENT_ENDED;
  document.getElementById("btn-send-reminders-bulk").disabled = !any || EVENT_ENDED;
}

function renderSendCards() {
  const pendingInvites = state.guests.filter((g) => !g.invite_sent_at).length;
  const pendingReminders = state.guests.filter((g) => g.rsvp_status === "confirmed" && !g.reminder_sent_at).length;
  const inv = document.getElementById("btn-send-invites-bulk");
  const rem = document.getElementById("btn-send-reminders-bulk");
  if (!inv.dataset.busy) inv.innerHTML = `${icon("send")} ${pendingInvites ? `Enviar ${pendingInvites} convite(s)` : "Sem convites por enviar"}`;
  if (!rem.dataset.busy) rem.innerHTML = `${icon("bell")} ${pendingReminders ? `Enviar ${pendingReminders} lembrete(s)` : "Sem lembretes por enviar"}`;
  if (!inv.dataset.busy && !pendingInvites) inv.disabled = true;
  else if (!inv.dataset.busy && state.channels) inv.disabled = !Object.values(state.channels).some((c) => c.configured) || EVENT_ENDED;
  if (!rem.dataset.busy && !pendingReminders) rem.disabled = true;
  else if (!rem.dataset.busy && state.channels) rem.disabled = !Object.values(state.channels).some((c) => c.configured) || EVENT_ENDED;
}

/**
 * Envia em etapas (o servidor trata alguns convidados por pedido) e mostra o
 * progresso real. Os que falham ficam de fora das etapas seguintes e são
 * listados no fim com o motivo.
 */
async function runBulkSend(kind) {
  const isInvite = kind === "invite";
  const btn = document.getElementById(isInvite ? "btn-send-invites-bulk" : "btn-send-reminders-bulk");
  const progress = document.getElementById(isInvite ? "progress-invites" : "progress-reminders");
  const report = document.getElementById(isInvite ? "report-invites" : "report-reminders");
  const url = `/api/organizador/events/${EVENT_ID}/guests/${isInvite ? "send-invites" : "send-reminders"}`;
  const original = btn.innerHTML;

  btn.disabled = true;
  btn.dataset.busy = "1";
  btn.innerHTML = '<span class="spinner"></span> A enviar…';
  report.innerHTML = "";
  progress.classList.add("is-active");

  let sent = 0;
  const failed = [];
  let total = null;
  let remaining = 1;
  let guard = 0;

  while (remaining > 0 && guard++ < 200) {
    const res = await apiRequest(url, { method: "POST", body: JSON.stringify({ skip_ids: failed.map((f) => f.id) }) });
    if (!res.success) {
      report.innerHTML = `<div class="notice is-warning">${icon("alert")}<div>${escapeHtml(res.error || "Erro ao enviar.")}</div></div>`;
      break;
    }
    const d = res.data;
    if (total === null) total = d.total_pending;
    sent += d.sent;
    failed.push(...d.failed);
    remaining = d.remaining;
    const done = sent + failed.length;
    progress.querySelector(".progress-fill").style.width = `${total ? Math.min(100, (done / total) * 100) : 100}%`;
    progress.querySelector("small").textContent = `${done} de ${total}`;
    if (d.sent === 0 && d.failed.length === 0) break;
  }

  delete btn.dataset.busy;
  btn.innerHTML = original;
  progress.classList.remove("is-active");

  if (total === 0) {
    report.innerHTML = `<div class="ok">Nada por enviar.</div>`;
  } else if (sent || failed.length) {
    report.innerHTML = `
      ${sent ? `<div class="ok">${icon("check", 15)} ${sent} enviado(s) com sucesso.</div>` : ""}
      ${failed.length ? `<div style="color:var(--color-error);font-weight:700;margin-top:6px">${failed.length} não enviado(s):</div>
        <ul>${failed.slice(0, 8).map((f) => `<li>${escapeHtml(f.name)} — ${escapeHtml(f.error || "erro")}</li>`).join("")}</ul>
        ${failed.length > 8 ? `<small>…e mais ${failed.length - 8}.</small>` : ""}` : ""}`;
  }
  if (sent) showToast(`${sent} ${isInvite ? "convite(s)" : "lembrete(s)"} enviado(s).`, "success");
  else if (failed.length) showToast("Nenhuma mensagem foi enviada. Veja o motivo abaixo.", "error", 5000);
  await refreshAll();
}

function bindSending() {
  loadChannels();
  document.getElementById("btn-send-invites-bulk").addEventListener("click", () => runBulkSend("invite"));
  document.getElementById("btn-send-reminders-bulk").addEventListener("click", () => runBulkSend("reminder"));

  const sendOne = async (kind) => {
    const g = state.actionGuest;
    if (!g) return;
    closeSheet("guest-actions-sheet");
    showToast("A enviar…", "info", 1500);
    const res = await apiRequest(`/api/organizador/events/${EVENT_ID}/guests/${g.id}/${kind === "invite" ? "send-invite" : "send-reminder"}`, { method: "POST" });
    if (!res.success) { showToast(res.error || "Não foi possível enviar.", "error", 6000); }
    else {
      const via = (res.raw.channels || []).map((c) => CHANNEL_LABEL[c] || c).join(" + ");
      showToast(`${kind === "invite" ? "Convite" : "Lembrete"} enviado${via ? ` por ${via}` : ""}.`, "success");
    }
    refreshAll();
  };
  document.getElementById("act-invite").addEventListener("click", () => sendOne("invite"));
  document.getElementById("act-reminder").addEventListener("click", () => sendOne("reminder"));
  document.getElementById("act-copy").addEventListener("click", async () => {
    const g = state.actionGuest;
    if (!g) return;
    const res = await apiRequest(`/api/organizador/events/${EVENT_ID}/guests/${g.id}/rsvp-link`);
    if (!res.success) { showToast(res.error || "Erro ao obter o link.", "error"); return; }
    try {
      await navigator.clipboard.writeText(res.data.url);
      showToast("Link copiado.", "success");
    } catch (e) {
      window.prompt("Copie o link:", res.data.url);
    }
    closeSheet("guest-actions-sheet");
  });
}

// ------------------------------------------------------ Adicionar convidados ----
function bindAddSheet() {
  const tabs = document.querySelectorAll("#add-mode-tabs [data-mode]");
  tabs.forEach((tab) => tab.addEventListener("click", () => {
    const mode = tab.getAttribute("data-mode");
    tabs.forEach((t) => t.setAttribute("aria-selected", t === tab ? "true" : "false"));
    document.querySelectorAll("[data-mode-panel]").forEach((p) => { p.hidden = p.getAttribute("data-mode-panel") !== mode; });
  }));
}

function bindForms() {
  document.getElementById("btn-download-template").addEventListener("click", downloadTemplate);
  document.getElementById("btn-import").addEventListener("click", handleImportGuests);
  document.getElementById("form-new-guest").addEventListener("submit", handleCreateGuestManual);
  document.getElementById("form-courtesy").addEventListener("submit", handleIssueCourtesy);
  document.getElementById("form-rsvp-settings").addEventListener("submit", handleSaveRsvpSettings);
  document.getElementById("form-event-edit").addEventListener("submit", handleSaveEvent);
}

async function handleSaveEvent(e) {
  e.preventDefault();
  const btn = document.getElementById("btn-save-edit");
  const payload = {
    name: document.getElementById("edit-name").value.trim(),
    event_date: document.getElementById("edit-date").value,
    location: document.getElementById("edit-location").value.trim(),
    organizer_display_name: document.getElementById("edit-organizer").value.trim(),
    description: document.getElementById("edit-description").value.trim(),
  };
  if (!payload.name || !payload.event_date || !payload.location || !payload.organizer_display_name) {
    showToast("Preencha nome, data, local e organizador.", "error");
    return;
  }
  btn.disabled = true;
  const res = await apiRequest(`/api/organizador/events/${EVENT_ID}`, { method: "PUT", body: JSON.stringify(payload) });
  btn.disabled = false;
  if (!res.success) { showToast(res.error || "Erro ao guardar.", "error"); return; }
  showToast("Evento atualizado.", "success");
  setTimeout(() => window.location.reload(), 600);
}

async function handleSaveRsvpSettings(e) {
  e.preventDefault();
  const deadlineRaw = document.getElementById("rsvp-deadline-days").value.trim();
  const res = await apiRequest(`/api/organizador/events/${EVENT_ID}/rsvp-settings`, {
    method: "PUT",
    body: JSON.stringify({
      rsvp_deadline_days: deadlineRaw === "" ? null : parseInt(deadlineRaw, 10),
      location_maps_url: document.getElementById("rsvp-maps-url").value.trim(),
    }),
  });
  if (!res.success) { showToast(res.error || "Erro ao guardar.", "error"); return; }
  showToast("Definições guardadas.", "success");
}

async function handleCreateGuestManual(e) {
  e.preventDefault();
  const btn = document.getElementById("btn-save-guest");
  const full_name = document.getElementById("guest-name").value.trim();
  const phone = document.getElementById("guest-phone").value.trim();
  const email = document.getElementById("guest-email").value.trim();
  const companionsAllowed = parseInt(document.getElementById("guest-companions").value || "0", 10);
  if (!full_name) { showToast("O nome é obrigatório.", "error"); return; }
  if (!phone && !email) {
    if (!confirm("Sem telemóvel nem e-mail não será possível enviar o convite a este convidado. Adicionar mesmo assim?")) return;
  }

  btn.disabled = true;
  const result = await apiRequest(`/api/organizador/events/${EVENT_ID}/guests`, {
    method: "POST",
    body: JSON.stringify({
      full_name, email, phone,
      role: document.getElementById("guest-role").value.trim(),
      table_number: document.getElementById("guest-table").value.trim(),
    }),
  });
  if (result.success && companionsAllowed > 0) {
    await apiRequest(`/api/organizador/events/${EVENT_ID}/guests/${result.data.id}/companions`, {
      method: "PUT", body: JSON.stringify({ companions_allowed: companionsAllowed }),
    });
  }
  btn.disabled = false;
  if (!result.success) { showToast(result.error || "Erro ao adicionar.", "error"); return; }

  showToast(`${result.data.full_name} adicionado(a).`, "success");
  document.getElementById("form-new-guest").reset();
  document.getElementById("guest-companions").value = 0;
  document.getElementById("guest-name").focus();
  refreshAll(); // a folha fica aberta para adicionar o seguinte
}

async function handleIssueCourtesy(e) {
  e.preventDefault();
  const fullName = document.getElementById("courtesy-name").value.trim();
  if (!fullName) { showToast("O nome é obrigatório.", "error"); return; }
  const res = await apiRequest(`/api/organizador/events/${EVENT_ID}/guests/courtesy`, {
    method: "POST",
    body: JSON.stringify({
      full_name: fullName,
      email: document.getElementById("courtesy-email").value.trim(),
      phone: document.getElementById("courtesy-phone").value.trim(),
      table_number: document.getElementById("courtesy-table").value.trim(),
    }),
  });
  if (!res.success) { showToast(res.error || "Erro ao emitir convite.", "error"); return; }
  showToast("Convite de cortesia emitido.", "success");
  document.getElementById("form-courtesy").reset();
  refreshAll();
}

async function handleImportGuests() {
  const fileInput = document.getElementById("input-xlsx");
  const file = fileInput.files[0];
  if (!file) { showToast("Escolha um ficheiro .xlsx.", "error"); return; }
  const btn = document.getElementById("btn-import");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> A importar…';
  const formData = new FormData();
  formData.append("file", file);
  const res = await apiRequest(`/api/organizador/events/${EVENT_ID}/import`, { method: "POST", body: formData });
  btn.disabled = false;
  btn.innerHTML = `${icon("upload")} Importar`;
  if (!res.success) { showToast(res.error || "Erro ao importar.", "error"); return; }
  showToast(res.data.summary, "success", 5000);
  fileInput.value = "";
  closeSheet("add-guests-sheet");
  refreshAll();
  if (window.gotoTab) window.gotoTab("convidados");
}

async function downloadTemplate() {
  try {
    const response = await fetch(`${window.location.origin}/api/events/template-xlsx`, { credentials: "same-origin" });
    if (!response.ok) { showToast("Erro ao baixar o modelo.", "error"); return; }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "modelo_convidados_gateflow.xlsx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    showToast("Erro de ligação ao baixar o modelo.", "error");
  }
}
