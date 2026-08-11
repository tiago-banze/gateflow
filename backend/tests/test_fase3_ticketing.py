"""
test_fase3_ticketing.py
Suíte de testes da Fase 3 — Motor de Bilheteria (Ticketing).

Cobre exatamente os 3 pontos pedidos na bateria de validação:
  1) Bloqueio de vendas quando a lotação atinge o limite (VIP/Normal/ambos),
     incluindo um teste de CONCORRÊNCIA REAL (threads simultâneas) que
     prova que não há overbooking sob pressão.
  2) Integridade e unicidade das assinaturas HMAC-SHA256 dos QR Codes
     (anti-fraude): determinismo, unicidade por salt, e rejeição de
     qualquer campo adulterado.
  3) Geração física do PDF (grid 2x4 com marcas de corte) e integridade
     dos elementos gráficos (conteúdo, contagem de páginas, tipos VIP/Normal
     presentes no texto extraído).

Rodar:  python3 tests/test_fase3_ticketing.py
"""

import sys
import io
import threading
import time
import datetime

sys.path.insert(0, ".")
import config
config.ensure_directories()
import database as db
import ticket_security
import pdf_generator
import app as flask_app_module
flask_app = flask_app_module.app


def check(label, condition):
    status = "OK" if condition else "FALHOU"
    print(f"[{status}] {label}")
    if not condition:
        raise AssertionError(label)


def section(title):
    print(f"\n--- {title} ---")


db.init_db()

# ============================================================================
# 1) BLOQUEIO DE VENDAS NO LIMITE DA LOTAÇÃO (+ concorrência real)
# ============================================================================
section("1. Bloqueio de vendas no limite da lotação")

org = db.create_user("org.fase3.testes", "hash", "organizador", email="fase3testes@gateflow.com")

event_pequeno = db.create_event_full(
    org["id"], "B", "Evento Lotação Pequena", "Produtora Teste", "Beira",
    "2026-12-01T18:00", contact_phone="841111111",
    capacity_vip=3, capacity_normal=5, capacity_total=8,
)

# --- VIP esgota ---
batch, tickets, error = db.create_ticket_batch(event_pequeno["id"], org["id"], quantity_vip=3, quantity_normal=0)
check("Compra exata do limite VIP é aceita", error is None and len(tickets) == 3)

batch2, tickets2, error2 = db.create_ticket_batch(event_pequeno["id"], org["id"], quantity_vip=1, quantity_normal=0)
check("VIP esgotado é bloqueado", batch2 is None and error2 is not None)
check("Mensagem de VIP esgotado sugere setor Normal", "Normal" in error2 and "841111111" in error2)

# --- Normal esgota (evento separado, para não confundir com VIP já esgotado acima) ---
event_normal_teste = db.create_event_full(
    org["id"], "B", "Evento Teste Normal", "X", "Y", "2026-12-02T18:00",
    contact_phone="841111111", capacity_vip=10, capacity_normal=5, capacity_total=15,
)
batch3, tickets3, error3 = db.create_ticket_batch(event_normal_teste["id"], org["id"], quantity_vip=0, quantity_normal=5)
check("Compra exata do limite Normal é aceita", error3 is None and len(tickets3) == 5)

batch4, tickets4, error4 = db.create_ticket_batch(event_normal_teste["id"], org["id"], quantity_vip=0, quantity_normal=1)
check("Normal esgotado (com VIP ainda disponível) é bloqueado", batch4 is None)
check("Mensagem de Normal esgotado sugere setor VIP", "VIP" in error4)

# --- Ambos esgotados: mensagem de contato direto ---
# (event_pequeno já está com VIP esgotado; esgota o Normal dele também)
db.create_ticket_batch(event_pequeno["id"], org["id"], quantity_vip=0, quantity_normal=5)
batch5, tickets5, error5 = db.create_ticket_batch(event_pequeno["id"], org["id"], quantity_vip=1, quantity_normal=1)
check("Pedido com ambos setores esgotados é bloqueado", batch5 is None)
check("Mensagem de esgotamento total menciona contato direto", "ESGOTADO" in error5 and "841111111" in error5)

stock_final = db.get_event_ticket_stock(event_pequeno["id"])
check("Estoque final bate exatamente com a capacidade (sem overbooking)",
      stock_final["sold_vip"] == 3 and stock_final["sold_normal"] == 5)
check("sold_out=True quando os dois setores zeram", stock_final["sold_out"] is True)

