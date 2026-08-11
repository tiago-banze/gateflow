"""
ticket_security.py
Assinatura criptográfica (HMAC-SHA256) dos bilhetes emitidos pelo motor
de bilheteria — a camada anti-fraude da Fase 3.

Por que HMAC e não só um hash comum (SHA-256 puro)? Um hash comum de
"ticket_id:event_id:tipo" seria recalculável por QUALQUER PESSOA, já
que essas informações não são secretas (aparecem no próprio QR Code).
Um atacante poderia gerar QR Codes falsos de bilhetes que nunca foram
comprados, só sabendo o formato. O HMAC usa uma CHAVE SECRETA que só o
servidor conhece — sem ela, é computacionalmente inviável forjar uma
assinatura que bata com a validação, mesmo sabendo o formato exato.
"""

import hmac
import hashlib
import os

import config


def _get_ticket_secret():
    """
    Retorna a chave secreta de assinatura como bytes. Prioriza a
    variável de ambiente (uso recomendado em produção); se ausente, usa
    (ou gera na primeira vez) uma chave persistida em disco — mesmo
    padrão já usado para a SECRET_KEY de sessão.
    """
    env_secret = os.environ.get(config.TICKET_SECRET_ENV_VAR)
    if env_secret:
        return env_secret.encode("utf-8")

    if os.path.exists(config.TICKET_SECRET_PATH):
        with open(config.TICKET_SECRET_PATH, "r", encoding="utf-8") as f:
            key = f.read().strip()
            if key:
                return key.encode("utf-8")

    new_key = os.urandom(32).hex()
    os.makedirs(os.path.dirname(config.TICKET_SECRET_PATH), exist_ok=True)
    with open(config.TICKET_SECRET_PATH, "w", encoding="utf-8") as f:
        f.write(new_key)
    return new_key.encode("utf-8")


def _build_message(ticket_id, event_id, ticket_type, salt):
    return f"{ticket_id}:{event_id}:{ticket_type}:{salt}".encode("utf-8")


def generate_ticket_signature(ticket_id, event_id, ticket_type, salt):
    """
    Gera a assinatura HMAC-SHA256 de um bilhete a partir dos seus dados
    essenciais + um salt aleatório único por bilhete (o salt garante que
    dois bilhetes com os mesmos ticket_type/event nunca produzam a
    mesma assinatura, mesmo em tese).
    """
    secret = _get_ticket_secret()
    message = _build_message(ticket_id, event_id, ticket_type, salt)
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_ticket_signature(ticket_id, event_id, ticket_type, salt, signature):
    """
    Recalcula a assinatura esperada a partir dos dados armazenados no
    banco e compara com a assinatura apresentada (ex: lida do QR Code na
    portaria) usando comparação de tempo constante (hmac.compare_digest)
    — evita vazar informação sobre o quanto a assinatura "quase bateu"
    através do tempo de resposta (proteção contra timing attack).
    """
    expected = generate_ticket_signature(ticket_id, event_id, ticket_type, salt)
    return hmac.compare_digest(expected, signature)


def build_ticket_qr_payload(ticket_id, signature):
    """Monta o texto codificado no QR Code do bilhete físico."""
    return f"TICKET:{ticket_id}:{signature}"


def parse_ticket_qr_payload(raw_value):
    """
    Extrai (ticket_id, signature) de um payload de QR Code lido na
    portaria. Retorna (None, None) se o formato não bater com o
    esperado — protege contra QR Codes de outro contexto/sistema.
    """
    if not raw_value:
        return None, None
    parts = raw_value.strip().split(":")
    if len(parts) != 3 or parts[0] != "TICKET":
        return None, None
    return parts[1], parts[2]
