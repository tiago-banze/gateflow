import sys, datetime
sys.path.insert(0, ".")
import app as flask_app_module
app = flask_app_module.app
client = app.test_client()

def check(label, condition):
    status = "OK" if condition else "FALHOU"
    print(f"[{status}] {label}")
    if not condition:
        raise AssertionError(label)

client.post("/login", data={"username": "admin", "password": "TrocarSenha@123"})

# --- Criar evento FUTURO para testes de CRUD normais ---
future_date = (datetime.date.today() + datetime.timedelta(days=30)).isoformat() + "T18:00"
r = client.post("/api/events", json={"name": "Evento Futuro CRUD", "event_date": future_date})
event_id = r.get_json()["data"]["id"]
check("Criar evento", r.status_code == 201)

# --- PUT editar evento ---
r = client.put(f"/api/events/{event_id}", json={
    "name": "Evento Futuro CRUD (Editado)", "location": "Novo Local",
    "description": "desc", "event_date": future_date
})
check("Editar evento (PUT)", r.status_code == 200 and r.get_json()["data"]["name"] == "Evento Futuro CRUD (Editado)")

# --- Cadastrar convidado manual ---
r = client.post(f"/api/events/{event_id}/guests", json={"full_name": "Convidado Original", "table_number": "Mesa 01"})
guest_id = r.get_json()["data"]["id"]
check("Criar convidado", r.status_code == 201)

# --- PUT editar convidado ---
r = client.put(f"/api/events/{event_id}/guests/{guest_id}", json={
    "full_name": "Convidado Editado", "email": "editado@email.com",
    "phone": "840000000", "role": "VIP", "table_number": "Mesa 02"
})
check("Editar convidado (PUT)", r.status_code == 200 and r.get_json()["data"]["full_name"] == "Convidado Editado")
check("Mesa atualizada na edição", r.get_json()["data"]["table_number"] == "Mesa 02")

# --- Criar 2º convidado para testar duplicidade na edição ---
r = client.post(f"/api/events/{event_id}/guests", json={"full_name": "Segundo Convidado", "email": "segundo@email.com"})
guest_id_2 = r.get_json()["data"]["id"]
r = client.put(f"/api/events/{event_id}/guests/{guest_id_2}", json={"full_name": "Convidado Editado", "email": "editado@email.com"})
check("Editar para duplicata retorna 409", r.status_code == 409)

# --- DELETE convidado ---
r = client.delete(f"/api/events/{event_id}/guests/{guest_id_2}")
check("Excluir convidado", r.status_code == 200)
r = client.get(f"/api/events/{event_id}/guests")
names = [g["full_name"] for g in r.get_json()["data"]]
check("Convidado excluído não aparece mais", "Segundo Convidado" not in names)

# --- Importar mais convidados para o PDF de contingência ---
import openpyxl
wb = openpyxl.Workbook(); ws = wb.active
ws.append(["Nome Completo", "Email", "Telefone", "Cargo/Tipo", "Mesa"])
ws.append(["Zeca Ultimo", "z@e.com", "841111111", "Convidado", "Mesa 09"])
ws.append(["Ana Primeiro", "a@e.com", "842222222", "Convidado", "Mesa 08"])
wb.save("/tmp/teste_crud.xlsx")
with open("/tmp/teste_crud.xlsx", "rb") as f:
    client.post(f"/api/events/{event_id}/import", data={"file": (f, "x.xlsx")}, content_type="multipart/form-data")

# --- PDF de contingência ---
r = client.get(f"/api/events/{event_id}/guests/contingency-pdf")
check("PDF de contingência gera 200", r.status_code == 200)
check("PDF de contingência tem Content-Disposition", "attachment" in r.headers.get("Content-Disposition", ""))

# --- Relatório de presença CSV ---
r = client.get(f"/api/events/{event_id}/guests/attendance-report")
check("Relatório CSV gera 200", r.status_code == 200)
check("Relatório CSV é text/csv", "csv" in r.headers.get("Content-Type", ""))

# --- Checkin normal em evento FUTURO deve funcionar ---
r = client.post(f"/api/checkin/manual/{guest_id}", json={})
check("Check-in em evento futuro funciona", r.status_code == 200)

# --- Criar evento PASSADO e testar bloqueio de check-in ---
past_date = (datetime.date.today() - datetime.timedelta(days=10)).isoformat() + "T18:00"
r = client.post("/api/events", json={"name": "Evento Passado", "event_date": past_date})
past_event_id = r.get_json()["data"]["id"]
r = client.post(f"/api/events/{past_event_id}/guests", json={"full_name": "Convidado do Passado"})
past_guest_id = r.get_json()["data"]["id"]

r = client.post(f"/api/checkin/manual/{past_guest_id}", json={})
check("Check-in BLOQUEADO em evento passado", r.status_code == 403 and r.get_json().get("event_ended") is True)

r = client.post("/api/checkin/qr", json={"qr_value": f"CHECKIN:{past_guest_id}", "event_id": past_event_id})
check("Check-in via QR BLOQUEADO em evento passado", r.status_code == 403)

# --- Kill switch de sessões ---
r = client.post("/api/admin/security/invalidate-all-sessions")
check("Kill switch retorna sucesso", r.status_code == 200 and r.get_json()["success"] is True)

# A MESMA sessão (mesmo cookie) que chamou o kill switch deve estar invalidada agora
r = client.get("/api/events")
check("Sessão do próprio admin foi invalidada pelo kill switch", r.status_code == 401)

print("\n=== TODOS OS TESTES DE CRUD, PDFs, BLOQUEIO DE EVENTO PASSADO E KILL SWITCH PASSARAM ===")
