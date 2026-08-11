/**
 * storefront_catalog.js
 * Catálogo público de eventos (/storefront) — lista todos os eventos
 * elegíveis para venda online, com busca por nome no lado do cliente.
 * Acesso livre, sem autenticação (Fase 5, item B4).
 */
(function () {
  const els = {
    loading: document.getElementById("catalog-loading"),
    empty: document.getElementById("catalog-empty"),
    grid: document.getElementById("catalog-grid"),
    search: document.getElementById("catalog-search"),
  };

  let allEvents = [];

  function formatDate(isoString) {
    if (!isoString) return "Data a confirmar";
    try {
      const d = new Date(isoString);
      return d.toLocaleString("pt-MZ", {
        day: "2-digit", month: "2-digit", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
    } catch (e) {
      return isoString;
    }
  }

  function formatPrice(event) {
    const prices = [event.price_vip, event.price_normal].filter((p) => p && p > 0);
    if (!prices.length) return "Consulte valores";
    const min = Math.min(...prices);
    return `A partir de ${min.toFixed(2)} MT`;
  }

  function renderEvents(events) {
    els.grid.innerHTML = "";
    if (!events.length) {
      els.empty.classList.remove("sf-hidden");
      return;
    }
    els.empty.classList.add("sf-hidden");

    events.forEach((event) => {
      const card = document.createElement("a");
      card.className = "sf-event-card";
      card.href = `/e/${event.slug}`;

      const soldOut = event.stock && event.stock.sold_out;

      card.innerHTML = `
        <div class="sf-event-card-name">${escapeHtml(event.name)}</div>
        <div class="sf-event-card-meta">${escapeHtml(event.location || "Local a confirmar")} · ${formatDate(event.event_date)}</div>
        <div class="sf-event-card-footer">
          <span class="sf-event-card-price">${soldOut ? "Esgotado" : formatPrice(event)}</span>
          <span class="sf-event-card-cta">${soldOut ? "Ver detalhes →" : "Comprar bilhetes →"}</span>
        </div>
      `;
      els.grid.appendChild(card);
    });
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
  }

  function applySearch() {
    const term = (els.search.value || "").trim().toLowerCase();
    if (!term) {
      renderEvents(allEvents);
      return;
    }
    renderEvents(allEvents.filter((e) => (e.name || "").toLowerCase().includes(term)));
  }

  async function loadCatalog() {
    const result = await apiRequest("/api/public/events");
    els.loading.classList.add("sf-hidden");

    if (!result.success || !result.data) {
      els.empty.classList.remove("sf-hidden");
      return;
    }

    allEvents = result.data;
    renderEvents(allEvents);
  }

  els.search.addEventListener("input", applySearch);

  loadCatalog();
})();
