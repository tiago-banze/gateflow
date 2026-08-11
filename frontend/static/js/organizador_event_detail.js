/**
 * organizador_event_detail.js
 * Gestão de convidados e RSVP de um evento do Organizador. O resumo de
 * confirmações atualiza sozinho via polling (POLL_INTERVAL_MS) -- é
 * assim que o "tempo real" é implementado aqui: simples, robusto, sem
 * depender de WebSockets/infra extra.
 */

const EVENT_ID = document.body.getAttribute("data-event-id");
const POLL_INTERVAL_MS = 8000;

let guestsSearchTimeout = null;
let rsvpPollTimer = null;
let lastSearchValue = "";

document.addEventListener("DOMContentLoaded", () => {
  loadGuests("");
  loadRsvpSummary();
  rsvpPollTimer = setInterval(() => {
    loadRsvpSummary();
    loadGuests(lastSearchValue);
  }, POLL_INTERVAL_MS);

  // Pausa o polling quando a aba não está visível -- evita gastar bateria/dados
  // do organizador com o telemóvel no bolso durante o próprio evento.
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      clearInterval(rsvpPollTimer);
    } else {
      loadRsvpSummary();
      loadGuests(lastSearchValue);
      rsvpPollTimer = setInterval(() => {
        loadRsvpSummary();
        loadGuests(lastSearchValue);
      }, POLL_INTERVAL_MS);
    }
  });

  document.getElementById("btn-download-template").addEventListener("click", downloadTemplate);
  document.getElementById("btn-import").addEventListener("click", handleImportGuests);
  document.getElementById("form-new-guest").addEventListener("submit", handleCreateGuestManual);
  document.getElementById("form-courtesy").addEventListener("submit", handleIssueCourtesy);
  document.getElementById("form-rsvp-settings").addEventListener("submit", handleSaveRsvpSettings);
  document.getElementById("btn-send-invites-bulk").addEventListener("click", handleSendInvitesBulk);
  document.getElementById("btn-send-reminders-bulk").addEventListener("click", handleSendRemindersBulk);
  document.getElementById("detail-search").addEventListener("input", (e) => {
    lastSearchValue = e.target.value;
    clearTimeout(guestsSearchTimeout);
    guestsSearchTimeout = setTimeout(() => loadGuests(lastSearchValue), 250);
  });
});

function renderStats(stats) {
  const statsEl = document.getElementById("detail-stats");
  if (!stats) { statsEl.innerHTML = ""; return; }
  statsEl.innerHTML = `
    <span class="stat-pill">Total: ${stats.total}</span>
    <span class="stat-pill success">Presentes: ${stats.checked_in}</span>
    <span class="stat-pill pending">Pendentes: ${stats.pending}</span>
  `;

  const miniCountEl = document.getElementById("event-mini-count");
  if (miniCountEl) {
    miniCountEl.textContent = `${stats.checked_in}/${stats.total}`;
  }
}

async function loadRsvpSummary() {
  const barEl = document.getElementById("rsvp-summary-bar");
  const result = await apiRequest(`/api/organizador/events/${EVENT_ID}/rsvp-summary`);
  if (!result.success) return;
  const s = result.data;
  barEl.innerHTML = `
    <span class="stat-pill success">✓ Confirmados: ${s.confirmed}</span>
    <span class="stat-pill" style="background:var(--color-error-bg); color:var(--color-error);">✕ Recusados: ${s.declined}</span>
    <span class="stat-pill pending">… Pendentes: ${s.pending}</span>
    <span class="stat-pill">+ Acompanhantes: ${s.total_companions}</span>
  `;
}

async function handleSaveRsvpSettings(e) {
  e.preventDefault();
  const deadlineRaw = document.getElementById("rsvp-deadline-days").value.trim();
  const mapsUrl = document.getElementById("rsvp-maps-url").value.trim();

  const result = await apiRequest(`/api/organizador/events/${EVENT_ID}/rsvp-settings`, {
    method: "PUT",
    body: JSON.stringify({
      rsvp_deadline_days: deadlineRaw === "" ? null : parseInt(deadlineRaw, 10),
      location_maps_url: mapsUrl,
    }),
  });

  if (!result.success) {
    showToast(result.error || "Erro ao guardar configurações.", "error");
    return;
  }
  showToast("Configurações de convite guardadas!", "success");
}

