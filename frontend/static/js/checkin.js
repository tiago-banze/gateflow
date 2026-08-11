/**
 * checkin.js
 * Tela de check-in (busca + leitor de QR Code) de UM evento específico.
 * O event_id vem embutido no HTML (data-event-id no <body>), definido
 * pela rota /checkin/<event_id> no servidor - não depende mais de
 * seleção via localStorage no navegador.
 */

const EVENT_ID = document.body.getAttribute("data-event-id");
const EVENT_STATUS = document.body.getAttribute("data-event-status"); // "proximo" | "andamento" | "encerrado"
const EVENT_HAS_ENDED = EVENT_STATUS === "encerrado";

let currentSearchTerm = "";
let pollingIntervalId = null;
let html5QrCode = null;
let isProcessingCheckin = false;
let isScannerTransitioning = false; // previne abrir/fechar sobrepostos (causa raiz de "câmera recusa acesso")

const POLLING_INTERVAL_MS = 3000;

// --------------------------------------------------------------------------
// OFFLINE-FIRST: Service Worker (app shell) + IndexedDB (dados + fila)
// --------------------------------------------------------------------------

let offlineReady = false;

function isNetworkFailure(result) {
  // status 0 = apiRequest() não conseguiu sequer completar o fetch (ver
  // common.js) -- é o único jeito confiável de distinguir "estou offline"
  // de uma falha de regra de negócio normal (ex: já fez check-in, evento
  // encerrado), que também vêm como success:false mas com status HTTP real.
  return result && result.status === 0;
}

function updateOfflineIndicator() {
  const el = document.getElementById("offline-indicator");
  if (!el) return;
  if (!navigator.onLine) {
    el.textContent = "📴 Sem internet — a validar com a lista guardada neste aparelho";
    el.classList.remove("hidden");
    return;
  }
  OfflineCheckin.countPending().then((count) => {
    if (count > 0) {
      el.textContent = `🔄 A sincronizar ${count} check-in(s) pendente(s)...`;
      el.classList.remove("hidden");
    } else {
      el.classList.add("hidden");
    }
  });
}

async function trySyncPending() {
  if (!offlineReady || !navigator.onLine) return;
  const pendingBefore = await OfflineCheckin.countPending();
  if (pendingBefore === 0) return;

  const { synced } = await OfflineCheckin.syncPending(apiRequest);
  if (synced > 0) {
    showToast(`${synced} check-in(s) feito(s) offline foram sincronizados.`, "success");
    refreshGuests();
    loadLiveStats();
  }
  updateOfflineIndicator();
}

window.addEventListener("online", () => {
  updateOfflineIndicator();
  trySyncPending();
});
window.addEventListener("offline", updateOfflineIndicator);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((err) => {
      console.warn("Não foi possível registar o Service Worker (modo offline ficará limitado):", err);
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
 refreshGuests();
 startPolling();
 loadLiveStats();
 setInterval(loadLiveStats, 15000);

 OfflineCheckin.ready(EVENT_ID).then((ok) => {
   offlineReady = ok;
   updateOfflineIndicator();
   setInterval(trySyncPending, 10000); // tenta sincronizar a cada 10s se houver fila pendente
 });

 document.getElementById("search-input").addEventListener("input", (e) => {
 currentSearchTerm = e.target.value;
 refreshGuests();
 });

 const scannerBtn = document.getElementById("btn-open-scanner");
 if (scannerBtn) scannerBtn.addEventListener("click", openScanner);
 document.getElementById("btn-close-scanner").addEventListener("click", closeScanner);
});

// --------------------------------------------------------------------------
// SOM DE FEEDBACK (Web Audio API - sem arquivos externos)
// --------------------------------------------------------------------------

let audioContext = null;

function getAudioContext() {
 // Criado sob demanda (no primeiro toque do usuário), pois navegadores
 // bloqueiam áudio automático sem interação prévia.
 if (!audioContext) {
 const AudioContextClass = window.AudioContext || window.webkitAudioContext;
 if (!AudioContextClass) return null;
 audioContext = new AudioContextClass();
 }
 if (audioContext.state === "suspended") {
 audioContext.resume().catch(() => {});
 }
 return audioContext;
}

