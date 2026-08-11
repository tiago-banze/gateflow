"""
database.py
Camada de acesso a dados. Usa SQLite em modo WAL (Write-Ahead Logging)
para permitir leitura e escrita concorrente de múltiplos porteiros
acessando o mesmo backend simultaneamente pela rede local.

Todas as funções tratam exceções de banco de dados e nunca deixam uma
conexão aberta sem fechamento (uso de context manager).
"""

import logging
import re
import sqlite3
import time
import uuid
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta

import config
import ticket_security

logger = logging.getLogger("gateflow.database")

# --------------------------------------------------------------------------
# Camada de compatibilidade SQLite <-> PostgreSQL (Neon.tech)
#
# O resto deste arquivo foi escrito 100% em SQL "cru" (sem ORM), usando
# `conn.execute(sql, params)` no estilo sqlite3, com `?` como marcador de
# parâmetro. Em vez de reescrever ~180 queries espalhadas pelo arquivo,
# esta camada faz duas coisas:
#   1. Decide qual driver usar (psycopg2 se DATABASE_URL estiver definida
#      -> produção/Neon; sqlite3 caso contrário -> dev local), e
#   2. Envolve a conexão do psycopg2 numa casca fina que entende
#      `.execute()`/`.executescript()` do mesmo jeito que sqlite3.Connection,
#      convertendo `?` -> `%s` automaticamente.
# Assim, TODAS as funções abaixo desta seção continuam inalteradas.
# --------------------------------------------------------------------------

IS_POSTGRES = config.USE_POSTGRES

_DB_ERROR_TYPES = (sqlite3.Error,)