async function handleSendInvitesBulk() {
  const btn = document.getElementById("btn-send-invites-bulk");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> A enviar...';

  const result = await apiRequest(`/api/organizador/events/${EVENT_ID}/guests/send-invites`, { method: "POST" });

  btn.disabled = false;
  btn.textContent = "✉ Enviar Convites Pendentes";

  if (!result.success) {
    showToast(result.error || "Erro ao enviar convites.", "error");
    return;
  }
  showToast(`${result.data.sent} convite(s) enviado(s).`, "success");
  loadGuests(lastSearchValue);
}

async function handleSendRemindersBulk() {
  const btn = document.getElementById("btn-send-reminders-bulk");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> A enviar...';

  const result = await apiRequest(`/api/organizador/events/${EVENT_ID}/guests/send-reminders`, { method: "POST" });

  btn.disabled = false;
  btn.textContent = "🔔 Enviar Lembretes aos Confirmados";

  if (!result.success) {
    showToast(result.error || "Erro ao enviar lembretes.", "error");
    return;
  }
  showToast(`${result.data.sent} lembrete(s) enviado(s).`, "success");
  loadGuests(lastSearchValue);
}

const RSVP_STATUS_BADGE = {
  confirmed: `<span class="badge" style="background:var(--color-success-bg); color:var(--color-success-text);">✓ Confirmado</span>`,
  declined: `<span class="badge" style="background:var(--color-error-bg); color:var(--color-error);">✕ Recusou</span>`,
  pending: `<span class="badge">… Pendente</span>`,
};

async function loadGuests(search) {
  const tableEl = document.getElementById("detail-guests-table");
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  const result = await apiRequest(`/api/organizador/events/${EVENT_ID}/guests${query}`);

  if (!result.success) {
    tableEl.innerHTML = `<div class="empty-state">Erro ao carregar convidados.</div>`;
    return;
  }

  if (result.stats) renderStats(result.stats);

  const guests = result.data || [];
  if (guests.length === 0) {
    tableEl.innerHTML = `<div class="empty-state">Nenhum convidado encontrado.</div>`;
    return;
  }

  tableEl.innerHTML = `
    <div class="table-responsive">
      <table>
        <thead>
          <tr style="text-align:left; border-bottom:2px solid var(--color-border-soft);">
            <th style="padding:10px;">Nome</th>
            <th style="padding:10px;">Mesa</th>
            <th style="padding:10px;">RSVP</th>
            <th class="hide-on-mobile" style="padding:10px;">Acomp.</th>
            <th style="padding:10px;">Check-in</th>
            <th style="padding:10px;">Ações</th>
          </tr>
        </thead>
        <tbody>
          ${guests.map((g) => `
            <tr style="border-bottom:1px solid var(--color-border-soft); ${g.checked_in ? "background:var(--color-success-bg);" : ""}">
              <td style="padding:10px; font-weight:600;">${escapeHtml(g.full_name)}</td>
              <td style="padding:10px; font-weight:700; color:var(--color-primary);">${escapeHtml(g.table_name || g.table_number || "-")}</td>
              <td style="padding:10px;">${RSVP_STATUS_BADGE[g.rsvp_status] || RSVP_STATUS_BADGE.pending}</td>
              <td class="hide-on-mobile" style="padding:10px;">${g.rsvp_status === "confirmed" ? (g.companions_confirmed ?? 0) : "-"}${g.companions_allowed ? ` / ${g.companions_allowed}` : ""}</td>
              <td style="padding:10px;">${g.checked_in ? "✓ Presente" : "-"}</td>
              <td style="padding:10px; white-space:nowrap;">
                <button class="btn btn-secondary" style="padding:6px 10px; font-size:0.78rem;" data-send-invite="${g.id}" title="Enviar convite">✉</button>
                ${g.rsvp_status === "confirmed" ? `<button class="btn btn-secondary" style="padding:6px 10px; font-size:0.78rem;" data-send-reminder="${g.id}" title="Enviar lembrete">🔔</button>` : ""}
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

  tableEl.querySelectorAll("[data-send-invite]").forEach((btn) => {
    btn.addEventListener("click", () => handleSendSingleInvite(btn.getAttribute("data-send-invite"), btn));
  });
  tableEl.querySelectorAll("[data-send-reminder]").forEach((btn) => {
    btn.addEventListener("click", () => handleSendSingleReminder(btn.getAttribute("data-send-reminder"), btn));
  });
}

