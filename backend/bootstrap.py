"""
bootstrap.py
Criação do primeiro administrador. Corre apenas quando a base de dados não
tem utilizadores. NÃO existe palavra-passe padrão conhecida: usa
GATEFLOW_ADMIN_PASSWORD (recomendado) ou gera uma aleatória, mostrada uma
única vez no log/consola.
"""

import os
import secrets

from werkzeug.security import generate_password_hash

import database as db

MIN_ADMIN_PASSWORD_LENGTH = 10


def seed_initial_admin():
    """Cria o admin inicial se ainda não houver utilizadores. Devolve (username, password|None) ou None."""
    if db.count_users() > 0:
        return None

    username = (os.environ.get("GATEFLOW_ADMIN_USERNAME") or "admin").strip() or "admin"
    configured = os.environ.get("GATEFLOW_ADMIN_PASSWORD", "")
    generated = False
    if len(configured) >= MIN_ADMIN_PASSWORD_LENGTH:
        password = configured
    else:
        password = secrets.token_urlsafe(12)
        generated = True

    db.create_user(username, generate_password_hash(password), "admin")

    if generated:
        print("\n" + "=" * 72)
        print("ADMINISTRADOR INICIAL CRIADO (palavra-passe gerada, mostrada só desta vez)")
        print(f"   utilizador: {username}    palavra-passe: {password}")
        print("   Altere-a após o primeiro login (ou defina GATEFLOW_ADMIN_PASSWORD antes).")
        print("=" * 72 + "\n")
    else:
        print(f"Administrador inicial '{username}' criado com a palavra-passe de GATEFLOW_ADMIN_PASSWORD.")
    return username, (password if generated else None)