/**
 * Toca um "beep" curto usando um oscilador simples (sem dependências
 * externas). `frequency` em Hz, `durationMs` em milissegundos.
 */
function playTone(frequency, durationMs, delayMs = 0, volume = 0.2) {
 const ctx = getAudioContext();
 if (!ctx) return;

 const startTime = ctx.currentTime + delayMs / 1000;
 const oscillator = ctx.createOscillator();
 const gainNode = ctx.createGain();

 oscillator.type = "sine";
 oscillator.frequency.setValueAtTime(frequency, startTime);

 // Fade in/out rápido para evitar "clique" audível no início/fim do som
 gainNode.gain.setValueAtTime(0, startTime);
 gainNode.gain.linearRampToValueAtTime(volume, startTime + 0.01);
 gainNode.gain.linearRampToValueAtTime(0, startTime + durationMs / 1000);

 oscillator.connect(gainNode);
 gainNode.connect(ctx.destination);

 oscillator.start(startTime);
 oscillator.stop(startTime + durationMs / 1000 + 0.02);
}

/** Bipe agudo único e satisfatório - check-in confirmado com sucesso. */
function playSuccessSound() {
 playTone(880, 90, 0, 0.22);
 playTone(1318, 130, 90, 0.22);
}

/** Som duplo mais grave - erro, QR Code inválido ou check-in duplicado. */
function playErrorSound() {
 playTone(220, 140, 0, 0.22);
 playTone(220, 140, 170, 0.22);
}

// --------------------------------------------------------------------------
// LISTAGEM / BUSCA / POLLING
// --------------------------------------------------------------------------

function startPolling() {
 if (pollingIntervalId) clearInterval(pollingIntervalId);
 pollingIntervalId = setInterval(refreshGuests, POLLING_INTERVAL_MS);
}

async function refreshGuests() {
 const query = currentSearchTerm ? `?search=${encodeURIComponent(currentSearchTerm)}` : "";
 const result = await apiRequest(`/api/events/${EVENT_ID}/guests${query}`);

 if (!result.success) {
 if (isNetworkFailure(result) && offlineReady) {
 // Sem rede: usa a cópia local (IndexedDB) em vez de deixar a tela
 // vazia -- é exatamente o cenário "internet caiu no casamento".
 const localGuests = await OfflineCheckin.getAllGuests();
 const term = currentSearchTerm.trim().toLowerCase();
 const filtered = term
 ? localGuests.filter((g) => g.full_name.toLowerCase().includes(term))
 : localGuests;
 const total = localGuests.length;
 const checkedIn = localGuests.filter((g) => g.checked_in).length;
 renderStats({ total, checked_in: checkedIn, pending: Math.max(0, total - checkedIn) });
 renderGuests(filtered);
 }
 return; // Evita spam de toasts durante polling; falha silenciosa e tenta de novo no próximo ciclo
 }

 renderStats(result.stats);
 renderGuests(result.data || []);
 if (offlineReady) OfflineCheckin.cacheGuests(result.data || []);
}

function renderStats(stats) {
 const el = document.getElementById("stats-bar");
 if (!stats) { el.innerHTML = ""; return; }
 el.innerHTML = `
 <span class="stat-pill">Total: ${stats.total}</span>
 <span class="stat-pill success">Presentes: ${stats.checked_in}</span>
 <span class="stat-pill pending">Pendentes: ${stats.pending}</span>
 `;
}

function renderGuests(guests) {
 const container = document.getElementById("guests-container");
 const tableBody = document.getElementById("guests-table-body");
 const emptyEl = document.getElementById("guests-empty");

 if (guests.length === 0) {
 container.innerHTML = "";
 tableBody.innerHTML = "";
 emptyEl.classList.remove("hidden");
 return;
 }
 emptyEl.classList.add("hidden");

 // A API já retorna ordenado alfabeticamente por nome (COLLATE NOCASE),
 // mas reforçamos aqui também para garantir a ordem mesmo se a origem
 // dos dados mudar no futuro (ex: cache local, outra fonte de dados).
 const sortedGuests = [...guests].sort((a, b) =>
 a.full_name.localeCompare(b.full_name, "pt-BR", { sensitivity: "base" })
 );

 renderGuestCards(sortedGuests, container);
 renderGuestTable(sortedGuests, tableBody);
}

