"""
test_fase4_mpesa_checkout.py
Suíte de testes da Fase 4 — Storefront Público, Checkout Online e
Pagamento M-Pesa (Vodacom iPG).

Cobre os pontos pedidos na Fase 4:
  1) Storefront público: evento por slug, preços e disponibilidade real.
  2) Reserva ATÔMICA de estoque no checkout online, incluindo um teste de
     CONCORRÊNCIA REAL (múltiplas compras simultâneas pela última vaga).
  3) mpesa_service: normalização/validação de MSISDN, geração de
     Bearer Token (RSA-OAEP), e os parâmetros EXATOS enviados ao C2B
     Single Stage e ao Query Transaction Status (via mocks de rede —
     nenhuma chamada real à Vodacom é feita nestes testes).
  4) Tratamento de cada código de erro M-Pesa exigido no briefing:
     INS-0, INS-5, INS-6, INS-10, INS-2006, INS-2051.
  5) Confirmação de pagamento IDEMPOTENTE (não duplica bilhetes mesmo
     chamada múltiplas vezes / concorrentemente).
  6) Retentativa de pagamento (resiliência): referência NOVA a cada
     tentativa, pedido original preservado.
  7) Expiração da reserva de estoque libera as vagas de volta.
  8) Download do PDF de bilhetes só liberado após pagamento confirmado.

Rodar:  python3 tests/test_fase4_mpesa_checkout.py
"""

import sys
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, ".")
import config
config.ensure_directories()
import database as db
import mpesa_service
import app as flask_app_module
flask_app = flask_app_module.app


def check(label, condition):
    status = "OK" if condition else "FALHOU"
    print(f"[{status}] {label}")
    if not condition:
        raise AssertionError(label)


def section(title):
    print(f"\n--- {title} ---")


def mock_mpesa_post(response_code="INS-0", response_desc="Sucesso", conversation_id="conv-1",
                     transaction_id="txn-1", transaction_status=None):
    """Constrói um mock de requests.post para o C2B Single Stage."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "output_ResponseCode": response_code,
        "output_ResponseDesc": response_desc,
        "output_ConversationID": conversation_id,
        "output_TransactionID": transaction_id,
        "output_ResponseTransactionStatus": transaction_status,
    }
    return resp


def mock_mpesa_get(response_code="INS-0", transaction_status="Completed"):
    """Constrói um mock de requests.get para o Query Transaction Status."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "output_ResponseCode": response_code,
        "output_ResponseDesc": mpesa_service.describe_response_code(response_code),
        "output_ConversationID": "conv-1",
        "output_TransactionID": "txn-1",
        "output_ResponseTransactionStatus": transaction_status,
    }
    return resp


db.init_db()
client = flask_app.test_client()

org = db.create_user("org.fase4.testes", "hash", "organizador", email="fase4testes@gateflow.com")

# ============================================================================
# 1) STOREFRONT PÚBLICO — SLUG, PREÇOS E DISPONIBILIDADE REAL
# ============================================================================
section("1. Storefront público (evento por slug, preços, estoque real)")

event = db.create_event_full(
    org["id"], "B", "Festa Fase 4", "Produtora Fase 4", "Beira", "2026-12-15T20:00",
    contact_phone="841111111", capacity_vip=2, capacity_normal=3, capacity_total=5,
    price_vip=1000, price_normal=500,
)

check("Evento recebeu um slug único e não vazio", bool(event.get("slug")))

fetched = db.get_event_by_slug(event["slug"])
check("get_event_by_slug encontra o evento pelo slug", fetched is not None and fetched["id"] == event["id"])

r = client.get(f"/e/{event['slug']}")
check("Página pública do storefront responde 200", r.status_code == 200)
check("Página pública contém o nome do evento", b"Festa Fase 4" in r.data)

r = client.get(f"/api/public/events/{event['slug']}")
payload = r.get_json()
check("API pública do evento responde success=True", payload["success"] is True)
check("API pública expõe price_vip/price_normal corretos", payload["data"]["price_vip"] == 1000 and payload["data"]["price_normal"] == 500)
check("API pública expõe estoque com vagas restantes corretas", payload["data"]["stock"]["remaining_vip"] == 2 and payload["data"]["stock"]["remaining_normal"] == 3)

r = client.get("/e/evento-que-nao-existe-xyz")
check("Slug inexistente retorna 404 na página pública", r.status_code == 404)

