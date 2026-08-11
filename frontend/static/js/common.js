/**
 * common.js
 * Funções utilitárias compartilhadas entre o Painel Administrativo e o
 * Painel do Porteiro: chamadas de API com tratamento de erro padronizado
 * e exibição de notificações (toasts).
 */

const API_BASE = window.location.origin;

/**
 * Wrapper para fetch com tratamento de erro consistente.
 * Nunca lança exceção não tratada: sempre retorna { success, data, error }.
 */
async function apiRequest(path, options = {}) {
 try {
 const response = await fetch(`${API_BASE}${path}`, {
 headers: options.body instanceof FormData
 ? {}
 : { "Content-Type": "application/json" },
 ...options,
 });

 let payload;
 try {
 payload = await response.json();
 } catch (parseError) {
 return {
 success: false,
 status: response.status,
 error: "Resposta inválida do servidor.",
 };
 }

 // Sessão expirada ou não autenticada: limpa qualquer resíduo local e
 // manda para o login automaticamente. Este sistema usa cookie de
 // sessão assinado pelo servidor (não localStorage/JWT), mas limpamos
 // mesmo assim por segurança defensiva, caso algo tenha sido salvo
 // localmente (ex: preferências, cache de formulário).
 if (response.status === 401 && payload.auth_required) {
 try {
 localStorage.clear();
 sessionStorage.clear();
 } catch (storageError) {
 // Alguns navegadores em modo privado bloqueiam localStorage; ignorar.
 }
 window.location.href = "/login";
 return { success: false, status: 401, error: payload.error };
 }

 return {
 success: Boolean(payload.success) && response.ok,
 status: response.status,
 data: payload.data,
 stats: payload.stats,
 error: payload.error,
 already_checked_in: payload.already_checked_in,
 raw: payload,
 };
 } catch (networkError) {
 return {
 success: false,
 status: 0,
 error: "Não foi possível conectar ao servidor. Verifique a rede e o IP do backend.",
 };
 }
}

function showToast(message, type = "info", durationMs = 3500) {
 let container = document.getElementById("toast-container");
 if (!container) {
 container = document.createElement("div");
 container.id = "toast-container";
 container.className = "toast-container";
 document.body.appendChild(container);
 }

 const toast = document.createElement("div");
 toast.className = `toast ${type}`;
 toast.textContent = message;
 container.appendChild(toast);

 setTimeout(() => {
 toast.style.opacity = "0";
 toast.style.transition = "opacity 0.3s ease";
 setTimeout(() => toast.remove(), 300);
 }, durationMs);
}

function formatDateTime(isoOrDatetimeLocal) {
 if (!isoOrDatetimeLocal) return "";
 try {
 const date = new Date(isoOrDatetimeLocal);
 if (Number.isNaN(date.getTime())) return isoOrDatetimeLocal;
 return date.toLocaleString("pt-BR", {
 day: "2-digit",
 month: "2-digit",
 year: "numeric",
 hour: "2-digit",
 minute: "2-digit",
 });
 } catch (e) {
 return isoOrDatetimeLocal;
 }
}

function escapeHtml(text) {
 const div = document.createElement("div");
 div.textContent = text ?? "";
 return div.innerHTML;
}

function getQueryParam(name) {
 return new URLSearchParams(window.location.search).get(name);
}

// --------------------------------------------------------------------------
// TRANSIÇÃO SUAVE DA LISTA DE EVENTOS (Admin + Porteiro)
// Troca o conteúdo de #events-list (do skeleton estático para a lista real,
// ou entre estados de erro/vazio/lista) sem o "flash" de um innerHTML
// instantâneo: o container passa por opacity:0 durante a troca do DOM e só
// volta a opacity:1 no frame seguinte, quando o conteúdo novo já está
// totalmente inserido. Usado por admin_events.js e checkin_events.js.
// --------------------------------------------------------------------------
function renderEventsListWithFade(listEl, html) {
 return new Promise((resolve) => {
 listEl.style.opacity = "0";
 // requestAnimationFrame garante que o navegador já pintou o frame com
 // opacity:0 antes de trocarmos o conteúdo — é essa troca (innerHTML) que
 // recalcula o layout e causava o salto visível.
 requestAnimationFrame(() => {
 listEl.innerHTML = html;
 listEl.removeAttribute("aria-busy");
 requestAnimationFrame(() => {
 listEl.style.opacity = "1";
 // Só resolve DEPOIS do innerHTML estar mesmo no DOM, para quem
 // chamou poder ligar event listeners aos elementos novos sem
 // risco de "apanhar" o conteúdo antigo (skeleton) por engano.
 resolve();
 });
 });
 });
}

