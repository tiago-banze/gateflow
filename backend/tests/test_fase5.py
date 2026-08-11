"""
test_fase5.py
Suite de testes da Fase 5 - Design System, Regras de Negocio Criticas e
os 5 Pilares (Financeiro, Portaria em Tempo Real, Cortesias/VIP,
Notificacoes, Hardening).

Cobre os tres pontos explicitamente exigidos no briefing:
  1) Sessao unica por utilizador (prevencao de acesso simultaneo)
  2) Segregacao estrita entre Modelo A e Modelo B (UI/API)
  3) Reconciliacao financeira (Pilar 1)

E tambem cobre, de forma mais leve: regras obrigatorias de lotacao/preco
na criacao de evento, cota de cortesias (Pilar 3), e o endpoint de
estatisticas de portaria em tempo real (Pilar 2).

Rodar:  python3 tests/test_fase5.py
"""

import sys
import datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, ".")
import config
config.ensure_directories()
import database as db
import mpesa_service
import app as flask_app_module
flask_app = flask_app_module.app
flask_app.testing = True


def check(label, condition):
    status = "OK" if condition else "FALHOU"
    print(f"[{status}] {label}")
    if not condition:
        raise AssertionError(label)


def section(title):
    print(f"\n--- {title} ---")


def mock_mpesa_post(response_code="INS-0"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "output_ResponseCode": response_code, "output_ResponseDesc": "Sucesso",
        "output_ConversationID": "conv-f5", "output_TransactionID": "txn-f5",
    }
    return resp


def mock_mpesa_get(transaction_status="Completed"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "output_ResponseCode": "INS-0", "output_ResponseDesc": "Sucesso",
        "output_ConversationID": "conv-f5", "output_TransactionID": "txn-f5",
        "output_ResponseTransactionStatus": transaction_status,
    }
    return resp


db.init_db()
future_date = (datetime.date.today() + datetime.timedelta(days=30)).isoformat() + "T18:00"

client_admin = flask_app.test_client()
r = client_admin.post("/login", data={"username": "admin", "password": "TrocarSenha@123"})
check("Login do admin padrao", r.status_code == 302)


# ============================================================================
# 1) SESSAO UNICA POR UTILIZADOR
# ============================================================================
section("1. Sessao unica por utilizador (bloqueio de acesso simultaneo)")

r = flask_app.test_client().post("/organizador/cadastro", data={
    "full_name": "Organizador Fase 5", "email": "org.fase5.sessao@teste.com",
    "username": "org.fase5.sessao", "phone": "841234567",
    "password": "Senha@123Forte", "password_confirm": "Senha@123Forte",
})
check("Signup do organizador de teste (form) responde 302", r.status_code == 302)

client_a = flask_app.test_client()
client_b = flask_app.test_client()

r = client_a.post("/login", data={"username": "org.fase5.sessao", "password": "Senha@123Forte"})
check("Cliente A (primeiro navegador) faz login", r.status_code == 302)

r = client_a.get("/organizador")
check("Cliente A tem acesso valido ao painel logo apos o login", r.status_code == 200)

r = client_b.post("/login", data={"username": "org.fase5.sessao", "password": "Senha@123Forte"})
check("Cliente B (segundo navegador, mesma conta) faz login", r.status_code == 302)

r = client_a.get("/organizador")
check("Cliente A perde o acesso IMEDIATAMENTE apos o login do Cliente B (sessao invalidada)", r.status_code == 302)

r = client_b.get("/organizador")
check("Cliente B mantem acesso normalmente (e a sessao ativa)", r.status_code == 200)

r = client_b.get("/logout")
r = client_b.get("/organizador")
check("Apos logout explicito, o acesso tambem e negado", r.status_code == 302)


# ============================================================================
# 2) SEGREGACAO ESTRITA ENTRE MODELO A E MODELO B
# ============================================================================
section("2. Segregacao estrita entre Modelo A e Modelo B (UI e API)")

client_org = flask_app.test_client()
r = client_org.post("/login", data={"username": "org.fase5.sessao", "password": "Senha@123Forte"})

r = client_org.post("/api/organizador/events", json={
    "event_module": "B", "name": "Show Fase 5", "organizer_display_name": "Produtora F5",
    "location": "Beira", "event_date": future_date, "contact_phone": "841234567",
    "capacity_vip": 10, "capacity_normal": 40, "capacity_total": 50,
    "price_vip": 1000, "price_normal": 500,
})
check("Criacao do evento Modulo B (com precos obrigatorios) responde 201", r.status_code == 201)
event_b_id = r.get_json()["data"]["id"]
event_b_slug = r.get_json()["data"]["slug"]
client_admin.put(f"/api/admin/events/{event_b_id}/mark-paid", json={"is_paid": True})