# --- Pedido MAIOR que o estoque restante é recusado com a quantidade certa ---
event_parcial = db.create_event_full(
    org["id"], "B", "Evento Parcial", "X", "Y", "2026-12-05T18:00",
    contact_phone="841111111", capacity_vip=10, capacity_normal=0, capacity_total=10,
)
db.create_ticket_batch(event_parcial["id"], org["id"], quantity_vip=7, quantity_normal=0)
batch6, _, error6 = db.create_ticket_batch(event_parcial["id"], org["id"], quantity_vip=5, quantity_normal=0)
check("Pedido maior que o restante (5 pedidos, só 3 restam) é recusado", batch6 is None)
check("Mensagem informa a quantidade exata restante", "3" in error6)

# --- CONCORRÊNCIA REAL: 30 threads disputando 10 vagas VIP simultaneamente ---
section("1b. Concorrência real (30 threads, estoque de 10) — anti-overbooking")

event_race = db.create_event_full(
    org["id"], "B", "Evento Concorrencia", "X", "Y", "2026-12-10T18:00",
    contact_phone="841111111", capacity_vip=10, capacity_normal=0, capacity_total=10,
)

results = []
results_lock = threading.Lock()

def attempt_purchase(_worker_num):
    b, t, e = db.create_ticket_batch(event_race["id"], org["id"], quantity_vip=1, quantity_normal=0)
    with results_lock:
        results.append(b is not None)

threads = [threading.Thread(target=attempt_purchase, args=(i,)) for i in range(30)]
start = time.time()
for t in threads:
    t.start()
for t in threads:
    t.join()
elapsed = time.time() - start

successes = sum(1 for r in results if r)
stock_race = db.get_event_ticket_stock(event_race["id"])

print(f"  30 threads concorrentes em {elapsed:.3f}s -> {successes} sucessos")
check("EXATAMENTE 10 de 30 tentativas simultâneas venceram (não mais, não menos)", successes == 10)
check("Estoque no banco bate exatamente com 10 (zero overbooking real)", stock_race["sold_vip"] == 10)

# ============================================================================
# 2) INTEGRIDADE E UNICIDADE DAS ASSINATURAS (ANTI-FRAUDE)
# ============================================================================
section("2. Integridade e unicidade dos hashes de QR Code")

sig_a = ticket_security.generate_ticket_signature("id-1", "evt-1", "VIP", "salt-1")
sig_b = ticket_security.generate_ticket_signature("id-2", "evt-1", "VIP", "salt-2")
check("Bilhetes diferentes geram assinaturas diferentes (unicidade)", sig_a != sig_b)
check("Mesma entrada é determinística (mesma assinatura sempre)",
      sig_a == ticket_security.generate_ticket_signature("id-1", "evt-1", "VIP", "salt-1"))
check("Assinatura genuína é validada com sucesso",
      ticket_security.verify_ticket_signature("id-1", "evt-1", "VIP", "salt-1", sig_a))

for field_name, tampered_args in [
    ("ticket_id", ("id-FALSO", "evt-1", "VIP", "salt-1")),
    ("event_id", ("id-1", "evt-FALSO", "VIP", "salt-1")),
    ("ticket_type", ("id-1", "evt-1", "NORMAL", "salt-1")),
    ("salt", ("id-1", "evt-1", "VIP", "salt-FALSO")),
]:
    is_valid = ticket_security.verify_ticket_signature(*tampered_args, sig_a)
    check(f"Adulterar '{field_name}' invalida a assinatura (anti-fraude)", is_valid is False)

check("Assinatura forjada sem a chave secreta é rejeitada",
      not ticket_security.verify_ticket_signature("id-1", "evt-1", "VIP", "salt-1", "f" * 64))

# Unicidade em escala: gera 500 bilhetes e confirma ZERO colisões de assinatura
all_signatures = set()
for i in range(500):
    import secrets as _secrets
    salt = _secrets.token_hex(8)
    sig = ticket_security.generate_ticket_signature(f"ticket-{i}", "evt-escala", "VIP", salt)
    all_signatures.add(sig)
check("500 bilhetes gerados -> 500 assinaturas únicas (zero colisões)", len(all_signatures) == 500)

