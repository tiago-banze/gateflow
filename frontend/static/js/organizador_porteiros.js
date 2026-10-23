/**
 * organizador_porteiros.js, contas de porteiro do organizador.
 */
document.addEventListener("DOMContentLoaded", () => {
  loadPorteiros();
  document.getElementById("form-new-porteiro").addEventListener("submit", handleCreatePorteiro);
});

async function loadPorteiros() {
  const listEl = document.getElementById("porteiros-list");
  const result = await apiRequest("/api/organizador/porteiros");
  if (!result.success) {
    listEl.innerHTML = `<div class="empty-state">Erro ao carregar: ${escapeHtml(result.error || "desconhecido")}</div>`;
    return;
  }

  const porteiros = result.data || [];
  const limit = result.raw?.limit || Number(document.body.dataset.maxPorteiros) || 3;
  const fab = document.getElementById("btn-open-porteiro");
  fab.classList.toggle("hidden", porteiros.length >= limit);

  if (porteiros.length === 0) {
    listEl.className = "";
    listEl.innerHTML = `
      <div class="empty-card">
        <span class="empty-icon">${icon("users")}</span>
        <strong>Sem porteiros</strong>
        <p>Crie uma conta para quem vai ler os QR Codes à entrada do evento.</p>
        <button class="btn btn-primary" type="button" data-sheet-open="porteiro-sheet">${icon("user-plus")} Adicionar porteiro</button>
      </div>`;
    return;
  }

  listEl.className = "list-card";
  listEl.innerHTML = porteiros.map((p) => `
    <div class="list-row">
      <span class="list-row-icon">${icon("user")}</span>
      <div class="list-row-body">
        <div class="list-row-title">${escapeHtml(p.full_name || p.username)}</div>
        <div class="list-row-sub">Utilizador: ${escapeHtml(p.username)}</div>
      </div>
      <div class="list-row-end">
        <button class="icon-btn icon-btn-delete" type="button" data-remove="${p.id}" data-name="${escapeHtml(p.full_name || p.username)}" aria-label="Remover ${escapeHtml(p.full_name || p.username)}">${icon("trash")}</button>
      </div>
    </div>`).join("") +
    `<div class="list-row"><div class="list-row-body"><div class="list-row-sub">${porteiros.length} de ${limit} porteiros utilizados</div></div></div>`;

  listEl.querySelectorAll("[data-remove]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm(`Remover o porteiro "${btn.dataset.name}"? Ele deixa de poder entrar no sistema.`)) return;
      const res = await apiRequest(`/api/organizador/porteiros/${btn.dataset.remove}`, { method: "DELETE" });
      if (!res.success) { showToast(res.error || "Erro ao remover.", "error"); return; }
      showToast("Porteiro removido.", "success");
      loadPorteiros();
    });
  });
}

async function handleCreatePorteiro(e) {
  e.preventDefault();
  const btn = document.getElementById("btn-save-porteiro");
  const payload = {
    full_name: document.getElementById("porteiro-full-name").value.trim(),
    username: document.getElementById("porteiro-username").value.trim(),
    password: document.getElementById("porteiro-password").value,
  };
  if (!payload.username || payload.password.length < 8) {
    showToast("Indique o utilizador e uma senha de pelo menos 8 caracteres.", "error");
    return;
  }
  btn.disabled = true;
  const result = await apiRequest("/api/organizador/porteiros", { method: "POST", body: JSON.stringify(payload) });
  btn.disabled = false;
  if (!result.success) {
    showToast(result.error || "Erro ao criar porteiro.", "error");
    return;
  }
  showToast("Porteiro criado.", "success");
  document.getElementById("form-new-porteiro").reset();
  closeSheet("porteiro-sheet");
  loadPorteiros();
}
