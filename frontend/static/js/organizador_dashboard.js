/**
 * organizador_dashboard.js
 * Painel do Organizador (Fase 2): formulário dinâmico de criação de
 * evento (Módulo A ou B) e listagem de TODOS os eventos da plataforma,
 * com os que não pertencem ao usuário aparecendo desabilitados.
 */

document.addEventListener("DOMContentLoaded", () => {
 loadEvents();
 loadPorteiros();
 document.getElementById("form-new-event").addEventListener("submit", handleCreateEvent);
 document.getElementById("form-new-porteiro").addEventListener("submit", handleCreatePorteiro);
});

async function loadEvents() {
 const listEl = document.getElementById("events-list");
 const result = await apiRequest("/api/organizador/events");

 if (!result.success) {
 listEl.innerHTML = `<div class="empty-state">Erro ao carregar eventos: ${escapeHtml(result.error || "desconhecido")}</div>`;
 return;
 }

 const events = result.data || [];
 renderNextEventCard(events.filter((e) => e.is_own), "organizador");
 if (events.length === 0) {
 listEl.innerHTML = `<div class="empty-state">Nenhum evento cadastrado na plataforma ainda. Crie o primeiro evento acima!</div>`;
 return;
 }

 listEl.innerHTML = events.map((event) => {
 if (event.is_own) {
 return `
 <div class="event-item event-item-own">
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
 <span class="badge">${event.total_guests ?? 0} convidados</span>
 <a href="/organizador/eventos/${event.id}" class="btn btn-primary">⚙ Gerenciar</a>
 </div>
 </div>`;
 }

 return `
 <div class="event-item event-item-disabled">
 <div>
 <div class="event-name">
 ${escapeHtml(event.name)}
 <span class="badge badge-other-organizer" style="margin-left:8px;">Outro Organizador</span>
 </div>
 <div class="event-meta">
 ${escapeHtml(event.location || "Local não informado")} &nbsp;|&nbsp;
 ${formatDateTime(event.event_date)}
 </div>
 </div>
 <div>
 <button class="btn btn-secondary" disabled title="Você só pode gerenciar seus próprios eventos">🔒 Indisponível</button>
 </div>
 </div>`;
 }).join("");
}

async function handleCreateEvent(e) {
 e.preventDefault();
 const btn = document.getElementById("btn-save-event");

 const payload = {
 event_module: "A",
 name: document.getElementById("event-name").value.trim(),
 organizer_display_name: document.getElementById("event-organizer-name").value.trim(),
 location: document.getElementById("event-location").value.trim(),
 event_date: document.getElementById("event-date").value,
 description: document.getElementById("event-description").value.trim(),
 };

 if (!payload.name || !payload.organizer_display_name || !payload.location || !payload.event_date) {
 showToast("Preencha todos os campos obrigatórios.", "error");
 return;
 }

 btn.disabled = true;
 btn.innerHTML = '<span class="spinner"></span> Criando...';

 const result = await apiRequest("/api/organizador/events", {
 method: "POST",
 body: JSON.stringify(payload),
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

// --------------------------------------------------------------------------
// MEUS PORTEIROS (Fase 5, item C4) — até 3 contas de "porteiro do promotor"
// --------------------------------------------------------------------------

async function loadPorteiros() {
 const listEl = document.getElementById("porteiros-list");
 const result = await apiRequest("/api/organizador/porteiros");

 if (!result.success) {
 listEl.innerHTML = `<div class="empty-state">Erro ao carregar porteiros: ${escapeHtml(result.error || "desconhecido")}</div>`;
 return;
 }

 const porteiros = result.data || [];
 const limit = result.limit || 3;

 const form = document.getElementById("form-new-porteiro");
 const submitBtn = document.getElementById("btn-save-porteiro");
 if (porteiros.length >= limit) {
 submitBtn.disabled = true;
 submitBtn.textContent = "Limite atingido";
 } else {
 submitBtn.disabled = false;
 submitBtn.textContent = "Adicionar Porteiro";
 }

 if (porteiros.length === 0) {
 listEl.innerHTML = `<div class="empty-state">Nenhum porteiro cadastrado ainda.</div>`;
 return;
 }

 listEl.innerHTML = porteiros.map((p) => `
 <div class="event-item">
 <div>
 <div class="event-name">${escapeHtml(p.full_name || p.username)}</div>
 <div class="event-meta">Usuário: ${escapeHtml(p.username)} · Vinculado só aos seus eventos</div>
 </div>
 </div>
 `).join("");
}

async function handleCreatePorteiro(e) {
 e.preventDefault();
 const btn = document.getElementById("btn-save-porteiro");
 btn.disabled = true;

 const payload = {
 full_name: document.getElementById("porteiro-full-name").value.trim(),
 username: document.getElementById("porteiro-username").value.trim(),
 password: document.getElementById("porteiro-password").value,
 };

 const result = await apiRequest("/api/organizador/porteiros", {
 method: "POST",
 body: JSON.stringify(payload),
 });

 if (!result.success) {
 showToast(result.error || "Erro ao criar porteiro.", "error");
 btn.disabled = false;
 btn.textContent = "Adicionar Porteiro";
 return;
 }

 showToast("Porteiro criado com sucesso!", "success");
 document.getElementById("form-new-porteiro").reset();
 loadPorteiros();
}