function renderGuestCards(guests, container) {
 container.innerHTML = guests.map((g) => `
 <div class="guest-card ${g.checked_in ? "checked-in" : ""}" data-guest-id="${g.id}">
 <div class="guest-name">${escapeHtml(g.full_name)}</div>
 <div class="guest-role">${escapeHtml(g.role || "Convidado")}</div>
 <div class="guest-table"> Mesa: <strong>${escapeHtml(g.table_number || "Não definida")}</strong></div>
 ${g.checked_in
 ? `<div class="checked-label"> Presença confirmada</div>`
 : EVENT_HAS_ENDED
 ? `<div class="checked-label" style="color:var(--color-text-muted);"> Não compareceu</div>`
 : `<button class="btn btn-primary checkin-btn" data-checkin-guest="${g.id}">Check-in</button>`}
 </div>
 `).join("");

 if (!EVENT_HAS_ENDED) {
 container.querySelectorAll("[data-checkin-guest]").forEach((btn) => {
 btn.addEventListener("click", () => handleManualCheckin(btn.getAttribute("data-checkin-guest"), btn));
 });
 }
}

function renderGuestTable(guests, tableBody) {
 tableBody.innerHTML = guests.map((g) => `
 <tr class="${g.checked_in ? "checked-in" : ""}" data-guest-id="${g.id}">
 <td class="table-guest-name">${escapeHtml(g.full_name)}</td>
 <td>${escapeHtml(g.role || "Convidado")}</td>
 <td class="table-guest-table">${escapeHtml(g.table_number || "Não definida")}</td>
 <td>
 ${g.checked_in
 ? `<span class="badge" style="background:var(--color-success-bg); color:var(--color-success-text);"> Presente</span>`
 : EVENT_HAS_ENDED
 ? `<span class="badge"> Não compareceu</span>`
 : `<button class="btn btn-primary table-checkin-btn" data-checkin-guest="${g.id}">Check-in</button>`}
 </td>
 </tr>
 `).join("");

 if (!EVENT_HAS_ENDED) {
 tableBody.querySelectorAll("[data-checkin-guest]").forEach((btn) => {
 btn.addEventListener("click", () => handleManualCheckin(btn.getAttribute("data-checkin-guest"), btn));
 });
 }
}

// --------------------------------------------------------------------------
// CHECK-IN MANUAL (BOTÃO)
// --------------------------------------------------------------------------

async function handleManualCheckin(guestId, btnEl) {
 if (EVENT_HAS_ENDED) {
 playErrorSound();
 showToast("Este evento já foi encerrado. Não é possível fazer novos check-ins.", "error");
 return;
 }

 if (btnEl) {
 btnEl.disabled = true;
 btnEl.innerHTML = '<span class="spinner"></span>';
 }

 const result = await apiRequest(`/api/checkin/manual/${guestId}`, {
 method: "POST",
 body: JSON.stringify({}),
 });

 if (!result.success) {
 if (isNetworkFailure(result) && offlineReady) {
 const applied = await offlineCheckinFallback(guestId);
 if (applied === "checked_in") {
 playSuccessSound();
 const guest = await OfflineCheckin.findGuestById(guestId);
 showCheckinConfirmation(guest);
 refreshGuests();
 updateOfflineIndicator();
 return;
 }
 if (applied === "already_checked_in") {
 playErrorSound();
 showToast("Este convidado já tinha feito check-in (registado neste aparelho).", "error");
 if (btnEl) { btnEl.disabled = false; btnEl.textContent = "Check-in"; }
 return;
 }
 // applied === "not_found": cai para o tratamento de erro normal abaixo
 }
 playErrorSound();
 if (result.already_checked_in) {
 showToast("Check-in já realizado anteriormente!", "error");
 } else if (result.raw && result.raw.event_ended) {
 showToast(result.error || "Este evento já foi encerrado.", "error");
 } else {
 showToast(result.error || "Erro ao registrar check-in.", "error");
 }
 if (btnEl) {
 btnEl.disabled = false;
 btnEl.textContent = "Check-in";
 }
 refreshGuests();
 return;
 }

 playSuccessSound();
 showCheckinConfirmation(result.data);
 refreshGuests();
}