if IS_POSTGRES:
    import psycopg2
    import psycopg2.extras

    _DB_ERROR_TYPES = (sqlite3.Error, psycopg2.Error)

    def _translate_placeholders(sql):
        # As queries deste arquivo nunca usam "?" como dado literal
        # (LIKE usa "%", nunca "?"), então uma troca direta é segura.
        return sql.replace("?", "%s")

    class _PGCursorResult:
        """Encapsula um cursor psycopg2 para casar com o uso feito neste
        arquivo (fetchone/fetchall/rowcount) sem mudanças adicionais."""

        def __init__(self, cursor):
            self._cursor = cursor

        def fetchone(self):
            return self._cursor.fetchone()

        def fetchall(self):
            return self._cursor.fetchall()

        @property
        def rowcount(self):
            return self._cursor.rowcount

    class _PGConnectionWrapper:
        """Faz uma conexão psycopg2 se comportar, nos pontos usados por
        este módulo, como uma sqlite3.Connection: `.execute(sql, params)`
        retorna um cursor com fetchone/fetchall/rowcount, e
        `.executescript(sql)` roda um bloco DDL com múltiplos statements."""

        def __init__(self, raw_conn):
            self._conn = raw_conn

        def execute(self, sql, params=None):
            cursor = self._conn.cursor()
            cursor.execute(_translate_placeholders(sql), params or ())
            return _PGCursorResult(cursor)

        def executescript(self, sql):
            cursor = self._conn.cursor()
            cursor.execute(sql)
            cursor.close()

        def commit(self):
            self._conn.commit()

        def rollback(self):
            self._conn.rollback()

        def close(self):
            self._conn.close()

    def _connect_postgres():
        raw = psycopg2.connect(config.DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return _PGConnectionWrapper(raw)


class DatabaseError(Exception):
    """Erro genérico de camada de dados, usado para repassar falhas ao Flask."""
    pass


class _GuestBusinessError(Exception):
    """Erro de regra de negócio na emissão/gestão de convidados (ex: cota de cortesias esgotada, duplicado)."""
    pass


def _row_to_dict(row):
    return dict(row) if row is not None else None


@contextmanager
def get_connection():
    """
    Fornece uma conexão (PostgreSQL/Neon em produção, SQLite em modo WAL
    em desenvolvimento local) com row_factory retornando dicionários.
    Fecha a conexão automaticamente ao final do bloco `with`.
    """
    conn = None
    try:
        if IS_POSTGRES:
            conn = _connect_postgres()
        else:
            conn = sqlite3.connect(config.DATABASE_PATH, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
        yield conn
        conn.commit()
    except _DB_ERROR_TYPES as exc:
        if conn is not None:
            conn.rollback()
        raise DatabaseError(f"Erro de banco de dados: {exc}") from exc
    finally:
        if conn is not None:
            conn.close()


@contextmanager
def get_connection_immediate():
    """
    Igual ao get_connection(), mas garante que a transação tenha a
    exclusividade de escrita JÁ NA ABERTURA — antes até do primeiro
    SELECT — em vez do padrão "deferred".

    Por quê isso importa: sem isso, DUAS conexões podem fazer um SELECT
    de contagem (ex: "quantas cortesias já foram emitidas?") vendo o
    MESMO número, e só disputar a trava depois, no INSERT. Isso é
    exatamente o cenário de overbooking: as duas acham que há vaga, uma
    escreve primeiro, a outra escreve em seguida baseada num número que
    já não é mais verdade.

    - SQLite: `BEGIN IMMEDIATE` pede a trava de escrita do banco inteiro
      já na abertura da transação.
    - PostgreSQL: não existe equivalente direto de "BEGIN IMMEDIATE"
      (MVCC não trava o banco inteiro por padrão). Em vez disso, usamos
      um advisory lock transacional (`pg_advisory_xact_lock`) — um mutex
      lógico do Postgres que qualquer conexão pode tentar adquirir; a
      segunda conexão concorrente fica bloqueada até a primeira commitar
      ou dar rollback (o lock é liberado automaticamente nesse momento).
      É a mesma garantia de exclusividade, só que via um mecanismo
      diferente do SQLite.

    Usado especificamente na emissão de cortesias/VIP, onde a decisão
    depende de uma contagem agregada (quantas já foram emitidas para o
    evento), não de uma única linha.
    """
    conn = None
    try:
        if IS_POSTGRES:
            conn = _connect_postgres()
            conn.execute("SELECT pg_advisory_xact_lock(742001001)")
        else:
            conn = sqlite3.connect(config.DATABASE_PATH, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except _DB_ERROR_TYPES as exc:
        if conn is not None:
            conn.rollback()
        raise DatabaseError(f"Erro de banco de dados: {exc}") from exc
    finally:
        if conn is not None:
            conn.close()


def init_db():
    """Cria as tabelas do sistema caso ainda não existam. Idempotente."""
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                location TEXT,
                description TEXT,
                event_date TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS guests (
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
                created_at TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_guests_event_id ON guests (event_id);
            CREATE INDEX IF NOT EXISTS idx_guests_full_name ON guests (full_name);

            -- Índice composto: acelera a busca por nome DENTRO de um evento
            -- específico (padrão de query mais comum no painel do porteiro).
            CREATE INDEX IF NOT EXISTS idx_guests_event_name ON guests (event_id, full_name);

            -- Índices de EXPRESSÃO: a checagem de duplicidade (find_duplicate_guest)
            -- roda LOWER(email) e LOWER(full_name) — um índice normal não acelera
            -- buscas com função. Sem isso, cada linha importada de uma planilha
            -- de 500-2000 convidados faz uma varredura completa da tabela (O(n)
            -- por linha = O(n²) no import inteiro). Com o índice de expressão,
            -- cada checagem vira uma busca O(log n).
            CREATE INDEX IF NOT EXISTS idx_guests_event_email_lower ON guests (event_id, LOWER(email));
            CREATE INDEX IF NOT EXISTS idx_guests_event_name_lower_phone ON guests (event_id, LOWER(full_name), phone);

            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'porteiro')),
                created_at TEXT NOT NULL
            );
            """
        )
        _migrate_add_column_if_missing(conn, "users", "full_name", "TEXT")
        _migrate_add_column_if_missing(conn, "guests", "table_number", "TEXT")
        _migrate_users_multitenancy(conn)
        _migrate_add_column_if_missing(conn, "events", "organizador_id", "TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_organizador_id ON events (organizador_id)")

        # --- Fase 2: Módulos A (convites/lista fechada) e B (público/bilhetes) ---
        # event_module NÃO usa CHECK constraint via ALTER TABLE (suporte
        # inconsistente entre versões do SQLite para ADD COLUMN + CHECK em
        # tabelas já existentes) — a validação 'A'/'B' é feita em Python,
        # antes de qualquer INSERT/UPDATE, no mesmo padrão já usado para
        # validar `role` no cadastro de usuários.
        _migrate_add_column_if_missing(conn, "events", "event_module", "TEXT")
        _migrate_add_column_if_missing(conn, "events", "organizer_display_name", "TEXT")
        _migrate_add_column_if_missing(conn, "events", "is_paid", "INTEGER NOT NULL DEFAULT 0")
        _migrate_add_column_if_missing(conn, "events", "logo_path", "TEXT")
        _migrate_add_column_if_missing(conn, "events", "contact_phone", "TEXT")
        _migrate_add_column_if_missing(conn, "events", "capacity_vip", "INTEGER")
        _migrate_add_column_if_missing(conn, "events", "capacity_normal", "INTEGER")
        _migrate_add_column_if_missing(conn, "events", "capacity_total", "INTEGER")

        # Todo evento já existente antes da Fase 2 foi criado no fluxo
        # "convite/lista fechada" original — migramos para event_module='A'
        # explicitamente (em vez de deixar NULL) para não quebrar nenhuma
        # lógica futura que assuma que event_module sempre tem um valor.
        conn.execute("UPDATE events SET event_module = 'A' WHERE event_module IS NULL")

        # --- Fase 4: Storefront publico, precos online e slug de URL ---
        _migrate_add_column_if_missing(conn, "events", "price_vip", "REAL NOT NULL DEFAULT 0")
        _migrate_add_column_if_missing(conn, "events", "price_normal", "REAL NOT NULL DEFAULT 0")
        _migrate_add_column_if_missing(conn, "events", "slug", "TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_events_slug ON events (slug)")
        _backfill_event_slugs(conn)

        # --- Fase 5: sessao unica por utilizador ---
        _migrate_add_column_if_missing(conn, "users", "active_session_token", "TEXT")

        # --- Fase 5: cortesias/VIP (Modelo A) ---
        _migrate_add_column_if_missing(conn, "events", "courtesy_quota", "INTEGER")
        _migrate_add_column_if_missing(conn, "guests", "is_courtesy", "INTEGER NOT NULL DEFAULT 0")

        # --- Fase 6: Depoimentos/Avaliações públicas (Landing Page) ---
        # Tabela nova (não é migração de coluna): CREATE TABLE IF NOT EXISTS
        # já é idempotente, então basta executar direto, no mesmo padrão do
        # idx_events_organizador_id acima.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedbacks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                comment TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedbacks_created_at ON feedbacks (created_at DESC)")

        # --- Fase 6b: Moderação de depoimentos ---
        # Para bancos já existentes (criados antes do campo `status`
        # existir): ADD COLUMN idempotente, mesmo padrão usado em todas as
        # outras migrações desta função. Depoimentos antigos, sem esta
        # migração, cairiam em NULL e sumiriam da landing (que agora só
        # mostra status='approved') — por isso o DEFAULT 'pending' aqui é
        # importante: eles voltam a aparecer na fila de moderação do admin
        # em vez de desaparecer silenciosamente.
        _migrate_add_column_if_missing(conn, "feedbacks", "status", "TEXT NOT NULL DEFAULT 'pending'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedbacks_status ON feedbacks (status)")

        # --- Fase 8: Convites / RSVP ---
        # rsvp_token: identificador único e não-adivinhável do link pessoal
        # de cada convidado (/rsvp/<token>) -- gerado na criação do
        # convidado (ver create_single_guest / bulk_create_guests).
        _migrate_add_column_if_missing(conn, "guests", "rsvp_token", "TEXT")
        _migrate_add_column_if_missing(conn, "guests", "rsvp_status", "TEXT NOT NULL DEFAULT 'pending'")
        _migrate_add_column_if_missing(conn, "guests", "companions_allowed", "INTEGER NOT NULL DEFAULT 0")
        _migrate_add_column_if_missing(conn, "guests", "companions_confirmed", "INTEGER")
        _migrate_add_column_if_missing(conn, "guests", "table_name", "TEXT")
        _migrate_add_column_if_missing(conn, "guests", "invite_sent_at", "TEXT")
        _migrate_add_column_if_missing(conn, "guests", "reminder_sent_at", "TEXT")

        # --- Fase 9: status do convite por e-mail (Módulo A, envio manual) ---
        # Coluna nova e independente de `invite_sent_at` (que já é usada pelo
        # fluxo de RSVP do Módulo B): aqui guardamos o RESULTADO do último
        # envio manual pelo Admin ('sent' | 'failed'), para exibir o selo
        # Enviado/Pendente/Falhou na tabela de convidados. NULL = nunca
        # tentado -- convidados antigos continuam válidos, só aparecem como
        # "Pendente".
        _migrate_add_column_if_missing(conn, "guests", "invite_email_status", "TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_guests_rsvp_token ON guests (rsvp_token)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_guests_rsvp_status ON guests (event_id, rsvp_status)")

        # rsvp_deadline_days: quantos dias antes do evento o link de RSVP
        # expira (ex: 7). NULL = sem prazo (link nunca expira).
        _migrate_add_column_if_missing(conn, "events", "rsvp_deadline_days", "INTEGER")
        _migrate_add_column_if_missing(conn, "events", "location_maps_url", "TEXT")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rsvp_responses (
                id TEXT PRIMARY KEY,
                guest_id TEXT NOT NULL,
                response TEXT NOT NULL CHECK (response IN ('confirmed', 'declined')),
                companions_confirmed INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'web' CHECK (source IN ('web', 'whatsapp', 'sms', 'manual')),
                responded_at TEXT NOT NULL,
                FOREIGN KEY (guest_id) REFERENCES guests (id) ON DELETE CASCADE
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rsvp_responses_guest_id ON rsvp_responses (guest_id)")


def _migrate_users_multitenancy(conn):
    """
    Migração estrutural (Fase 1 — Multi-Tenant): expande a tabela `users`
    para suportar os 4 papéis do ecossistema GateFlow:
      - 'admin'       -> Super Admin (controle total da plataforma)
      - 'organizador' -> Dono de evento, cadastro autônomo (NOVO)
      - 'porteiro'    -> Staff de portaria; se organizador_id for NULL,
                         é um "porteiro global" criado pelo Super Admin
                         (comportamento idêntico ao que já existia);
                         se organizador_id estiver preenchido, é um
                         porteiro criado por um Organizador específico
                         e só verá os eventos DESSE organizador (Fase 2).
      - 'cliente'     -> Comprador de bilhetes (NOVO — schema pronto,
                         fluxo de cadastro vem em fase futura).

    IMPORTANTE: usuários 'admin' e 'porteiro' já existentes NÃO são
    renomeados nem tocados — apenas passam a caber num CHECK constraint
    mais amplo. Nenhuma conta existente muda de comportamento.

    Como o SQLite não permite alterar uma CHECK constraint com ALTER
    TABLE, a tabela é reconstruída (rename -> create nova -> copiar
    dados -> drop da antiga), preservando 100% dos dados. Idempotente:
    se a coluna 'organizador_id' já existir, não faz nada.
    """
    existing_columns = _table_columns(conn, "users")
    if "organizador_id" in existing_columns:
        return  # já migrado

    has_full_name = "full_name" in existing_columns

    conn.execute("ALTER TABLE users RENAME TO users_migration_backup")

    conn.execute(
        """
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'organizador', 'porteiro', 'cliente')),
            full_name TEXT,
            email TEXT,
            phone TEXT,
            organizador_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (organizador_id) REFERENCES users (id) ON DELETE CASCADE
        )
        """
    )

    old_rows = conn.execute("SELECT * FROM users_migration_backup").fetchall()
    for row in old_rows:
        row_dict = dict(row)
        conn.execute(
            """
            INSERT INTO users (id, username, password_hash, role, full_name, email, phone, organizador_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row_dict["id"],
                row_dict["username"],
                row_dict["password_hash"],
                row_dict["role"],
                row_dict.get("full_name") if has_full_name else None,
                None,   # email: coluna nova, contas antigas não tinham
                None,   # phone: coluna nova, contas antigas não tinham
                None,   # organizador_id: contas antigas de porteiro viram "porteiros globais"
                row_dict["created_at"],
            ),
        )

    conn.execute("DROP TABLE users_migration_backup")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_organizador_id ON users (organizador_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)")


