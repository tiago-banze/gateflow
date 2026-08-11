/**
 * landing.js
 * Depoimentos/Avaliações da landing page:
 *  - "Ver mais" nos cartões já renderizados via SSR (index.html) — não
 *    depende de nenhuma chamada de rede, só mede o texto que já está no HTML.
 *  - Modal "Ver todos os comentários": busca a lista completa em
 *    GET /api/feedbacks só na primeira vez que é aberto (fica em cache
 *    depois), para o load inicial da landing continuar leve.
 *  - Formulário de novo depoimento: POST /api/feedbacks.
 *
 * Mantém a landing leve de propósito: nenhum fetch dispara sozinho no
 * carregamento da página — os depoimentos iniciais já vêm prontos do
 * servidor (window não precisa de nada aqui além do que o HTML já tem).
 */

let lpAllFeedbacksCache = null; // null = ainda não buscado

document.addEventListener("DOMContentLoaded", () => {
  setupVerMaisToggles(document.getElementById("lp-testimonials-grid"));
  setupStarInput();

  const viewAllBtn = document.getElementById("lp-btn-view-all-testimonials");
  if (viewAllBtn) viewAllBtn.addEventListener("click", openTestimonialsModal);

  const closeModalBtn = document.getElementById("lp-btn-close-testimonials-modal");
  if (closeModalBtn) closeModalBtn.addEventListener("click", closeTestimonialsModal);

  const modal = document.getElementById("lp-testimonials-modal");
  if (modal) {
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeTestimonialsModal();
    });
  }

  const openFormBtn = document.getElementById("lp-btn-open-testimonial-form");
  if (openFormBtn) openFormBtn.addEventListener("click", openTestimonialForm);

  const closeFormBtn = document.getElementById("lp-btn-close-testimonial-form");
  if (closeFormBtn) closeFormBtn.addEventListener("click", closeTestimonialForm);

  const formModal = document.getElementById("lp-testimonial-form-modal");
  if (formModal) {
    formModal.addEventListener("click", (event) => {
      if (event.target === formModal) closeTestimonialForm();
    });
  }

  const form = document.getElementById("lp-testimonial-form");
  if (form) form.addEventListener("submit", handleSubmitTestimonial);

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    closeTestimonialsModal();
    closeTestimonialForm();
  });
});

/**
 * Adiciona o botão "Ver mais/Ver menos" só nos comentários que o CSS
 * (-webkit-line-clamp: 4) realmente cortou — comentários curtos não
 * ganham botão nenhum. Funciona tanto para os cartões SSR quanto para
 * os que o modal insere depois.
 */
function setupVerMaisToggles(containerEl) {
  if (!containerEl) return;
  containerEl.querySelectorAll(".lp-testimonial-comment").forEach((p) => {
    if (p.dataset.toggleReady) return; // evita duplicar o botão
    p.dataset.toggleReady = "1";

    // Precisa medir depois do layout aplicar o line-clamp.
    requestAnimationFrame(() => {
      if (p.scrollHeight <= p.clientHeight + 1) return; // não foi cortado, sem botão
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "lp-testimonial-toggle";
      toggle.textContent = "Ver mais";
      toggle.addEventListener("click", () => {
        const expanded = p.classList.toggle("lp-is-expanded");
        toggle.textContent = expanded ? "Ver menos" : "Ver mais";
      });
      p.insertAdjacentElement("afterend", toggle);
    });
  });
}

function renderTestimonialCard(feedback) {
  const stars = "★".repeat(feedback.rating) + "☆".repeat(5 - feedback.rating);
  return `
    <div class="lp-testimonial-card">
      <div class="lp-testimonial-head">
        <img class="lp-testimonial-avatar" src="${escapeHtml(feedback.avatar_url)}" alt="" loading="lazy" width="44" height="44" />
        <div>
          <div class="lp-testimonial-name">${escapeHtml(feedback.name)}</div>
          <div class="lp-testimonial-stars" aria-label="${feedback.rating} de 5 estrelas">${stars}</div>
        </div>
      </div>
      <p class="lp-testimonial-comment">${escapeHtml(feedback.comment)}</p>
    </div>
  `;
}

