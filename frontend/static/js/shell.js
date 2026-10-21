/**
 * shell.js
 * Comportamento comum das áreas autenticadas:
 *  - botão Voltar que regressa mesmo ao ecrã anterior (com fallback)
 *  - folhas (sheets) deslizantes: abrir/fechar, Esc, clique fora, foco
 *  - botão "voltar ao topo"
 *  - separadores segmentados ligados ao hash do URL (o botão Voltar do
 *    telemóvel e os links partilhados funcionam)
 *  - alternar tema a partir da folha da conta
 */

(function () {
  "use strict";

  document.body.classList.add("has-shell");

  // ----- Voltar -------------------------------------------------------------
  function sameOriginReferrer() {
    try {
      return Boolean(document.referrer) && new URL(document.referrer).origin === window.location.origin;
    } catch (e) {
      return false;
    }
  }

  document.addEventListener("click", (event) => {
    const link = event.target.closest("[data-back]");
    if (!link) return;
    if (sameOriginReferrer() && window.history.length > 1) {
      event.preventDefault();
      window.history.back();
    }
    // Sem histórico útil: segue o href de segurança.
  });

  // Seta "avançar": volta ao ecrã de onde se acabou de recuar.
  function syncForward() {
    const can = window.navigation && typeof window.navigation.canGoForward === "boolean" ? window.navigation.canGoForward : false;
    document.querySelectorAll("[data-forward]").forEach((b) => { b.hidden = !can; });
  }
  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-forward]")) window.history.forward();
  });
  window.addEventListener("pageshow", syncForward);
  syncForward();

  // ----- Sheets -------------------------------------------------------------
  let lastFocused = null;

  function getFocusable(root) {
    return Array.from(
      root.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])')
    ).filter((el) => el.offsetParent !== null);
  }

  window.openSheet = function (id) {
    const sheet = document.getElementById(id);
    if (!sheet) return;
    lastFocused = document.activeElement;
    sheet.classList.remove("hidden");
    document.body.classList.add("sheet-open");
    const first = sheet.querySelector("[data-autofocus]") || getFocusable(sheet).find((el) => !el.matches("[data-sheet-close]"));
    if (first) setTimeout(() => first.focus({ preventScroll: true }), 30);
  };

  window.closeSheet = function (id) {
    const sheet = id ? document.getElementById(id) : document.querySelector("[data-sheet]:not(.hidden)");
    if (!sheet) return;
    sheet.classList.add("hidden");
    if (!document.querySelector("[data-sheet]:not(.hidden)")) document.body.classList.remove("sheet-open");
    if (lastFocused && typeof lastFocused.focus === "function") lastFocused.focus({ preventScroll: true });
  };

  document.addEventListener("click", (event) => {
    const opener = event.target.closest("[data-sheet-open]");
    if (opener) {
      event.preventDefault();
      window.openSheet(opener.getAttribute("data-sheet-open"));
      return;
    }
    if (event.target.closest("[data-sheet-close]")) {
      event.preventDefault();
      window.closeSheet(event.target.closest("[data-sheet]").id);
      return;
    }
    // Clique no fundo escurecido fecha a folha.
    if (event.target.matches("[data-sheet]")) window.closeSheet(event.target.id);
  });

  document.addEventListener("keydown", (event) => {
    const open = document.querySelector("[data-sheet]:not(.hidden)");
    if (!open) return;
    if (event.key === "Escape") {
      window.closeSheet(open.id);
      return;
    }
    if (event.key === "Tab") {
      const items = getFocusable(open);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });

  // ----- Tema (folha da conta) ---------------------------------------------
  document.addEventListener("DOMContentLoaded", () => {
    const row = document.getElementById("account-theme-row");
    const label = document.getElementById("account-theme-label");
    if (!row) return;
    const refresh = () => {
      if (label) label.textContent = document.documentElement.getAttribute("data-theme") === "dark" ? "Modo escuro (tocar para claro)" : "Modo claro (tocar para escuro)";
    };
    refresh();
    row.addEventListener("click", () => {
      if (typeof toggleTheme === "function") toggleTheme();
      refresh();
    });
  });

  // ----- Voltar ao topo -----------------------------------------------------
  document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("to-top");
    if (!btn) return;
    btn.hidden = false;
    let ticking = false;
    const update = () => {
      btn.classList.toggle("is-visible", window.scrollY > 700);
      ticking = false;
    };
    window.addEventListener("scroll", () => {
      if (!ticking) {
        window.requestAnimationFrame(update);
        ticking = true;
      }
    }, { passive: true });
    btn.addEventListener("click", () => {
      const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
    });
  });

  // ----- Separadores segmentados -------------------------------------------
  /**
   * <div class="seg-tabs" role="tablist" data-tabs>
   *   <button class="seg-tab" role="tab" data-tab="resumo">…</button>
   * </div>
   * <section class="tab-panel" data-tab-panel="resumo">…</section>
   */
  window.initTabs = function (defaultTab) {
    const tablist = document.querySelector("[data-tabs]");
    if (!tablist) return;
    const tabs = Array.from(tablist.querySelectorAll("[data-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-tab-panel]"));
    const names = tabs.map((t) => t.getAttribute("data-tab"));

    function select(name, { updateHash = true, scroll = true } = {}) {
      if (!names.includes(name)) name = defaultTab || names[0];
      tabs.forEach((t) => {
        const on = t.getAttribute("data-tab") === name;
        t.setAttribute("aria-selected", on ? "true" : "false");
        t.tabIndex = on ? 0 : -1;
      });
      panels.forEach((p) => { p.hidden = p.getAttribute("data-tab-panel") !== name; });
      if (updateHash && window.location.hash !== `#${name}`) {
        window.history.pushState(null, "", `#${name}`);
      }
      if (scroll) window.scrollTo({ top: 0, behavior: "auto" });
      document.dispatchEvent(new CustomEvent("gf:tabchange", { detail: { tab: name } }));
    }

    tabs.forEach((t) => t.addEventListener("click", () => select(t.getAttribute("data-tab"))));
    tablist.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      const current = tabs.findIndex((t) => t.getAttribute("aria-selected") === "true");
      const next = (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
      tabs[next].focus();
      select(tabs[next].getAttribute("data-tab"));
    });
    window.addEventListener("popstate", () => select(window.location.hash.slice(1), { updateHash: false, scroll: false }));
    document.querySelectorAll("[data-goto-tab]").forEach((el) => {
      el.addEventListener("click", (event) => {
        event.preventDefault();
        select(el.getAttribute("data-goto-tab"));
        const filter = el.getAttribute("data-goto-filter");
        if (filter) document.dispatchEvent(new CustomEvent("gf:setfilter", { detail: { filter } }));
      });
    });

    select(window.location.hash.slice(1) || defaultTab || names[0], { updateHash: false, scroll: false });
    window.gotoTab = (name) => select(name);
  };
})();
