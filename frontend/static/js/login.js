/**
 * login.js — abas Entrar / Criar conta (acessíveis: role=tab, aria-selected,
 * setas ← → do teclado) e mostrar/ocultar palavra-passe.
 * O servidor decide a aba inicial (data-panel no #login-container).
 */
document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("login-container");
  if (!container) return;

  const tabs = Array.from(container.querySelectorAll("[role='tab']"));
  const panels = { signin: document.getElementById("panel-signin"), signup: document.getElementById("panel-signup") };

  function activate(name, focus) {
    container.dataset.panel = name;
    tabs.forEach((tab) => {
      const on = tab.dataset.panel === name;
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.tabIndex = on ? 0 : -1;
    });
    Object.entries(panels).forEach(([key, el]) => { el.hidden = key !== name; });
    if (focus) {
      const first = panels[name].querySelector("input");
      if (first) first.focus();
    }
    history.replaceState(null, "", name === "signup" ? "/organizador/cadastro" : "/login");
  }

  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => activate(tab.dataset.panel, false));
    tab.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      const next = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
      activate(next.dataset.panel, false);
      next.focus();
    });
  });

  container.querySelectorAll("[data-panel-switch]").forEach((link) => {
    link.addEventListener("click", (e) => { e.preventDefault(); activate(link.dataset.panelSwitch, true); });
  });

  container.querySelectorAll("[data-toggle-password]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = document.getElementById(btn.dataset.togglePassword);
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.setAttribute("aria-pressed", show ? "true" : "false");
      btn.setAttribute("aria-label", show ? "Ocultar senha" : "Mostrar senha");
    });
  });
});
