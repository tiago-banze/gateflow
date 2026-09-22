/**
 * common.js
 * Funções utilitárias compartilhadas entre o Painel Administrativo e o
 * Painel do Porteiro: chamadas de API com tratamento de erro padronizado
 * e exibição de notificações (toasts).
 */


/* >>> GF-ICONS (gerado por tools/gen_icons.py — não editar à mão) >>> */
const GF_ICONS = {
  "arrow-left": "<path d=\"M19 12H5\"/><path d=\"m12 19-7-7 7-7\"/>",
  "arrow-right": "<path d=\"M5 12h14\"/><path d=\"m12 5 7 7-7 7\"/>",
  "arrow-up-right": "<path d=\"M7 17 17 7\"/><path d=\"M7 7h10v10\"/>",
  "check": "<path d=\"M20 6 9 17l-5-5\"/>",
  "check-circle": "<path d=\"M22 11.08V12a10 10 0 1 1-5.93-9.14\"/><path d=\"m9 11 3 3L22 4\"/>",
  "x": "<path d=\"M18 6 6 18\"/><path d=\"m6 6 12 12\"/>",
  "x-circle": "<circle cx=\"12\" cy=\"12\" r=\"10\"/><path d=\"m15 9-6 6\"/><path d=\"m9 9 6 6\"/>",
  "plus": "<path d=\"M12 5v14\"/><path d=\"M5 12h14\"/>",
  "minus": "<path d=\"M5 12h14\"/>",
  "edit": "<path d=\"M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z\"/><path d=\"m15 5 4 4\"/>",
  "trash": "<path d=\"M3 6h18\"/><path d=\"M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6\"/><path d=\"M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2\"/><path d=\"M10 11v6\"/><path d=\"M14 11v6\"/>",
  "sliders": "<path d=\"M21 4h-7\"/><path d=\"M10 4H3\"/><path d=\"M21 12h-9\"/><path d=\"M8 12H3\"/><path d=\"M21 20h-5\"/><path d=\"M12 20H3\"/><path d=\"M14 2v4\"/><path d=\"M8 10v4\"/><path d=\"M16 18v4\"/>",
  "camera": "<path d=\"M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z\"/><circle cx=\"12\" cy=\"13\" r=\"3\"/>",
  "scan": "<path d=\"M3 7V5a2 2 0 0 1 2-2h2\"/><path d=\"M17 3h2a2 2 0 0 1 2 2v2\"/><path d=\"M21 17v2a2 2 0 0 1-2 2h-2\"/><path d=\"M7 21H5a2 2 0 0 1-2-2v-2\"/><path d=\"M7 12h10\"/>",
  "qr": "<rect x=\"3\" y=\"3\" width=\"7\" height=\"7\" rx=\"1\"/><rect x=\"14\" y=\"3\" width=\"7\" height=\"7\" rx=\"1\"/><rect x=\"3\" y=\"14\" width=\"7\" height=\"7\" rx=\"1\"/><path d=\"M14 14h3v3h-3z\"/><path d=\"M20 14v.01\"/><path d=\"M14 20v.01\"/><path d=\"M17 20h4v-3\"/>",
  "sun": "<circle cx=\"12\" cy=\"12\" r=\"4\"/><path d=\"M12 2v2\"/><path d=\"M12 20v2\"/><path d=\"m4.93 4.93 1.41 1.41\"/><path d=\"m17.66 17.66 1.41 1.41\"/><path d=\"M2 12h2\"/><path d=\"M20 12h2\"/><path d=\"m6.34 17.66-1.41 1.41\"/><path d=\"m19.07 4.93-1.41 1.41\"/>",
  "moon": "<path d=\"M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z\"/>",
  "download": "<path d=\"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4\"/><path d=\"m7 10 5 5 5-5\"/><path d=\"M12 15V3\"/>",
  "upload": "<path d=\"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4\"/><path d=\"m17 8-5-5-5 5\"/><path d=\"M12 3v12\"/>",
  "mail": "<rect x=\"2\" y=\"4\" width=\"20\" height=\"16\" rx=\"2\"/><path d=\"m22 7-10 6L2 7\"/>",
  "bell": "<path d=\"M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9\"/><path d=\"M10.3 21a1.94 1.94 0 0 0 3.4 0\"/>",
  "lock": "<rect x=\"3\" y=\"11\" width=\"18\" height=\"11\" rx=\"2\"/><path d=\"M7 11V7a5 5 0 0 1 10 0v4\"/>",
  "message": "<path d=\"M7.9 20A9 9 0 1 0 4 16.1L2 22Z\"/>",
  "wifi-off": "<path d=\"M12 20h.01\"/><path d=\"M8.5 16.43a5 5 0 0 1 7 0\"/><path d=\"M5 12.86a10 10 0 0 1 5.17-2.69\"/><path d=\"M19 12.86a10 10 0 0 0-2.01-1.52\"/><path d=\"M2 8.82a15 15 0 0 1 4.18-2.64\"/><path d=\"M22 8.82a15 15 0 0 0-11.29-3.76\"/><path d=\"m2 2 20 20\"/>",
  "refresh": "<path d=\"M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8\"/><path d=\"M3 3v5h5\"/><path d=\"M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16\"/><path d=\"M16 16h5v5\"/>",
  "star": "<path d=\"M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z\"/>",
  "calendar": "<rect x=\"3\" y=\"4\" width=\"18\" height=\"18\" rx=\"2\"/><path d=\"M16 2v4\"/><path d=\"M8 2v4\"/><path d=\"M3 10h18\"/>",
  "map-pin": "<path d=\"M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0Z\"/><circle cx=\"12\" cy=\"10\" r=\"3\"/>",
  "clock": "<circle cx=\"12\" cy=\"12\" r=\"10\"/><path d=\"M12 6v6l4 2\"/>",
  "users": "<path d=\"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2\"/><circle cx=\"9\" cy=\"7\" r=\"4\"/><path d=\"M22 21v-2a4 4 0 0 0-3-3.87\"/><path d=\"M16 3.13a4 4 0 0 1 0 7.75\"/>",
  "user": "<path d=\"M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2\"/><circle cx=\"12\" cy=\"7\" r=\"4\"/>",
  "user-plus": "<path d=\"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2\"/><circle cx=\"9\" cy=\"7\" r=\"4\"/><path d=\"M19 8v6\"/><path d=\"M22 11h-6\"/>",
  "ticket": "<path d=\"M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z\"/><path d=\"M13 5v2\"/><path d=\"M13 17v2\"/><path d=\"M13 11v2\"/>",
  "bar-chart": "<path d=\"M12 20V10\"/><path d=\"M18 20V4\"/><path d=\"M6 20v-4\"/>",
  "zap": "<path d=\"M13 2 3 14h9l-1 8 10-12h-9l1-8z\"/>",
  "shield-check": "<path d=\"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z\"/><path d=\"m9 12 2 2 4-4\"/>",
  "smartphone": "<rect x=\"5\" y=\"2\" width=\"14\" height=\"20\" rx=\"2\"/><path d=\"M12 18h.01\"/>",
  "log-out": "<path d=\"M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4\"/><path d=\"m16 17 5-5-5-5\"/><path d=\"M21 12H9\"/>",
  "menu": "<path d=\"M4 12h16\"/><path d=\"M4 6h16\"/><path d=\"M4 18h16\"/>",
  "alert": "<path d=\"M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z\"/><path d=\"M12 9v4\"/><path d=\"M12 17h.01\"/>",
  "frown": "<circle cx=\"12\" cy=\"12\" r=\"10\"/><path d=\"M16 16s-1.5-2-4-2-4 2-4 2\"/><path d=\"M9 9h.01\"/><path d=\"M15 9h.01\"/>",
  "credit-card": "<rect x=\"2\" y=\"5\" width=\"20\" height=\"14\" rx=\"2\"/><path d=\"M2 10h20\"/>",
  "grid": "<rect x=\"3\" y=\"3\" width=\"7\" height=\"7\" rx=\"1\"/><rect x=\"14\" y=\"3\" width=\"7\" height=\"7\" rx=\"1\"/><rect x=\"14\" y=\"14\" width=\"7\" height=\"7\" rx=\"1\"/><rect x=\"3\" y=\"14\" width=\"7\" height=\"7\" rx=\"1\"/>",
  "hourglass": "<path d=\"M5 22h14\"/><path d=\"M5 2h14\"/><path d=\"M17 22v-4.17a2 2 0 0 0-.59-1.42L12 12l-4.41 4.41A2 2 0 0 0 7 17.83V22\"/><path d=\"M7 2v4.17a2 2 0 0 0 .59 1.42L12 12l4.41-4.41A2 2 0 0 0 17 6.17V2\"/>",
  "heart": "<path d=\"M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z\"/>",
  "search": "<circle cx=\"11\" cy=\"11\" r=\"8\"/><path d=\"m21 21-4.3-4.3\"/>",
  "info": "<circle cx=\"12\" cy=\"12\" r=\"10\"/><path d=\"M12 16v-4\"/><path d=\"M12 8h.01\"/>",
  "eye": "<path d=\"M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z\"/><circle cx=\"12\" cy=\"12\" r=\"3\"/>",
  "eye-off": "<path d=\"M9.88 9.88a3 3 0 1 0 4.24 4.24\"/><path d=\"M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68\"/><path d=\"M6.61 6.61A13.53 13.53 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61\"/><path d=\"m2 2 20 20\"/>",
  "layers": "<path d=\"m12 2 10 5-10 5L2 7l10-5Z\"/><path d=\"m2 17 10 5 10-5\"/><path d=\"m2 12 10 5 10-5\"/>",
  "file-text": "<path d=\"M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z\"/><path d=\"M14 2v6h6\"/><path d=\"M16 13H8\"/><path d=\"M16 17H8\"/><path d=\"M10 9H8\"/>",
  "quote": "<path d=\"M3 21c3 0 7-1 7-8V5c0-1.25-.76-2-2-2H4c-1.25 0-2 .75-2 2v6c0 1.25.75 2 2 2h4\"/><path d=\"M15 21c3 0 7-1 7-8V5c0-1.25-.76-2-2-2h-4c-1.25 0-2 .75-2 2v6c0 1.25.75 2 2 2h4\"/>",
  "sparkles": "<path d=\"m12 3-1.9 5.8a2 2 0 0 1-1.29 1.29L3 12l5.8 1.9a2 2 0 0 1 1.29 1.29L12 21l1.9-5.8a2 2 0 0 1 1.29-1.29L21 12l-5.8-1.9a2 2 0 0 1-1.29-1.29Z\"/>",
  "home": "<path d=\"m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z\"/><path d=\"M9 22V12h6v10\"/>",
  "chevron-right": "<path d=\"m9 18 6-6-6-6\"/>",
  "inbox": "<path d=\"M22 12h-6l-2 3h-4l-2-3H2\"/><path d=\"M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z\"/>",
  "power": "<path d=\"M18.36 6.64a9 9 0 1 1-12.73 0\"/><path d=\"M12 2v10\"/>",
  "ban": "<circle cx=\"12\" cy=\"12\" r=\"10\"/><path d=\"m4.9 4.9 14.2 14.2\"/>",
  "wifi": "<path d=\"M12 20h.01\"/><path d=\"M2 8.82a15 15 0 0 1 20 0\"/><path d=\"M5 12.86a10 10 0 0 1 14 0\"/><path d=\"M8.5 16.43a5 5 0 0 1 7 0\"/>"
};

