/**
 * admin_event_detail.js
 * Gerenciamento de UM evento específico: o event_id vem embutido no HTML
 * (data-event-id no <body>), definido pela rota /admin/eventos/<event_id>
 * no servidor - não depende mais de seleção via JavaScript.
 */

const EVENT_ID = document.body.getAttribute("data-event-id");
const EVENT_MODULE = document.body.getAttribute("data-event-module");
let guestsSearchTimeout = null;
let guestsCache = [];

// Corre sempre, independente do Módulo (A ou B): o servidor manda a data
// crua em ISO (ex: "2026-08-25T18:12:00") -- aqui trocamos pelo formato
// amigável (formatDateTime, já usado no resto do sistema) para não
// "estourar" o cabeçalho do card em telas pequenas nem exibir um formato
// técnico ao utilizador.
document.addEventListener("DOMContentLoaded", () => {
 const dateEl = document.getElementById("event-date-display");
 if (dateEl && dateEl.textContent.trim()) {
 dateEl.textContent = formatDateTime(dateEl.textContent.trim());
 }
});

document.addEventListener("DOMContentLoaded", () => {
 if (EVENT_MODULE !== "A") return; // Modelo B: elementos de convidados nem existem no HTML (ver Jinja no template)

 loadGuests("");
 document.getElementById("btn-import").addEventListener("click", handleImportGuests);
 document.getElementById("btn-export-pdf").addEventListener("click", () =>
 downloadFile(`/api/events/${EVENT_ID}/guests/export-pdf`, "btn-export-pdf", `${icon("download")} Baixar documento de convites`, "Gerando PDF...")
 );
 // Atalho no topo da página (Problema 3): o botão original fica dentro do
 // card "Documentos e Relatórios", mais abaixo -- este duplica a mesma
 // ação logo junto às estatísticas do evento, para quem não desce a
 // página, sem duplicar lógica (mesmo endpoint, seu próprio spinner).
 const quickPdfBtn = document.getElementById("btn-export-pdf-quick");
 if (quickPdfBtn) {
 quickPdfBtn.addEventListener("click", () =>
 downloadFile(`/api/events/${EVENT_ID}/guests/export-pdf`, "btn-export-pdf-quick", `${icon("download")} Baixar PDF de convites`, "Gerando PDF...")
 );
 }
 document.getElementById("btn-export-contingency").addEventListener("click", () =>
 downloadFile(`/api/events/${EVENT_ID}/guests/contingency-pdf`, "btn-export-contingency", `${icon("file-text")} Baixar lista de contingência (PDF)`, "Gerando PDF...")
 );
 document.getElementById("btn-export-attendance").addEventListener("click", () =>
 downloadFile(`/api/events/${EVENT_ID}/guests/attendance-report`, "btn-export-attendance", `${icon("bar-chart")} Baixar relatório de presença (CSV)`, "Gerando CSV...")
 );
 document.getElementById("form-new-guest").addEventListener("submit", handleCreateGuestManual);
 document.getElementById("form-edit-guest").addEventListener("submit", handleSaveEditGuest);
 document.getElementById("btn-close-edit-guest").addEventListener("click", closeEditGuestModal);
 document.getElementById("detail-search").addEventListener("input", (e) => {
 clearTimeout(guestsSearchTimeout);
 guestsSearchTimeout = setTimeout(() => loadGuests(e.target.value), 250);
 });
});

function renderStats(stats) {
 const statsEl = document.getElementById("detail-stats");
 if (!stats) { statsEl.innerHTML = ""; return; }
 statsEl.innerHTML = `
 <div class="stat-pill"><span class="stat-label">Total</span><span class="stat-value">${stats.total}</span></div>
 <div class="stat-pill success"><span class="stat-label">Presentes</span><span class="stat-value">${stats.checked_in}</span></div>
 <div class="stat-pill pending"><span class="stat-label">Pendentes</span><span class="stat-value">${stats.pending}</span></div>
 `;

 const miniCountEl = document.getElementById("event-mini-count");
 if (miniCountEl) {
 miniCountEl.textContent = `${stats.checked_in}/${stats.total}`;
 }
}

