import sys, datetime
sys.path.insert(0, ".")
import app as flask_app_module
app = flask_app_module.app

def check(label, condition):
    status = "OK" if condition else "FALHOU"
    print(f"[{status}] {label}")
    if not condition:
        raise AssertionError(label)

# --------------------------------------------------------------------
# 1) CADASTRO AUTÔNOMO DE ORGANIZADOR
# --------------------------------------------------------------------
client_org_a = app.test_client()

r = client_org_a.get("/organizador/cadastro")
check("GET /organizador/cadastro (formulário público)", r.status_code == 200)

r = client_org_a.post("/organizador/cadastro", data={
    "full_name": "Organizador Alpha",
    "email": "alpha@eventos.com",
    "username": "org.alpha",
    "phone": "841111111",
    "password": "SenhaForte123",
    "password_confirm": "SenhaForte123",
})
check("POST /organizador/cadastro cria conta e redireciona (302)", r.status_code == 302)
check("Redireciona para o dashboard do organizador", "/organizador" in r.headers.get("Location", ""))

# Confirma que o signup já deixou a sessão logada (não precisa logar de novo)
r = client_org_a.get("/organizador")
check("Já está logado automaticamente após o cadastro (200 direto)", r.status_code == 200)

# --------------------------------------------------------------------
# 2) VALIDAÇÕES DO CADASTRO
# --------------------------------------------------------------------
client_validation = app.test_client()

r = client_validation.post("/organizador/cadastro", data={
    "full_name": "Teste Duplicado", "email": "alpha@eventos.com",  # e-mail já usado acima
    "username": "outro.usuario", "password": "SenhaForte123", "password_confirm": "SenhaForte123",
})
check("E-mail duplicado é rejeitado (fica na tela, 200)", r.status_code == 200 and b"conta com este e-mail" in r.data)

r = client_validation.post("/organizador/cadastro", data={
    "full_name": "Teste Username Dup", "email": "outro@eventos.com",
    "username": "org.alpha",  # username já usado acima
    "password": "SenhaForte123", "password_confirm": "SenhaForte123",
})
check("Username duplicado é rejeitado", r.status_code == 200 and b"uso" in r.data)

r = client_validation.post("/organizador/cadastro", data={
    "full_name": "Teste Senha Curta", "email": "curta@eventos.com",
    "username": "senha.curta", "password": "123", "password_confirm": "123",
})
check("Senha curta é rejeitada", r.status_code == 200 and b"8 caracteres" in r.data)

r = client_validation.post("/organizador/cadastro", data={
    "full_name": "Teste Senhas Diferentes", "email": "diff@eventos.com",
    "username": "senhas.diff", "password": "SenhaForte123", "password_confirm": "OutraSenha456",
})
check("Senhas diferentes são rejeitadas", r.status_code == 200 and b"coincidem" in r.data)

r = client_validation.post("/organizador/cadastro", data={
    "full_name": "Teste Email Invalido", "email": "nao-e-email",
    "username": "email.invalido", "password": "SenhaForte123", "password_confirm": "SenhaForte123",
})
check("E-mail com formato inválido é rejeitado", r.status_code == 200 and b"v\xc3\xa1lido" in r.data)

# --------------------------------------------------------------------
# 3) LOGIN NORMAL DE ORGANIZADOR (sessão separada)
# --------------------------------------------------------------------
# Fase 5: sessão única por utilizador -- a partir deste login, a sessão
# criada no signup (client_org_a) fica automaticamente inválida (é a
# mesma conta org.alpha logando em outro "navegador"). Por isso, todo
# uso de client_org_a a partir daqui usa client_org_a_login.
client_org_a_login = app.test_client()
r = client_org_a_login.post("/login", data={"username": "org.alpha", "password": "SenhaForte123"})
check("Login do organizador cadastrado funciona", r.status_code == 302 and "/organizador" in r.headers.get("Location", ""))

# --------------------------------------------------------------------
# 4) SEGUNDO ORGANIZADOR (para testar isolamento)
# --------------------------------------------------------------------
client_org_b = app.test_client()
client_org_b.post("/organizador/cadastro", data={
    "full_name": "Organizador Beta",
    "email": "beta@eventos.com",
    "username": "org.beta",
    "password": "OutraSenhaForte456",
    "password_confirm": "OutraSenhaForte456",
})

