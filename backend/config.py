"""
config.py
Configurações centrais da aplicação: caminhos de diretórios, constantes
de negócio e parâmetros gerais. Mantido separado para facilitar ajustes
sem tocar na lógica de negócio.
"""

import os

# Diretório raiz do backend (onde este arquivo está)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Detecção de ambiente serverless (Vercel) ---
# A Vercel define automaticamente a variável VERCEL=1 em toda função
# serverless. Usamos isso para decidir onde gravar arquivos: o
# filesystem do deployment é SOMENTE LEITURA, exceto /tmp (que é
# efêmero — some a qualquer momento entre invocações/cold starts).
IS_SERVERLESS = bool(os.environ.get("VERCEL"))

# --- PostgreSQL (Neon.tech) em produção / SQLite em desenvolvimento local ---
# A Neon (e a Vercel, ao integrar um banco Postgres) normalmente fornece
# a URL no formato "postgres://...", mas o SQLAlchemy/psycopg2 modernos
# exigem o prefixo "postgresql://". Normalizamos aqui, uma única vez,
# para que o resto do código nunca precise se preocupar com isso.
_raw_database_url = os.environ.get("DATABASE_URL", "").strip()
if _raw_database_url.startswith("postgres://"):
    _raw_database_url = "postgresql://" + _raw_database_url[len("postgres://"):]
DATABASE_URL = _raw_database_url

# Se DATABASE_URL estiver definida, rodamos em modo PostgreSQL (produção).
# Caso contrário, caímos para SQLite local (desenvolvimento na sua máquina).
USE_POSTGRES = bool(DATABASE_URL)

# Diretório de dados persistentes. Em ambiente serverless não existe
# disco persistente de verdade — usamos /tmp apenas para arquivos
# realmente temporários (ex: geração de PDF/QR sob demanda antes de
# devolver ao cliente). Nada gravado aqui sobrevive entre requisições
# diferentes, então NUNCA deve ser a única cópia de um dado importante
# em produção (ver aviso no guia de deploy sobre logos/exports/uploads).
DATA_DIR = "/tmp/gateflow_data" if IS_SERVERLESS else os.path.join(BASE_DIR, "data")

# Banco de dados SQLite (usado apenas quando USE_POSTGRES é False)
DATABASE_PATH = os.path.join(DATA_DIR, "eventos.db")

# Diretório onde os QR Codes gerados (imagens PNG) ficam armazenados,
# organizados em subpastas por evento: data/qrcodes/<event_id>/<guest_id>.png
QRCODES_DIR = os.path.join(DATA_DIR, "qrcodes")

# Diretório onde os PDFs de convites exportados ficam armazenados
EXPORTS_DIR = os.path.join(DATA_DIR, "exports")

# Diretório temporário para uploads de planilhas .xlsx
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")

# Colunas obrigatórias esperadas na planilha de importação de convidados
REQUIRED_XLSX_COLUMNS = ["Nome Completo", "Email", "Telefone", "Cargo/Tipo"]

# Coluna opcional: se a planilha não tiver essa coluna (ou a célula estiver
# vazia), o convidado recebe o valor padrão DEFAULT_TABLE_LABEL — não
# quebra a importação nem exige atualizar planilhas antigas.
OPTIONAL_XLSX_COLUMN_TABLE = "Mesa"
DEFAULT_TABLE_LABEL = "Não definida"

# Extensões de arquivo permitidas para upload
ALLOWED_UPLOAD_EXTENSIONS = {".xlsx"}

# Upload de logo de evento (Módulo B) — validação de formato e tamanho no backend
ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg"}
MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB
LOGOS_DIR = os.path.join(DATA_DIR, "logos")

# Tamanho máximo de upload aceito (10 MB)
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024

# Host e porta padrão do servidor (0.0.0.0 permite acesso de outros
# dispositivos na mesma rede local, essencial para múltiplos porteiros)
HOST = "0.0.0.0"
PORT = 5000

# Cores da identidade visual (usadas também no PDF gerado)
COLOR_PRIMARY = "#004E92"
COLOR_BACKGROUND = "#F5F5F5"
COLOR_SUCCESS = "#E0F7E0"
COLOR_ERROR = "#EF4444"

