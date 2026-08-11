/**
 * admin_feedbacks.js
 * Fila de moderação de depoimentos (/admin/depoimentos).
 * A lista pendente já vem pronta via SSR (window.__INITIAL_PENDING_FEEDBACKS__),
 * então não há fetch nenhum no carregamento — só nas ações de Aprovar/Rejeitar.
 */

document.addEventListener("DOMContentLoaded", () => {
  if (Array.isArray(window.__INITIAL_PENDING_FEEDBACKS__)) {
    renderPendingFeedbacks(window.__INITIAL_PENDING_FEEDBACKS__);
  } else {
    // Fallback (ex: SSR falhou no servidor): busca via API.
    loadPendingFeedbacks();
  }
});

async function loadPendingFeedbacks() {
  const listEl = document.getElementById("pending-feedbacks-list");
  const result = await apiRequest("/api/admin/feedbacks/pending");
  if (!result.success) {
    listEl.innerHTML = `<p class="empty-state">Erro ao carregar depoimentos: ${escapeHtml(result.error || "desconhecido")}</p>`;
    return;
  }
  renderPendingFeedbacks(result.data || []);
}

function renderPendingFeedbacks(feedbacks) {
  const listEl = document.getElementById("pending-feedbacks-list");
  listEl.removeAttribute("aria-busy");

  if (feedbacks.length === 0) {
    listEl.innerHTML = `<p class="empty-state">Nenhum depoimento pendente no momento.</p>`;
    return;
  }

  listEl.innerHTML = feedbacks.map((fb) => `
    <div class="event-item" style="flex-direction:column; align-items:stretch; gap:10px; margin-bottom:12px;" data-feedback-id="${fb.id}">
      <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:10px; flex-wrap:wrap;">
        <div>
          <div class="event-name">${escapeHtml(fb.name)}</div>
          <div class="event-meta">
            <span style="color:#F5A623;">${"★".repeat(fb.rating)}${"☆".repeat(5 - fb.rating)}</span>
            &nbsp;|&nbsp; ${formatDateTime(fb.created_at)}
          </div>
        </div>
        <span class="badge">Pendente</span>
      </div>
      <p style="margin:0; font-size:0.9rem; color:var(--color-text);">${escapeHtml(fb.comment)}</p>
      <div style="display:flex; gap:10px;">
        <button class="btn btn-primary" data-approve-feedback="${fb.id}">✓ Aprovar</button>
        <button class="btn btn-danger" data-reject-feedback="${fb.id}">✕ Rejeitar</button>
      </div>
    </div>
  `).join("");

  listEl.querySelectorAll("[data-approve-feedback]").forEach((btn) => {
    btn.addEventListener("click", () => handleModerate(btn.getAttribute("data-approve-feedback"), "approve", btn));
  });
  listEl.querySelectorAll("[data-reject-feedback]").forEach((btn) => {
    btn.addEventListener("click", () => handleModerate(btn.getAttribute("data-reject-feedback"), "reject", btn));
  });
}

async function handleModerate(feedbackId, action, btn) {
  const card = document.querySelector(`[data-feedback-id="${feedbackId}"]`);
  const allButtons = card ? card.querySelectorAll("button") : [btn];
  allButtons.forEach((b) => (b.disabled = true));

  const result = await apiRequest(`/api/admin/feedbacks/${encodeURIComponent(feedbackId)}/${action}`, {
    method: "PUT",
  });

  if (!result.success) {
    showToast(result.error || "Não foi possível concluir a ação.", "error");
    allButtons.forEach((b) => (b.disabled = false));
    return;
  }

  showToast(action === "approve" ? "Depoimento aprovado." : "Depoimento rejeitado.", "success");
  if (card) {
    card.remove();
    const listEl = document.getElementById("pending-feedbacks-list");
    if (!listEl.querySelector("[data-feedback-id]")) {
      listEl.innerHTML = `<p class="empty-state">Nenhum depoimento pendente no momento.</p>`;
    }
  }
}