async function loadGuests(search) {
 const tableEl = document.getElementById("detail-guests-table");
 const query = search ? `?search=${encodeURIComponent(search)}` : "";
 const result = await apiRequest(`/api/events/${EVENT_ID}/guests${query}`);

 if (!result.success) {
 tableEl.innerHTML = `<div class="empty-state">Erro ao carregar convidados.</div>`;
 return;
 }

 if (result.stats) renderStats(result.stats);

 const guests = result.data || [];
 guestsCache = guests;

 if (guests.length === 0) {
 tableEl.innerHTML = `<div class="empty-state">Nenhum convidado encontrado.</div>`;
 return;
 }

 tableEl.innerHTML = `
 <div class="table-responsive">
 <table>
 <thead>
 <tr>
 <th>Nome</th>
 <th class="hide-on-mobile">Cargo/Tipo</th>
 <th>Mesa</th>
 <th>Email</th>
 <th class="hide-on-mobile">Telefone</th>
 <th>Status</th>
 <th>Convite</th>
 <th><span class="sr-only">Ações</span></th>
 </tr>
 </thead>
 <tbody>
 ${guests.map((g) => `
 <tr class="${g.checked_in ? "checked-in" : ""}">
 <td class="cell-strong">${escapeHtml(g.full_name)}</td>
 <td class="hide-on-mobile">${escapeHtml(g.role || "-")}</td>
 <td class="cell-accent">${escapeHtml(g.table_number || "Não definida")}</td>
 <td class="cell-muted">${escapeHtml(g.email || "-")}</td>
 <td class="hide-on-mobile cell-muted">${escapeHtml(g.phone || "-")}</td>
 <td>
 ${g.checked_in
 ? `<span class="badge badge-success">${icon("check", 13)} Presente</span>`
 : `<span class="badge badge-muted">Pendente</span>`}
 </td>
 <td>${renderInviteCell(g)}</td>
 <td class="cell-actions">
 <div class="action-icons">
 <button class="icon-btn icon-btn-edit" title="Editar" aria-label="Editar ${escapeHtml(g.full_name)}" data-edit-guest="${g.id}">${icon("edit")}</button>
 <button class="icon-btn icon-btn-delete" title="Excluir" aria-label="Excluir ${escapeHtml(g.full_name)}" data-delete-guest="${g.id}">${icon("trash")}</button>
 </div>
 </td>
 </tr>
 `).join("")}
 </tbody>
 </table>
 </div>
 `;

 tableEl.querySelectorAll("[data-edit-guest]").forEach((btn) => {
 btn.addEventListener("click", () => openEditGuestModal(btn.getAttribute("data-edit-guest")));
 });
 tableEl.querySelectorAll("[data-delete-guest]").forEach((btn) => {
 btn.addEventListener("click", () => handleDeleteGuest(btn.getAttribute("data-delete-guest")));
 });
 tableEl.querySelectorAll("[data-send-invite]").forEach((btn) => {
 btn.addEventListener("click", () => handleSendInvite(btn.getAttribute("data-send-invite")));
 });
}

// --------------------------------------------------------------------------
// CONVITE POR E-MAIL (envio manual / reenvio) — Módulo A
// --------------------------------------------------------------------------

function renderInviteCell(g) {
 if (!g.email) {
 return `<span class="badge badge-muted" title="Sem e-mail cadastrado">—</span>`;
 }

 let badge;
 if (g.invite_email_status === "sent") {
 badge = `<span class="badge badge-success">${icon("check", 13)} Enviado</span>`;
 } else if (g.invite_email_status === "failed") {
 badge = `<span class="badge badge-danger">${icon("x", 13)} Falhou</span>`;
 } else {
 badge = `<span class="badge badge-muted">Pendente</span>`;
 }

 const label = g.invite_email_status === "sent" ? "Reenviar" : "Enviar Convite";
 return `
 <div style="display:flex; flex-direction:column; align-items:flex-start; gap:6px;"> ${badge} <button type="button" class="btn btn-secondary btn-sm" data-send-invite="${g.id}">${label}</button> </div>
 `;
}

async function handleSendInvite(guestId) {
 const btn = document.querySelector(`[data-send-invite="${guestId}"]`);
 if (btn) {
 btn.disabled = true;
 btn.innerHTML = '<span class="spinner"></span>';
 }

 const result = await apiRequest(`/api/events/${EVENT_ID}/guests/${guestId}/send-invite`, { method: "POST" });

 if (!result.success) {
 showToast(result.error || "Erro ao enviar o convite por e-mail.", "error");
 } else {
 showToast("Convite enviado por e-mail com sucesso!", "success");
 }
 // Atualiza a badge/linha independentemente de sucesso ou falha, já que
 // o backend sempre grava o resultado ('sent' ou 'failed') no convidado.
 loadGuests(document.getElementById("detail-search").value);
}

async function handleImportGuests() {
 const fileInput = document.getElementById("input-xlsx");
 const file = fileInput.files[0];

 if (!file) {
 showToast("Selecione um arquivo .xlsx para importar.", "error");
 return;
 }

 const btn = document.getElementById("btn-import");
 btn.disabled = true;
 btn.innerHTML = '<span class="spinner"></span> Importando e gerando QR Codes...';

 const formData = new FormData();
 formData.append("file", file);

 const result = await apiRequest(`/api/events/${EVENT_ID}/import`, {
 method: "POST",
 body: formData,
 });

 btn.disabled = false;
 btn.innerHTML = `${icon("upload")} Importar lista de convidados`;

 if (!result.success) {
 showToast(result.error || "Erro ao importar convidados.", "error");
 return;
 }

 const { summary, warnings } = result.data;
 showToast(summary, "success", 5000);
 if (warnings && warnings.length > 0) {
 showToast(`${warnings.length} linha(s) da planilha foram ignoradas. Verifique o console.`, "info");
 console.warn("Avisos de importação:", warnings);
 }

 fileInput.value = "";
 loadGuests("");
}

