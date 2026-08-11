import sys, datetime
sys.path.insert(0, ".")
import app as flask_app_module
app = flask_app_module.app

def check(label, condition):
    status = "OK" if condition else "FALHOU"
    print(f"[{status}] {label}")
    if not condition:
        raise AssertionError(label)

client_a = app.test_client()
client_a.post("/organizador/cadastro", data={
    "full_name": "Organizador Guests", "email": "orgguests@fase2.com", "username": "org.guests.fase2",
    "password": "SenhaForte123", "password_confirm": "SenhaForte123",
})
client_admin = app.test_client()
client_admin.post("/login", data={"username": "admin", "password": "TrocarSenha@123"})

future_date = (datetime.date.today() + datetime.timedelta(days=30)).isoformat() + "T18:00"

r = client_a.post("/api/organizador/events", json={
    "event_module": "A", "name": "Evento Paywall Teste", "organizer_display_name": "X",
    "location": "Beira", "event_date": future_date,
})
event_id = r.get_json()["data"]["id"]

# --------------------------------------------------------------------
# 1) PAYWALL: sem pagamento, tudo bloqueado
# --------------------------------------------------------------------
r = client_a.get(f"/api/organizador/events/{event_id}/guests")
check("Listar convidados SEM pagamento é bloqueado (402)", r.status_code == 402 and r.get_json().get("payment_required") is True)

r = client_a.post(f"/api/organizador/events/{event_id}/guests", json={"full_name": "Teste"})
check("Cadastro manual SEM pagamento é bloqueado (402)", r.status_code == 402)

# --------------------------------------------------------------------
# 2) BAIXAR O TEMPLATE (não deve depender de pagamento)
# --------------------------------------------------------------------
r = client_a.get("/api/events/template-xlsx")
check("Download do template funciona mesmo SEM pagamento", r.status_code == 200)
check("Template é um xlsx válido (Content-Type correto)", "spreadsheet" in r.headers.get("Content-Type", ""))

with open("/tmp/template_baixado.xlsx", "wb") as f:
    f.write(r.data)

# --------------------------------------------------------------------
# 3) SUPER ADMIN LIBERA O PAGAMENTO
# --------------------------------------------------------------------
r = client_admin.put(f"/api/admin/events/{event_id}/mark-paid", json={"is_paid": True})
check("Super Admin marca evento como pago", r.status_code == 200)

# --------------------------------------------------------------------
# 4) AGORA A GESTÃO DE CONVIDADOS FUNCIONA
# --------------------------------------------------------------------
r = client_a.get(f"/api/organizador/events/{event_id}/guests")
check("Listar convidados COM pagamento funciona (200)", r.status_code == 200)

r = client_a.post(f"/api/organizador/events/{event_id}/guests", json={"full_name": "Convidado Pago", "table_number": "Mesa 01"})
check("Cadastro manual COM pagamento funciona (201)", r.status_code == 201)

# --------------------------------------------------------------------
# 5) RE-IMPORTA O TEMPLATE BAIXADO (prova que ele realmente é válido)
# --------------------------------------------------------------------
with open("/tmp/template_baixado.xlsx", "rb") as f:
    r = client_a.post(f"/api/organizador/events/{event_id}/import",
                       data={"file": (f, "template_baixado.xlsx")}, content_type="multipart/form-data")
check("Reimportar o PRÓPRIO template baixado funciona sem erro (201)", r.status_code == 201)
check("O convidado de exemplo do template foi importado", r.get_json()["data"]["imported_count"] == 1)

# --------------------------------------------------------------------
# 6) ISOLAMENTO: Org B não gerencia convidados do evento do Org A, mesmo pago
# --------------------------------------------------------------------
client_b = app.test_client()
client_b.post("/organizador/cadastro", data={
    "full_name": "Organizador B Guests", "email": "orgbguests@fase2.com", "username": "org.b.guests.fase2",
    "password": "SenhaForte123", "password_confirm": "SenhaForte123",
})
r = client_b.get(f"/api/organizador/events/{event_id}/guests")
check("Org B NÃO acessa convidados do evento do Org A (404)", r.status_code == 404)

# --------------------------------------------------------------------
# 7) MÓDULO B não tem gestão de lista de convidados
# --------------------------------------------------------------------
r = client_a.post("/api/organizador/events", json={
    "event_module": "B", "name": "Show Teste", "organizer_display_name": "X",
    "location": "Maputo", "event_date": future_date, "contact_phone": "841111111",
    "capacity_total": 200, "price_normal": 500,
})
event_b_id = r.get_json()["data"]["id"]
client_admin.put(f"/api/admin/events/{event_b_id}/mark-paid", json={"is_paid": True})
r = client_a.get(f"/api/organizador/events/{event_b_id}/guests")
check("Evento Módulo B não permite gestão de lista de convidados (400)", r.status_code == 400)

print("\n=== FASE 2 (CONVIDADOS + PAYWALL + TEMPLATE) — TODOS OS TESTES PASSARAM ===")