/**
 * Devolve um <svg> inline (mesmo conjunto de ícones do macro Jinja icon()).
 * Uso em templates literais: `${icon("check")} Confirmado`
 */
function icon(name, size = 20, cls = "") {
  const body = GF_ICONS[name] || "";
  return `<svg class="icon${cls ? " " + cls : ""}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${body}</svg>`;
}
/* <<< GF-ICONS <<< */

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
 toast.setAttribute("role", type === "error" ? "alert" : "status");
 const iconName = type === "success" ? "check-circle" : type === "error" ? "alert" : "info";
 toast.innerHTML = icon(iconName);
 const msgEl = document.createElement("span");
 msgEl.textContent = message; // textContent: a mensagem nunca é interpretada como HTML
 toast.appendChild(msgEl);
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

/** Linha de metadados padrão (local + data) com ícones — usada nas listas de eventos. */
function eventMetaHtml(location, isoDate) {
 return `<span class="meta-item">${icon("map-pin", 15)} ${escapeHtml(location || "Local não informado")}</span>` +
 `<span class="meta-item">${icon("calendar", 15)} ${escapeHtml(formatDateTime(isoDate))}</span>`;
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
 const label = getCurrentTheme() === "dark" ? "Mudar para modo claro" : "Mudar para modo escuro";
 btn.title = label; // o ícone sol/lua é trocado por CSS conforme o tema
 btn.setAttribute("aria-label", label);
}