r = client_org.post("/api/organizador/events", json={
    "event_module": "A", "name": "Festa Fechada Fase 5", "organizer_display_name": "Produtora F5",
    "location": "Beira", "event_date": future_date, "contact_phone": "841234567",
})
check("Criacao do evento Modulo A responde 201", r.status_code == 201)
event_a_id = r.get_json()["data"]["id"]
client_admin.put(f"/api/admin/events/{event_a_id}/mark-paid", json={"is_paid": True})

# --- rotas de convidados do ADMIN aplicadas a um evento MODELO B ---
r = client_admin.post(f"/api/events/{event_b_id}/guests", json={
    "full_name": "Convidado Indevido", "email": "x@x.com", "phone": "841111111",
    "role": "Convidado", "table_number": "",
})
check("Admin NAO consegue cadastrar convidado manual num evento Modelo B (403)", r.status_code == 403)

r = client_admin.get(f"/admin/eventos/{event_b_id}")
check("Pagina de admin do evento Modelo B carrega normalmente (200)", r.status_code == 200)
check("Pagina de admin do evento Modelo B NAO contem o formulario de convidados", b'id="form-new-guest"' not in r.data)
check("Pagina de admin do evento Modelo B mostra o resumo do storefront", b"Bilheteira Online" in r.data)

r = client_admin.get(f"/admin/eventos/{event_a_id}")
check("Pagina de admin do evento Modelo A CONTINUA mostrando o formulario de convidados", b'id="form-new-guest"' in r.data)

# guest_id qualquer (nem precisa existir - o guard de modulo barra antes da busca do convidado)
r = client_admin.put(f"/api/events/{event_b_id}/guests/qualquer-id", json={"full_name": "X"})
check("Admin NAO consegue editar convidado num evento Modelo B (403)", r.status_code == 403)

r = client_admin.delete(f"/api/events/{event_b_id}/guests/qualquer-id")
check("Admin NAO consegue excluir convidado num evento Modelo B (403)", r.status_code == 403)

# --- confere que o Modelo A continua funcionando normalmente para essas mesmas rotas ---
r = client_admin.post(f"/api/events/{event_a_id}/guests", json={
    "full_name": "Convidado Valido A", "email": "valido@x.com", "phone": "841111112",
    "role": "Convidado", "table_number": "",
})
check("Admin CONSEGUE cadastrar convidado manual num evento Modelo A (201)", r.status_code == 201)


# ============================================================================
# 3) REGRAS OBRIGATORIAS DE LOTACAO E PRECO NA CRIACAO DE EVENTO
# ============================================================================
section("3. Lotacao e preco obrigatorios por setor antes de publicar (Modelo B)")

r = client_org.post("/api/organizador/events", json={
    "event_module": "B", "name": "Evento Sem Lotacao", "organizer_display_name": "X",
    "location": "Beira", "event_date": future_date, "contact_phone": "841234567",
    "price_normal": 500,
})
check("Evento Modelo B SEM nenhuma lotacao definida e rejeitado (400)", r.status_code == 400)

r = client_org.post("/api/organizador/events", json={
    "event_module": "B", "name": "Evento Sem Preco VIP", "organizer_display_name": "X",
    "location": "Beira", "event_date": future_date, "contact_phone": "841234567",
    "capacity_vip": 20, "capacity_normal": 0, "capacity_total": 20,
})
check("Evento Modelo B com setor VIP mas SEM preco VIP e rejeitado (400)", r.status_code == 400)

r = client_org.post("/api/organizador/events", json={
    "event_module": "B", "name": "Evento Completo OK", "organizer_display_name": "X",
    "location": "Beira", "event_date": future_date, "contact_phone": "841234567",
    "capacity_vip": 5, "capacity_normal": 5, "capacity_total": 10,
    "price_vip": 900, "price_normal": 450,
})
check("Evento Modelo B com lotacao E precos completos e aceito (201)", r.status_code == 201)


# ============================================================================
# 4) DASHBOARD FINANCEIRO E RECONCILIACAO DE VENDAS (PILAR 1)
# ============================================================================
section("4. Dashboard financeiro e reconciliacao de vendas")

with patch("mpesa_service.requests.post") as mock_post:
    mock_post.return_value = mock_mpesa_post()
    r = client_org.post(f"/api/public/events/{event_b_slug}/checkout", json={
        "quantity_vip": 2, "quantity_normal": 3,
        "buyer_name": "Comprador Financeiro", "buyer_phone": "84 900 1122",
    })
    order_id = r.get_json()["data"]["order"]["id"]

with patch("mpesa_service.requests.get") as mock_get:
    mock_get.return_value = mock_mpesa_get(transaction_status="Completed")
    client_org.get(f"/api/public/orders/{order_id}/status")

r = client_org.get(f"/api/organizador/events/{event_b_id}/financials")
check("Endpoint financeiro do organizador responde 200", r.status_code == 200)
data = r.get_json()["data"]
summary = data["summary"]

expected_subtotal = 2 * 1000 + 3 * 500  # 3500
expected_fee = round(expected_subtotal * 0.05, 2)  # 175
expected_gross = round(expected_subtotal + expected_fee, 2)  # 3675

