"""
security.py
Proteção contra ataques de força bruta no login. Mantém em memória (por
processo) a contagem de tentativas falhas por usuário+IP, bloqueando
temporariamente após um número excessivo de falhas em uma janela de tempo.

Observação: por ser em memória, o contador é reiniciado quando o servidor
reinicia. Para instalações de alta exigência, isso pode ser trocado por
uma tabela no banco de dados sem alterar a interface deste módulo.
"""

import os
import threading
import time
from collections import defaultdict

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60  # 15 minutos de bloqueio após exceder as tentativas
ATTEMPT_WINDOW_SECONDS = 15 * 60  # janela em que as tentativas são contadas


def get_client_ip(req):
    """
    IP real do visitante. Atrás da Vercel, `remote_addr` é o IP do proxy; a
    Vercel define X-Forwarded-For com o IP do cliente (descarta o que o cliente enviar).
    Fora da Vercel só se confia no cabeçalho com GATEFLOW_TRUST_PROXY=1.
    """
    trust = bool(os.environ.get("VERCEL")) or os.environ.get("GATEFLOW_TRUST_PROXY", "").strip().lower() in ("1", "true", "yes")
    if trust:
        forwarded = (req.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        if forwarded:
            return forwarded[:64]
    return req.remote_addr or "unknown"


class LoginAttemptTracker:
    """Thread-safe: o Flask roda com threading habilitado (threaded=True)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._failed_attempts = defaultdict(list)  # key -> [timestamps]
        self._locked_until = {}  # key -> timestamp

    @staticmethod
    def _make_key(username, ip_address):
        return f"{(username or '').strip().lower()}::{ip_address or 'unknown'}"

    def is_locked(self, username, ip_address):
        """Retorna (bloqueado: bool, segundos_restantes: int)."""
        key = self._make_key(username, ip_address)
        with self._lock:
            locked_until = self._locked_until.get(key)
            if locked_until is None:
                return False, 0
            remaining = locked_until - time.time()
            if remaining <= 0:
                self._locked_until.pop(key, None)
                self._failed_attempts.pop(key, None)
                return False, 0
            return True, int(remaining)

    def register_failure(self, username, ip_address):
        key = self._make_key(username, ip_address)
        now = time.time()
        with self._lock:
            window_start = now - ATTEMPT_WINDOW_SECONDS
            recent = [t for t in self._failed_attempts[key] if t > window_start]
            recent.append(now)
            self._failed_attempts[key] = recent
            if len(recent) >= MAX_ATTEMPTS:
                self._locked_until[key] = now + LOCKOUT_SECONDS

    def register_success(self, username, ip_address):
        key = self._make_key(username, ip_address)
        with self._lock:
            self._failed_attempts.pop(key, None)
            self._locked_until.pop(key, None)


# Instância única compartilhada por todo o processo Flask
login_attempt_tracker = LoginAttemptTracker()


IP_MAX_ATTEMPTS = 30  # falhas por IP (qualquer utilizador) na janela — trava rotação de nomes de utilizador


class SharedLoginAttemptTracker:
    """
    Mesma interface do LoginAttemptTracker, mas guarda as falhas no banco, por isso
    vale para todas as instâncias serverless. Se o banco falhar, usa a memória.
    """

    def __init__(self, db_module, fallback):
        self._db = db_module
        self._fallback = fallback

    def is_locked(self, username, ip_address):
        try:
            now = int(time.time())
            since = now - ATTEMPT_WINDOW_SECONDS
            for bucket, key, limit in (
                ("login_user", LoginAttemptTracker._make_key(username, ip_address), MAX_ATTEMPTS),
                ("login_ip", ip_address or "unknown", IP_MAX_ATTEMPTS),
            ):
                count, last = self._db.rate_count(bucket, key, since)
                if count >= limit:
                    remaining = last + LOCKOUT_SECONDS - now
                    if remaining > 0:
                        return True, int(remaining)
            return False, 0
        except Exception:  # noqa: BLE001 - o login não pode cair por causa do contador
            return self._fallback.is_locked(username, ip_address)

    def register_failure(self, username, ip_address):
        self._fallback.register_failure(username, ip_address)
        try:
            now = int(time.time())
            self._db.rate_add("login_user", LoginAttemptTracker._make_key(username, ip_address), now)
            self._db.rate_add("login_ip", ip_address or "unknown", now)
        except Exception:  # noqa: BLE001
            pass

    def register_success(self, username, ip_address):
        self._fallback.register_success(username, ip_address)
        try:
            self._db.rate_clear("login_user", LoginAttemptTracker._make_key(username, ip_address))
        except Exception:  # noqa: BLE001
            pass


def too_many(db_module, bucket, key, limit, window_seconds):
    """
    Limite genérico partilhado (ex.: cadastros por IP). Regista a tentativa e devolve
    True se passou do limite. Falha aberta (False) se o banco estiver indisponível.
    """
    try:
        now = int(time.time())
        count, _ = db_module.rate_count(bucket, key, now - window_seconds)
        if count >= limit:
            return True
        db_module.rate_add(bucket, key, now)
        return False
    except Exception:  # noqa: BLE001
        return False