document.addEventListener("DOMContentLoaded", () => {
 const btn = document.getElementById("theme-toggle-btn");
 if (btn) {
 btn.addEventListener("click", toggleTheme);
 updateThemeToggleIcon();
 }
});

// --------------------------------------------------------------------------
// ALTURA REAL DO TOPBAR (--topbar-height)
// O .topbar é `position: sticky; top: 0`, mas sua altura muda entre
// breakpoints (quebra em 2 linhas no mobile). Elementos que precisam
// grudar logo ABAIXO dele (.search-bar, .event-mini-sticky) usavam um
// valor fixo em px que só era correto numa tela — isto lê a altura real
// do elemento renderizado e expõe como custom property, recalculada a
// cada resize/orientação para acompanhar mudanças de layout.
// --------------------------------------------------------------------------
function setTopbarHeightVar() {
 const topbar = document.querySelector(".topbar");
 if (topbar) {
 document.documentElement.style.setProperty("--topbar-height", `${topbar.offsetHeight}px`);
 }

 // Se existir um mini-cabeçalho fixo do evento nesta página (mobile) e ele
 // estiver visível (display != none, decidido via CSS/@media), soma a
 // altura dele -- assim a .search-bar (que também é sticky) empilha
 // corretamente LOGO ABAIXO dele, em vez de sobrepor os dois elementos
 // no mesmo `top`.
 const miniSticky = document.getElementById("event-mini-sticky");
 const miniHeight = miniSticky && miniSticky.offsetParent !== null ? miniSticky.offsetHeight : 0;
 document.documentElement.style.setProperty("--mini-sticky-height", `${miniHeight}px`);
}

