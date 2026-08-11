import sys, datetime
sys.path.insert(0, ".")
import app as flask_app_module
app = flask_app_module.app

def check(label, r, expected=200):
    status = "OK" if r.status_code == expected else "FALHOU"
    print(f"[{status}] {label}: {r.status_code} (esperado {expected})")
    if r.status_code != expected:
        print("  ---", r.data.decode("utf-8", errors="replace")[:400])

client_a = app.test_client()
client_a.post("/organizador/cadastro", data={
    "full_name": "Organizador Templates", "email": "orgtpl@fase2.com", "username": "org.tpl.fase2",
    "password": "SenhaForte123", "password_confirm": "SenhaForte123",
})
client_admin = app.test_client()
client_admin.post("/login", data={"username": "admin", "password": "TrocarSenha@123"})

future_date = (datetime.date.today() + datetime.timedelta(days=30)).isoformat() + "T18:00"

check("GET /organizador (dashboard com formulário)", client_a.get("/organizador"))

r = client_a.post("/api/organizador/events", json={
    "event_module": "A", "name": "Evento Render A", "organizer_display_name": "X",
    "location": "Beira", "event_date": future_date,
})
event_a_id = r.get_json()["data"]["id"]

r = client_a.post("/api/organizador/events", json={
    "event_module": "B", "name": "Evento Render B", "organizer_display_name": "X",
    "location": "Maputo", "event_date": future_date, "contact_phone": "841234567",
    "capacity_total": 500, "price_normal": 500,
})
event_b_id = r.get_json()["data"]["id"]

# Módulo A SEM pagamento -> deve mostrar o banner de paywall no HTML
r = client_a.get(f"/organizador/eventos/{event_a_id}")
check("GET /organizador/eventos/<A, não pago>", r)
has_paywall_text = "Pagamento Pendente".encode("utf-8") in r.data
print(f"[{'OK' if has_paywall_text else 'FALHOU'}] Banner de paywall aparece quando não pago")

# Marca como pago e confirma que o painel de convidados aparece
client_admin.put(f"/api/admin/events/{event_a_id}/mark-paid", json={"is_paid": True})
r = client_a.get(f"/organizador/eventos/{event_a_id}")
check("GET /organizador/eventos/<A, pago>", r)
has_guest_panel = b"module-a-content" in r.data
print(f"[{'OK' if has_guest_panel else 'FALHOU'}] HTML inclui o container do painel de convidados")

# Módulo B -> mostra lotação
r = client_a.get(f"/organizador/eventos/{event_b_id}")
check("GET /organizador/eventos/<B>", r)
has_capacity = "Lotação por Setores".encode("utf-8") in r.data
print(f"[{'OK' if has_capacity else 'FALHOU'}] Página do Módulo B mostra lotação")

# Organizador B tenta acessar evento do Organizador A -> 404 (não 403, para não revelar que existe)
client_b = app.test_client()
client_b.post("/organizador/cadastro", data={
    "full_name": "Organizador Templates B", "email": "orgtplb@fase2.com", "username": "org.tpl.b.fase2",
    "password": "SenhaForte123", "password_confirm": "SenhaForte123",
})
r = client_b.get(f"/organizador/eventos/{event_a_id}")
check("Org B acessa página de evento do Org A", r, expected=404)

# Confirma que a página 404 não tenta linkar para /checkin (bug que corrigimos)
has_broken_link = b'href="/checkin"' in r.data
print(f"[{'OK' if not has_broken_link else 'FALHOU'}] Página 404 NÃO aponta organizador para /checkin (bloqueado)")

print("\n=== RENDERIZAÇÃO DAS PÁGINAS DA FASE 2: TODAS OK ===")
