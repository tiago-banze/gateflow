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
    "full_name": "Organizador A", "email": "orga@fase2.com", "username": "org.a.fase2",
    "password": "SenhaForte123", "password_confirm": "SenhaForte123",
})
client_b = app.test_client()
client_b.post("/organizador/cadastro", data={
    "full_name": "Organizador B", "email": "orgb@fase2.com", "username": "org.b.fase2",
    "password": "SenhaForte123", "password_confirm": "SenhaForte123",
})

future_date = (datetime.date.today() + datetime.timedelta(days=30)).isoformat() + "T18:00"
past_date = (datetime.date.today() - datetime.timedelta(days=10)).isoformat() + "T18:00"

# --------------------------------------------------------------------
# 1) CRIAÇÃO MÓDULO A
# --------------------------------------------------------------------
r = client_a.post("/api/organizador/events", json={
    "event_module": "A", "name": "Casamento Fase 2", "organizer_display_name": "Buffet Real",
    "location": "Beira", "event_date": future_date,
})
check("Criar evento Módulo A", r.status_code == 201)
event_a_id = r.get_json()["data"]["id"]
check("event_module salvo corretamente", r.get_json()["data"]["event_module"] == "A")

# --------------------------------------------------------------------
# 2) CRIAÇÃO MÓDULO B — validação de setores
# --------------------------------------------------------------------
# 2a) Só o total -> VIP deve virar 0, Normal = total
r = client_a.post("/api/organizador/events", json={
    "event_module": "B", "name": "Festival Só Total", "organizer_display_name": "Prod X",
    "location": "Maputo", "event_date": future_date, "contact_phone": "841234567",
    "capacity_total": 500, "price_normal": 500,
})
check("Módulo B só com total: 201", r.status_code == 201)
data = r.get_json()["data"]
check("Módulo B só com total -> VIP=0", data["capacity_vip"] == 0)
check("Módulo B só com total -> Normal=total", data["capacity_normal"] == 500)

# 2b) VIP + Normal batendo com o total -> aceita
r = client_a.post("/api/organizador/events", json={
    "event_module": "B", "name": "Festival Setores OK", "organizer_display_name": "Prod X",
    "location": "Maputo", "event_date": future_date, "contact_phone": "841234567",
    "capacity_vip": 100, "capacity_normal": 900, "capacity_total": 1000,
    "price_vip": 1000, "price_normal": 500,
})
check("Módulo B com VIP+Normal=Total: 201", r.status_code == 201)

# 2c) VIP + Normal NÃO batendo com o total -> rejeita
r = client_a.post("/api/organizador/events", json={
    "event_module": "B", "name": "Festival Setores Errados", "organizer_display_name": "Prod X",
    "location": "Maputo", "event_date": future_date, "contact_phone": "841234567",
    "capacity_vip": 100, "capacity_normal": 800, "capacity_total": 1000,
})
check("Módulo B com soma ERRADA é rejeitado (400)", r.status_code == 400)
check("Mensagem de erro menciona a soma", "n\u00e3o bate" in r.get_json()["error"])

# 2d) Módulo B sem telefone de contato -> rejeita
r = client_a.post("/api/organizador/events", json={
    "event_module": "B", "name": "Festival Sem Contato", "organizer_display_name": "Prod X",
    "location": "Maputo", "event_date": future_date, "capacity_total": 100,
})
check("Módulo B sem contato é rejeitado (400)", r.status_code == 400)

# 2e) Módulo inválido
r = client_a.post("/api/organizador/events", json={
    "event_module": "Z", "name": "X", "organizer_display_name": "Y", "location": "Z", "event_date": future_date,
})
check("event_module inválido é rejeitado (400)", r.status_code == 400)

# --------------------------------------------------------------------
# 3) ISOLAMENTO NA LISTAGEM (Fase 2, item 3) — vê todos, mas sabe quem é dono
# --------------------------------------------------------------------
r = client_b.get("/api/organizador/events")
events_seen_by_b = r.get_json()["data"]
event_a_in_list = next((e for e in events_seen_by_b if e["id"] == event_a_id), None)
check("Org B VÊ o evento do Org A na listagem (dar volume à plataforma)", event_a_in_list is not None)
check("Org B vê is_own=False no evento do Org A", event_a_in_list["is_own"] is False)
check("Org B NÃO vê total_guests do evento do Org A (privacidade)", event_a_in_list["total_guests"] is None)

r = client_a.get("/api/organizador/events")
events_seen_by_a = r.get_json()["data"]
event_a_from_a = next((e for e in events_seen_by_a if e["id"] == event_a_id), None)
check("Org A vê is_own=True no PRÓPRIO evento", event_a_from_a["is_own"] is True)
check("Org A VÊ total_guests do PRÓPRIO evento", event_a_from_a["total_guests"] is not None)

# --------------------------------------------------------------------
# 4) ISOLAMENTO NO DETALHE E EDIÇÃO
# --------------------------------------------------------------------
r = client_b.get(f"/api/organizador/events/{event_a_id}")
check("Org B NÃO acessa detalhe do evento do Org A (404)", r.status_code == 404)

r = client_b.put(f"/api/organizador/events/{event_a_id}", json={"name": "Hackeado pelo B"})
check("Org B NÃO consegue editar evento do Org A (404)", r.status_code == 404)

r = client_a.get(f"/api/organizador/events/{event_a_id}")
check("Org A acessa o PRÓPRIO evento normalmente (200)", r.status_code == 200)

r = client_a.put(f"/api/organizador/events/{event_a_id}", json={"name": "Casamento Fase 2 Editado"})
check("Org A edita o PRÓPRIO evento normalmente (200)", r.status_code == 200 and r.get_json()["data"]["name"] == "Casamento Fase 2 Editado")

# --------------------------------------------------------------------
# 5) BLOQUEIO DE EDIÇÃO EM EVENTO ENCERRADO
# --------------------------------------------------------------------
r = client_a.post("/api/organizador/events", json={
    "event_module": "A", "name": "Evento Já Encerrado", "organizer_display_name": "X",
    "location": "Y", "event_date": past_date,
})
past_event_id = r.get_json()["data"]["id"]

r = client_a.put(f"/api/organizador/events/{past_event_id}", json={"name": "Tentando Editar Encerrado"})
check("Edição de evento ENCERRADO é bloqueada (403)", r.status_code == 403 and r.get_json().get("event_ended") is True)

# Confirma que o mesmo bloqueio vale para o Admin no evento global
client_admin = app.test_client()
client_admin.post("/login", data={"username": "admin", "password": "TrocarSenha@123"})
r = client_admin.post("/api/events", json={"name": "Evento Admin Encerrado", "event_date": past_date})
admin_past_event_id = r.get_json()["data"]["id"]
r = client_admin.put(f"/api/events/{admin_past_event_id}", json={"name": "Tentando Editar", "event_date": past_date})
check("Edição de evento ENCERRADO também bloqueada para o Admin (403)", r.status_code == 403)

# --------------------------------------------------------------------
# 6) PAYWALL TOGGLE (Super Admin)
# --------------------------------------------------------------------
r = client_admin.put(f"/api/admin/events/{event_a_id}/mark-paid", json={"is_paid": True})
check("Super Admin marca evento como pago", r.status_code == 200 and r.get_json()["data"]["is_paid"] == 1)
r = client_admin.put(f"/api/admin/events/{event_a_id}/mark-paid", json={"is_paid": False})
check("Super Admin desmarca pagamento", r.status_code == 200 and r.get_json()["data"]["is_paid"] == 0)

print("\n=== FASE 2 (EVENTOS) — TODOS OS TESTES PASSARAM ===")
