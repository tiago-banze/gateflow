"""
guest_import.py
Leitura SEGURA de listas de convidados (.xlsx, .csv ou texto colado).

Segurança:
  - extensões em lista branca (.xlsx, .csv) e limite de tamanho;
  - o conteúdo é verificado (assinatura ZIP para .xlsx, sem bytes nulos
    em .csv), a extensão sozinha não chega;
  - .xlsx com macros (vbaProject), ligações externas, objetos incorporados
    ou "zip bomb" são recusados; nada é executado, só lemos valores;
  - cada célula é limpa: caracteres de controlo removidos, tamanho limitado
    e "injeção de fórmulas" (=, +, -, @ no início) neutralizada.
"""

import csv
import io
import re
import unicodedata
import zipfile

import openpyxl

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ROWS = 2000
MAX_UNCOMPRESSED_BYTES = 30 * 1024 * 1024
ALLOWED_EXTENSIONS = {".xlsx", ".csv"}

TEMPLATE_HEADERS = ["Nome Completo", "Email", "Telefone", "Categoria", "Grupo", "Acompanhantes"]
TEMPLATE_EXAMPLE = ["Ex: João Manuel Sitoe", "joao@email.com", "841234567", "VIP", "Mesa 01", "1"]

# Cabeçalhos aceites (normalizados, sem acentos) -> campo interno.
_ALIASES = {
    "nome completo": "full_name", "nome": "full_name", "convidado": "full_name", "name": "full_name",
    "email": "email", "e-mail": "email", "correio": "email",
    "telefone": "phone", "telemovel": "phone", "celular": "phone", "contacto": "phone",
    "contato": "phone", "whatsapp": "phone", "phone": "phone",
    "categoria": "role", "cargo/tipo": "role", "cargo": "role", "tipo": "role", "role": "role",
    "grupo": "table_number", "mesa": "table_number", "zona": "table_number",
    "sector": "table_number", "setor": "table_number", "lugar": "table_number",
    "acompanhantes": "companions", "acompanhante": "companions", "pessoas extra": "companions",
    "mais": "companions",
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁠﻿]")


class ImportRejected(ValueError):
    """Ficheiro ou texto recusado por motivos de segurança/validade."""


