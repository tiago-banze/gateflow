/**
 * rsvp.js — página pública /rsvp/<token>
 * Sem dependências (não carrega common.js) -- página standalone, pensada
 * para abrir direto de um link do WhatsApp/SMS, o mais leve possível.
 */

(function () {
  let selectedResponse = null;
  let companionsCount = 0;
  const maxCompanions = guestData.companionsAllowed || 0;

  const btnYes = document.getElementById("btn-yes");
  const btnNo = document.getElementById("btn-no");
  const companionsBlock = document.getElementById("companions-block");
  const companionsCountEl = document.getElementById("companions-count");
  const btnMinus = document.getElementById("btn-minus");
  const btnPlus = document.getElementById("btn-plus");
  const btnSubmit = document.getElementById("btn-submit");
  const errorEl = document.getElementById("rsvp-error");
  const dateEl = document.getElementById("rsvp-event-date");

  // Formata a data ISO num formato amigável, sem depender de libs externas.
  if (dateEl && guestData.eventDate) {
    try {
      const d = new Date(guestData.eventDate);
      const formatted = d.toLocaleDateString("pt-PT", {
        weekday: "long", day: "2-digit", month: "long", year: "numeric",
      }) + " às " + d.toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" });
      dateEl.textContent = formatted.charAt(0).toUpperCase() + formatted.slice(1);
    } catch (e) { /* mantém o valor bruto se a data vier num formato inesperado */ }
  }

  function selectResponse(response) {
    selectedResponse = response;
    btnYes.classList.toggle("selected", response === "confirmed");
    btnNo.classList.toggle("selected", response === "declined");

    if (response === "confirmed" && maxCompanions > 0 && companionsBlock) {
      companionsBlock.classList.add("visible");
    } else if (companionsBlock) {
      companionsBlock.classList.remove("visible");
      companionsCount = 0;
      if (companionsCountEl) companionsCountEl.textContent = "0";
    }

    btnSubmit.disabled = false;
    hideError();
  }

  function updateCompanionsUI() {
    companionsCountEl.textContent = String(companionsCount);
    btnMinus.disabled = companionsCount <= 0;
    btnPlus.disabled = companionsCount >= maxCompanions;
  }

  function showError(message) {
    errorEl.textContent = message;
    errorEl.classList.add("visible");
  }

  function hideError() {
    errorEl.classList.remove("visible");
  }

  function showResult(response, companions) {
    document.getElementById("rsvp-form-section").style.display = "none";
    const resultEl = document.getElementById("rsvp-result");
    resultEl.style.display = "block";

    if (response === "confirmed") {
      resultEl.innerHTML = `
        <div class="icon">🎉</div>
        <h2>Presença confirmada!</h2>
        <p>Mal podemos esperar para o(a) receber${companions > 0 ? ` e mais ${companions} acompanhante${companions > 1 ? "s" : ""}` : ""}. Perto da data, vai receber o seu QR Code de acesso.</p>
      `;
    } else {
      resultEl.innerHTML = `
        <div class="icon">💜</div>
        <h2>Resposta registada</h2>
        <p>Obrigado por nos avisar. Vamos sentir a sua falta — se mudar de ideias, é só voltar a este link.</p>
      `;
    }
  }

  btnYes.addEventListener("click", () => selectResponse("confirmed"));
  btnNo.addEventListener("click", () => selectResponse("declined"));

  if (btnMinus) {
    btnMinus.addEventListener("click", () => {
      if (companionsCount > 0) { companionsCount -= 1; updateCompanionsUI(); }
    });
  }
  if (btnPlus) {
    btnPlus.addEventListener("click", () => {
      if (companionsCount < maxCompanions) { companionsCount += 1; updateCompanionsUI(); }
    });
  }

  btnSubmit.addEventListener("click", async () => {
    if (!selectedResponse) return;
    btnSubmit.disabled = true;
    btnSubmit.textContent = "A enviar…";
    hideError();

    const token = window.location.pathname.split("/").filter(Boolean).pop();
    try {
      const res = await fetch(`/api/rsvp/${encodeURIComponent(token)}/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ response: selectedResponse, companions_confirmed: companionsCount }),
      });
      const result = await res.json();
      if (!result.success) {
        showError(result.error || "Não foi possível enviar a sua resposta. Tente novamente.");
        btnSubmit.disabled = false;
        btnSubmit.textContent = "Confirmar resposta";
        return;
      }
      showResult(selectedResponse, companionsCount);
    } catch (e) {
      showError("Falha de ligação. Verifique a internet e tente novamente.");
      btnSubmit.disabled = false;
      btnSubmit.textContent = "Confirmar resposta";
    }
  });
})();