document.addEventListener("DOMContentLoaded", setTopbarHeightVar);
window.addEventListener("load", setTopbarHeightVar);
window.addEventListener("resize", setTopbarHeightVar);
window.addEventListener("orientationchange", setTopbarHeightVar);

// ResizeObserver: remede automaticamente sempre que a altura REAL do
// topbar (ou do mini-cabeçalho) mudar, por QUALQUER motivo -- a fonte
// web carregando um instante depois (mudando a métrica do texto), a
// logo da marca carregando depois (empurrando a altura para baixo),
// o nome do evento vindo da API e quebrando linha, etc. Os listeners
// acima cobrem só o carregamento inicial e o resize da janela; isto
// cobre tudo o resto, de uma vez, sem precisar prever cada causa
// possível de mudança de altura -- é a correção definitiva para a
// barra de busca "flutuar" fora do lugar depois que o topo termina de
// carregar de verdade.
if (window.ResizeObserver) {
  const topbarEl = document.querySelector(".topbar");
  if (topbarEl) new ResizeObserver(setTopbarHeightVar).observe(topbarEl);

  const miniStickyEl = document.getElementById("event-mini-sticky");
  if (miniStickyEl) new ResizeObserver(setTopbarHeightVar).observe(miniStickyEl);
}

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
 document.getElementById("next-event-meta").innerHTML =
 `<span class="meta-item">${icon("map-pin", 16)} ${escapeHtml(nextEvent.location || "Local não informado")}</span>` +
 `<span class="meta-item">${icon("calendar", 16)} ${escapeHtml(formatDateTime(nextEvent.event_date))}</span>`;

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
 ${icon("scan")} Iniciar Check-in
 </a>`;
 return;
 }

 if (mode === "organizador") {
 box.innerHTML = `
 <a href="/organizador/eventos/${event.id}" class="btn btn-secondary">${icon("edit")} Editar</a>
 <a href="/organizador/eventos/${event.id}" class="btn btn-primary">${icon("scan")} Trabalhar evento (check-in)</a>`;
 return;
 }

 // admin (padrão): edição/exclusão diretas + atalho de check-in.
 // Reaproveita openEditEventModal/handleDeleteEvent já existentes em
 // admin_events.js (mesmo modal e mesma lógica usados na lista de eventos).
 box.innerHTML = `
 <button type="button" class="btn btn-secondary" data-next-event-edit="${event.id}">${icon("edit")} Editar</button>
 <button type="button" class="btn btn-danger" data-next-event-delete="${event.id}">${icon("trash")} Excluir</button>
 <a href="/checkin/${event.id}" class="btn btn-primary">${icon("scan")} Trabalhar evento (check-in)</a>`;

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
