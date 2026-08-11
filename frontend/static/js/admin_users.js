/**
 * admin_users.js
 * Gerenciamento de usuários: qualquer admin pode criar novos perfis
 * (admin ou porteiro) com uma senha provisória. Senhas nunca circulam
 * de volta do servidor - apenas no momento da criação, para o admin
 * poder repassá-la ao novo usuário.
 */

document.addEventListener("DOMContentLoaded", () => {
 loadUsers();
 document.getElementById("form-new-user").addEventListener("submit", handleCreateUser);
 document.getElementById("btn-invalidate-sessions").addEventListener("click", handleInvalidateAllSessions);
});

async function handleInvalidateAllSessions() {
 if (!confirm("Isso vai desconectar TODOS os aparelhos logados agora, incluindo o seu. Você precisará fazer login de novo. Continuar?")) {
 return;
 }

 const btn = document.getElementById("btn-invalidate-sessions");
 btn.disabled = true;
 btn.innerHTML = '<span class="spinner"></span> Encerrando sessões...';

 const result = await apiRequest("/api/admin/security/invalidate-all-sessions", { method: "POST" });

 if (!result.success) {
 btn.disabled = false;
 btn.textContent = " Encerrar Todas as Sessões";
 showToast(result.error || "Erro ao encerrar sessões.", "error");
 return;
 }

 showToast("Todas as sessões foram encerradas. Redirecionando para o login...", "success", 2500);
 setTimeout(() => { window.location.href = "/login"; }, 1500);
}

async function loadUsers() {
 const listEl = document.getElementById("users-list");
 const result = await apiRequest("/api/admin/users");

 if (!result.success) {
 listEl.innerHTML = `<div class="empty-state">Erro ao carregar usuários.</div>`;
 return;
 }

 const users = result.data || [];
 if (users.length === 0) {
 listEl.innerHTML = `<div class="empty-state">Nenhum usuário cadastrado.</div>`;
 return;
 }

 listEl.innerHTML = `
 <div style="overflow-x:auto;">
 <table style="width:100%; border-collapse:collapse;">
 <thead>
 <tr style="text-align:left; border-bottom:2px solid #EEF1F4;">
 <th style="padding:10px;">Nome</th>
 <th style="padding:10px;">Usuário</th>
 <th style="padding:10px;">Tipo</th>
 <th style="padding:10px;">Criado em</th>
 </tr>
 </thead>
 <tbody>
 ${users.map((u) => `
 <tr style="border-bottom:1px solid #F1F3F5;">
 <td style="padding:10px; font-weight:600;">${escapeHtml(u.full_name || "-")}</td>
 <td style="padding:10px;">${escapeHtml(u.username)}</td>
 <td style="padding:10px;">
 <span class="badge" style="${u.role === 'admin' ? 'background:#E9EEF5; color:var(--color-primary);' : 'background:#F1F1F1; color:#555;'}">
 ${u.role === 'admin' ? 'Administrador' : 'Porteiro'}
 </span>
 </td>
 <td style="padding:10px; color:var(--color-text-muted); font-size:0.85rem;">${formatDateTime(u.created_at)}</td>
 </tr>
 `).join("")}
 </tbody>
 </table>
 </div>
 `;
}

async function handleCreateUser(e) {
 e.preventDefault();
 const btn = document.getElementById("btn-save-user");
 const full_name = document.getElementById("user-fullname").value.trim();
 const username = document.getElementById("user-username").value.trim();
 const role = document.getElementById("user-role").value;
 const password = document.getElementById("user-password").value;

 if (!username || !role || !password) {
 showToast("Preencha todos os campos obrigatórios.", "error");
 return;
 }
 if (password.length < 8) {
 showToast("A senha provisória deve ter pelo menos 8 caracteres.", "error");
 return;
 }

 btn.disabled = true;
 btn.innerHTML = '<span class="spinner"></span> Criando...';

 const result = await apiRequest("/api/admin/users", {
 method: "POST",
 body: JSON.stringify({ full_name, username, role, password }),
 });

 btn.disabled = false;
 btn.textContent = "Criar Usuário";

 if (!result.success) {
 showToast(result.error || "Erro ao criar usuário.", "error");
 return;
 }

 showToast(`Usuário "${username}" criado com sucesso!`, "success");
 document.getElementById("form-new-user").reset();
 loadUsers();
}