/**
 * Aplica um check-in localmente (IndexedDB) quando a rede falhou, e
 * adiciona à fila de sincronização. Retorna "checked_in",
 * "already_checked_in" ou "not_found" (convidado não está na cópia
 * local -- ex: cadastrado depois do último sync, ou QR de outro evento).
 */
async function offlineCheckinFallback(guestId) {
 const guest = await OfflineCheckin.findGuestById(guestId);
 if (!guest) return "not_found";
 if (guest.checked_in) return "already_checked_in";
 await OfflineCheckin.queueCheckin(guestId);
 return "checked_in";
}

// --------------------------------------------------------------------------
// BANNER DE CONFIRMAÇÃO (Mesa em destaque, para o porteiro avisar o convidado)
// --------------------------------------------------------------------------

function showCheckinConfirmation(guest) {
 // Fecha o scanner se estiver aberto, para o banner não ficar escondido atrás da câmera
 if (!document.getElementById("scanner-modal").classList.contains("hidden")) {
 closeScanner();
 }

 const existing = document.getElementById("checkin-confirmation-banner");
 if (existing) existing.remove();

 const tableLabel = guest.table_number || "Não definida";

 const overlay = document.createElement("div");
 overlay.id = "checkin-confirmation-banner";
 overlay.className = "checkin-confirmation-overlay";
 overlay.innerHTML = `
 <div class="checkin-confirmation-box">
 <div class="checkin-confirmation-check"></div>
 <div class="checkin-confirmation-name">${escapeHtml(guest.full_name)}</div>
 <div class="checkin-confirmation-label">Check-in confirmado</div>
 <div class="checkin-confirmation-table">
 <span>MESA</span>
 <strong>${escapeHtml(tableLabel)}</strong>
 </div>
 <button class="btn btn-primary btn-lg" id="btn-dismiss-confirmation">OK</button>
 </div>
 `;
 document.body.appendChild(overlay);

 const dismiss = () => overlay.remove();
 document.getElementById("btn-dismiss-confirmation").addEventListener("click", dismiss);
 overlay.addEventListener("click", (e) => {
 if (e.target === overlay) dismiss();
 });
 setTimeout(dismiss, 5000);
}

// --------------------------------------------------------------------------
// SCANNER DE QR CODE (CÂMERA)
// --------------------------------------------------------------------------

async function openScanner() {
 if (EVENT_HAS_ENDED) {
 playErrorSound();
 showToast("Este evento já foi encerrado. Não é possível fazer novos check-ins.", "error");
 return;
 }

 // Verificação prévia: se o navegador não expõe a API de câmera
 // (navigator.mediaDevices), significa que esta origem não está liberada
 // - seja por não ser https://, localhost, ou não ter sido configurada em
 // chrome://flags/#unsafely-treat-insecure-origin-as-secure (o caminho
 // recomendado no README). Detectamos isso ANTES de tentar, para dar uma
 // mensagem que realmente ajuda o porteiro, em vez do erro genérico.
 if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
 showToast(
 "Este aparelho ainda não está liberado para usar a câmera. Peça ao administrador para configurar o chrome://flags neste aparelho (ver README, seção 'Câmera não funciona pelo IP da rede') - é rápido e só precisa ser feito uma vez.",
 "error",
 9000
 );
 return;
 }

 // Proteção contra reentrância: ignora cliques repetidos enquanto o
 // scanner está no meio de abrir ou fechar (evita duas instâncias
 // disputando a mesma câmera ao mesmo tempo).
 if (isScannerTransitioning) return;

 // Se por qualquer motivo já existe uma instância viva (ex: um
 // fechamento anterior não terminou de verdade), força o encerramento
 // COMPLETO antes de abrir uma nova - nunca inicia um novo stream sem
 // ter certeza de que o anterior foi liberado. Essa é a causa raiz mais
 // provável do bug "câmera recusa acesso depois de um tempo".
 if (html5QrCode) {
 await hardStopScanner();
 }

 isScannerTransitioning = true;
 document.getElementById("scanner-modal").classList.remove("hidden");
 isProcessingCheckin = false;

 html5QrCode = new Html5Qrcode("qr-reader");
 const scannerConfig = { fps: 10, qrbox: { width: 240, height: 240 } };

 try {
 await html5QrCode.start({ facingMode: "environment" }, scannerConfig, onQrScanSuccess, () => {
 /* callback de erro de leitura por frame: ignorado silenciosamente,
 pois dispara constantemente enquanto não há QR Code no quadro */
 });
 } catch (err) {
 showToast(describeCameraError(err), "error", 8000);
 console.error("Erro ao iniciar câmera:", err);
 document.getElementById("scanner-modal").classList.add("hidden");
 await hardStopScanner();
 } finally {
 isScannerTransitioning = false;
 }
}

