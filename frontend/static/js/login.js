/**
 * login.js
 * Controla a alternância entre os painéis de Login e Cadastro na tela
 * única de acesso (Fase 5 — redesign do login):
 *   - Desktop/tablet: alterna a classe `.right-panel-active` no
 *     `#login-container` (efeito de painel deslizante duplo / overlay).
 *   - Mobile (≤768px): o layout de abas já é resolvido só com CSS
 *     (inputs radio + seletor `:checked ~`), então aqui só garantimos
 *     que os links "Criar Conta" / "Entrar" dentro dos formulários
 *     também marquem o radio correto, para os dois layouts ficarem
 *     sempre sincronizados independente da largura da tela.
 */
document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("login-container");
  const btnSignIn = document.getElementById("signIn");
  const btnSignUp = document.getElementById("signUp");
  const radioSignIn = document.getElementById("login-tab-signin");
  const radioSignUp = document.getElementById("login-tab-signup");

  if (!container) return;

  function activatePanel(panel) {
    const isSignup = panel === "signup";
    container.classList.toggle("right-panel-active", isSignup);
    if (radioSignIn && radioSignUp) {
      (isSignup ? radioSignUp : radioSignIn).checked = true;
    }
  }

  // Botões do overlay (desktop/tablet)
  if (btnSignUp) btnSignUp.addEventListener("click", () => activatePanel("signup"));
  if (btnSignIn) btnSignIn.addEventListener("click", () => activatePanel("signin"));

  // Links "Criar Conta" / "Já tem conta? Entrar" dentro dos formulários
  // (funcionam tanto no layout desktop quanto no mobile)
  document.querySelectorAll("[data-panel-switch]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      activatePanel(link.dataset.panelSwitch);
    });
  });

  // Mantém os dois mecanismos (radio mobile + classe desktop) sincronizados
  // também quando o próprio radio é clicado diretamente (toque na aba).
  if (radioSignIn) radioSignIn.addEventListener("change", () => container.classList.remove("right-panel-active"));
  if (radioSignUp) radioSignUp.addEventListener("change", () => container.classList.add("right-panel-active"));
});