r = client.get("/api/public/events/evento-que-nao-existe-xyz")
check("Slug inexistente retorna 404 na API pública", r.status_code == 404)

event_a = db.create_event_full(org["id"], "A", "Evento Convites Fase 4", "Produtora", "Beira", "2026-12-01T18:00")
check("Evento do Módulo A não é encontrado por get_event_by_slug (storefront é só Módulo B)",
      db.get_event_by_slug(event_a["slug"]) is None)


# ============================================================================
# 2) RESERVA ATÔMICA DE ESTOQUE NO CHECKOUT ONLINE (+ CONCORRÊNCIA REAL)
# ============================================================================
section("2. Reserva atômica de estoque no checkout online")

order1, err1 = db.create_online_order(event["id"], 1, 1, "Comprador Um", "258841234567")
check("Primeiro pedido criado sem erro", err1 is None and order1 is not None)
check("Pedido calcula subtotal corretamente (1*1000 + 1*500)", order1["subtotal"] == 1500.0)
check("Pedido calcula taxa de serviço de 5% corretamente", order1["service_fee_amount"] == 75.0)
check("Pedido calcula total corretamente (subtotal + taxa)", order1["total_amount"] == 1575.0)
check("Pedido nasce em status 'pending_payment'", order1["status"] == "pending_payment")

stock_after_hold = db.get_event_ticket_stock(event["id"])
check("Estoque reflete a reserva (held) imediatamente", stock_after_hold["held_vip"] == 1 and stock_after_hold["held_normal"] == 1)
check("Vagas restantes já descontam a reserva", stock_after_hold["remaining_vip"] == 1 and stock_after_hold["remaining_normal"] == 2)

order2, err2 = db.create_online_order(event["id"], 5, 0, "Comprador Dois", "258851234567")
check("Pedido além do estoque disponível é rejeitado", order2 is None and err2 is not None)

order3, err3 = db.create_online_order(event["id"], 0, 0, "Comprador Vazio", "258841234567")
check("Pedido com quantidade zero é rejeitado", order3 is None and err3 is not None)

event_gratuito = db.create_event_full(
    org["id"], "B", "Evento Sem Preco", "Produtora", "Beira", "2026-12-20T18:00",
    contact_phone="841111111", capacity_vip=0, capacity_normal=5, capacity_total=5,
    price_vip=0, price_normal=0,
)
order_zero, err_zero = db.create_online_order(event_gratuito["id"], 0, 1, "Comprador", "258841234567")
check("Pedido com subtotal 0 (evento sem preço configurado) é rejeitado", order_zero is None and "preços" in (err_zero or ""))

section("2b. Concorrência real (20 threads disputando 5 últimas vagas Normal)")

event_race = db.create_event_full(
    org["id"], "B", "Evento Concorrencia Online", "X", "Y", "2026-12-22T18:00",
    contact_phone="841111111", capacity_vip=0, capacity_normal=5, capacity_total=5,
    price_vip=0, price_normal=200,
)

race_results = []
race_lock = threading.Lock()

def attempt_checkout(worker_num):
    order, error = db.create_online_order(event_race["id"], 0, 1, f"Comprador {worker_num}", "258841234567")
    with race_lock:
        race_results.append(order is not None)

race_threads = [threading.Thread(target=attempt_checkout, args=(i,)) for i in range(20)]
start = time.time()
for t in race_threads:
    t.start()
for t in race_threads:
    t.join()
elapsed = time.time() - start

race_successes = sum(1 for r in race_results if r)
race_stock = db.get_event_ticket_stock(event_race["id"])

print(f"  20 threads concorrentes em {elapsed:.3f}s -> {race_successes} reservas bem-sucedidas")
check("EXATAMENTE 5 de 20 tentativas simultâneas conseguiram reservar (não mais, não menos)", race_successes == 5)
check("Estoque reservado bate exatamente com 5 (zero overbooking em pedidos online concorrentes)", race_stock["held_normal"] == 5)
check("Nenhuma vaga restante após a corrida", race_stock["remaining_normal"] == 0)


# ============================================================================
# 3) MPESA_SERVICE — MSISDN, BEARER TOKEN E PARÂMETROS EXATOS DA API
# ============================================================================
section("3. mpesa_service — validação de MSISDN e parâmetros da API oficial")