/**
 * Traduz os erros conhecidos da API de câmera do navegador em mensagens
 * específicas e acionáveis, em vez do genérico "não foi possível acessar
 * a câmera" que não ajuda o porteiro a resolver o problema.
 */
function describeCameraError(err) {
 const name = (err && err.name) || "";
 const message = (err && err.message) || String(err || "");

 if (name === "NotAllowedError" || /Permission denied/i.test(message)) {
 return "Permissão de câmera negada. Toque no cadeado/ícone ao lado do endereço no navegador, permita a câmera para este site e tente novamente.";
 }
 if (name === "NotFoundError" || /Requested device not found/i.test(message)) {
 return "Nenhuma câmera foi encontrada neste dispositivo.";
 }
 if (name === "NotReadableError" || /Could not start video source/i.test(message)) {
 return "A câmera está sendo usada por outro aplicativo. Feche outros apps que usem a câmera e tente novamente.";
 }
 if (name === "OverconstrainedError") {
 return "A câmera traseira não pôde ser ativada neste dispositivo.";
 }
 if (name === "SecurityError") {
 return "O navegador bloqueou a câmera neste endereço. Peça ao administrador para configurar o chrome://flags neste aparelho (ver README, seção 'Câmera não funciona pelo IP da rede').";
 }
 return "Não foi possível acessar a câmera. Verifique as permissões do navegador, ou peça ao administrador para configurar este aparelho (ver README).";
}

async function closeScanner() {
 document.getElementById("scanner-modal").classList.add("hidden");
 await hardStopScanner();
}

/**
 * Encerra COMPLETAMENTE o leitor de QR Code: chama html5-qrcode.stop()
 * (que internamente já deveria parar as faixas de mídia) E, como
 * segurança extra, também para MANUALMENTE qualquer MediaStreamTrack
 * que ainda esteja "viva" no elemento de vídeo. Isso cobre o caso em que
 * o encerramento interno da biblioteca falha silenciosamente e deixa a
 * câmera presa (o sintoma relatado: "a câmera recusa acesso depois de
 * um tempo, só resolve reiniciando o navegador").
 */
async function hardStopScanner() {
 const instance = html5QrCode;
 html5QrCode = null; // limpa a referência já - evita reentrância durante o await abaixo

 if (instance) {
 try {
 await instance.stop();
 } catch (err) {
 console.warn("Aviso ao parar o scanner (seguindo com limpeza manual):", err);
 }
 try {
 instance.clear();
 } catch (err) {
 /* elemento já pode ter sido removido/limpo; ignorar */
 }
 }

 // Segurança extra: garante que NENHUMA faixa de vídeo continue ativa,
 // mesmo que o html5-qrcode não tenha limpado corretamente por dentro.
 const videoEl = document.querySelector("#qr-reader video");
 if (videoEl && videoEl.srcObject) {
 try {
 videoEl.srcObject.getTracks().forEach((track) => track.stop());
 } catch (err) {
 /* ignorar */
 }
 videoEl.srcObject = null;
 }
}

// Garante que a câmera é liberada se o porteiro trocar de aba/app (mobile)
// ou sair da página, em vez de deixar o stream preso em segundo plano.
document.addEventListener("visibilitychange", () => {
 if (document.hidden && html5QrCode) {
 hardStopScanner();
 }
});
window.addEventListener("beforeunload", () => {
 if (html5QrCode) {
 hardStopScanner();
 }
});

/**
 * Extrai o ID do convidado de um valor de QR Code lido -- mesmo formato e
 * regra usados no servidor (qrcode_utils.extract_guest_id_from_payload):
 * prefixo "CHECKIN:" seguido do UUID. Usado só no fallback OFFLINE (sem
 * rede o QR precisa ser interpretado aqui mesmo, no aparelho).
 */
