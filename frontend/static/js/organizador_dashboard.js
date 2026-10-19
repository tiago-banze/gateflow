/**
 * organizador_dashboard.js — Início do Organizador: próximo evento, atalhos e eventos recentes.
 */
document.addEventListener("DOMContentLoaded", loadDashboard);

async function loadDashboard() {
  const listEl = document.getElementById("recent-events");
  const result = await apiRequest("/api/organizador/events");

  if (!result.success) {
    listEl.innerHTML = `<div class="empty-card"><p>Não foi possível carregar os eventos. ${escapeHtml(result.error || "")}</p>
      <button class="btn btn-secondary" type="button" onclick="loadDashboard()">${icon("refresh")} Tentar de novo</button></div>`;
    return;
  }

  const events = result.data || [];
  renderNextEventCard(events, "organizador");

  const upcoming = events.filter((e) => e.status.code !== "encerrado").length;
  const guests = events.reduce((sum, e) => sum + (e.total_guests || 0), 0);
  document.getElementById("tile-events-sub").textContent =
    events.length === 0 ? "Nenhum ainda" : `${upcoming} por realizar · ${events.length} no total`;
  document.getElementById("tile-guests-sub").textContent =
    guests === 0 ? "Adicione a sua lista" : `${guests} na sua lista`;

  if (events.length === 0) {
    listEl.innerHTML = `
      <div class="empty-card">
        <span class="empty-icon">${icon("calendar")}</span>
        <strong>Ainda não tem eventos</strong>
        <p>Crie o primeiro evento, adicione os convidados e envie os convites por WhatsApp, SMS ou e-mail.</p>
        <a class="btn btn-primary" href="/organizador/eventos/novo">${icon("plus")} Criar o primeiro evento</a>
      </div>`;
    return;
  }
  listEl.innerHTML = events.slice(0, 3).map(eventCardHtml).join("");
}