check("Normaliza número com espaços (84 123 4567)", mpesa_service.normalize_msisdn("84 123 4567") == "258841234567")
check("Normaliza número com zero à frente (0841234567)", mpesa_service.normalize_msisdn("0841234567") == "258841234567")
check("Normaliza número já no formato completo (+258851234567)", mpesa_service.normalize_msisdn("+258851234567") == "258851234567")
check("Rejeita número de operadora diferente (82xxxxxxx, não é M-Pesa)", mpesa_service.normalize_msisdn("821234567") is None)
check("Rejeita string vazia/None", mpesa_service.normalize_msisdn("") is None and mpesa_service.normalize_msisdn(None) is None)

cfg = mpesa_service.get_active_config()
token = mpesa_service._generate_bearer_token(cfg["api_key"], cfg["public_key"])
check("Bearer Token gerado via RSA-OAEP é uma string base64 não vazia", isinstance(token, str) and len(token) > 100)

third_ref_1 = mpesa_service.generate_third_party_reference()
third_ref_2 = mpesa_service.generate_third_party_reference()
check("Referências de terceiro geradas são únicas a cada chamada", third_ref_1 != third_ref_2)
check("Referência de terceiro respeita o limite de 20 caracteres da API", len(third_ref_1) <= 20)

with patch("mpesa_service.requests.post") as mock_post:
    mock_post.return_value = mock_mpesa_post()
    result = mpesa_service.initiate_c2b_push(
        transaction_reference="GF-TESTE01", customer_msisdn="258841234567",
        amount=1575.0, third_party_reference="GFABCDEF123456",
    )

    call_kwargs = mock_post.call_args
    sent_url = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("url")
    sent_body = call_kwargs.kwargs["json"]
    sent_headers = call_kwargs.kwargs["headers"]

    check("URL do C2B Single Stage bate com a documentação oficial (sandbox)",
          sent_url == "https://api.sandbox.vm.co.mz:18352/ipg/v1x/c2bPayment/singleStage/")
    check("input_TransactionReference enviado corretamente", sent_body["input_TransactionReference"] == "GF-TESTE01")
    check("input_CustomerMSISDN enviado corretamente", sent_body["input_CustomerMSISDN"] == "258841234567")
    check("input_Amount enviado como string (exigido pela API)", sent_body["input_Amount"] == "1575")
    check("input_ThirdPartyReference enviado corretamente", sent_body["input_ThirdPartyReference"] == "GFABCDEF123456")
    check("input_ServiceProviderCode enviado (shortcode do comerciante)", sent_body["input_ServiceProviderCode"] == cfg["shortcode"])
    check("Header Content-Type: application/json presente", sent_headers["Content-Type"] == "application/json")
    check("Header Origin presente", sent_headers["Origin"] == cfg["origin"])
    check("Header Authorization: Bearer <token> presente", sent_headers["Authorization"].startswith("Bearer "))
    check("Resposta parseada corretamente (response_code INS-0)", result["response_code"] == "INS-0")
    check("mpesa_service.is_success reconhece INS-0 como sucesso", mpesa_service.is_success(result["response_code"]))

with patch("mpesa_service.requests.get") as mock_get:
    mock_get.return_value = mock_mpesa_get()
    result = mpesa_service.query_transaction_status(
        third_party_reference="GFABCDEF123456", query_reference="txn-1",
    )
    call_kwargs = mock_get.call_args
    sent_url = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("url")
    sent_params = call_kwargs.kwargs["params"]

    check("URL do Query Transaction Status bate com a documentação oficial (sandbox)",
          sent_url == "https://api.sandbox.vm.co.mz:18353/ipg/v1x/queryTransactionStatus/")
    check("input_ThirdPartyReference enviado na consulta", sent_params["input_ThirdPartyReference"] == "GFABCDEF123456")
    check("input_QueryReference enviado na consulta", sent_params["input_QueryReference"] == "txn-1")
    check("input_ServiceProviderCode enviado na consulta", sent_params["input_ServiceProviderCode"] == cfg["shortcode"])
    check("transaction_status parseado corretamente ('Completed')", result["transaction_status"] == "Completed")


# ============================================================================
# 4) CÓDIGOS DE ERRO M-PESA (INS-*) — TODOS OS EXIGIDOS NO BRIEFING
# ============================================================================
section("4. Tratamento dos códigos de erro M-Pesa exigidos")

