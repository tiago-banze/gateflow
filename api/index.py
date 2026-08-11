"""
api/index.py
Ponto de entrada WSGI para a Vercel.

A Vercel (runtime @vercel/python) procura, em cada arquivo dentro de
/api, uma variável de nível de módulo chamada `app` que seja compatível
com WSGI -- e é exatamente isso que o Flask nos dá em `backend/app.py`.

Este arquivo só existe para resolver o import: o código de verdade
continua 100% em backend/app.py (nada foi duplicado), então qualquer
alteração feita lá já reflete aqui automaticamente.
"""

import os
import sys

# backend/ fica um nível acima deste arquivo (checkin_system/backend/).
# Adicionamos ao sys.path para que "import config", "import database as db"
# etc. dentro de app.py continuem funcionando exatamente como funcionam
# quando você roda `python app.py` localmente de dentro de backend/.
_BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, os.path.abspath(_BACKEND_DIR))

from app import app  # noqa: E402  (import depois do sys.path.insert é intencional)

# A Vercel detecta e usa esta variável `app` diretamente -- nenhuma
# chamada a app.run() acontece aqui (isso só roda em desenvolvimento
# local, dentro do `if __name__ == "__main__":` de backend/app.py).
