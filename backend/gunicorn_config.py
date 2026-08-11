"""
gunicorn_config.py
Configuracao de producao do Gunicorn para o GateFlow.

Uso:
    gunicorn -c gunicorn_config.py app:app

Notas importantes:
  - O motor de bilheteria usa SQLite em modo WAL com locking atomico
    (BEGIN IMMEDIATE) para evitar overbooking mesmo com varios workers
    concorrentes -- por isso e seguro rodar mais de 1 worker.
  - Se usar Flask-Limiter com storage em memoria (RATELIMIT_STORAGE_URI
    nao configurado), os limites de taxa sao POR WORKER, nao globais --
    em producao com mais de 1 worker, configure um Redis compartilhado
    (ver .env.example) para os limites serem realmente globais.
  - workers = (2 x nucleos) + 1 e a formula recomendada pelo proprio
    Gunicorn para cargas mistas de I/O (SQLite, chamadas HTTP a M-Pesa,
    SMTP) como esta aplicacao.
"""

import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
threads = int(os.environ.get("GUNICORN_THREADS", "2"))

timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))  # o USSD Push M-Pesa pode demorar
graceful_timeout = 30
keepalive = 5

accesslog = os.environ.get("GUNICORN_ACCESS_LOG", "-")
errorlog = os.environ.get("GUNICORN_ERROR_LOG", "-")
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

max_requests = 2000          # recicla workers periodicamente (mitiga memory leaks silenciosos)
max_requests_jitter = 200    # evita todos os workers reciclarem ao mesmo tempo

preload_app = True           # carrega o app antes de fazer fork dos workers (menos memoria, boot mais rapido)