check("INS-0 é reconhecido como sucesso", mpesa_service.is_success("INS-0"))
check("INS-5 (cancelado pelo cliente) é falha final do cliente", mpesa_service.is_final_customer_failure("INS-5"))
check("INS-6 (falha na transação) é falha final do cliente", mpesa_service.is_final_customer_failure("INS-6"))
check("INS-2006 (saldo insuficiente) é falha final do cliente", mpesa_service.is_final_customer_failure("INS-2006"))
check("INS-2051 (MSISDN inválido) é falha final do cliente", mpesa_service.is_final_customer_failure("INS-2051"))
check("INS-10 (transação duplicada) tem mensagem amigável mapeada", "uplicada" in mpesa_service.describe_response_code("INS-10"))
check("Código desconhecido não quebra describe_response_code", "erro" in mpesa_service.describe_response_code("INS-9999").lower())
check("Nenhum destes é confundido com sucesso", not any(mpesa_service.is_success(c) for c in ("INS-5", "INS-6", "INS-10", "INS-2006", "INS-2051")))


# ============================================================================
# 5) FLUXO HTTP COMPLETO: CHECKOUT -> POLLING -> CONFIRMAÇÃO (IDEMPOTENTE)
# ============================================================================
section("5. Fluxo HTTP completo (checkout -> polling -> confirmação idempotente)")

event_http = db.create_event_full(
    org["id"], "B", "Evento Fluxo HTTP", "Produtora", "Beira", "2026-12-25T20:00",
    contact_phone="841111111", capacity_vip=3, capacity_normal=0, capacity_total=3,
    price_vip=800, price_normal=0,
)

with patch("mpesa_service.requests.post") as mock_post:
    mock_post.return_value = mock_mpesa_post()
    r = client.post(f"/api/public/events/{event_http['slug']}/checkout", json={
        "quantity_vip": 1, "quantity_normal": 0,
        "buyer_name": "Cliente HTTP", "buyer_phone": "84 999 8888",
    })
    resp_data = r.get_json()
    check("Checkout HTTP responde 201", r.status_code == 201)
    check("Checkout HTTP retorna o pedido criado", resp_data["success"] and resp_data["data"]["order"]["status"] == "pending_payment")
    order_id_http = resp_data["data"]["order"]["id"]

with patch("mpesa_service.requests.get") as mock_get:
    mock_get.return_value = mock_mpesa_get(transaction_status="Completed")
    r = client.get(f"/api/public/orders/{order_id_http}/status")
    resp_data = r.get_json()
    check("Polling confirma o pagamento e emite os bilhetes", resp_data["data"]["status"] == "paid" and resp_data["data"]["tickets_ready"])

order_after, tickets_after = db.get_online_order(order_id_http), db.list_tickets_for_order(order_id_http)
check("Exatamente 1 bilhete VIP foi emitido para o pedido", len(tickets_after) == 1 and tickets_after[0]["ticket_type"] == "VIP")

# Confirmação chamada MANUALMENTE de novo (simulando corrida entre polling e
# um callback assíncrono chegando ao mesmo tempo) -- não deve duplicar nada.
order_dup, tickets_dup, err_dup = db.confirm_online_order_paid(order_id_http)
check("Confirmação repetida é idempotente: nenhum erro", err_dup is None)
check("Confirmação repetida NÃO duplica bilhetes (continua exatamente 1)", len(tickets_dup) == 1)

r = client.get(f"/api/public/orders/{order_id_http}/tickets/pdf")
check("Download do PDF liberado após pagamento confirmado", r.status_code == 200 and r.content_type == "application/pdf")

stock_http = db.get_event_ticket_stock(event_http["id"])
check("Estoque final reflete 1 vendido, 0 reservado (hold virou venda)", stock_http["sold_vip"] == 1 and stock_http["held_vip"] == 0)


# ============================================================================
# 6) PDF BLOQUEADO ANTES DO PAGAMENTO SER CONFIRMADO
# ============================================================================
section("6. Paywall do download do PDF (bilhetes só após pagamento confirmado)")

order_pending, _ = db.create_online_order(event_http["id"], 1, 0, "Cliente Pendente", "258841112222")
r = client.get(f"/api/public/orders/{order_pending['id']}/tickets/pdf")
check("Download de pedido NÃO PAGO retorna 402 Payment Required", r.status_code == 402)

r = client.get("/api/public/orders/id-que-nao-existe/tickets/pdf")
check("Download de pedido inexistente retorna 404", r.status_code == 404)


# ============================================================================
# 7) RETENTATIVA DE PAGAMENTO (RESILIÊNCIA) -- FALHA -> RETRY COM NOVA REF
# ============================================================================
section("7. Retentativa de pagamento após falha (referência nova a cada tentativa)")

