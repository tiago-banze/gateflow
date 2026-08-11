/**
 * storefront.js
 * Página pública de venda de bilhetes (Fase 4) - carrega o evento, deixa
 * o cliente escolher a quantidade por setor, coleta os dados do
 * comprador, dispara o checkout (que aciona o USSD Push M-Pesa) e faz
 * polling do estado do pagamento até a confirmação (ou falha/expiração).
 */

(function () {
 const root = document.getElementById("storefront-root");
 const slug = root.dataset.eventSlug;

 const state = {
 event: null,
 stock: null,
 qtyVip: 0,
 qtyNormal: 0,
 orderId: null,
 orderCode: null,
 pollTimer: null,
 pollAttempts: 0,
 };

 const els = {
 loadingCard: document.getElementById("sf-loading-card"),
 notFoundCard: document.getElementById("sf-notfound-card"),
 soldOutCard: document.getElementById("sf-soldout-card"),
 soldOutContact: document.getElementById("sf-soldout-contact"),
 infoCard: document.getElementById("sf-info-card"),
 ticketsCard: document.getElementById("sf-tickets-card"),
 buyerCard: document.getElementById("sf-buyer-card"),
 waitingCard: document.getElementById("sf-waiting-card"),
 successCard: document.getElementById("sf-success-card"),

 eventName: document.getElementById("sf-event-name"),
 eventOrg: document.getElementById("sf-event-org"),
 eventLocation: document.getElementById("sf-event-location"),
 eventDate: document.getElementById("sf-event-date"),
 eventDesc: document.getElementById("sf-event-desc"),

 sectorVip: document.getElementById("sf-sector-vip"),
 sectorNormal: document.getElementById("sf-sector-normal"),
 priceVip: document.getElementById("sf-price-vip"),
 priceNormal: document.getElementById("sf-price-normal"),
 remainingVip: document.getElementById("sf-remaining-vip"),
 remainingNormal: document.getElementById("sf-remaining-normal"),
 qtyVipInput: document.getElementById("sf-qty-vip"),
 qtyNormalInput: document.getElementById("sf-qty-normal"),

 summarySubtotal: document.getElementById("sf-summary-subtotal"),
 summaryFee: document.getElementById("sf-summary-fee"),
 summaryTotal: document.getElementById("sf-summary-total"),
 btnContinue: document.getElementById("sf-btn-continue"),

 buyerName: document.getElementById("sf-buyer-name"),
 buyerPhone: document.getElementById("sf-buyer-phone"),
 buyerEmail: document.getElementById("sf-buyer-email"),
 buyerError: document.getElementById("sf-buyer-error"),
 btnPay: document.getElementById("sf-btn-pay"),
 btnPayAmount: document.getElementById("sf-btn-pay-amount"),
 btnBackToTickets: document.getElementById("sf-btn-back-to-tickets"),

 waitingPhone: document.getElementById("sf-waiting-phone"),
 waitingAmount: document.getElementById("sf-waiting-amount"),
 waitingWarning: document.getElementById("sf-waiting-warning"),
 btnRetry: document.getElementById("sf-btn-retry"),

 successCode: document.getElementById("sf-success-code"),
 btnDownload: document.getElementById("sf-btn-download"),
 };

 function formatMT(value) {
 const number = Number(value) || 0;
 return number.toLocaleString("pt-MZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " MT";
 }

 function showOnly(card) {
 [els.loadingCard, els.notFoundCard, els.soldOutCard, els.ticketsCard, els.buyerCard, els.waitingCard, els.successCard]
 .forEach((el) => el.classList.add("sf-hidden"));
 if (card) card.classList.remove("sf-hidden");
 }

 async function loadEvent() {
 const result = await apiRequest(`/api/public/events/${encodeURIComponent(slug)}`);
 if (!result.success || !result.data) {
 els.infoCard.classList.add("sf-hidden");
 showOnly(els.notFoundCard);
 return;
 }

 state.event = result.data;
 state.stock = result.data.stock;
 renderEventInfo();

 if (state.stock.sold_out) {
 els.soldOutContact.textContent = state.event.contact_phone
 ? `Contacto: ${state.event.contact_phone}`
 : "";
 showOnly(els.soldOutCard);
 return;
 }

 renderSectors();
 showOnly(els.ticketsCard);
 }

 function renderEventInfo() {
 els.eventName.textContent = state.event.name;
 els.eventOrg.textContent = state.event.organizer_display_name || "";
 els.eventLocation.textContent = state.event.location || " - ";
 els.eventDate.textContent = formatDateTime(state.event.event_date) || " - ";
 if (state.event.description) {
 els.eventDesc.textContent = state.event.description;
 } else {
 els.eventDesc.style.display = "none";
 }
 }

 function renderSectors() {
 const hasVip = (state.stock.capacity_vip || 0) > 0;
 const hasNormal = (state.stock.capacity_normal || 0) > 0;

 if (hasVip) {
 els.sectorVip.classList.remove("sf-hidden");
 els.priceVip.textContent = formatMT(state.event.price_vip);
 els.remainingVip.textContent = state.stock.remaining_vip > 0
 ? `${state.stock.remaining_vip} vaga(s) disponível(is)`
 : "Esgotado";
 }
 if (hasNormal) {
 els.sectorNormal.classList.remove("sf-hidden");
 els.priceNormal.textContent = formatMT(state.event.price_normal);
 els.remainingNormal.textContent = state.stock.remaining_normal > 0
 ? `${state.stock.remaining_normal} vaga(s) disponível(is)`
 : "Esgotado";
 }
 }

 function currentUnitPrice(sector) {
 return sector === "vip" ? Number(state.event.price_vip) || 0 : Number(state.event.price_normal) || 0;
 }

 function maxRemaining(sector) {
 return sector === "vip" ? state.stock.remaining_vip : state.stock.remaining_normal;
 }

 function updateQuantity(sector, delta) {
 const key = sector === "vip" ? "qtyVip" : "qtyNormal";
 const max = maxRemaining(sector);
 let next = state[key] + delta;
 if (next < 0) next = 0;
 if (next > max) next = max;
 state[key] = next;

 const input = sector === "vip" ? els.qtyVipInput : els.qtyNormalInput;
 input.value = next;

 renderSummary();
 }

 function renderSummary() {
 const subtotal = state.qtyVip * currentUnitPrice("vip") + state.qtyNormal * currentUnitPrice("normal");
 const feeRate = state.event.service_fee_rate || 0.05;
 const fee = Math.round(subtotal * feeRate * 100) / 100;
 const total = Math.round((subtotal + fee) * 100) / 100;

 els.summarySubtotal.textContent = formatMT(subtotal);
 els.summaryFee.textContent = formatMT(fee);
 els.summaryTotal.textContent = formatMT(total);

 const totalQty = state.qtyVip + state.qtyNormal;
 els.btnContinue.disabled = totalQty === 0;
 els.btnPayAmount.textContent = formatMT(total);
 }

 document.querySelectorAll(".sf-qty-btn").forEach((btn) => {
 btn.addEventListener("click", () => {
 const sector = btn.dataset.sector;
 const delta = btn.dataset.action === "inc" ? 1 : -1;
 updateQuantity(sector, delta);
 });
 });

 els.btnContinue.addEventListener("click", () => {
 showOnly(els.buyerCard);
 });

 els.btnBackToTickets.addEventListener("click", () => {
 showOnly(els.ticketsCard);
 });

 function validatePhone(raw) {
 const digits = (raw || "").replace(/\D/g, "");
 // Aceita 9 dígitos (84/85XXXXXXX), 10 com 0 na frente, ou 12 com 258 - 
 // validação final e normalização definitivas acontecem no backend.
 return /^(258)?0?(84|85)\d{7}$/.test(digits.startsWith("258") ? digits : (digits.startsWith("0") ? digits.slice(1) : digits)) || /^(258)?(84|85)\d{7}$/.test(digits);
 }

 els.btnPay.addEventListener("click", async () => {
 const buyerName = els.buyerName.value.trim();
 const buyerPhone = els.buyerPhone.value.trim();
 const buyerEmail = els.buyerEmail.value.trim();

 els.buyerError.classList.add("sf-hidden");

 if (!buyerName) {
 showBuyerError("Por favor, indique o seu nome completo.");
 return;
 }
 if (!validatePhone(buyerPhone)) {
 showBuyerError("Número M-Pesa inválido. Use um número 84 ou 85 (ex: 84 123 4567).");
 return;
 }

 els.btnPay.disabled = true;
 els.btnPay.textContent = "A processar…";

 const result = await apiRequest(`/api/public/events/${encodeURIComponent(slug)}/checkout`, {
 method: "POST",
 body: JSON.stringify({
 quantity_vip: state.qtyVip,
 quantity_normal: state.qtyNormal,
 buyer_name: buyerName,
 buyer_phone: buyerPhone,
 buyer_email: buyerEmail || null,
 }),
 });

 els.btnPay.disabled = false;
 els.btnPay.innerHTML = `Pagar <span id="sf-btn-pay-amount">${els.summaryTotal.textContent}</span> via M-Pesa`;

 if (!result.success || !result.data || !result.data.order) {
 showBuyerError(result.error || "Não foi possível iniciar a compra. Tente novamente.");
 return;
 }

 state.orderId = result.data.order.id;
 state.orderCode = result.data.order.order_code;
 state.pollAttempts = 0;

 els.waitingPhone.textContent = buyerPhone;
 els.waitingAmount.textContent = els.summaryTotal.textContent;
 els.waitingWarning.classList.add("sf-hidden");
 els.btnRetry.classList.add("sf-hidden");

 if (result.data.payment_warning) {
 els.waitingWarning.textContent = result.data.payment_warning;
 els.waitingWarning.classList.remove("sf-hidden");
 els.btnRetry.classList.remove("sf-hidden");
 }

 showOnly(els.waitingCard);
 startPolling();
 });

 function showBuyerError(message) {
 els.buyerError.textContent = message;
 els.buyerError.classList.remove("sf-hidden");
 }

 function startPolling() {
 stopPolling();
 state.pollTimer = setInterval(pollOrderStatus, 4000);
 // Primeira checagem quase imediata (dá tempo do push chegar ao telemóvel).
 setTimeout(pollOrderStatus, 2500);
 }

 function stopPolling() {
 if (state.pollTimer) {
 clearInterval(state.pollTimer);
 state.pollTimer = null;
 }
 }

 async function pollOrderStatus() {
 if (!state.orderId) return;
 state.pollAttempts += 1;

 const result = await apiRequest(`/api/public/orders/${state.orderId}/status`);
 if (!result.success || !result.data) {
 return; // falha passageira de rede -- tenta de novo no próximo ciclo
 }

 const order = result.data;

 if (order.status === "paid" && order.tickets_ready) {
 stopPolling();
 showSuccess(order);
 return;
 }

 if (order.status === "expired" || order.status === "cancelled") {
 stopPolling();
 els.waitingWarning.textContent = "O tempo para concluir este pagamento expirou. Por favor, inicie uma nova compra.";
 els.waitingWarning.classList.remove("sf-hidden");
 els.btnRetry.classList.add("sf-hidden");
 return;
 }

 if (order.payment_failed) {
 els.waitingWarning.textContent = order.payment_message || "O pagamento não foi concluído.";
 els.waitingWarning.classList.remove("sf-hidden");
 els.btnRetry.classList.remove("sf-hidden");
 return;
 }

 // Depois de ~2 minutos de polling sem resposta, mostra o botão de
 // retentativa mesmo sem falha explícita -- o telemóvel do cliente
 // pode ter perdido o pedido USSD por sinal fraco.
 if (state.pollAttempts >= 30) {
 els.btnRetry.classList.remove("sf-hidden");
 }
 }

 els.btnRetry.addEventListener("click", async () => {
 if (!state.orderId) return;
 els.btnRetry.disabled = true;
 els.btnRetry.textContent = "A reenviar…";
 els.waitingWarning.classList.add("sf-hidden");

 const result = await apiRequest(`/api/public/orders/${state.orderId}/retry-payment`, {
 method: "POST",
 body: JSON.stringify({ buyer_phone: els.buyerPhone.value.trim() }),
 });

 els.btnRetry.disabled = false;
 els.btnRetry.textContent = "Tentar novamente";

 if (!result.success) {
 els.waitingWarning.textContent = result.error || "Não foi possível reenviar o pedido de pagamento.";
 els.waitingWarning.classList.remove("sf-hidden");
 return;
 }

 if (result.data && result.data.payment_warning) {
 els.waitingWarning.textContent = result.data.payment_warning;
 els.waitingWarning.classList.remove("sf-hidden");
 } else {
 els.btnRetry.classList.add("sf-hidden");
 state.pollAttempts = 0;
 startPolling();
 }
 });

 function showSuccess(order) {
 els.successCode.textContent = order.order_code;
 els.btnDownload.href = `/api/public/orders/${state.orderId}/tickets/pdf`;
 showOnly(els.successCard);
 }

 loadEvent();
})();
