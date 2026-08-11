import sys
sys.path.insert(0, ".")
import config
config.ensure_directories()
import database as db

db.init_db()

def check(label, condition):
    status = "OK" if condition else "FALHOU"
    print(f"[{status}] {label}")
    if not condition:
        raise AssertionError(label)

org_a = db.create_user("org.a.db", "hash", "organizador", full_name="Org A", email="orga@teste.com")
org_b = db.create_user("org.b.db", "hash", "organizador", full_name="Org B", email="orgb@teste.com")

# --- Evento existente (admin, pré-Fase 2) recebe event_module='A' automaticamente ---
legacy_event = db.create_event("Evento Legado Admin", "Local", "", "2026-12-01T18:00")
check("Evento criado via create_event() antiga tem event_module='A'", legacy_event["event_module"] == "A")
check("Evento antigo não tem organizador_id (é do Super Admin)", legacy_event["organizador_id"] is None)

# --- Criação Módulo A pelo organizador ---
event_a = db.create_event_full(
    org_a["id"], "A", "Casamento Teste", "Buffet Real Eventos", "Beira", "2026-12-10T18:00",
    description="Festa privada",
)
check("Evento Módulo A criado com organizador_id correto", event_a["organizador_id"] == org_a["id"])
check("Evento Módulo A com is_paid=0 por padrão", event_a["is_paid"] == 0)

# --- Criação Módulo B pelo organizador ---
event_b = db.create_event_full(
    org_a["id"], "B", "Festival de Verão", "Festival Produções Lda", "Maputo", "2026-12-20T20:00",
    contact_phone="841234567", capacity_vip=100, capacity_normal=900, capacity_total=1000,
)
check("Evento Módulo B criado com setores corretos", event_b["capacity_vip"] == 100 and event_b["capacity_normal"] == 900)

# --- event_module inválido é rejeitado ---
try:
    db.create_event_full(org_a["id"], "Z", "Invalido", "X", "Y", "2026-01-01T00:00")
    check("event_module inválido levanta ValueError", False)
except ValueError:
    check("event_module inválido levanta ValueError", True)

# --- Isolamento na EDIÇÃO: Org B tenta editar evento do Org A ---
result, owned = db.update_event_by_organizador(event_a["id"], org_b["id"], name="Hackeado")
check("Org B NÃO consegue editar evento do Org A (owned=False)", owned is False and result is None)

# Confirma que o evento do Org A NÃO foi alterado pela tentativa acima
event_a_check = db.get_event(event_a["id"])
check("Nome do evento do Org A permanece intacto após tentativa de invasão", event_a_check["name"] == "Casamento Teste")

# --- Edição legítima: Org A edita o PRÓPRIO evento ---
result, owned = db.update_event_by_organizador(event_a["id"], org_a["id"], name="Casamento Teste Editado")
check("Org A consegue editar o PRÓPRIO evento", owned is True and result["name"] == "Casamento Teste Editado")

# --- Paywall: marcar como pago ---
paid_event = db.mark_event_paid(event_a["id"], True)
check("mark_event_paid ativa a flag is_paid", paid_event["is_paid"] == 1)
unpaid_event = db.mark_event_paid(event_a["id"], False)
check("mark_event_paid desativa a flag is_paid", unpaid_event["is_paid"] == 0)

print("\n=== TODAS AS FUNÇÕES DE BANCO DA FASE 2 VALIDADAS ===")