// --------------------------------------------------------------------------
// MODO ESCURO (Dark Mode) - persistido em localStorage, aplicado via
// atributo data-theme no <html>. A aplicação INICIAL (para evitar "flash"
// de tela clara antes de escurecer) acontece por um script inline no
// <head> de cada página, ANTES do CSS carregar - ver THEME_STORAGE_KEY.
// --------------------------------------------------------------------------

const THEME_STORAGE_KEY = "gateflow-theme";

function getCurrentTheme() {
 return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

function setTheme(theme) {
 document.documentElement.setAttribute("data-theme", theme);
 try {
 localStorage.setItem(THEME_STORAGE_KEY, theme);
 } catch (storageError) {
 // Modo privado/navegador bloqueando localStorage: o tema ainda funciona
 // nesta sessão, só não persiste entre recarregamentos. Sem problema.
 }
 updateThemeToggleIcon();
}

function toggleTheme() {
 setTheme(getCurrentTheme() === "dark" ? "light" : "dark");
}

function updateThemeToggleIcon() {
 const btn = document.getElementById("theme-toggle-btn");
 if (!btn) return;
 // Mostra o ícone da ação que o clique VAI EXECUTAR (não do tema atual):
 // no modo escuro, oferece voltar ao claro (☀); no claro, oferece ir ao escuro (🌙).
 btn.textContent = getCurrentTheme() === "dark" ? "☀" : "🌙";
 btn.title = getCurrentTheme() === "dark" ? "Mudar para modo claro" : "Mudar para modo escuro";
}

document.addEventListener("DOMContentLoaded", () => {
 const btn = document.getElementById("theme-toggle-btn");
 if (btn) {
 btn.addEventListener("click", toggleTheme);
 updateThemeToggleIcon();
 }
});

// --------------------------------------------------------------------------
// CARD DO PRÓXIMO EVENTO + CONTADOR REGRESSIVO
// (compartilhado entre o Painel Administrativo e o Painel do Porteiro - 
// ambos têm o mesmo bloco de HTML com os ids next-event-card, cd-days, etc.)
// --------------------------------------------------------------------------

let _countdownIntervalId = null;

function renderNextEventCard(events, mode) {
 const card = document.getElementById("next-event-card");
 if (!card) return; // página não tem o card (ex: tela de gerenciamento de um evento específico)

 if (_countdownIntervalId) {
 clearInterval(_countdownIntervalId);
 _countdownIntervalId = null;
 }

 // "Próximo evento" = o de status Próximo ou Em Andamento com a data mais
 // próxima de agora (eventos encerrados nunca aparecem aqui).
 const upcoming = events
 .filter((e) => e.status.code === "proximo" || e.status.code === "andamento")
 .sort((a, b) => new Date(a.event_date) - new Date(b.event_date));

 if (upcoming.length === 0) {
 card.classList.add("hidden");
 card.classList.remove("is-visible");
 return;
 }

 const nextEvent = upcoming[0];
 card.classList.remove("hidden");
 document.getElementById("next-event-name").textContent = nextEvent.name;
 document.getElementById("next-event-meta").textContent =
 ` ${nextEvent.location || "Local não informado"} · ${formatDateTime(nextEvent.event_date)}`;

 _renderNextEventActions(nextEvent, mode);

 const targetDate = new Date(nextEvent.event_date);

 const updateCountdown = () => {
 const now = new Date();
 const diffMs = targetDate.getTime() - now.getTime();

 if (diffMs <= 0) {
 // "O Dia Chegou": aplica o efeito de pulsação sutil e zera o contador
 card.classList.add("today-pulse");
 _setCountdownValues(0, 0, 0, 0);
 return;
 }

 card.classList.remove("today-pulse");
 const totalSeconds = Math.floor(diffMs / 1000);
 const days = Math.floor(totalSeconds / 86400);
 const hours = Math.floor((totalSeconds % 86400) / 3600);
 const minutes = Math.floor((totalSeconds % 3600) / 60);
 const seconds = totalSeconds % 60;
 _setCountdownValues(days, hours, minutes, seconds);
 };

 // Se o evento é HOJE (status "andamento"), aplica o efeito visual direto
 if (nextEvent.status.code === "andamento") {
 card.classList.add("today-pulse");
 }

 updateCountdown();
 _countdownIntervalId = setInterval(updateCountdown, 1000);

 // Revela o card já com todo o conteúdo preenchido (nome, contagem,
 // ações) - o requestAnimationFrame garante que o navegador registou o
 // estado inicial (opacity:0) antes de aplicarmos a classe que anima
 // para opacity:1, para a transição do CSS realmente ser executada.
 requestAnimationFrame(() => card.classList.add("is-visible"));
}

/**
 * Card de Ação (Fase 5, item E): converte o card do próximo evento em
 * atalhos diretos, sem precisar procurar o evento na lista abaixo.
 *   - mode "admin"       -> Editar / Excluir / Trabalhar Evento (check-in)
 *   - mode "organizador" -> Editar / Excluir (via página de gerenciamento) / Trabalhar Evento
 *   - mode "porteiro"    -> CTA única e destacada "Iniciar Check-in"
 */
function _renderNextEventActions(event, mode) {
 const box = document.getElementById("next-event-actions");
 if (!box) return;

 if (mode === "porteiro") {
 box.innerHTML = `
 <a href="/checkin/${event.id}" class="btn btn-primary btn-lg next-event-cta">
 📷 Iniciar Check-in
 </a>`;
 return;
 }

 if (mode === "organizador") {
 box.innerHTML = `
 <a href="/organizador/eventos/${event.id}" class="btn btn-secondary">✎ Editar</a>
 <a href="/organizador/eventos/${event.id}" class="btn btn-primary">📷 Trabalhar Evento (Check-in)</a>`;
 return;
 }

 // admin (padrão): edição/exclusão diretas + atalho de check-in.
 // Reaproveita openEditEventModal/handleDeleteEvent já existentes em
 // admin_events.js (mesmo modal e mesma lógica usados na lista de eventos).
 box.innerHTML = `
 <button type="button" class="btn btn-secondary" data-next-event-edit="${event.id}">✎ Editar</button>
 <button type="button" class="btn btn-danger" data-next-event-delete="${event.id}">🗑 Excluir</button>
 <a href="/checkin/${event.id}" class="btn btn-primary">📷 Trabalhar Evento (Check-in)</a>`;

 const editBtn = box.querySelector("[data-next-event-edit]");
 if (editBtn && typeof window.openEditEventModal === "function") {
 editBtn.addEventListener("click", () => window.openEditEventModal(event.id));
 } else if (editBtn) {
 editBtn.addEventListener("click", () => { window.location.href = `/admin/eventos/${event.id}`; });
 }

 const deleteBtn = box.querySelector("[data-next-event-delete]");
 if (deleteBtn && typeof window.handleDeleteEvent === "function") {
 deleteBtn.addEventListener("click", () => window.handleDeleteEvent(event.id));
 }
}

function _setCountdownValues(days, hours, minutes, seconds) {
 document.getElementById("cd-days").textContent = String(days).padStart(2, "0");
 document.getElementById("cd-hours").textContent = String(hours).padStart(2, "0");
 document.getElementById("cd-minutes").textContent = String(minutes).padStart(2, "0");
 document.getElementById("cd-seconds").textContent = String(seconds).padStart(2, "0");
}