def _table_columns(conn, table_name):
    """
    Retorna o conjunto de nomes de colunas existentes numa tabela, de
    forma portável entre SQLite (via `PRAGMA table_info`) e PostgreSQL
    (via `information_schema.columns`, que não tem equivalente a PRAGMA).
    """
    if IS_POSTGRES:
        rows = conn.execute(
            "SELECT column_name AS name FROM information_schema.columns WHERE table_name = ?",
            (table_name,),
        ).fetchall()
    else:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _migrate_add_column_if_missing(conn, table_name, column_name, column_type):
    """
    Migração idempotente: adiciona uma coluna a uma tabela já existente
    SOMENTE se ela ainda não existir, sem apagar nenhum dado. Checamos o
    schema atual antes de tentar o ALTER TABLE (o PostgreSQL moderno
    suporta `ADD COLUMN IF NOT EXISTS`, mas mantemos a checagem manual
    para o código continuar idêntico em ambos os bancos).
    """
    existing_columns = _table_columns(conn, table_name)
    if column_name not in existing_columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def _slugify(text):
    """Slug de URL simples (letras minusculas, digitos e hifens)."""
    import re
    import unicodedata

    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", without_accents.lower())
    return slug.strip("-")


def generate_unique_event_slug(conn, name, event_id):
    """Gera um slug unico (URL publica /e/<slug>) a partir do nome do evento; nunca falha, nunca gera slug vazio."""
    base = _slugify(name) or "evento"
    short_id = event_id.replace("-", "")[:8]
    candidate = f"{base}-{short_id}"

    suffix = 0
    final_candidate = candidate
    while conn.execute(
        "SELECT 1 FROM events WHERE slug = ? AND id != ?", (final_candidate, event_id)
    ).fetchone():
        suffix += 1
        final_candidate = f"{candidate}-{suffix}"
    return final_candidate


def _backfill_event_slugs(conn):
    """Gera o slug para todo evento existente que ainda nao tem um (idempotente)."""
    rows = conn.execute("SELECT id, name FROM events WHERE slug IS NULL OR slug = ''").fetchall()
    for row in rows:
        slug = generate_unique_event_slug(conn, row["name"], row["id"])
        conn.execute("UPDATE events SET slug = ? WHERE id = ?", (slug, row["id"]))


# --------------------------------------------------------------------------
# EVENTOS
# --------------------------------------------------------------------------

def create_event(name, location, description, event_date):
    event_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO events (id, name, location, description, event_date, created_at, event_module)
            VALUES (?, ?, ?, ?, ?, ?, 'A')
            """,
            (event_id, name, location, description, event_date, created_at),
        )
    return get_event(event_id)


VALID_EVENT_MODULES = ("A", "B")


def create_event_full(organizador_id, event_module, name, organizer_display_name, location, event_date,
                       description="", contact_phone="", logo_path=None,
                       capacity_vip=None, capacity_normal=None, capacity_total=None,
                       price_vip=0, price_normal=0):
    """
    Cria um evento pelo fluxo do Organizador (Fase 2), suportando os dois
    módulos. `event_module` já deve vir validado como 'A' ou 'B' pelo
    chamador (rota da API) — esta camada só persiste.

    Fase 4: eventos do Módulo B também recebem `price_vip`/`price_normal`
    (preços de venda ONLINE, em Meticais — usados pelo storefront público
    e pelo cálculo da taxa SaaS de 5%) e um `slug` único, gerado
    automaticamente a partir do nome, para compor a URL pública /e/<slug>.
    """
    if event_module not in VALID_EVENT_MODULES:
        raise ValueError(f"event_module inválido: {event_module!r}")

    event_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    with get_connection() as conn:
        slug = generate_unique_event_slug(conn, name, event_id)
        conn.execute(
            """
            INSERT INTO events (
                id, name, location, description, event_date, created_at,
                organizador_id, event_module, organizer_display_name, is_paid,
                logo_path, contact_phone, capacity_vip, capacity_normal, capacity_total,
                price_vip, price_normal, slug
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id, name, location, description, event_date, created_at,
                organizador_id, event_module, organizer_display_name,
                logo_path, contact_phone, capacity_vip, capacity_normal, capacity_total,
                price_vip or 0, price_normal or 0, slug,
            ),
        )
    return get_event(event_id)


