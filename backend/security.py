"""
security.py
Proteção contra ataques de força bruta no login. Mantém em memória (por
processo) a contagem de tentativas falhas por usuário+IP, bloqueando
temporariamente após um número excessivo de falhas em uma janela de tempo.

Observação: por ser em memória, o contador é reiniciado quando o servidor
reinicia. Para instalações de alta exigência, isso pode ser trocado por
uma tabela no banco de dados sem alterar a interface deste módulo.
"""

import threading
import time
from collections import defaultdict

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60  # 15 minutos de bloqueio após exceder as tentativas
ATTEMPT_WINDOW_SECONDS = 15 * 60  # janela em que as tentativas são contadas


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
