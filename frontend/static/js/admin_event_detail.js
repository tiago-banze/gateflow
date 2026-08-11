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

document.addEventListener("DOMContentLoaded", () => {
 if (EVENT_MODULE !== "A") return; // Modelo B: elementos de convidados nem existem no HTML (ver Jinja no template)

 loadGuests("");
 document.getElementById("btn-import").addEventListener("click", handleImportGuests);
 document.getElementById("btn-export-pdf").addEventListener("click", () =>
 downloadFile(`/api/events/${EVENT_ID}/guests/export-pdf`, "btn-export-pdf", "Baixar Documento de Convites", "Gerando PDF...")
 );
 // Atalho no topo da página (Problema 3): o botão original fica dentro do
 // card "Documentos e Relatórios", mais abaixo -- este duplica a mesma
 // ação logo junto às estatísticas do evento, para quem não desce a
 // página, sem duplicar lógica (mesmo endpoint, seu próprio spinner).
 const quickPdfBtn = document.getElementById("btn-export-pdf-quick");
 if (quickPdfBtn) {
 quickPdfBtn.addEventListener("click", () =>
 downloadFile(`/api/events/${EVENT_ID}/guests/export-pdf`, "btn-export-pdf-quick", "⬇ Baixar PDF de Convites", "Gerando PDF...")
 );
 }
 document.getElementById("btn-export-contingency").addEventListener("click", () =>
 downloadFile(`/api/events/${EVENT_ID}/guests/contingency-pdf`, "btn-export-contingency", "Baixar Lista de Contingência (PDF)", "Gerando PDF...")
 );
 document.getElementById("btn-export-attendance").addEventListener("click", () =>
 downloadFile(`/api/events/${EVENT_ID}/guests/attendance-report`, "btn-export-attendance", "Baixar Relatório de Presença (CSV)", "Gerando CSV...")
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
 <span class="stat-pill">Total: ${stats.total}</span>
 <span class="stat-pill success">Presentes: ${stats.checked_in}</span>
 <span class="stat-pill pending">Pendentes: ${stats.pending}</span>
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
 <tr style="text-align:left; border-bottom:2px solid #EEF1F4;">
 <th style="padding:10px;">Nome</th>
 <th class="hide-on-mobile" style="padding:10px;">Cargo/Tipo</th>
 <th style="padding:10px;">Mesa</th>
 <th style="padding:10px;">Email</th>
 <th class="hide-on-mobile" style="padding:10px;">Telefone</th>
 <th style="padding:10px;">Status</th>
 <th style="padding:10px;">Convite</th>
 <th style="padding:10px;"></th>
 </tr>
 </thead>
 <tbody>
 ${guests.map((g) => `
 <tr style="border-bottom:1px solid #F1F3F5; ${g.checked_in ? "background:#F5FCF5;" : ""}">
 <td style="padding:10px; font-weight:600;">${escapeHtml(g.full_name)}</td>
 <td class="hide-on-mobile" style="padding:10px;">${escapeHtml(g.role || "-")}</td>
 <td style="padding:10px; font-weight:700; color:var(--color-primary);">${escapeHtml(g.table_number || "Não definida")}</td>
 <td style="padding:10px;">${escapeHtml(g.email || "-")}</td>
 <td class="hide-on-mobile" style="padding:10px;">${escapeHtml(g.phone || "-")}</td>
 <td style="padding:10px;">
 ${g.checked_in
 ? `<span class="badge" style="background:#E0F7E0; color:#1B7A1B;"> Presente</span>`
 : `<span class="badge">Pendente</span>`}
 </td>
 <td style="padding:10px;">
 ${renderInviteCell(g)}
 </td>
 <td style="padding:10px;">
 <div class="action-icons">
 <button class="icon-btn icon-btn-edit" title="Editar" data-edit-guest="${g.id}">✎</button>
 <button class="icon-btn icon-btn-delete" title="Excluir" data-delete-guest="${g.id}">🗑</button>
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
 return `<span class="badge" style="background:var(--color-hover-bg); color:var(--color-text-muted);" title="Sem e-mail cadastrado">—</span>`;
 }

 let badge;
 if (g.invite_email_status === "sent") {
 badge = `<span class="badge" style="background:#E0F7E0; color:#1B7A1B;">Enviado</span>`;
 } else if (g.invite_email_status === "failed") {
 badge = `<span class="badge" style="background:var(--color-error-bg); color:var(--color-error);">Falhou</span>`;
 } else {
 badge = `<span class="badge">Pendente</span>`;
 }

 const label = g.invite_email_status === "sent" ? "Reenviar" : "Enviar Convite";
 return `
 <div style="display:flex; flex-direction:column; align-items:flex-start; gap:4px;">
 ${badge}
 <button type="button" class="btn btn-secondary" style="padding:4px 10px; font-size:0.72rem; min-height:auto;" data-send-invite="${g.id}">${label}</button>
 </div>
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
 btn.textContent = "Importar Lista de Convidados";

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
 btn.textContent = "Adicionar Convidado";

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
 btn.textContent = "Salvar Alterações";

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