# Bilhetes reais criados pelo banco também têm assinatura íntegra e verificável
batch_real, tickets_real, _ = db.create_ticket_batch(event_parcial["id"], org["id"], quantity_vip=0, quantity_normal=0)
# (o evento acima já não tem capacity_normal, então usamos o evento_race que ainda tem vagas normais=0;
#  para testar assinatura real, puxamos um ticket já emitido em testes anteriores)
existing_ticket = db.list_tickets_for_batch(
    db.list_ticket_batches_for_event(event_pequeno["id"])[0]["id"]
)[0]
check(
    "Assinatura de um bilhete REAL persistido no banco é verificável",
    ticket_security.verify_ticket_signature(
        existing_ticket["id"], existing_ticket["event_id"],
        existing_ticket["ticket_type"], existing_ticket["salt"], existing_ticket["signature"],
    ),
)

# ============================================================================
# 3) GERAÇÃO FÍSICA DO PDF E INTEGRIDADE DO GRID
# ============================================================================
section("3. Geração do PDF físico (grid 2x4 + marcas de corte)")

event_pdf = db.create_event_full(
    org["id"], "B", "Evento PDF Fase3", "Produtora PDF", "Maputo", "2026-12-15T18:00",
    contact_phone="849999999", capacity_vip=4, capacity_normal=6, capacity_total=10,
)
batch_pdf, tickets_pdf, err_pdf = db.create_ticket_batch(event_pdf["id"], org["id"], quantity_vip=2, quantity_normal=6)
check("Lote de 8 bilhetes (2 VIP + 6 Normal) criado para teste de PDF", err_pdf is None and len(tickets_pdf) == 8)

pdf_path = pdf_generator.generate_tickets_pdf(event_pdf, batch_pdf, tickets_pdf)
import os
check("Arquivo PDF foi criado no disco", os.path.exists(pdf_path))
check("PDF tem tamanho razoável (não está vazio/corrompido)", os.path.getsize(pdf_path) > 5000)

# Extrai o texto para confirmar os elementos gráficos essenciais
import subprocess
extracted_text = subprocess.run(
    ["pdftotext", "-layout", pdf_path, "-"], capture_output=True, text=True, timeout=15
).stdout

check("PDF contém o nome do evento", "Evento PDF Fase3" in extracted_text)
check("PDF contém o nome do organizador", "Produtora PDF" in extracted_text)
check("PDF contém marcação [ VIP ]", "[ VIP ]" in extracted_text)
check("PDF contém marcação [ NORMAL ]", "[ NORMAL ]" in extracted_text)
check("PDF contém 2 ocorrências de [ VIP ] (2 bilhetes VIP no lote)", extracted_text.count("[ VIP ]") == 2)
check("PDF contém 6 ocorrências de [ NORMAL ] (6 bilhetes Normal no lote)", extracted_text.count("[ NORMAL ]") == 6)
check("PDF indica 8 bilhete(s) no cabeçalho", "8 bilhete(s)" in extracted_text)
check("PDF indica página única (8 cabem em 1 página de grid 2x4)", "Página 1/1" in extracted_text)

# Lote maior que 8 (cabe numa página) força múltiplas páginas -> confirma paginação
event_pdf2 = db.create_event_full(
    org["id"], "B", "Evento PDF Multi Pagina", "X", "Y", "2026-12-20T18:00",
    contact_phone="840000000", capacity_vip=0, capacity_normal=20, capacity_total=20,
)
batch_pdf2, tickets_pdf2, _ = db.create_ticket_batch(event_pdf2["id"], org["id"], quantity_vip=0, quantity_normal=12)
pdf_path2 = pdf_generator.generate_tickets_pdf(event_pdf2, batch_pdf2, tickets_pdf2)
extracted_text2 = subprocess.run(
    ["pdftotext", "-layout", pdf_path2, "-"], capture_output=True, text=True, timeout=15
).stdout
check("12 bilhetes (>8 por página) gera 2 páginas", "Página 1/2" in extracted_text2 and "Página 2/2" in extracted_text2)
check("Total de [ NORMAL ] no PDF multi-página bate com os 12 emitidos", extracted_text2.count("[ NORMAL ]") == 12)

# ============================================================================
# 4) PAYWALL DO DOWNLOAD DO PDF DE BILHETES (rotas HTTP fim-a-fim)
# ============================================================================
section("4. Paywall do download do PDF de bilhetes físicos (rotas HTTP)")

future_date = (datetime.date.today() + datetime.timedelta(days=30)).isoformat() + "T18:00"