function extractGuestIdFromQr(rawValue) {
 if (!rawValue) return null;
 const trimmed = rawValue.trim();
 const prefix = "CHECKIN:";
 if (!trimmed.startsWith(prefix)) return null;
 const guestId = trimmed.slice(prefix.length).trim();
 return guestId || null;
}

async function onQrScanSuccess(decodedText) {
 if (isProcessingCheckin) return; // evita disparos múltiplos do mesmo frame
 isProcessingCheckin = true;

 const result = await apiRequest("/api/checkin/qr", {
 method: "POST",
 body: JSON.stringify({
 qr_value: decodedText,
 event_id: EVENT_ID,
 }),
 });

 if (!result.success) {
 if (isNetworkFailure(result) && offlineReady) {
 const guestId = extractGuestIdFromQr(decodedText);
 if (guestId) {
 const applied = await offlineCheckinFallback(guestId);
 if (applied === "checked_in") {
 playSuccessSound();
 const guest = await OfflineCheckin.findGuestById(guestId);
 showCheckinConfirmation(guest);
 refreshGuests();
 updateOfflineIndicator();
 setTimeout(() => { isProcessingCheckin = false; }, 1500);
 return;
 }
 if (applied === "already_checked_in") {
 playErrorSound();
 showToast("Check-in já realizado (registado neste aparelho)!", "error");
 setTimeout(() => { isProcessingCheckin = false; }, 1500);
 return;
 }
 }
 }
 playErrorSound();
 if (result.already_checked_in) {
 showToast(result.error || "Check-in já realizado!", "error");
 } else {
 showToast(result.error || "QR Code inválido.", "error");
 }
 } else {
 playSuccessSound();
 showCheckinConfirmation(result.data);
 refreshGuests();
 loadLiveStats();
 }

 // Pequeno intervalo antes de aceitar o próximo QR Code, para permitir
 // que o porteiro afaste a câmera e evitar leituras duplicadas do mesmo código.
 setTimeout(() => { isProcessingCheckin = false; }, 1500);
}

async function loadLiveStats() {
  const barEl = document.getElementById("live-stats-bar");
  const chartEl = document.getElementById("live-stats-chart");
  if (!barEl) return;

  const result = await apiRequest(`/api/checkin/events/${EVENT_ID}/live-stats`);
  if (!result.success) return;

  const stats = result.data;
  barEl.innerHTML = `
    <span class="stat-pill">${stats.event_module === "A" ? "Convidados" : "Vendidos"}: ${stats.total}</span>
    <span class="stat-pill success">Entradas: ${stats.checked_in}</span>
    <span class="stat-pill">Pendentes: ${stats.pending}</span>
    <span class="stat-pill">Taxa de Comparencia: ${stats.attendance_rate}%</span>
  `;

  if (!stats.hourly || stats.hourly.length === 0) {
    chartEl.innerHTML = `<p style="color:var(--color-text-muted); font-size:0.85rem;">Ainda sem entradas registadas.</p>`;
    return;
  }

  const maxCount = Math.max(...stats.hourly.map((h) => h.count), 1);
  const barWidth = 32;
  const gap = 10;
  const chartHeight = 90;
  const width = stats.hourly.length * (barWidth + gap);

  const bars = stats.hourly.map((h, i) => {
    const barHeight = Math.round((h.count / maxCount) * (chartHeight - 20));
    const x = i * (barWidth + gap);
    const y = chartHeight - barHeight;
    return `
      <text x="${x + barWidth / 2}" y="${chartHeight - barHeight - 6}" text-anchor="middle" font-size="11" fill="var(--color-text)">${h.count}</text>
      <rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" rx="4" fill="var(--color-primary)" />
      <text x="${x + barWidth / 2}" y="${chartHeight + 14}" text-anchor="middle" font-size="10" fill="var(--color-text-muted)">${h.hour}h</text>
    `;
  }).join("");

  chartEl.innerHTML = `
    <p style="color:var(--color-text-muted); font-size:0.8rem; margin-bottom:6px;">Entradas por hora</p>
    <svg viewBox="0 0 ${width} ${chartHeight + 20}" width="100%" height="${chartHeight + 20}" preserveAspectRatio="xMinYMid meet">
      ${bars}
    </svg>
  `;
}
