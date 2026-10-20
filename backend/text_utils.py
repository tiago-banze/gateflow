"""
text_utils.py
Utilitários de texto — atualmente apenas a geração de nomes de arquivo
seguros (slug) a partir de texto livre, usada para nomear os PDFs de
convites dinamicamente com base no nome do evento.
"""

import re
import unicodedata

_MSISDN_PATTERN = re.compile(r"^258(8[2-7])\d{7}$")


def normalize_msisdn(raw_phone):
    """
    Normaliza um número de telemóvel para o formato internacional sem "+"
    (E.164 sem o sinal), aceitando os formatos comuns de entrada:
      "84 123 4567", "0841234567", "+258841234567", "258841234567"
      "+27 82 123 4567" (outros países, desde que com + ou 00 à frente)

    - Números moçambicanos: 9 dígitos começando por 82-87 -> "258XXXXXXXXX".
    - Números internacionais: só aceites quando vêm com "+" ou "00" (senão
      é impossível saber o país); 8 a 15 dígitos.
    Retorna None se o número não for válido.
    """
    if not raw_phone:
        return None
    raw = raw_phone.strip()
    has_international_prefix = raw.startswith("+") or raw.startswith("00")
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("00"):
        digits = digits[2:]

    if has_international_prefix and not digits.startswith("258"):
        return digits if 8 <= len(digits) <= 15 else None

    if digits.startswith("258"):
        digits = digits[3:]
    elif digits.startswith("0"):
        digits = digits[1:]

    candidate = f"258{digits}"
    return candidate if _MSISDN_PATTERN.match(candidate) else None


def slugify_filename(text, fallback="arquivo"):
    """
    Converte um texto livre em um nome de arquivo seguro:
      "Workshop de Inovação 2026"  ->  "Workshop_de_Inovacao_2026"

    - Remove acentos (á, ã, ç, ê, etc.) preservando a letra base.
    - Substitui espaços e qualquer caractere especial por underscore.
    - Remove underscores duplicados/nas pontas.
    - Retorna `fallback` se o resultado ficar vazio (ex: nome só com
      caracteres especiais), para nunca gerar um nome de arquivo em branco.
    """
    if not text:
        return fallback

    # NFKD decompõe caracteres acentuados em (letra base + marca diacrítica),
    # o que permite remover só a marca e manter a letra (á -> a + ´ -> a).
    normalized = unicodedata.normalize("NFKD", text)
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))

    # Qualquer sequência de caracteres que não seja letra/número vira "_"
    slug = re.sub(r"[^A-Za-z0-9]+", "_", without_accents)
    slug = slug.strip("_")

    return slug or fallback


# --------------------------------------------------------------------------
# Nomes de utilizador: uma única regra para guardar, validar e comparar.
# --------------------------------------------------------------------------

_USERNAME_OK = re.compile(r"^[\w.\-@]{3,40}$")


def normalize_username(raw):
    """Limpa (espaços/Unicode) e põe em minúsculas. Usar SEMPRE ao guardar e ao comparar."""
    text = unicodedata.normalize("NFKC", str(raw or ""))
    return text.strip().lower()


def validate_username(raw):
    """Devolve mensagem de erro, ou None se válido. Só para contas NOVAS (o login não a aplica)."""
    value = normalize_username(raw)
    if not value:
        return "O usuário (login) é obrigatório e não pode ser só espaços."
    if not _USERNAME_OK.match(value):
        return "O usuário deve ter 3 a 40 caracteres: letras, números, ponto, hífen, _ ou @ (sem espaços)."
    return None
