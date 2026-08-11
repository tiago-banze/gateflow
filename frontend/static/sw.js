/**
 * sw.js — Service Worker do check-in offline-first.
 *
 * Objetivo único: garantir que a TELA de check-in (HTML + CSS + JS) e o
 * leitor de QR continuam a abrir mesmo sem internet no local do evento.
 * A validação dos convidados em si (dados) fica a cargo do IndexedDB,
 * gerido por offline_checkin.js — este ficheiro só cuida dos "ficheiros
 * estáticos" (o "app shell").
 *
 * Estratégia:
 *   - install: pré-carrega o app shell no cache.
 *   - fetch (GET, mesmo domínio): cache-first para assets estáticos
 *     (css/js/fontes locais); network-first com fallback para cache no
 *     HTML da própria página de check-in (para pegar atualizações
 *     quando online, sem nunca ficar "presa" sem internet).
 *   - fetch para chamadas /api/... : NUNCA intercetado aqui -- passa
 *     direto para a rede. Ficar offline numa chamada de API é tratado
 *     pelo próprio checkin.js + offline_checkin.js (fila de sincronização),
 *     não pelo Service Worker.
 */

const CACHE_NAME = "gateflow-checkin-shell-v1";

const APP_SHELL_URLS = [
  "/static/css/style.css",
  "/static/css/footer.css",
  "/static/js/common.js",
  "/static/js/checkin.js",
  "/static/js/offline_checkin.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL_URLS)).catch(() => {
      // Falha ao pré-cachear (ex: primeira instalação já offline) não deve
      // impedir o Service Worker de instalar -- o cache vai sendo
      // preenchido aos poucos pelo handler de fetch abaixo.
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

function isApiRequest(url) {
  return url.pathname.startsWith("/api/") || url.pathname.startsWith("/webhooks/");
}

function isCheckinPage(url) {
  return url.pathname.startsWith("/checkin/");
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Só cuidamos de GET no mesmo domínio; POST/PUT e chamadas de API vão
  // sempre direto para a rede (nunca servidas do cache).
  if (event.request.method !== "GET" || url.origin !== self.location.origin || isApiRequest(url)) {
    return;
  }

  if (isCheckinPage(url)) {
    // Network-first: tenta a rede (pega o HTML mais recente, com os
    // dados do evento já embutidos), e só usa o cache se estiver offline.
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Assets estáticos (css/js): cache-first, com atualização em segundo
  // plano -- resposta instantânea mesmo offline, e o cache fica sempre
  // atualizado para a próxima visita.
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const networkFetch = fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => cached);
      return cached || networkFetch;
    })
  );
});
