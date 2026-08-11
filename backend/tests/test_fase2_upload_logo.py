import sys, datetime, io
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
    "full_name": "Organizador Logo", "email": "orglogo@fase2.com", "username": "org.logo.fase2",
    "password": "SenhaForte123", "password_confirm": "SenhaForte123",
})
client_b = app.test_client()
client_b.post("/organizador/cadastro", data={
    "full_name": "Organizador Logo B", "email": "orglogob@fase2.com", "username": "org.logo.b.fase2",
    "password": "SenhaForte123", "password_confirm": "SenhaForte123",
})

future_date = (datetime.date.today() + datetime.timedelta(days=30)).isoformat() + "T18:00"

r = client_a.post("/api/organizador/events", json={
    "event_module": "B", "name": "Show Com Logo", "organizer_display_name": "X",
    "location": "Maputo", "event_date": future_date, "contact_phone": "841111111",
    "capacity_total": 300, "price_normal": 300,
})
event_b_id = r.get_json()["data"]["id"]

r = client_a.post("/api/organizador/events", json={
    "event_module": "A", "name": "Evento Modulo A (sem logo)", "organizer_display_name": "X",
    "location": "Beira", "event_date": future_date,
})
event_a_id = r.get_json()["data"]["id"]

# --------------------------------------------------------------------
# 1) IMAGEM VÁLIDA -> aceita
# --------------------------------------------------------------------
from PIL import Image
img_buffer = io.BytesIO()
Image.new("RGB", (200, 100), color="blue").save(img_buffer, format="PNG")
img_buffer.seek(0)

r = client_a.post(f"/api/organizador/events/{event_b_id}/logo",
                   data={"logo": (img_buffer, "logo_evento.png")}, content_type="multipart/form-data")
check("Upload de logo PNG válido é aceito (201)", r.status_code == 201)

# Confirma que dá para buscar o logo de volta
r = client_a.get(f"/api/events/{event_b_id}/logo")
check("Logo pode ser recuperado depois do upload (200)", r.status_code == 200)

# --------------------------------------------------------------------
# 2) ARQUIVO FALSO DISFARÇADO DE IMAGEM -> rejeitado (validação de conteúdo real)
# --------------------------------------------------------------------
fake_image = io.BytesIO(b"isto nao e uma imagem de verdade, e so texto")
r = client_a.post(f"/api/organizador/events/{event_b_id}/logo",
                   data={"logo": (fake_image, "malicioso.png")}, content_type="multipart/form-data")
check("Arquivo FALSO disfarçado de .png é REJEITADO (400)", r.status_code == 400)

# --------------------------------------------------------------------
# 3) EXTENSÃO NÃO PERMITIDA -> rejeitado
# --------------------------------------------------------------------
exe_file = io.BytesIO(b"conteudo qualquer")
r = client_a.post(f"/api/organizador/events/{event_b_id}/logo",
                   data={"logo": (exe_file, "virus.exe")}, content_type="multipart/form-data")
check("Extensão .exe é rejeitada (400)", r.status_code == 400)

# --------------------------------------------------------------------
# 4) TAMANHO EXCEDIDO -> rejeitado
# --------------------------------------------------------------------
big_buffer = io.BytesIO(b"0" * (3 * 1024 * 1024))  # 3MB > limite de 2MB
r = client_a.post(f"/api/organizador/events/{event_b_id}/logo",
                   data={"logo": (big_buffer, "grande.png")}, content_type="multipart/form-data")
check("Imagem maior que 2MB é rejeitada (400)", r.status_code == 400)

# --------------------------------------------------------------------
# 5) LOGO SÓ PARA MÓDULO B
# --------------------------------------------------------------------
img_buffer2 = io.BytesIO()
Image.new("RGB", (100, 100), color="red").save(img_buffer2, format="PNG")
img_buffer2.seek(0)
r = client_a.post(f"/api/organizador/events/{event_a_id}/logo",
                   data={"logo": (img_buffer2, "logo.png")}, content_type="multipart/form-data")
check("Upload de logo em evento Módulo A é rejeitado (400)", r.status_code == 400)

# --------------------------------------------------------------------
# 6) ISOLAMENTO: Org B não sobe logo no evento do Org A
# --------------------------------------------------------------------
img_buffer3 = io.BytesIO()
Image.new("RGB", (100, 100), color="green").save(img_buffer3, format="PNG")
img_buffer3.seek(0)
r = client_b.post(f"/api/organizador/events/{event_b_id}/logo",
                   data={"logo": (img_buffer3, "logo.png")}, content_type="multipart/form-data")
check("Org B NÃO consegue subir logo no evento do Org A (404)", r.status_code == 404)

print("\n=== FASE 2 (UPLOAD DE LOGO) — TODOS OS TESTES PASSARAM ===")