async function openTestimonialsModal() {
  const modal = document.getElementById("lp-testimonials-modal");
  const listEl = document.getElementById("lp-testimonials-modal-list");
  modal.classList.remove("hidden");

  if (lpAllFeedbacksCache) {
    return; // já está pintado de uma abertura anterior, nada para refazer
  }

  listEl.innerHTML = `<p class="lp-testimonial-empty">A carregar comentários…</p>`;
  const result = await apiRequest("/api/feedbacks");

  if (!result.success) {
    listEl.innerHTML = `<p class="lp-testimonial-empty">Não foi possível carregar os comentários agora.</p>`;
    return;
  }

  lpAllFeedbacksCache = result.data || [];

  if (lpAllFeedbacksCache.length === 0) {
    listEl.innerHTML = `<p class="lp-testimonial-empty">Ainda não há depoimentos — sê o primeiro a partilhar a tua experiência.</p>`;
    return;
  }

  listEl.innerHTML = lpAllFeedbacksCache.map(renderTestimonialCard).join("");
  setupVerMaisToggles(listEl);
}

function closeTestimonialsModal() {
  const modal = document.getElementById("lp-testimonials-modal");
  if (modal) modal.classList.add("hidden");
}

function openTestimonialForm() {
  document.getElementById("lp-testimonial-form-modal").classList.remove("hidden");
}

function closeTestimonialForm() {
  document.getElementById("lp-testimonial-form-modal").classList.add("hidden");
}

function setupStarInput() {
  const wrapper = document.getElementById("lp-star-input");
  if (!wrapper) return;
  const buttons = Array.from(wrapper.querySelectorAll(".lp-star-btn"));
  let selected = 0;

  function paint(value) {
    buttons.forEach((btn) => {
      const isActive = Number(btn.dataset.star) <= value;
      btn.classList.toggle("lp-star-active", isActive);
      btn.setAttribute("aria-checked", Number(btn.dataset.star) === value ? "true" : "false");
    });
  }

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      selected = Number(btn.dataset.star);
      wrapper.dataset.value = String(selected);
      paint(selected);
    });
    btn.addEventListener("mouseenter", () => paint(Number(btn.dataset.star)));
  });
  wrapper.addEventListener("mouseleave", () => paint(selected));
}

async function handleSubmitTestimonial(event) {
  event.preventDefault();

  const submitBtn = document.getElementById("lp-btn-submit-testimonial");
  const starWrapper = document.getElementById("lp-star-input");
  const payload = {
    name: document.getElementById("lp-testimonial-name").value.trim(),
    email: document.getElementById("lp-testimonial-email").value.trim(),
    rating: Number(starWrapper.dataset.value || 0),
    comment: document.getElementById("lp-testimonial-comment").value.trim(),
  };

  if (!payload.rating) {
    showToast("Selecione uma nota de 1 a 5 estrelas.", "error");
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = "A enviar…";

  const result = await apiRequest("/api/feedbacks", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  submitBtn.disabled = false;
  submitBtn.textContent = "Enviar comentário";

  if (!result.success) {
    showToast(result.error || "Não foi possível enviar o comentário.", "error");
    return;
  }

  showToast(
    result.message || "Obrigado pelo seu depoimento! Ele será exibido na página assim que for verificado pela nossa equipa.",
    "success",
    6000
  );
  document.getElementById("lp-testimonial-form").reset();
  starWrapper.dataset.value = "0";
  starWrapper.querySelectorAll(".lp-star-btn").forEach((btn) => {
    btn.classList.remove("lp-star-active");
    btn.setAttribute("aria-checked", "false");
  });
  closeTestimonialForm();

  // O depoimento fica pendente de moderação (ver /admin/depoimentos) --
  // por isso NÃO entra na grelha nem no cache do modal "ver todos" agora;
  // só passa a aparecer publicamente depois de um admin aprovar.
}
