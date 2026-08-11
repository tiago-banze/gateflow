import sys, os, sqlite3, uuid
from datetime import datetime
sys.path.insert(0, ".")
import config
config.ensure_directories()

# --- PASSO 1: cria um banco com o schema ANTIGO manualmente (simulando uma instalação real já em uso) ---
db_path = config.DATABASE_PATH
if os.path.exists(db_path):
    os.remove(db_path)

old_conn = sqlite3.connect(db_path)
old_conn.executescript("""
    CREATE TABLE events (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        location TEXT,
        description TEXT,
        event_date TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE guests (
        id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        role TEXT,
        qr_code_path TEXT,
        checked_in INTEGER NOT NULL DEFAULT 0,
        checkin_time TEXT,
        checkin_by TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE users (
        id TEXT PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('admin', 'porteiro')),
        created_at TEXT NOT NULL
    );
""")

admin_id = str(uuid.uuid4())
porteiro_id = str(uuid.uuid4())
event_id = str(uuid.uuid4())
now = datetime.utcnow().isoformat()

old_conn.execute(
    "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
    (admin_id, "admin", "HASH_FAKE_ADMIN_SENHA_ORIGINAL", "admin", now),
)
old_conn.execute(
    "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
    (porteiro_id, "porteiro", "HASH_FAKE_PORTEIRO_SENHA_ORIGINAL", "porteiro", now),
)
old_conn.execute(
    "INSERT INTO events (id, name, location, description, event_date, created_at) VALUES (?, ?, ?, ?, ?, ?)",
    (event_id, "Evento Criado Antes da Migracao", "Local Antigo", "desc", "2026-12-01T18:00", now),
)
old_conn.commit()
old_conn.close()

print("Banco ANTIGO criado com 2 usuários e 1 evento (schema pré multi-tenant).")

# --- PASSO 2: roda o init_db() novo, que deve migrar o schema antigo automaticamente ---
import database as db
db.init_db()
print("Migração executada (init_db).\n")

# --- PASSO 3: verifica que os dados sobreviveram intactos ---
admin_user = db.get_user_by_id(admin_id)
porteiro_user = db.get_user_by_id(porteiro_id)
event = db.get_event(event_id)

print("--- Usuário admin após migração ---")
print(admin_user)
assert admin_user is not None, "FALHOU: usuário admin sumiu na migração!"
assert admin_user["username"] == "admin"
assert admin_user["password_hash"] == "HASH_FAKE_ADMIN_SENHA_ORIGINAL", "FALHOU: hash de senha foi corrompido!"
assert admin_user["role"] == "admin", "FALHOU: role do admin mudou!"
assert admin_user["organizador_id"] is None
assert admin_user["email"] is None

print("\n--- Usuário porteiro após migração ---")
print(porteiro_user)
assert porteiro_user is not None, "FALHOU: usuário porteiro sumiu na migração!"
assert porteiro_user["password_hash"] == "HASH_FAKE_PORTEIRO_SENHA_ORIGINAL"
assert porteiro_user["role"] == "porteiro"
assert porteiro_user["organizador_id"] is None  # vira "porteiro global"

print("\n--- Evento criado ANTES da migração ---")
print(event)
assert event is not None, "FALHOU: evento sumiu na migração!"
assert event["name"] == "Evento Criado Antes da Migracao"
assert event["organizador_id"] is None  # evento antigo = "dono" é o Super Admin/plataforma

# --- PASSO 4: confirma que a nova CHECK constraint aceita os papéis novos ---
new_organizador = db.create_user("organizador.teste", "hash_novo", "organizador",
                                   full_name="Maria Organizadora", email="maria@evento.com", phone="841234567")
print("\n--- Novo usuário 'organizador' criado com sucesso ---")
print(new_organizador)
assert new_organizador["role"] == "organizador"
assert new_organizador["email"] == "maria@evento.com"

new_cliente = db.create_user("cliente.teste", "hash_cliente", "cliente", email="cliente@email.com")
assert new_cliente["role"] == "cliente"
print("--- Novo usuário 'cliente' criado com sucesso ---")

# --- PASSO 5: confirma que rodar init_db() de novo (idempotência) não quebra nada ---
db.init_db()
admin_user_again = db.get_user_by_id(admin_id)
assert admin_user_again["password_hash"] == "HASH_FAKE_ADMIN_SENHA_ORIGINAL"
print("\n--- init_db() rodado uma SEGUNDA vez: idempotente, nada quebrou ---")

print("\n=== MIGRAÇÃO MULTI-TENANT: TODOS OS DADOS PRESERVADOS, NENHUMA CONTA QUEBROU ===")
