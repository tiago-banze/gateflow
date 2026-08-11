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
    Normaliza um número de telemóvel moçambicano para o formato
    258XXXXXXXXX, aceitando os formatos comuns de entrada:
      "84 123 4567", "0841234567", "+258841234567", "258841234567"
    Retorna None se o número não for um MSISDN moçambicano válido (9
    dígitos após o 258, começando por 82-87 — as faixas atualmente
    atribuídas pelas operadoras).
    """
    if not raw_phone:
        return None
    digits = re.sub(r"\D", "", raw_phone)
    if digits.startswith("00258"):
        digits = digits[5:]
    elif digits.startswith("258"):
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