def _norm_header(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip().lower()


def clean_cell(value, max_len=120):
    """Limpa uma célula de texto e neutraliza injeção de fórmulas."""
    if value is None:
        return ""
    text = str(value)
    text = _CONTROL_RE.sub("", text)
    text = re.sub(r"[ \t]+", " ", text.replace("\r", " ").replace("\n", " ")).strip()
    # Fórmulas ao abrir no Excel: remove o prefixo perigoso.
    while text and text[0] in "=+-@\t":
        if text[0] == "+" and re.match(r"^\+\d", text):
            break  # número internacional (+258...) é legítimo
        text = text[1:].lstrip()
    return text[:max_len]


def clean_phone(value):
    text = clean_cell(value, 40)
    return re.sub(r"[^\d+()\- ]", "", text).strip()


def validate_file(filename, data):
    """Valida extensão, tamanho e conteúdo real. Devolve a extensão."""
    name = (filename or "").lower()
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ImportRejected("Formato não aceite. Use .xlsx ou .csv (ou cole os dados).")
    if not data:
        raise ImportRejected("O ficheiro está vazio.")
    if len(data) > MAX_FILE_BYTES:
        raise ImportRejected("Ficheiro demasiado grande (máximo 2 MB).")

    if ext == ".xlsx":
        if not data.startswith(b"PK\x03\x04"):
            raise ImportRejected("O ficheiro não é um .xlsx válido.")
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                infos = archive.infolist()
                if len(infos) > 500:
                    raise ImportRejected("Ficheiro .xlsx suspeito (demasiadas partes).")
                if sum(i.file_size for i in infos) > MAX_UNCOMPRESSED_BYTES:
                    raise ImportRejected("Ficheiro .xlsx suspeito (conteúdo demasiado grande).")
                names = " ".join(i.filename.lower() for i in infos)
                if "vbaproject" in names or "/macrosheets/" in names:
                    raise ImportRejected("Ficheiros com macros não são aceites.")
                if "externallinks" in names or "/embeddings/" in names or "activex" in names:
                    raise ImportRejected("Ficheiros com ligações externas ou objetos incorporados não são aceites.")
                if archive.testzip() is not None:
                    raise ImportRejected("Ficheiro .xlsx corrompido.")
        except zipfile.BadZipFile as exc:
            raise ImportRejected("O ficheiro não é um .xlsx válido.") from exc
    else:
        if b"\x00" in data[:4096]:
            raise ImportRejected("O ficheiro .csv contém dados binários e foi recusado.")
    return ext


def _decode_csv(data):
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportRejected("Não foi possível ler o texto (use UTF-8).")


def rows_from_text(text):
    """Texto colado ou CSV -> lista de linhas (listas de strings)."""
    text = _CONTROL_RE.sub("", text or "")
    if not text.strip():
        raise ImportRejected("Sem dados para importar.")
    if len(text) > MAX_FILE_BYTES:
        raise ImportRejected("Texto demasiado grande.")
    sample = text[:4096]
    delimiter = max([",", ";", "\t"], key=sample.count)
    if sample.count(delimiter) == 0:
        delimiter = ","
    return [row for row in csv.reader(io.StringIO(text), delimiter=delimiter)]


def rows_from_xlsx(data):
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
        sheet = workbook.active
        rows = [[("" if c is None else c) for c in row] for row in sheet.iter_rows(values_only=True, max_row=MAX_ROWS + 1)]
        workbook.close()
    except Exception as exc:  # noqa: BLE001
        raise ImportRejected("Não foi possível ler o .xlsx (ficheiro inválido).") from exc
    return rows


def rows_from_upload(filename, data):
    ext = validate_file(filename, data)
    if ext == ".xlsx":
        return rows_from_xlsx(data)
    return rows_from_text(_decode_csv(data))


def parse_rows(rows):
    """
    Converte linhas em convidados normalizados.
    Devolve (guests, issues): `issues` lista avisos por linha.
    Se a primeira linha não parecer cabeçalho, assume a ordem do modelo.
    """
    if not rows:
        raise ImportRejected("Sem dados para importar.")
    if len(rows) > MAX_ROWS + 1:
        raise ImportRejected(f"Máximo de {MAX_ROWS} convidados por importação.")

    first = [_norm_header(c) for c in rows[0]]
    mapped = {i: _ALIASES[h] for i, h in enumerate(first) if h in _ALIASES}
    if "full_name" in mapped.values():
        columns, body, start = mapped, rows[1:], 2
    else:
        order = ["full_name", "email", "phone", "role", "table_number", "companions"]
        columns = {i: order[i] for i in range(min(len(order), len(rows[0])))}
        body, start = rows, 1

    guests, issues = [], []
    for offset, row in enumerate(body):
        number = start + offset
        if all(clean_cell(c) == "" for c in row):
            continue
        record = {"full_name": "", "email": "", "phone": "", "role": "", "table_number": "", "companions": ""}
        for idx, field in columns.items():
            if idx < len(row):
                record[field] = row[idx]
        raw_name = _CONTROL_RE.sub("", str(record["full_name"] or "")).strip()
        if raw_name[:1] in ("=", "@") or re.match(r"^[+\-][^\d\s]", raw_name):
            issues.append(f"Linha {number}: valor suspeito (fórmula) no nome, ignorada.")
            continue
        name = clean_cell(record["full_name"], 120)
        if name.lower().startswith("ex:"):
            continue  # linha de exemplo do modelo
        if not name:
            issues.append(f"Linha {number}: sem nome, ignorada.")
            continue
        email = clean_cell(record["email"], 160).lower()
        if email and not _EMAIL_RE.match(email):
            issues.append(f"Linha {number} ({name}): e-mail inválido, ignorado.")
            email = ""
        try:
            companions = max(0, min(int(float(clean_cell(record["companions"], 6) or 0)), 20))
        except ValueError:
            issues.append(f"Linha {number} ({name}): acompanhantes inválido, assumido 0.")
            companions = 0
        guests.append({
            "full_name": name,
            "email": email,
            "phone": clean_phone(record["phone"]),
            "role": clean_cell(record["role"], 40),
            "table_number": clean_cell(record["table_number"], 40),
            "companions_allowed": companions,
        })
    return guests, issues


def build_template_csv():
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(TEMPLATE_HEADERS)
    writer.writerow(TEMPLATE_EXAMPLE)
    return ("﻿" + buffer.getvalue()).encode("utf-8")  # BOM: o Excel abre com acentos