def update_event_by_organizador(event_id, organizador_id, **fields):
    """
    Atualiza um evento SOMENTE se pertencer ao organizador informado —
    a checagem de dono acontece dentro da MESMA query de UPDATE
    (WHERE id = ? AND organizador_id = ?), não como um SELECT separado
    antes: isso evita qualquer janela onde a posse poderia ser
    verificada e mudar antes da escrita de fato acontecer.

    Retorna (event: dict|None, found_and_owned: bool).
    """
    allowed_fields = {
        "name", "location", "description", "event_date", "organizer_display_name",
        "contact_phone", "logo_path", "capacity_vip", "capacity_normal", "capacity_total",
        "price_vip", "price_normal",
    }
    updates = {k: v for k, v in fields.items() if k in allowed_fields and v is not None}
    if not updates:
        event = get_event(event_id)
        owned = bool(event and event.get("organizador_id") == organizador_id)
        return (event, True) if owned else (None, False)

    set_clause = ", ".join(f"{key} = ?" for key in updates)
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE events SET {set_clause} WHERE id = ? AND organizador_id = ?",
            (*updates.values(), event_id, organizador_id),
        )
        if cursor.rowcount == 0:
            return None, False
    return get_event(event_id), True


def list_events():
    # A query em si é uma única SELECT com LEFT JOIN + GROUP BY (sem N+1)
    # e usa o índice idx_guests_event_id no JOIN. O log de duração abaixo
    # existe para diferenciar, em produção, "a query é lenta" (aparece
    # aqui, no valor de duration_ms) de "algo fora da query é lento"
    # (abertura de conexão, lock de escrita concorrente, disco lento etc.
    # — nesse caso duration_ms fica baixo mesmo com a rota /api/events
    # inteira demorando segundos).
    start = time.monotonic()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT e.*,
                   COUNT(g.id) AS total_guests,
                   SUM(CASE WHEN g.checked_in = 1 THEN 1 ELSE 0 END) AS total_checked_in
            FROM events e
            LEFT JOIN guests g ON g.event_id = e.id
            GROUP BY e.id
            ORDER BY e.event_date DESC, e.created_at DESC
            """
        )
        rows = [_row_to_dict(row) for row in cursor.fetchall()]
    duration_ms = (time.monotonic() - start) * 1000
    if duration_ms > 200:
        logger.warning("list_events() levou %.0fms para %d evento(s)", duration_ms, len(rows))
    return rows


def list_events_owned_by(organizador_id):
    """
    Retorna SOMENTE os eventos pertencentes a um Organizador específico.
    Esta é a query de ISOLAMENTO multi-tenant (Fase 1, item 2): o filtro
    `WHERE e.organizador_id = ?` acontece no próprio SQL, não em Python
    depois de buscar tudo — um Organizador nunca recebe do banco sequer
    UMA linha de dado de outro Organizador.
    """
    start = time.monotonic()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT e.*,
                   COUNT(g.id) AS total_guests,
                   SUM(CASE WHEN g.checked_in = 1 THEN 1 ELSE 0 END) AS total_checked_in
            FROM events e
            LEFT JOIN guests g ON g.event_id = e.id
            WHERE e.organizador_id = ?
            GROUP BY e.id
            ORDER BY e.event_date DESC, e.created_at DESC
            """,
            (organizador_id,),
        )
        rows = [_row_to_dict(row) for row in cursor.fetchall()]
    duration_ms = (time.monotonic() - start) * 1000
    if duration_ms > 200:
        logger.warning(
            "list_events_owned_by() levou %.0fms para %d evento(s)", duration_ms, len(rows)
        )
    return rows


def event_belongs_to_organizador(event_id, organizador_id):
    """Confirma no banco (não confia em nada vindo do cliente) se um evento pertence a este organizador."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id FROM events WHERE id = ? AND organizador_id = ?", (event_id, organizador_id)
        )
        return cursor.fetchone() is not None


def get_event(event_id):
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        return _row_to_dict(cursor.fetchone())


def update_event(event_id, name, location, description, event_date):
    """Atualiza os dados de um evento existente. Retorna o evento atualizado ou None se não existir."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE events SET name = ?, location = ?, description = ?, event_date = ?
            WHERE id = ?
            """,
            (name, location, description, event_date, event_id),
        )
        if cursor.rowcount == 0:
            return None
    return get_event(event_id)


def delete_event(event_id):
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
        return cursor.rowcount > 0


# --------------------------------------------------------------------------
# CONVIDADOS
# --------------------------------------------------------------------------

def bulk_create_guests(event_id, guests):
    """
    Insere vários convidados de uma vez (usado na importação de planilha).
    `guests` é uma lista de dicts com full_name, email, phone, role,
    table_number. Retorna a lista de convidados criados (já com id
    atribuído), para que o chamador possa gerar os QR Codes na sequência.
    """
    created_at = datetime.utcnow().isoformat()
    created = []
    with get_connection() as conn:
        for guest in guests:
            guest_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO guests
                    (id, event_id, full_name, email, phone, role, table_number,
                     qr_code_path, checked_in, checkin_time, checkin_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 0, NULL, NULL, ?)
                """,
                (
                    guest_id,
                    event_id,
                    guest["full_name"],
                    guest.get("email", ""),
                    guest.get("phone", ""),
                    guest.get("role", ""),
                    guest.get("table_number", config.DEFAULT_TABLE_LABEL),
                    created_at,
                ),
            )
            created.append(
                {
                    "id": guest_id,
                    "event_id": event_id,
                    "full_name": guest["full_name"],
                    "email": guest.get("email", ""),
                    "phone": guest.get("phone", ""),
                    "role": guest.get("role", ""),
                    "table_number": guest.get("table_number", config.DEFAULT_TABLE_LABEL),
                }
            )
    return created


