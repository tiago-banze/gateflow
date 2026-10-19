"""
migrate_neon.py
Roda a criação/migração das tabelas diretamente contra o banco definido
em DATABASE_URL (a string de conexão do Neon.tech) e, se ainda não
houver nenhum usuário, cria os administrador inicial.

Isso é o MESMO código (`db.init_db()` + `bootstrap.seed_initial_admin`) que já
roda automaticamente a cada cold start do app.py na Vercel -- rodar
manualmente uma vez, ANTES do primeiro deploy, serve só para você ver o
resultado na hora (erros de conexão, etc.) em vez de descobrir só
quando o site já estiver no ar.

Uso (a partir da pasta checkin_system/backend):
    export DATABASE_URL="postgresql://usuario:senha@ep-xxxxx.neon.tech/neondb?sslmode=require"
    python migrate_neon.py

No Windows (PowerShell):
    $env:DATABASE_URL = "postgresql://usuario:senha@ep-xxxxx.neon.tech/neondb?sslmode=require"
    python migrate_neon.py
"""

import os
import sys


def _main():
    if not os.environ.get("DATABASE_URL"):
        print(
            "Erro: variável de ambiente DATABASE_URL não definida.\n"
            "Defina-a com a connection string do Neon antes de rodar este script "
            "(veja o cabeçalho deste arquivo para o comando exato).",
            file=sys.stderr,
        )
        sys.exit(1)

    import config
    import database as db

    if not config.USE_POSTGRES:
        # Não deveria acontecer (já checamos DATABASE_URL acima), mas é
        # uma segunda trava para nunca rodar isto por engano contra o
        # eventos.db local por falta de variável de ambiente carregada.
        print("Erro: config.USE_POSTGRES está False -- DATABASE_URL não foi lida corretamente.", file=sys.stderr)
        sys.exit(1)

    print("Conectando ao PostgreSQL (Neon)... ", end="", flush=True)
    try:
        with db.get_connection() as conn:
            conn.execute("SELECT 1")
    except db.DatabaseError as exc:
        print("FALHOU.")
        print(f"Erro de conexão: {exc}", file=sys.stderr)
        sys.exit(1)
    print("OK.")

    print("Criando/migrando tabelas (idempotente, seguro rodar mais de uma vez)... ", end="", flush=True)
    db.init_db()
    print("OK.")

    import bootstrap

    if bootstrap.seed_initial_admin() is None:
        print("Já existem utilizadores no banco -- nada a criar.")

    print("Banco Neon pronto para uso em produção.")


if __name__ == "__main__":
    _main()
