/**
 * admin_events.js
 * Painel Geral de Eventos do Admin (Multi-Eventos): criação, edição e
 * listagem de TODOS os eventos, e botão para entrar na tela de
 * gerenciamento de um evento específico.
 * O card do próximo evento com cronômetro (renderNextEventCard) vive em
 * common.js, pois é compartilhado com o Painel do Porteiro.
 */

let allEventsCache = [];

document.addEventListener("DOMContentLoaded", () => {
 if (Array.isArray(window.__INITIAL_EVENTS__)) {
 // Dados já vieram prontos do servidor (SSR) junto com o HTML: pinta a
 // lista real de imediato (sem fade, sem skeleton) e só então revalida
 // em segundo plano, para pegar qualquer mudança feita por outro
 // usuário entre o render do servidor e agora.
 applyEvents(window.__INITIAL_EVENTS__, { fade: false });
 loadEvents({ silent: true });
 } else {
 // Fallback (ex: SSR falhou no servidor): comportamento antigo.
 loadEvents();
 }
 document.getElementById("form-new-event").addEventListener("submit", handleCreateEvent);
 document.getElementById("form-edit-event").addEventListener("submit", handleSaveEditEvent);
 document.getElementById("btn-close-edit-event").addEventListener("click", closeEditEventModal);
});

async function loadEvents({ silent = false } = {}) {
 const listEl = document.getElementById("events-list");
 const result = await apiRequest("/api/events");

 if (!result.success) {
 // Numa revalidação silenciosa, um erro não deve derrubar a lista que
 // já está na tela (possivelmente vinda do SSR) — só loga e mantém.
 if (!silent) {
 renderEventsListWithFade(listEl, `<div class="empty-state">Erro ao carregar eventos: ${escapeHtml(result.error || "desconhecido")}</div>`);
 }
 return;
 }

 await applyEvents(result.data || [], { fade: !silent });
}

/**
 * Pinta allEventsCache + o card do próximo evento + a lista de eventos a
 * partir de um array de eventos já pronto (vindo do SSR ou da API).
 * `fade: false` pula a transição de opacidade do skeleton — usado só no
 * primeiro paint quando os dados já chegam junto com o HTML.
 */
async function applyEvents(events, { fade = true } = {}) {
 const listEl = document.getElementById("events-list");
 allEventsCache = events;
 renderNextEventCard(events, "admin");

 let html;
 if (events.length === 0) {
 html = `<div class="empty-state">Nenhum evento cadastrado ainda. Crie o primeiro evento acima.</div>`;
 } else {
 html = events.map((event) => `
 <div class="event-item">
 <div>
 <div class="event-name">
 ${escapeHtml(event.name)}
 <span class="badge ${event.status.css_class}" style="margin-left:8px;">${escapeHtml(event.status.label)}</span>
 </div>
 <div class="event-meta">
 ${escapeHtml(event.location || "Local não informado")} &nbsp;|&nbsp;
 ${formatDateTime(event.event_date)}
 </div>
 </div>
 <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
 <span class="badge">${event.total_guests || 0} convidados</span>
 <span class="badge" style="background:#E0F7E0; color:#1B7A1B;">${event.total_checked_in || 0} presentes</span>
 <a href="/admin/eventos/${event.id}" class="btn btn-primary">⚙ Gerenciar</a>
 <button class="btn btn-secondary" data-edit-event="${event.id}">✎ Editar</button>
 <button class="btn btn-danger" data-delete-event="${event.id}">🗑 Excluir</button>
 </div>
 </div>
 `).join("");
 }

 if (fade) {
 await renderEventsListWithFade(listEl, html);
 } else {
 listEl.innerHTML = html;
 listEl.removeAttribute("aria-busy");
 }

 listEl.querySelectorAll("[data-delete-event]").forEach((btn) => {
 btn.addEventListener("click", () => handleDeleteEvent(btn.getAttribute("data-delete-event")));
 });
 listEl.querySelectorAll("[data-edit-event]").forEach((btn) => {
 btn.addEventListener("click", () => openEditEventModal(btn.getAttribute("data-edit-event")));
 });
}

async function handleCreateEvent(e) {
 e.preventDefault();
 const btn = document.getElementById("btn-save-event");
 const name = document.getElementById("event-name").value.trim();
 const location = document.getElementById("event-location").value.trim();
 const eventDate = document.getElementById("event-date").value;
 const description = document.getElementById("event-description").value.trim();

 if (!name || !eventDate) {
 showToast("Preencha os campos obrigatórios (Nome e Data).", "error");
 return;
 }

 btn.disabled = true;
 btn.innerHTML = '<span class="spinner"></span> Salvando...';

 const result = await apiRequest("/api/events", {
 method: "POST",
 body: JSON.stringify({ name, location, description, event_date: eventDate }),
 });

 btn.disabled = false;
 btn.textContent = "Criar Evento";

 if (!result.success) {
 showToast(result.error || "Erro ao criar evento.", "error");
 return;
 }

 showToast("Evento criado com sucesso!", "success");
 document.getElementById("form-new-event").reset();
 loadEvents();
}

async function handleDeleteEvent(eventId) {
 if (!confirm("Tem certeza que deseja excluir este evento e todos os seus convidados? Esta ação não pode ser desfeita.")) {
 return;
 }
 const result = await apiRequest(`/api/events/${eventId}`, { method: "DELETE" });
 if (!result.success) {
 showToast(result.error || "Erro ao excluir evento.", "error");
 return;
 }
 showToast("Evento excluído.", "success");
 loadEvents();
}

// --------------------------------------------------------------------------
// EDIÇÃO DE EVENTO (MODAL)
// --------------------------------------------------------------------------

function openEditEventModal(eventId) {
 const event = allEventsCache.find((e) => e.id === eventId);
 if (!event) return;

 document.getElementById("edit-event-id").value = event.id;
 document.getElementById("edit-event-name").value = event.name || "";
 document.getElementById("edit-event-location").value = event.location || "";
 document.getElementById("edit-event-description").value = event.description || "";
 // datetime-local exige "YYYY-MM-DDTHH:MM" -- a API já retorna nesse formato
 document.getElementById("edit-event-date").value = (event.event_date || "").slice(0, 16);

 document.getElementById("edit-event-modal").classList.remove("hidden");
}

function closeEditEventModal() {
 document.getElementById("edit-event-modal").classList.add("hidden");
}

async function handleSaveEditEvent(e) {
 e.preventDefault();
 const btn = document.getElementById("btn-save-edit-event");
 const eventId = document.getElementById("edit-event-id").value;
 const name = document.getElementById("edit-event-name").value.trim();
 const location = document.getElementById("edit-event-location").value.trim();
 const description = document.getElementById("edit-event-description").value.trim();
 const eventDate = document.getElementById("edit-event-date").value;

 if (!name || !eventDate) {
 showToast("Preencha os campos obrigatórios (Nome e Data).", "error");
 return;
 }

 btn.disabled = true;
 btn.innerHTML = '<span class="spinner"></span> Salvando...';

 const result = await apiRequest(`/api/events/${eventId}`, {
 method: "PUT",
 body: JSON.stringify({ name, location, description, event_date: eventDate }),
 });

 btn.disabled = false;
 btn.textContent = "Salvar Alterações";

 if (!result.success) {
 showToast(result.error || "Erro ao editar evento.", "error");
 return;
 }

 showToast("Evento atualizado com sucesso!", "success");
 closeEditEventModal();
 loadEvents();
}