def find_duplicate_guest(conn, event_id, email, full_name, phone):
    """
    Verifica se já existe um convidado igual para este evento específico.
    Critério de identidade única:
      1) Se o convidado tiver e-mail preenchido, compara por e-mail
         (case-insensitive) dentro do mesmo evento.
      2) Caso contrário, compara pela combinação Nome Completo + Telefone
         (case-insensitive) dentro do mesmo evento.
    Recebe uma conexão já aberta (para ser usada dentro do mesmo lote
    transacional do import, evitando condição de corrida entre linhas
    da mesma planilha).
    """
    email_norm = (email or "").strip().lower()
    name_norm = (full_name or "").strip().lower()
    phone_norm = (phone or "").strip()

    if email_norm:
        cursor = conn.execute(
            "SELECT * FROM guests WHERE event_id = ? AND LOWER(email) = ?",
            (event_id, email_norm),
        )
        row = cursor.fetchone()
        if row is not None:
            return _row_to_dict(row)

    cursor = conn.execute(
        "SELECT * FROM guests WHERE event_id = ? AND LOWER(full_name) = ? AND phone = ?",
        (event_id, name_norm, phone_norm),
    )
    row = cursor.fetchone()
    return _row_to_dict(row) if row is not None else None


def import_guests_with_dedup(event_id, guests):
    """
    Importa convidados verificando duplicidade ANTES de inserir, dentro
    de uma única transação. Retorna (created_guests, skipped_count).
    `created_guests` é a lista de convidados efetivamente inseridos
    (para o chamador gerar os QR Codes na sequência); registros já
    existentes para este evento são ignorados e contados em `skipped_count`.
    """
    created_at = datetime.utcnow().isoformat()
    created = []
    skipped_count = 0
    with get_connection() as conn:
        for guest in guests:
            full_name = guest["full_name"]
            email = guest.get("email", "")
            phone = guest.get("phone", "")
            role = guest.get("role", "")
            table_number = guest.get("table_number") or config.DEFAULT_TABLE_LABEL

            existing = find_duplicate_guest(conn, event_id, email, full_name, phone)
            if existing is not None:
                skipped_count += 1
                continue

            guest_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO guests
                    (id, event_id, full_name, email, phone, role, table_number,
                     qr_code_path, checked_in, checkin_time, checkin_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 0, NULL, NULL, ?)
                """,
                (guest_id, event_id, full_name, email, phone, role, table_number, created_at),
            )
            created.append({
                "id": guest_id,
                "event_id": event_id,
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "role": role,
                "table_number": table_number,
            })
    return created, skipped_count


def create_single_guest(event_id, full_name, email, phone, role, table_number):
    """
    Cria UM único convidado (usado no cadastro manual pelo painel do
    Admin, diferente da importação em lote via planilha). Aplica a MESMA
    verificação de duplicidade usada no import, para manter consistência.
    Retorna (guest: dict|None, duplicate: bool).
    """
    created_at = datetime.utcnow().isoformat()
    table_number = table_number or config.DEFAULT_TABLE_LABEL
    with get_connection() as conn:
        existing = find_duplicate_guest(conn, event_id, email, full_name, phone)
        if existing is not None:
            return existing, True

        guest_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO guests
                (id, event_id, full_name, email, phone, role, table_number,
                 qr_code_path, checked_in, checkin_time, checkin_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 0, NULL, NULL, ?)
            """,
            (guest_id, event_id, full_name, email, phone, role, table_number, created_at),
        )
        cursor = conn.execute("SELECT * FROM guests WHERE id = ?", (guest_id,))
        return _row_to_dict(cursor.fetchone()), False


def update_guest_qr_path(guest_id, qr_code_path):
    with get_connection() as conn:
        conn.execute(
            "UPDATE guests SET qr_code_path = ? WHERE id = ?",
            (qr_code_path, guest_id),
        )


def list_guests(event_id, search=None):
    # LIKE é case-insensitive por padrão no SQLite (para ASCII), mas
    # case-SENSITIVE no PostgreSQL -- usamos ILIKE lá para manter o
    # mesmo comportamento de busca em ambos os bancos. Pelo mesmo
    # motivo, "COLLATE NOCASE" (SQLite) vira "ORDER BY LOWER(...)"
    # (portável para os dois bancos).
    like_op = "ILIKE" if IS_POSTGRES else "LIKE"
    query = "SELECT * FROM guests WHERE event_id = ?"
    params = [event_id]
    if search:
        query += f" AND full_name {like_op} ?"
        params.append(f"%{search}%")
    query += " ORDER BY LOWER(full_name) ASC"
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return [_row_to_dict(row) for row in cursor.fetchall()]


def get_guest(guest_id):
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM guests WHERE id = ?", (guest_id,))
        return _row_to_dict(cursor.fetchone())


def get_guest_by_event(event_id, guest_id):
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM guests WHERE id = ? AND event_id = ?", (guest_id, event_id)
        )
        return _row_to_dict(cursor.fetchone())


def update_guest(event_id, guest_id, full_name, email, phone, role, table_number):
    """
    Atualiza os dados de um convidado existente (usado na edição manual
    pelo Admin). Verifica duplicidade contra OUTROS convidados do mesmo
    evento (excluindo o próprio registro sendo editado), usando o mesmo
    critério do import/cadastro (e-mail, ou Nome+Telefone).
    Retorna (guest: dict|None, duplicate: bool). guest=None se não encontrado.
    """
    table_number = table_number or config.DEFAULT_TABLE_LABEL
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM guests WHERE id = ? AND event_id = ?", (guest_id, event_id)
        )
        if cursor.fetchone() is None:
            return None, False

        existing = find_duplicate_guest(conn, event_id, email, full_name, phone)
        if existing is not None and existing["id"] != guest_id:
            return existing, True

        conn.execute(
            """
            UPDATE guests SET full_name = ?, email = ?, phone = ?, role = ?, table_number = ?
            WHERE id = ? AND event_id = ?
            """,
            (full_name, email, phone, role, table_number, guest_id, event_id),
        )
        cursor = conn.execute("SELECT * FROM guests WHERE id = ?", (guest_id,))
        return _row_to_dict(cursor.fetchone()), False


def delete_guest(event_id, guest_id):
    """Remove um convidado do evento (o QR Code em disco fica órfão, removido pelo chamador se desejado)."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM guests WHERE id = ? AND event_id = ?", (guest_id, event_id)
        )
        return cursor.rowcount > 0


def list_guests_alphabetical(event_id):
    """Lista todos os convidados de um evento em ordem alfabética pelo nome — usado no PDF de contingência."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM guests WHERE event_id = ? ORDER BY LOWER(full_name) ASC",
            (event_id,),
        )
        return [_row_to_dict(row) for row in cursor.fetchall()]