client_org = flask_app.test_client()
client_org.post("/organizador/cadastro", data={
    "full_name": "Organizador Paywall Fase3", "email": "orgpaywallf3@gateflow.com",
    "username": "org.paywall.fase3", "password": "SenhaForte123", "password_confirm": "SenhaForte123",
})
client_outro = flask_app.test_client()
client_outro.post("/organizador/cadastro", data={
    "full_name": "Outro Organizador Fase3", "email": "outrof3@gateflow.com",
    "username": "org.outro.fase3", "password": "SenhaForte123", "password_confirm": "SenhaForte123",
})
client_admin_http = flask_app.test_client()
client_admin_http.post("/login", data={"username": "admin", "password": "TrocarSenha@123"})

# --- Cria evento Módulo B via API ---
r = client_org.post("/api/organizador/events", json={
    "event_module": "B", "name": "Show Paywall HTTP", "organizer_display_name": "Produtora HTTP",
    "location": "Beira", "event_date": future_date, "contact_phone": "843000000",
    "capacity_vip": 5, "capacity_normal": 5, "capacity_total": 10,
    "price_vip": 800, "price_normal": 400,
})
check("Criar evento Módulo B via API (201)", r.status_code == 201)
event_http_id = r.get_json()["data"]["id"]

# --- Emite lote de bilhetes via API ---
r = client_org.post(f"/api/organizador/events/{event_http_id}/tickets/batch", json={
    "quantity_vip": 2, "quantity_normal": 2,
})
check("Emitir lote via API (201)", r.status_code == 201)
batch_http = r.get_json()["data"]["batch"]
batch_http_id = batch_http["id"]
check("Lote criado com is_paid=0 por padrão", batch_http["is_paid"] == 0)

# --- Download ANTES do pagamento: bloqueado (402) ---
r = client_org.get(f"/api/organizador/ticket-batches/{batch_http_id}/pdf")
check("Download do PDF SEM pagamento é bloqueado (402)", r.status_code == 402)
check("Resposta indica payment_required=True", r.get_json().get("payment_required") is True)

# --- Outro organizador não pode nem ver/baixar o lote alheio ---
r = client_outro.get(f"/api/organizador/ticket-batches/{batch_http_id}/pdf")
check("Organizador de OUTRA conta não acessa o lote alheio (404)", r.status_code == 404)

# --- Organizador comum não pode confirmar pagamento (só Super Admin) ---
r = client_org.put(f"/api/admin/ticket-batches/{batch_http_id}/mark-paid", json={"is_paid": True})
check("Organizador comum NÃO pode confirmar o próprio pagamento (403)", r.status_code == 403)

# --- Super Admin confirma o pagamento da taxa ---
r = client_admin_http.put(f"/api/admin/ticket-batches/{batch_http_id}/mark-paid", json={"is_paid": True})
check("Super Admin confirma pagamento do lote (200)", r.status_code == 200)
check("is_paid=1 confirmado na resposta", r.get_json()["data"]["is_paid"] == 1)

# --- Agora o download funciona ---
r = client_org.get(f"/api/organizador/ticket-batches/{batch_http_id}/pdf")
check("Download do PDF COM pagamento confirmado funciona (200)", r.status_code == 200)
check("Resposta é um PDF", r.headers.get("Content-Type") == "application/pdf")
check("PDF retornado não está vazio", len(r.data) > 5000)
check("Content-Disposition indica anexo para download", "attachment" in r.headers.get("Content-Disposition", ""))

# --- Super Admin reverte o pagamento -> download volta a ser bloqueado ---
r = client_admin_http.put(f"/api/admin/ticket-batches/{batch_http_id}/mark-paid", json={"is_paid": False})
check("Super Admin reverte o pagamento (200)", r.status_code == 200)
r = client_org.get(f"/api/organizador/ticket-batches/{batch_http_id}/pdf")
check("Download volta a ser bloqueado após reverter pagamento (402)", r.status_code == 402)

# --- Lote inexistente ---
r = client_org.get("/api/organizador/ticket-batches/lote-que-nao-existe/pdf")
check("Lote inexistente retorna 404", r.status_code == 404)

# --- Porteiro (papel errado) não pode emitir nem baixar bilhetes ---
client_porteiro_http = flask_app.test_client()
client_porteiro_http.post("/login", data={"username": "porteiro", "password": "TrocarSenha@123"})
r = client_porteiro_http.get(f"/api/organizador/ticket-batches/{batch_http_id}/pdf")
check("Porteiro não pode acessar rota de download de bilhetes (403)", r.status_code == 403)

print("\n=== FASE 3 (TICKETING): TODOS OS TESTES PASSARAM ===")