# Arquivo onde a chave secreta de sessão (Flask) é persistida, para que os
# logins não sejam todos invalidados a cada reinício do servidor.
SECRET_KEY_PATH = os.path.join(DATA_DIR, "secret.key")

# Diretório onde o certificado HTTPS autoassinado (gerado automaticamente
# na primeira execução) é armazenado. É necessário porque navegadores
# modernos bloqueiam acesso à câmera (getUserMedia) em páginas servidas
# por http:// que não sejam localhost — o que impediria o leitor de QR
# Code de funcionar ao acessar o backend pelo IP da rede local.
CERTS_DIR = os.path.join(DATA_DIR, "certs")

# Chave secreta usada para assinar (HMAC-SHA256) cada bilhete emitido —
# ESSA chave é diferente da SECRET_KEY de sessão de login. Pode vir de
# variável de ambiente (recomendado em produção); se não vier, o sistema
# gera e persiste uma automaticamente na primeira execução (mesmo padrão
# já usado para a chave de sessão), para funcionar sem configuração
# manual em desenvolvimento/testes.
TICKET_SECRET_ENV_VAR = "GATEFLOW_TICKET_SECRET"
TICKET_SECRET_PATH = os.path.join(DATA_DIR, "ticket_secret.key")

# Duração da sessão de login (em minutos) por inatividade.
SESSION_LIFETIME_MINUTES = 480  # 8 horas — cobre um turno de trabalho

# Credenciais do usuário administrador criado automaticamente na primeira
# execução, caso ainda não exista nenhum usuário no banco. DEVEM ser
# alteradas imediatamente após o primeiro login (ver README).
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "TrocarSenha@123"
DEFAULT_PORTEIRO_USERNAME = "porteiro"
DEFAULT_PORTEIRO_PASSWORD = "TrocarSenha@123"


# --- Convites / RSVP ---

# URL pública do próprio GateFlow (ex: "https://meudominio.com"), usada
# para montar o link pessoal de RSVP (/rsvp/<token>) enviado por
# WhatsApp/SMS/e-mail. Se não configurada, cai para request.host_url em
# tempo de execução — o que funciona na maioria dos casos, mas é menos
# confiável atrás de proxy/load balancer sem X-Forwarded-Host configurado
# corretamente.
PUBLIC_BASE_URL = os.environ.get("GATEFLOW_PUBLIC_BASE_URL", "").strip().rstrip("/")

# Fase 2/5, item C4: número máximo de porteiros que cada Organizador
# pode criar para sua própria conta ("porteiro do promotor").
MAX_PORTEIROS_POR_ORGANIZADOR = int(os.environ.get("MAX_PORTEIROS_POR_ORGANIZADOR", "3"))


def ensure_directories():
    """Garante que todos os diretórios necessários existam antes de subir o app."""
    for directory in (DATA_DIR, QRCODES_DIR, EXPORTS_DIR, UPLOADS_DIR, CERTS_DIR, LOGOS_DIR):
        os.makedirs(directory, exist_ok=True)


def get_or_create_secret_key():
    """
    Prioriza a variável de ambiente SECRET_KEY (uso obrigatório em
    produção/Vercel: cada cold start é uma execução nova e sem isso as
    sessões de login seriam invalidadas a cada requisição). Se ausente,
    cai para uma chave persistida em disco — válido para desenvolvimento
    local, onde o disco realmente persiste entre reinícios do servidor.
    """
    env_key = os.environ.get("SECRET_KEY", "").strip()
    if env_key:
        return env_key

    if IS_SERVERLESS:
        # Sem SECRET_KEY configurada na Vercel: não há disco persistente
        # para guardar uma chave gerada, então cada cold start teria uma
        # chave diferente e derrubaria todas as sessões ativas. Melhor
        # falhar alto e cedo do que operar silenciosamente quebrado.
        raise RuntimeError(
            "A variável de ambiente SECRET_KEY é obrigatória em produção (Vercel). "
            "Configure-a em Project Settings -> Environment Variables."
        )

    if os.path.exists(SECRET_KEY_PATH):
        with open(SECRET_KEY_PATH, "r", encoding="utf-8") as f:
            key = f.read().strip()
            if key:
                return key
    new_key = os.urandom(32).hex()
    with open(SECRET_KEY_PATH, "w", encoding="utf-8") as f:
        f.write(new_key)
    return new_key
