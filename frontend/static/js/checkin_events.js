/**
 * checkin_events.js
 * Painel Geral do Porteiro (Multi-Eventos): lista todos os eventos
 * cadastrados com status calculado, e direciona para a tela de check-in
 * do evento escolhido em /checkin/<event_id>.
 */

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
});

async function loadEvents({ silent = false } = {}) {
 const listEl = document.getElementById("events-list");
 const result = await apiRequest("/api/events");

 if (!result.success) {
 if (!silent) {
 renderEventsListWithFade(listEl, `<div class="empty-state">Erro ao carregar eventos.</div>`);
 }
 return;
 }

 await applyEvents(result.data || [], { fade: !silent });
}

/**
 * Pinta o card do próximo evento + a lista de eventos a partir de um
 * array de eventos já pronto (vindo do SSR ou da API). `fade: false`
 * pula a transição de opacidade do skeleton — usado só no primeiro
 * paint, quando os dados já chegam junto com o HTML.
 */
async function applyEvents(events, { fade = true } = {}) {
 const listEl = document.getElementById("events-list");
 renderNextEventCard(events, "porteiro");

 let html;
 if (events.length === 0) {
 html = `<div class="empty-state">Nenhum evento cadastrado. Peça ao administrador para criar um evento primeiro.</div>`;
 } else {
 html = events.map((event) => `
 <div class="event-item">
 <div>
 <div class="event-name">
 ${escapeHtml(event.name)}
 <span class="badge ${event.status.css_class}" style="margin-left:8px;">${escapeHtml(event.status.label)}</span>
 </div>
 <div class="event-meta"> ${formatDateTime(event.event_date)}</div>
 </div>
 <a href="/checkin/${event.id}" class="btn btn-primary">📷 Trabalhar neste Evento</a>
 </div>
 `).join("");
 }

 if (fade) {
 await renderEventsListWithFade(listEl, html);
 } else {
 listEl.innerHTML = html;
 listEl.removeAttribute("aria-busy");
 }
}