event_retry = db.create_event_full(
    org["id"], "B", "Evento Retry", "Produtora", "Beira", "2026-12-28T20:00",
    contact_phone="841111111", capacity_vip=2, capacity_normal=0, capacity_total=2,
    price_vip=600, price_normal=0,
)

with patch("mpesa_service.requests.post") as mock_post:
    mock_post.return_value = mock_mpesa_post(response_code="INS-5", response_desc="Cancelado pelo cliente")
    r = client.post(f"/api/public/events/{event_retry['slug']}/checkout", json={
        "quantity_vip": 1, "quantity_normal": 0,
        "buyer_name": "Cliente Retry", "buyer_phone": "84 777 6666",
    })
    order_retry_id = r.get_json()["data"]["order"]["id"]

attempts_before_retry = db.list_payment_attempts_for_order(order_retry_id)
check("Primeira tentativa registrada com status 'failed' (INS-5)", len(attempts_before_retry) == 1 and attempts_before_retry[0]["status"] == "failed")

order_check = db.get_online_order(order_retry_id)
check("Pedido continua 'pending_payment' após 1ª tentativa falhar (cliente pode tentar de novo)", order_check["status"] == "pending_payment")

stock_during_retry = db.get_event_ticket_stock(event_retry["id"])
check("Vaga continua RESERVADA para este pedido durante a retentativa (não libera para outros)", stock_during_retry["held_vip"] == 1)

with patch("mpesa_service.requests.post") as mock_post:
    mock_post.return_value = mock_mpesa_post(response_code="INS-0")
    r = client.post(f"/api/public/orders/{order_retry_id}/retry-payment", json={"buyer_phone": "84 777 6666"})
    check("Retentativa HTTP responde com sucesso", r.status_code == 200 and r.get_json()["success"])

attempts_after_retry = db.list_payment_attempts_for_order(order_retry_id)
check("Uma SEGUNDA tentativa foi criada (histórico completo preservado)", len(attempts_after_retry) == 2)
check("A referência da 2ª tentativa é DIFERENTE da 1ª (evita INS-10 duplicada)",
      attempts_after_retry[0]["third_party_reference"] != attempts_after_retry[1]["third_party_reference"])
check("A 2ª tentativa está com status 'pending' (push aceito, aguardando PIN)", attempts_after_retry[1]["status"] == "pending")

with patch("mpesa_service.requests.get") as mock_get:
    mock_get.return_value = mock_mpesa_get(transaction_status="Completed")
    r = client.get(f"/api/public/orders/{order_retry_id}/status")
    check("Após retentativa bem-sucedida, o pedido é confirmado como pago", r.get_json()["data"]["status"] == "paid")


# ============================================================================
# 8) EXPIRAÇÃO DA RESERVA LIBERA O ESTOQUE DE VOLTA
# ============================================================================
section("8. Expiração da reserva de estoque (hold) libera as vagas")

event_expira = db.create_event_full(
    org["id"], "B", "Evento Expiracao", "Produtora", "Beira", "2026-12-30T20:00",
    contact_phone="841111111", capacity_vip=1, capacity_normal=0, capacity_total=1,
    price_vip=300, price_normal=0,
)

order_expira, _ = db.create_online_order(event_expira["id"], 1, 0, "Cliente Expira", "258841231111")
check("Pedido reservou a única vaga VIP disponível", order_expira is not None)

stock_before_expiry = db.get_event_ticket_stock(event_expira["id"])
check("Evento fica sem vagas restantes enquanto a reserva está ativa", stock_before_expiry["remaining_vip"] == 0)

# Força a reserva a já estar expirada (simula o prazo de config.ORDER_HOLD_MINUTES
# tendo passado) escrevendo diretamente hold_expires_at no passado.
with db.get_connection() as conn:
    past = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
    conn.execute("UPDATE online_orders SET hold_expires_at = ? WHERE id = ?", (past, order_expira["id"]))

order_novo, err_novo = db.create_online_order(event_expira["id"], 1, 0, "Outro Cliente", "258851239999")
check("Novo pedido consegue reservar a vaga após a reserva anterior expirar", order_novo is not None and err_novo is None)

order_expira_refreshed = db.get_online_order(order_expira["id"])
check("Pedido antigo foi marcado como 'expired' pela expiração lazy", order_expira_refreshed["status"] == "expired")


print("\n" + "=" * 76)
print("TODOS OS TESTES DA FASE 4 PASSARAM.")
print("=" * 76)