def checkin_guest(guest_id, checkin_by=None):
    """
    Marca um convidado como presente. Retorna uma tupla:
    (sucesso: bool, mensagem: str, guest: dict|None)
    - sucesso=False e mensagem="already_checked_in" caso já tenha sido
      feito o check-in anteriormente (evita check-in duplicado).

    IMPORTANTE (proteção contra condição de corrida): a atualização usa
    UPDATE ... WHERE checked_in = 0 em uma única instrução atômica, em
    vez do padrão "ler, checar em Python, depois escrever". Isso importa
    porque, se dois porteiros lerem o MESMO QR Code quase ao mesmo tempo,
    duas requisições podem chegar ao servidor com poucos milissegundos de
    diferença — com "ler-depois-escrever", ambas poderiam passar pela
    checagem antes de qualquer uma gravar, e as duas receberiam "sucesso".
    Com o UPDATE atômico, o SQLite serializa as duas escritas: a primeira
    a chegar realmente atualiza a linha (rowcount=1); a segunda tenta
    atualizar uma linha que já não bate mais com "checked_in = 0"
    (rowcount=0) e recebe corretamente "já foi feito o check-in".
    """
    checkin_time = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = conn.execute("SELECT id FROM guests WHERE id = ?", (guest_id,))
        if cursor.fetchone() is None:
            return False, "not_found", None

        cursor = conn.execute(
            "UPDATE guests SET checked_in = 1, checkin_time = ?, checkin_by = ? "
            "WHERE id = ? AND checked_in = 0",
            (checkin_time, checkin_by, guest_id),
        )

        if cursor.rowcount == 0:
            # Perdeu a corrida (ou outra requisição já tinha feito o
            # check-in um instante antes): busca o estado atual para
            # informar quem realmente ficou com o check-in.
            cursor = conn.execute("SELECT * FROM guests WHERE id = ?", (guest_id,))
            existing = _row_to_dict(cursor.fetchone())
            return False, "already_checked_in", existing

        cursor = conn.execute("SELECT * FROM guests WHERE id = ?", (guest_id,))
        updated = _row_to_dict(cursor.fetchone())
        return True, "ok", updated


def get_event_stats(event_id):
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN checked_in = 1 THEN 1 ELSE 0 END) AS checked_in
            FROM guests WHERE event_id = ?
            """,
            (event_id,),
        )
        row = _row_to_dict(cursor.fetchone())
        total = row["total"] or 0
        checked_in = row["checked_in"] or 0
        return {
            "total": total,
            "checked_in": checked_in,
            "pending": total - checked_in,
        }


# --------------------------------------------------------------------------
# USUÁRIOS / AUTENTICAÇÃO (RBAC)
# --------------------------------------------------------------------------

def create_user(username, password_hash, role, full_name="", email="", phone="", organizador_id=None):
    """
    Cria um usuário. `password_hash` já deve vir criptografado (Werkzeug
    generate_password_hash) — esta camada nunca lida com senha em texto puro.
    `role` deve ser 'admin', 'organizador', 'porteiro' ou 'cliente' (garantido
    pelo CHECK do schema). `organizador_id` só é usado para porteiros criados
    por um Organizador específico (None = porteiro global / demais papéis).
    """
    user_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (id, username, password_hash, role, created_at, full_name, email, phone, organizador_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username.strip().lower(),
                password_hash,
                role,
                created_at,
                (full_name or "").strip(),
                (email or "").strip().lower(),
                (phone or "").strip(),
                organizador_id,
            ),
        )
    return get_user_by_id(user_id)


def email_exists(email):
    if not email:
        return False
    with get_connection() as conn:
        cursor = conn.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email.strip().lower(),))
        return cursor.fetchone() is not None


def count_porteiros_by_organizador(organizador_id):
    """Conta quantos porteiros um Organizador já criou (usado para limitar a 3 — regra da Fase 2)."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) AS total FROM users WHERE organizador_id = ? AND role = 'porteiro'",
            (organizador_id,),
        )
        return cursor.fetchone()["total"]


def username_exists(username):
    return get_user_by_username(username) is not None


def get_user_by_username(username):
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip().lower(),)
        )
        return _row_to_dict(cursor.fetchone())


def get_user_by_id(user_id):
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return _row_to_dict(cursor.fetchone())


def count_users():
    with get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) AS total FROM users")
        return _row_to_dict(cursor.fetchone())["total"]


def start_new_user_session(user_id):
    """
    Fase 5: sessao unica por utilizador. Gera um novo token e o grava
    como o UNICO token de sessao valido para este usuario -- qualquer
    sessao anterior (outro dispositivo/navegador) passa a ter um token
    que nao bate mais com o do banco, e portanto e tratada como
    invalida na proxima requisicao (ver app.get_current_user).
    """
    token = secrets.token_hex(32)
    with get_connection() as conn:
        conn.execute("UPDATE users SET active_session_token = ? WHERE id = ?", (token, user_id))
    return token


def is_session_token_valid(user_id, token):
    """True se `token` ainda e o token de sessao ativo deste usuario no banco."""
    if not token:
        return False
    with get_connection() as conn:
        row = conn.execute(
            "SELECT active_session_token FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return row is not None and row["active_session_token"] == token


def list_porteiros_by_organizador(organizador_id):
    """Lista os porteiros ('porteiro do promotor') criados por este Organizador — metadados apenas, sem password_hash."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id, username, full_name, role, created_at FROM users "
            "WHERE role = 'porteiro' AND organizador_id = ? ORDER BY created_at ASC",
            (organizador_id,),
        )
        return [_row_to_dict(row) for row in cursor.fetchall()]


def list_users():
    """Não retorna password_hash, apenas metadados — usado em telas administrativas."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id, username, full_name, role, created_at FROM users ORDER BY created_at ASC"
        )
        return [_row_to_dict(row) for row in cursor.fetchall()]


# --------------------------------------------------------------------------
# FASE 5 - CORTESIAS/VIP (MODELO A)
# --------------------------------------------------------------------------

def count_courtesy_guests(event_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM guests WHERE event_id = ? AND is_courtesy = 1", (event_id,)
        ).fetchone()
        return row["c"]


