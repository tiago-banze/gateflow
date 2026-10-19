/**
 * organizador_events.js — lista de eventos do organizador, com pesquisa e filtros.
 */
let allEvents = [];
let activeFilter = "proximos";

const FILTERS = {
  proximos: (e) => e.status.code === "proximo" || e.status.code === "andamento",
  andamento: (e) => e.status.code === "andamento",
  encerrados: (e) => e.status.code === "encerrado",
  todos: () => true,
};

document.addEventListener("DOMContentLoaded", async () => {
  const hash = window.location.hash.slice(1);
  if (FILTERS[hash]) activeFilter = hash;

  document.querySelectorAll("#events-filters [data-filter]").forEach((btn) => {
    btn.addEventListener("click", () => setFilter(btn.getAttribute("data-filter")));
  });
  document.getElementById("events-search").addEventListener("input", render);

  const result = await apiRequest("/api/organizador/events");
  const listEl = document.getElementById("events-list");
  if (!result.success) {
    listEl.innerHTML = `<div class="empty-card"><p>Erro ao carregar eventos: ${escapeHtml(result.error || "desconhecido")}</p></div>`;
    return;
  }
  allEvents = result.data || [];
  // Se não há próximos mas há encerrados, mostra tudo para não parecer vazio.
  if (!FILTERS[hash] && !allEvents.some(FILTERS.proximos) && allEvents.length) activeFilter = "todos";
  render();
});

function setFilter(name) {
  activeFilter = name;
  render();
}

function render() {
  document.querySelectorAll("#events-filters [data-filter]").forEach((btn) => {
    const name = btn.getAttribute("data-filter");
    btn.setAttribute("aria-pressed", name === activeFilter ? "true" : "false");
    const countEl = btn.querySelector("[data-count]");
    if (countEl) countEl.textContent = allEvents.filter(FILTERS[name]).length;
  });

  const term = document.getElementById("events-search").value.trim().toLowerCase();
  const items = allEvents
    .filter(FILTERS[activeFilter])
    .filter((e) => !term || `${e.name} ${e.location || ""}`.toLowerCase().includes(term));

  const listEl = document.getElementById("events-list");
  if (allEvents.length === 0) {
    listEl.innerHTML = `
      <div class="empty-card" style="grid-column:1/-1">
        <span class="empty-icon">${icon("calendar")}</span>
        <strong>Ainda não tem eventos</strong>
        <p>Crie um evento para começar a convidar pessoas.</p>
        <a class="btn btn-primary" href="/organizador/eventos/novo">${icon("plus")} Criar evento</a>
      </div>`;
    return;
  }
  if (items.length === 0) {
    listEl.innerHTML = `<div class="empty-card" style="grid-column:1/-1"><strong>Nada por aqui</strong><p>Nenhum evento corresponde a este filtro.</p></div>`;
    return;
  }
  listEl.innerHTML = items.map(eventCardHtml).join("");
}