# --------------------------------------------------------------------
# 5) ISOLAMENTO MULTI-TENANT — o teste mais importante da Fase 1
# --------------------------------------------------------------------
# Cria eventos DIRETO no banco, um para cada organizador (simulando o
# que a Fase 2 vai fazer via API de criação de eventos)
import database as db
org_a_user = db.get_user_by_username("org.alpha")
org_b_user = db.get_user_by_username("org.beta")

event_a = db.create_event("Evento do Organizador Alpha", "Local A", "", "2026-12-01T18:00")
db_conn_fix = db.update_event(event_a["id"], event_a["name"], event_a["location"], "", event_a["event_date"])
# update_event não seta organizador_id (não existia antes) -- setamos direto via SQL para o teste
with db.get_connection() as conn:
    conn.execute("UPDATE events SET organizador_id = ? WHERE id = ?", (org_a_user["id"], event_a["id"]))

event_b = db.create_event("Evento do Organizador Beta", "Local B", "", "2026-12-05T18:00")
with db.get_connection() as conn:
    conn.execute("UPDATE events SET organizador_id = ? WHERE id = ?", (org_b_user["id"], event_b["id"]))

# Organizador ALPHA busca eventos -- na Fase 2 (item 3) passou a ver TODOS
# os eventos da plataforma, mas com is_own=True só no que é dele
r = client_org_a_login.get("/api/organizador/events")
data_a = r.get_json()["data"]
event_from_a = next((e for e in data_a if e["name"] == "Evento do Organizador Alpha"), None)
event_from_b_seen_by_a = next((e for e in data_a if e["name"] == "Evento do Organizador Beta"), None)
check("Organizador Alpha vê seu próprio evento", event_from_a is not None)
check("Organizador Alpha vê is_own=True no PRÓPRIO evento", event_from_a["is_own"] is True)
check("Organizador Alpha TAMBÉM vê o evento do Beta na listagem (Fase 2, item 3)", event_from_b_seen_by_a is not None)
check("Organizador Alpha vê is_own=False no evento do Beta", event_from_b_seen_by_a["is_own"] is False)

# Organizador BETA busca eventos -- mesma regra, espelhada
r = client_org_b.get("/api/organizador/events")
data_b = r.get_json()["data"]
event_from_b = next((e for e in data_b if e["name"] == "Evento do Organizador Beta"), None)
check("Organizador Beta vê seu próprio evento", event_from_b is not None)
check("Organizador Beta vê is_own=True no PRÓPRIO evento", event_from_b["is_own"] is True)

# --------------------------------------------------------------------
# 6) PORTEIRO/ADMIN CONTINUAM FUNCIONANDO NORMALMENTE (sem regressão)
# --------------------------------------------------------------------
client_admin = app.test_client()
client_admin.post("/login", data={"username": "admin", "password": "TrocarSenha@123"})
r = client_admin.get("/admin")
check("Admin (Super Admin) continua acessando /admin normalmente", r.status_code == 200)

client_porteiro = app.test_client()
client_porteiro.post("/login", data={"username": "porteiro", "password": "TrocarSenha@123"})
r = client_porteiro.get("/checkin")
check("Porteiro global continua acessando /checkin normalmente", r.status_code == 200)

# --------------------------------------------------------------------
# 7) PORTEIRO/CLIENTE NÃO PODEM ACESSAR O PAINEL DE ORGANIZADOR
# --------------------------------------------------------------------
r = client_porteiro.get("/organizador")
check("Porteiro NÃO acessa /organizador (403)", r.status_code == 403)
r = client_admin.get("/organizador")
check("Admin (Super Admin) NÃO acessa /organizador (403 -- papéis são estritamente separados)", r.status_code == 403)

# --------------------------------------------------------------------
# 8) ORGANIZADOR NÃO PODE ACESSAR PAINÉIS DE ADMIN/PORTEIRO
# --------------------------------------------------------------------
r = client_org_a_login.get("/admin")
check("Organizador NÃO acessa /admin (403)", r.status_code == 403)
r = client_org_a_login.get("/checkin")
check("Organizador NÃO acessa /checkin (403)", r.status_code == 403)

print("\n=== FASE 1 COMPLETA: CADASTRO, LOGIN, ISOLAMENTO MULTI-TENANT E SEPARAÇÃO DE PAPÉIS TUDO OK ===")