def issue_courtesy_guest(event_id, full_name, email, phone, table_number=""):
    """
    Emite um convidado do tipo Cortesia/VIP de forma ATOMICA respeitando
    a cota do evento (events.courtesy_quota, se definida). Retorna
    (guest: dict|None, error: str|None).
    """
    if not full_name or not full_name.strip():
        return None, "Nome do convidado e obrigatorio."

    created_at = datetime.utcnow().isoformat()
    table_number = table_number or config.DEFAULT_TABLE_LABEL
    try:
        with get_connection_immediate() as conn:
            event_row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
            if event_row is None:
                raise _GuestBusinessError("Evento nao encontrado.")
            event = _row_to_dict(event_row)
            if event.get("event_module") != "A":
                raise _GuestBusinessError("Cortesias/VIP so estao disponiveis para eventos do Modelo A.")

            quota = event.get("courtesy_quota")
            if quota is not None:
                used = conn.execute(
                    "SELECT COUNT(*) AS c FROM guests WHERE event_id = ? AND is_courtesy = 1", (event_id,)
                ).fetchone()["c"]
                if used >= quota:
                    raise _GuestBusinessError(
                        f"Cota de cortesias esgotada ({used}/{quota} ja emitidas para este evento)."
                    )

            existing = find_duplicate_guest(conn, event_id, email, full_name, phone)
            if existing is not None:
                raise _GuestBusinessError(f"Ja existe um convidado igual neste evento: {existing['full_name']}.")

            guest_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO guests
                    (id, event_id, full_name, email, phone, role, table_number,
                     qr_code_path, checked_in, checkin_time, checkin_by, created_at, is_courtesy)
                VALUES (?, ?, ?, ?, ?, 'Cortesia', ?, NULL, 0, NULL, NULL, ?, 1)
                """,
                (guest_id, event_id, full_name.strip(), email, phone, table_number, created_at),
            )
            guest = _row_to_dict(conn.execute("SELECT * FROM guests WHERE id = ?", (guest_id,)).fetchone())
    except _GuestBusinessError as exc:
        return None, str(exc)

    return guest, None


# --------------------------------------------------------------------------
# CONVITES / RSVP
# --------------------------------------------------------------------------

def _generate_rsvp_token():
    return secrets.token_urlsafe(16)


def ensure_rsvp_token(guest_id):
    """
    Garante que o convidado tem um rsvp_token (link pessoal /rsvp/<token>),
    gerando e persistindo um na primeira chamada. Idempotente -- chamadas
    seguintes devolvem sempre o mesmo token. Retorna None se o convidado
    não existir.
    """
    with get_connection() as conn:
        row = conn.execute("SELECT rsvp_token FROM guests WHERE id = ?", (guest_id,)).fetchone()
        if row is None:
            return None
        if row["rsvp_token"]:
            return row["rsvp_token"]
        token = _generate_rsvp_token()
        conn.execute("UPDATE guests SET rsvp_token = ? WHERE id = ?", (token, guest_id))
        return token


def get_guest_by_rsvp_token(token):
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT g.*, e.name AS event_name, e.event_date, e.location, e.location_maps_url, "
            "e.rsvp_deadline_days FROM guests g JOIN events e ON e.id = g.event_id WHERE g.rsvp_token = ?",
            (token,),
        )
        return _row_to_dict(cursor.fetchone())


def rsvp_deadline_for_event(event):
    """Calcula a data-limite de RSVP (event_date - rsvp_deadline_days). None = sem prazo definido."""
    if not event.get("rsvp_deadline_days"):
        return None
    try:
        event_dt = datetime.fromisoformat(event["event_date"])
    except (ValueError, TypeError):
        return None
    return event_dt - timedelta(days=int(event["rsvp_deadline_days"]))


def submit_rsvp_response(guest_id, response, companions_confirmed, source="web"):
    """
    Grava a resposta de presença de um convidado: atualiza guests.rsvp_status
    (+ companions_confirmed) e insere uma linha em rsvp_responses (histórico
    auditável — importante porque o convidado pode responder mais de uma vez
    ou por mais de um canal, ex: mudar de "vou" para "não vou" depois, ou
    responder pela página web e também pelo WhatsApp).
    """
    now_iso = datetime.utcnow().isoformat()
    response_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "UPDATE guests SET rsvp_status = ?, companions_confirmed = ? WHERE id = ?",
            (response, companions_confirmed, guest_id),
        )
        conn.execute(
            """
            INSERT INTO rsvp_responses (id, guest_id, response, companions_confirmed, source, responded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (response_id, guest_id, response, companions_confirmed, source, now_iso),
        )
        cursor = conn.execute("SELECT * FROM guests WHERE id = ?", (guest_id,))
        return _row_to_dict(cursor.fetchone())


def set_guest_companions_allowed(event_id, guest_id, companions_allowed):
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE guests SET companions_allowed = ? WHERE id = ? AND event_id = ?",
            (companions_allowed, guest_id, event_id),
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM guests WHERE id = ?", (guest_id,)).fetchone()
        return _row_to_dict(row)


def mark_guest_invite_sent(guest_id):
    with get_connection() as conn:
        conn.execute(
            "UPDATE guests SET invite_sent_at = ? WHERE id = ?", (datetime.utcnow().isoformat(), guest_id)
        )


def mark_guest_invite_email_status(guest_id, status):
    """
    Atualiza o resultado do envio MANUAL do convite por e-mail (Módulo A),
    disparado pelo botão "Enviar Convite" no painel do Admin.

    `status`: 'sent' ou 'failed'. Em caso de sucesso também marcamos
    `invite_sent_at` (reaproveitando a mesma coluna do fluxo de RSVP) para
    manter só uma fonte de verdade de "quando o convite foi enviado".
    """
    with get_connection() as conn:
        if status == "sent":
            conn.execute(
                "UPDATE guests SET invite_email_status = ?, invite_sent_at = ? WHERE id = ?",
                (status, datetime.utcnow().isoformat(), guest_id),
            )
        else:
            conn.execute(
                "UPDATE guests SET invite_email_status = ? WHERE id = ?",
                (status, guest_id),
            )


def mark_guest_reminder_sent(guest_id):
    with get_connection() as conn:
        conn.execute(
            "UPDATE guests SET reminder_sent_at = ? WHERE id = ?", (datetime.utcnow().isoformat(), guest_id)
        )


def list_guests_pending_invite(event_id):
    """Convidados que ainda não receberam o convite inicial (invite_sent_at IS NULL)."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM guests WHERE event_id = ? AND invite_sent_at IS NULL ORDER BY created_at ASC",
            (event_id,),
        )
        return [_row_to_dict(row) for row in cursor.fetchall()]


def list_guests_pending_reminder(event_id):
    """Convidados CONFIRMADOS que ainda não receberam o lembrete com QR Code."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM guests WHERE event_id = ? AND rsvp_status = 'confirmed' AND reminder_sent_at IS NULL "
            "ORDER BY created_at ASC",
            (event_id,),
        )
        return [_row_to_dict(row) for row in cursor.fetchall()]