async function handleSendSingleInvite(guestId, btn) {
  btn.disabled = true;
  const result = await apiRequest(`/api/organizador/events/${EVENT_ID}/guests/${guestId}/send-invite`, { method: "POST" });
  btn.disabled = false;
  if (!result.success) {
    showToast(result.error || "Erro ao enviar convite.", "error");
    return;
  }
  showToast("Convite enviado!", "success");
}

async function handleSendSingleReminder(guestId, btn) {
  btn.disabled = true;
  const result = await apiRequest(`/api/organizador/events/${EVENT_ID}/guests/${guestId}/send-reminder`, { method: "POST" });
  btn.disabled = false;
  if (!result.success) {
    showToast(result.error || "Erro ao enviar lembrete.", "error");
    return;
  }
  showToast("Lembrete enviado!", "success");
}

async function handleCreateGuestManual(e) {
  e.preventDefault();
  const btn = document.getElementById("btn-save-guest");
  const full_name = document.getElementById("guest-name").value.trim();
  const email = document.getElementById("guest-email").value.trim();
  const phone = document.getElementById("guest-phone").value.trim();
  const role = document.getElementById("guest-role").value.trim();
  const table_number = document.getElementById("guest-table").value.trim();
  const companionsAllowed = parseInt(document.getElementById("guest-companions").value || "0", 10);

  if (!full_name) {
    showToast("O nome completo é obrigatório.", "error");
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Adicionando...';

  const result = await apiRequest(`/api/organizador/events/${EVENT_ID}/guests`, {
    method: "POST",
    body: JSON.stringify({ full_name, email, phone, role, table_number }),
  });

  if (result.success && companionsAllowed > 0) {
    await apiRequest(`/api/organizador/events/${EVENT_ID}/guests/${result.data.id}/companions`, {
      method: "PUT",
      body: JSON.stringify({ companions_allowed: companionsAllowed }),
    });
  }

  btn.disabled = false;
  btn.textContent = "+ Adicionar Convidado";

  if (!result.success) {
    showToast(result.error || "Erro ao adicionar convidado.", "error");
    return;
  }

  showToast(`Convidado "${result.data.full_name}" adicionado com sucesso!`, "success");
  document.getElementById("form-new-guest").reset();
  loadGuests(lastSearchValue);
}

async function handleImportGuests() {
  const fileInput = document.getElementById("input-xlsx");
  const file = fileInput.files[0];
  if (!file) {
    showToast("Selecione um arquivo .xlsx para importar.", "error");
    return;
  }

  const btn = document.getElementById("btn-import");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Importando...';

  const formData = new FormData();
  formData.append("file", file);

  const result = await apiRequest(`/api/organizador/events/${EVENT_ID}/import`, {
    method: "POST",
    body: formData,
  });

  btn.disabled = false;
  btn.textContent = "⬆ Importar Lista de Convidados";

  if (!result.success) {
    showToast(result.error || "Erro ao importar convidados.", "error");
    return;
  }

  showToast(result.data.summary, "success", 5000);
  fileInput.value = "";
  loadGuests(lastSearchValue);
}

async function downloadTemplate() {
  try {
    const response = await fetch(`${window.location.origin}/api/events/template-xlsx`);
    if (!response.ok) {
      showToast("Erro ao baixar o modelo.", "error");
      return;
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "modelo_convidados_gateflow.xlsx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    showToast("Erro de conexão ao baixar o modelo.", "error");
  }
}

async function handleIssueCourtesy(e) {
  e.preventDefault();
  const fullName = document.getElementById("courtesy-name").value.trim();
  const email = document.getElementById("courtesy-email").value.trim();
  const phone = document.getElementById("courtesy-phone").value.trim();
  const tableNumber = document.getElementById("courtesy-table").value.trim();

  if (!fullName) {
    showToast("Nome do convidado é obrigatório.", "error");
    return;
  }

  const result = await apiRequest(`/api/organizador/events/${EVENT_ID}/guests/courtesy`, {
    method: "POST",
    body: JSON.stringify({ full_name: fullName, email, phone, table_number: tableNumber }),
  });

  if (!result.success) {
    showToast(result.error || "Erro ao emitir convite de cortesia.", "error");
    return;
  }

  showToast("Convite de cortesia emitido!", "success");
  document.getElementById("form-courtesy").reset();
  loadGuests(lastSearchValue);
}