async function handleCreateGuestManual(e) {
 e.preventDefault();
 const btn = document.getElementById("btn-save-guest");
 const full_name = document.getElementById("guest-name").value.trim();
 const email = document.getElementById("guest-email").value.trim();
 const phone = document.getElementById("guest-phone").value.trim();
 const role = document.getElementById("guest-role").value.trim();
 const table_number = document.getElementById("guest-table").value.trim();

 if (!full_name) {
 showToast("O nome completo é obrigatório.", "error");
 return;
 }

 btn.disabled = true;
 btn.innerHTML = '<span class="spinner"></span> Adicionando...';

 const result = await apiRequest(`/api/events/${EVENT_ID}/guests`, {
 method: "POST",
 body: JSON.stringify({ full_name, email, phone, role, table_number }),
 });

 btn.disabled = false;
 btn.innerHTML = `${icon("plus")} Adicionar convidado`;

 if (!result.success) {
 showToast(result.error || "Erro ao adicionar convidado.", "error");
 return;
 }

 showToast(`Convidado "${result.data.full_name}" adicionado com sucesso!`, "success");
 document.getElementById("form-new-guest").reset();
 loadGuests("");
}

// --------------------------------------------------------------------------
// EDIÇÃO E EXCLUSÃO DE CONVIDADO
// --------------------------------------------------------------------------

function openEditGuestModal(guestId) {
 const guest = guestsCache.find((g) => g.id === guestId);
 if (!guest) return;

 document.getElementById("edit-guest-id").value = guest.id;
 document.getElementById("edit-guest-name").value = guest.full_name || "";
 document.getElementById("edit-guest-email").value = guest.email || "";
 document.getElementById("edit-guest-phone").value = guest.phone || "";
 document.getElementById("edit-guest-role").value = guest.role || "";
 document.getElementById("edit-guest-table").value = guest.table_number || "";

 document.getElementById("edit-guest-modal").classList.remove("hidden");
}

function closeEditGuestModal() {
 document.getElementById("edit-guest-modal").classList.add("hidden");
}

async function handleSaveEditGuest(e) {
 e.preventDefault();
 const btn = document.getElementById("btn-save-edit-guest");
 const guestId = document.getElementById("edit-guest-id").value;
 const full_name = document.getElementById("edit-guest-name").value.trim();
 const email = document.getElementById("edit-guest-email").value.trim();
 const phone = document.getElementById("edit-guest-phone").value.trim();
 const role = document.getElementById("edit-guest-role").value.trim();
 const table_number = document.getElementById("edit-guest-table").value.trim();

 if (!full_name) {
 showToast("O nome completo é obrigatório.", "error");
 return;
 }

 btn.disabled = true;
 btn.innerHTML = '<span class="spinner"></span> Salvando...';

 const result = await apiRequest(`/api/events/${EVENT_ID}/guests/${guestId}`, {
 method: "PUT",
 body: JSON.stringify({ full_name, email, phone, role, table_number }),
 });

 btn.disabled = false;
 btn.innerHTML = `${icon("check")} Salvar alterações`;

 if (!result.success) {
 showToast(result.error || "Erro ao editar convidado.", "error");
 return;
 }

 showToast("Convidado atualizado com sucesso!", "success");
 closeEditGuestModal();
 loadGuests("");
}

async function handleDeleteGuest(guestId) {
 const guest = guestsCache.find((g) => g.id === guestId);
 const name = guest ? guest.full_name : "este convidado";
 if (!confirm(`Tem certeza que deseja excluir "${name}"? Esta ação não pode ser desfeita.`)) {
 return;
 }

 const result = await apiRequest(`/api/events/${EVENT_ID}/guests/${guestId}`, { method: "DELETE" });
 if (!result.success) {
 showToast(result.error || "Erro ao excluir convidado.", "error");
 return;
 }

 showToast("Convidado excluído.", "success");
 loadGuests("");
}

// --------------------------------------------------------------------------
// DOWNLOADS (Convites, Contingência, Relatório de Presença)
// --------------------------------------------------------------------------

async function downloadFile(path, btnId, originalLabel, loadingLabel) {
 const btn = document.getElementById(btnId);
 btn.disabled = true;
 btn.innerHTML = `<span class="spinner"></span> ${loadingLabel}`;

 try {
 const response = await fetch(`${window.location.origin}${path}`);
 if (!response.ok) {
 const errorPayload = await response.json().catch(() => ({}));
 showToast(errorPayload.error || "Erro ao gerar o arquivo.", "error");
 return;
 }

 const blob = await response.blob();
 const url = window.URL.createObjectURL(blob);
 const a = document.createElement("a");
 a.href = url;
 a.download = extractFilenameFromContentDisposition(response.headers.get("Content-Disposition")) || "arquivo";
 document.body.appendChild(a);
 a.click();
 a.remove();
 window.URL.revokeObjectURL(url);
 showToast("Arquivo gerado com sucesso!", "success");
 } catch (err) {
 showToast("Erro de conexão ao gerar o arquivo.", "error");
 } finally {
 btn.disabled = false;
 btn.innerHTML = originalLabel;
 }
}

function extractFilenameFromContentDisposition(headerValue) {
 if (!headerValue) return null;
 const match = /filename="?([^"]+)"?/.exec(headerValue);
 return match ? match[1] : null;
}
