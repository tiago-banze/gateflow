/**
 * organizador_event_new.js — criação de evento; depois segue direto para adicionar convidados.
 */
document.addEventListener("DOMContentLoaded", () => {
  const dateInput = document.getElementById("event-date");
  // Não permite escolher uma data no passado.
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  dateInput.min = now.toISOString().slice(0, 16);

  document.getElementById("form-new-event").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("btn-save-event");
    const payload = {
      name: document.getElementById("event-name").value.trim(),
      organizer_display_name: document.getElementById("event-organizer-name").value.trim(),
      location: document.getElementById("event-location").value.trim(),
      event_date: dateInput.value,
      description: document.getElementById("event-description").value.trim(),
      event_type: document.getElementById("event-type").value,
      group_label: document.getElementById("event-group-label").value,
    };
    if (!payload.name || !payload.organizer_display_name || !payload.location || !payload.event_date) {
      showToast("Falta preencher o nome, a data, o local ou o organizador.", "error");
      return;
    }

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> A criar…';
    const result = await apiRequest("/api/organizador/events", { method: "POST", body: JSON.stringify(payload) });
    if (!result.success) {
      btn.disabled = false;
      btn.innerHTML = `${icon("check")} Criar evento`;
      showToast(result.error || "Erro ao criar evento.", "error");
      return;
    }
    window.location.href = `/organizador/eventos/${result.data.id}?novo=1#convidados`;
  });
});