check("Receita Bruta reconciliada corretamente (subtotal + taxa)", summary["gross_revenue"] == expected_gross)
check("Taxa GateFlow de 5% reconciliada corretamente", summary["platform_fee"] == expected_fee)
check("Valor Liquido do Organizador reconciliado corretamente (= subtotal)", summary["net_organizer"] == expected_subtotal)
check("Contagem de bilhetes vendidos bate (2 VIP + 3 Normal = 5)", summary["tickets_sold"] == 5)
check("Historico de transacoes contem a transacao M-Pesa recem-paga", len(data["transactions"]) == 1)
check("Transacao registrada tem o TransactionID retornado pela M-Pesa", data["transactions"][0]["transaction_id"] == "txn-f5")

r = client_admin.get(f"/api/admin/events/{event_b_id}/financials")
check("Endpoint financeiro do ADMIN (qualquer evento) tambem responde 200", r.status_code == 200)
check("Admin ve o mesmo valor de receita bruta que o organizador", r.get_json()["data"]["summary"]["gross_revenue"] == expected_gross)

r = client_org.get(f"/api/organizador/events/{event_b_id}/financials/export-csv")
check("Exportacao CSV do relatorio financeiro responde 200", r.status_code == 200 and r.content_type.startswith("text/csv"))

r = client_org.get(f"/api/organizador/events/{event_b_id}/financials/export-pdf")
check("Exportacao PDF do relatorio financeiro responde 200", r.status_code == 200 and r.content_type == "application/pdf")

# Organizador nao pode ver o financeiro de um evento que nao e dele
r = flask_app.test_client().post("/organizador/cadastro", data={
    "full_name": "Outro Organizador", "email": "outro.fase5@teste.com",
    "username": "org.fase5.outro", "phone": "841234567",
    "password": "Senha@123Forte", "password_confirm": "Senha@123Forte",
})
check("Signup do segundo organizador (form) responde 302", r.status_code == 302)
client_outro = flask_app.test_client()
client_outro.post("/login", data={"username": "org.fase5.outro", "password": "Senha@123Forte"})
r = client_outro.get(f"/api/organizador/events/{event_b_id}/financials")
check("Organizador SEM posse do evento NAO acessa o financeiro dele (404)", r.status_code == 404)


# ============================================================================
# 5) CORTESIAS/VIP COM COTA LIMITE (PILAR 3)
# ============================================================================
section("5. Gestao de cortesias/VIP com cota limite (Modelo A)")

r = client_org.post("/api/organizador/events", json={
    "event_module": "A", "name": "Festa Cortesias Fase 5", "organizer_display_name": "X",
    "location": "Beira", "event_date": future_date, "contact_phone": "841234567",
})
event_cortesia_id = r.get_json()["data"]["id"]
client_admin.put(f"/api/admin/events/{event_cortesia_id}/mark-paid", json={"is_paid": True})

with db.get_connection() as conn:
    conn.execute("UPDATE events SET courtesy_quota = 1 WHERE id = ?", (event_cortesia_id,))

r = client_org.post(f"/api/organizador/events/{event_cortesia_id}/guests/courtesy", json={
    "full_name": "Convidado Cortesia Um", "email": "", "phone": "841112223",
})
check("Primeira cortesia dentro da cota (1/1) e aceita (201)", r.status_code == 201)

r = client_org.post(f"/api/organizador/events/{event_cortesia_id}/guests/courtesy", json={
    "full_name": "Convidado Cortesia Dois", "email": "", "phone": "841112224",
})
check("Segunda cortesia ALEM da cota (1/1 ja usada) e rejeitada (409)", r.status_code == 409)

r = client_org.post(f"/api/organizador/events/{event_b_id}/guests/courtesy", json={
    "full_name": "Convidado Errado", "email": "", "phone": "841112225",
})
check("Cortesia num evento Modelo B (nao suportado) e rejeitada", r.status_code == 409)


# ============================================================================
# 6) PORTARIA EM TEMPO REAL (PILAR 2)
# ============================================================================
section("6. Estatisticas de portaria em tempo real")

r = client_org.get(f"/api/checkin/events/{event_b_id}/live-stats")
check("Endpoint de live-stats responde 200 para evento Modelo B", r.status_code == 200)
live = r.get_json()["data"]
check("live-stats reporta o total de bilhetes vendidos corretamente", live["total"] == 5)
check("live-stats reporta 0 entradas (ninguem fez check-in ainda)", live["checked_in"] == 0)
check("live-stats calcula taxa de comparencia 0%", live["attendance_rate"] == 0.0)

r = client_org.get(f"/api/checkin/events/{event_cortesia_id}/live-stats")
check("Endpoint de live-stats responde 200 para evento Modelo A", r.status_code == 200)
check("live-stats do Modelo A conta convidados (1 cortesia emitida)", r.get_json()["data"]["total"] == 1)


print("\n" + "=" * 76)
print("TODOS OS TESTES DA FASE 5 PASSARAM.")
print("=" * 76)