def get_rsvp_summary(event_id):
    """Contagem de confirmados/recusados/pendentes + total de acompanhantes confirmados -- usado no dashboard ao vivo do organizador."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN rsvp_status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed,
                SUM(CASE WHEN rsvp_status = 'declined' THEN 1 ELSE 0 END) AS declined,
                SUM(CASE WHEN rsvp_status = 'pending' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN rsvp_status = 'confirmed' THEN COALESCE(companions_confirmed, 0) ELSE 0 END) AS total_companions
            FROM guests WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()
    return {
        "total": row["total"] or 0,
        "confirmed": row["confirmed"] or 0,
        "declined": row["declined"] or 0,
        "pending": row["pending"] or 0,
        "total_companions": row["total_companions"] or 0,
    }


def set_event_rsvp_settings(event_id, rsvp_deadline_days, location_maps_url):
    with get_connection() as conn:
        conn.execute(
            "UPDATE events SET rsvp_deadline_days = ?, location_maps_url = ? WHERE id = ?",
            (rsvp_deadline_days, location_maps_url, event_id),
        )
        cursor = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        return _row_to_dict(cursor.fetchone())


def get_guest_by_phone_pending_rsvp(normalized_phone):
    """
    Encontra o convidado PENDENTE mais recente cujo telefone (normalizado)
    bate com `normalized_phone` -- usado pelo webhook de resposta inbound
    do WhatsApp ("1"/"2"), que só identifica quem respondeu pelo número
    de origem da mensagem. `guests.phone` é texto livre (o organizador
    pode ter digitado "84 123 4567", "0841234567" etc.), por isso a
    comparação usa os últimos 9 dígitos (o número "local", sem prefixo de
    país) em vez de exigir o mesmo formato exato salvo no banco.

    Se o mesmo telefone estiver cadastrado como convidado pendente em
    mais de um evento ao mesmo tempo, fica ambíguo por natureza (o
    WhatsApp não manda o token do link) -- resolve pelo convite mais
    recente.
    """
    local_digits = re.sub(r"\D", "", normalized_phone or "")[-9:]
    if len(local_digits) != 9:
        return None
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT g.*, e.event_date, e.rsvp_deadline_days FROM guests g "
            "JOIN events e ON e.id = g.event_id "
            "WHERE g.rsvp_status = 'pending' AND replace(replace(replace(g.phone, ' ', ''), '-', ''), '+', '') "
            "LIKE ? "
            "ORDER BY g.invite_sent_at DESC, g.created_at DESC LIMIT 1",
            (f"%{local_digits}",),
        )
        return _row_to_dict(cursor.fetchone())


# --------------------------------------------------------------------------
def get_event_live_checkin_stats(event_id):
    """Estatísticas de portaria em tempo real (convidados totais/já validados/pendentes, e distribuição por hora)."""
    with get_connection() as conn:
        event_row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if event_row is None:
            return None
        event = _row_to_dict(event_row)

        total = conn.execute("SELECT COUNT(*) AS c FROM guests WHERE event_id = ?", (event_id,)).fetchone()["c"]
        checked_in = conn.execute(
            "SELECT COUNT(*) AS c FROM guests WHERE event_id = ? AND checked_in = 1", (event_id,)
        ).fetchone()["c"]
        # checkin_time é gravado como texto ISO-8601 (ex: "2026-08-11T14:23:05")
        # em ambos os bancos -- extraímos os 2 caracteres da hora (posição 12)
        # com a função de substring de cada dialeto.
        hour_expr = "substring(checkin_time from 12 for 2)" if IS_POSTGRES else "substr(checkin_time, 12, 2)"
        hourly_rows = conn.execute(
            f"""
            SELECT {hour_expr} AS hour, COUNT(*) AS c
            FROM guests WHERE event_id = ? AND checked_in = 1 AND checkin_time IS NOT NULL
            GROUP BY hour ORDER BY hour ASC
            """,
            (event_id,),
        ).fetchall()

    attendance_rate = round((checked_in / total * 100), 1) if total > 0 else 0.0
    return {
        "event_module": event["event_module"],
        "total": total,
        "checked_in": checked_in,
        "pending": max(0, total - checked_in),
        "attendance_rate": attendance_rate,
        "hourly": [{"hour": r["hour"], "count": r["c"]} for r in hourly_rows],
    }


# --------------------------------------------------------------------------
# DEPOIMENTOS / AVALIAÇÕES PÚBLICAS (Landing Page)
# --------------------------------------------------------------------------

def create_feedback(name, email, rating, comment):
    """
    Grava um novo depoimento público com status='pending'. A validação de
    formato (nome, e-mail, nota 1-5, tamanho do comentário) já aconteceu
    em app.py antes de chegar aqui — esta função só persiste. `rating` é
    protegido também no schema (CHECK BETWEEN 1 AND 5), como defesa em
    profundidade.

    Fica pendente até um admin aprovar em /admin/depoimentos — não
    aparece na landing (list_feedbacks) nem no modal público até lá.
    """
    feedback_id = str(uuid.uuid4())
    now_iso = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO feedbacks (id, name, email, rating, comment, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """,
            (feedback_id, name, email, rating, comment, now_iso),
        )
    return get_feedback(feedback_id)


def get_feedback(feedback_id):
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM feedbacks WHERE id = ?", (feedback_id,))
        return _row_to_dict(cursor.fetchone())


def list_feedbacks(limit=None):
    """
    Lista os depoimentos JÁ APROVADOS, mais recentes primeiro — é a única
    fonte usada pela landing pública (SSR inicial e o modal "ver todos"),
    então um depoimento nunca aparece publicamente antes de passar pela
    moderação em /admin/depoimentos. `limit` é usado pela landing page
    para trazer só os primeiros (ex: 6) já prontos via SSR; o modal
    "ver todos" busca sem limite, sob demanda (só quando o visitante
    realmente clica em abrir o modal). A query continua uma única SELECT
    com índice em (status) — mesmo custo de antes, nada mais pesado.
    """
    query = "SELECT * FROM feedbacks WHERE status = 'approved' ORDER BY created_at DESC"
    params = ()
    if limit:
        query += " LIMIT ?"
        params = (int(limit),)
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return [_row_to_dict(row) for row in cursor.fetchall()]


def list_pending_feedbacks():
    """
    Fila de moderação: depoimentos com status='pending', mais antigos
    primeiro (FIFO — o admin limpa a fila na ordem em que chegaram). Só
    usada pelo painel /admin/depoimentos (autenticado); nunca exposta
    publicamente — a landing só enxerga status='approved' via
    list_feedbacks() acima.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM feedbacks WHERE status = 'pending' ORDER BY created_at ASC"
        )
        return [_row_to_dict(row) for row in cursor.fetchall()]


def approve_feedback(feedback_id):
    """Aprova um depoimento pendente: passa a aparecer na landing. Retorna True se algum registo foi alterado."""
    with get_connection() as conn:
        cursor = conn.execute("UPDATE feedbacks SET status = 'approved' WHERE id = ?", (feedback_id,))
        return cursor.rowcount > 0


def reject_feedback(feedback_id):
    """
    Rejeita um depoimento (soft-reject: muda o status, não apaga a
    linha) — mesmo padrão já usado no resto do sistema para estados
    finais (ex: pedidos 'expired'/'cancelled'): mantém rastro sem custo
    extra e continua reversível manualmente, sem perder o comentário
    original. Retorna True se algum registo foi alterado.
    """
    with get_connection() as conn:
        cursor = conn.execute("UPDATE feedbacks SET status = 'rejected' WHERE id = ?", (feedback_id,))
        return cursor.rowcount > 0
