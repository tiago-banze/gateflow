"""
pdf_generator.py
Gera o documento PDF de convites, em formato de grade limpa, contendo
para cada convidado: Nome, Cargo/Tipo e o QR Code correspondente.
Pronto para impressão e distribuição na portaria.
"""

import os
import io
from datetime import datetime

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

import config

# Layout da grade: 2 colunas x 4 linhas por página (8 convites por página)
COLUMNS = 2
ROWS = 4
MARGIN = 15 * mm
CARD_SPACING = 6 * mm

PRIMARY_COLOR = colors.HexColor(config.COLOR_PRIMARY)

# Assinatura do Administrador, aplicada no rodapé de TODAS as páginas de
# TODOS os PDFs gerados (convites e contingência), como marca de
# autenticidade do documento. Se o arquivo não existir, simplesmente não
# desenha nada, nunca quebra a geração do PDF por causa disso.
SIGNATURE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "signature_admin.png")
SIGNATURE_NAME = "Tiago Victor Banze"
SIGNATURE_ASPECT_RATIO = 174 / 804  # altura / largura da imagem original enviada


def _draw_signature_footer(c, page_width, margin):
    """Desenha a assinatura do administrador no rodapé (dentro da margem inferior já reservada)."""
    if not os.path.exists(SIGNATURE_PATH):
        return
    try:
        sig_width = 30 * mm
        sig_height = sig_width * SIGNATURE_ASPECT_RATIO
        x = page_width - margin - sig_width
        y_image = 7 * mm
        c.drawImage(
            ImageReader(SIGNATURE_PATH),
            x, y_image,
            width=sig_width, height=sig_height,
            mask="auto",
            preserveAspectRatio=True,
        )
        c.setFont("Helvetica-Oblique", 6.5)
        c.setFillColor(colors.HexColor("#999999"))
        c.drawRightString(
            page_width - margin, 3.5 * mm, f"Assinado digitalmente por {SIGNATURE_NAME}, Administrador"
        )
    except Exception:
        pass  # nunca deixa a assinatura quebrar a geração do PDF inteiro


class PDFGenerationError(Exception):
    pass


def _generate_guest_qr_image(guest_id):
    """
    Gera a imagem do QR Code de UM convidado em memória (sem salvar em
    disco). Não depender de um arquivo
    pré-gerado em `guest["qr_code_path"]` é importante em produção
    serverless: esse caminho pode apontar para um /tmp de um cold start
    anterior que já não existe mais, e o PDF de convites acabava sendo
    gerado silenciosamente SEM o QR Code de alguns convidados.
    O conteúdo codificado (payload "CHECKIN:<guest_id>") é idêntico ao
    de qrcode_utils.generate_guest_qrcode, então os dois continuam
    100% compatíveis com o leitor da portaria.
    """
    payload = f"CHECKIN:{guest_id}"
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#000000", back_color="#FFFFFF")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


_CATEGORY_COLORS = {
    "vip": "#B8860B", "imprensa": "#1F6FB2", "staff": "#2E7D32", "orador": "#7B1FA2",
    "artista": "#C2185B", "patrocinador": "#00796B",
}


def _event_date_label(event):
    raw = (event or {}).get("event_date") or ""
    try:
        from datetime import datetime
        return datetime.fromisoformat(raw).strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return raw


def _draw_card(c, x, y, card_width, card_height, guest, qr_image_path, event=None):
    """
    Cartão: QR Code à esquerda; à direita só o que identifica o convidado
    (nome, grupo, nº de pessoas, categoria). Evento/data/local ficam no
    cabeçalho da página. Nada ultrapassa a moldura.
    """
    event = event or {}
    pad = 4 * mm
    c.setStrokeColor(PRIMARY_COLOR)
    c.setLineWidth(1)
    c.roundRect(x, y, card_width, card_height, 3 * mm, stroke=1, fill=0)

    qr_size = min(card_height - 2 * pad, card_width * 0.46)
    qr_y = y + (card_height - qr_size) / 2
    try:
        c.drawImage(ImageReader(_generate_guest_qr_image(guest["id"])), x + pad, qr_y,
                    width=qr_size, height=qr_size, preserveAspectRatio=True)
    except Exception:
        pass  # nunca deixa um QR falhado travar o PDF inteiro

    text_x = x + pad + qr_size + 4 * mm
    text_w = x + card_width - pad - text_x
    top = y + card_height - pad

    # Nome (até 3 linhas, reduz a letra se for muito comprido)
    size = 11
    lines = _wrap_text(c, guest["full_name"], "Helvetica-Bold", size, text_w)
    if len(lines) > 3:
        size = 9
        lines = _wrap_text(c, guest["full_name"], "Helvetica-Bold", size, text_w)
    lines = lines[:3]
    c.setFillColor(PRIMARY_COLOR)
    c.setFont("Helvetica-Bold", size)
    ty = top - size
    for line in lines:
        c.drawString(text_x, ty, line)
        ty -= size + 2

    # Grupo (Mesa/Zona/...) e pessoas
    group_name = event.get("group_label") or "Mesa"
    table_label = guest.get("table_number") or config.DEFAULT_TABLE_LABEL
    ty -= 3
    c.setFont("Helvetica-Bold", 9)
    for line in _wrap_text(c, f"{group_name}: {table_label}", "Helvetica-Bold", 9, text_w)[:2]:
        c.drawString(text_x, ty, line)
        ty -= 11
    extra = int(guest.get("companions_allowed") or 0)
    if extra:
        c.setFillColor(colors.HexColor("#555555"))
        c.setFont("Helvetica", 8)
        c.drawString(text_x, ty, f"Válido para {1 + extra} pessoas")

    # Categoria: etiqueta na base da coluna de texto
    role_text = (guest.get("role") or "Convidado").strip().upper()[:18]
    c.setFont("Helvetica-Bold", 7.5)
    badge_w = min(c.stringWidth(role_text, "Helvetica-Bold", 7.5) + 5 * mm, text_w)
    c.setFillColor(colors.HexColor(_CATEGORY_COLORS.get(role_text.lower(), "#555555")))
    c.roundRect(text_x, y + pad, badge_w, 4.6 * mm, 1.6 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.drawString(text_x + 2.5 * mm, y + pad + 1.4 * mm, role_text)


def _wrap_text(c, text, font_name, font_size, max_width):
    """Quebra o texto em múltiplas linhas para caber na largura do cartão."""
    words = (text or "").split()
    lines = []
    current_line = ""
    for word in words:
        candidate = f"{current_line} {word}".strip()
        if c.stringWidth(candidate, font_name, font_size) <= max_width:
            current_line = candidate
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines or [""]


def generate_invites_pdf(event, guests):
    """
    Gera o PDF de convites para todos os convidados de um evento.
    Retorna o caminho absoluto do arquivo PDF gerado.
    """
    try:
        os.makedirs(config.EXPORTS_DIR, exist_ok=True)
        output_path = os.path.join(config.EXPORTS_DIR, f"{event['id']}_convites.pdf")

        page_width, page_height = A4
        usable_width = page_width - (2 * MARGIN)
        usable_height = page_height - (2 * MARGIN) - (15 * mm)  # reserva cabeçalho

        card_width = (usable_width - (CARD_SPACING * (COLUMNS - 1))) / COLUMNS
        card_height = (usable_height - (CARD_SPACING * (ROWS - 1))) / ROWS

        c = canvas.Canvas(output_path, pagesize=A4)

        per_page = COLUMNS * ROWS
        total_guests = len(guests)
        page_count = max(1, -(-total_guests // per_page))  # ceil division

        guest_index = 0
        for page_num in range(page_count):
            _draw_header(c, event, page_width, page_height, page_num + 1, page_count)

            for row in range(ROWS):
                for col in range(COLUMNS):
                    if guest_index >= total_guests:
                        break
                    guest = guests[guest_index]
                    x = MARGIN + col * (card_width + CARD_SPACING)
                    y = (
                        page_height
                        - MARGIN
                        - (20 * mm)
                        - (row + 1) * card_height
                        - row * CARD_SPACING
                    )
                    qr_path = guest.get("qr_code_path")
                    _draw_card(c, x, y, card_width, card_height, guest, qr_path, event)
                    guest_index += 1

            _draw_signature_footer(c, page_width, MARGIN)
            c.showPage()

        c.save()
        return output_path
    except Exception as exc:  # noqa: BLE001
        raise PDFGenerationError(f"Falha ao gerar PDF de convites: {exc}") from exc


def _draw_header(c, event, page_width, page_height, page_num, page_count):
    c.setFillColor(PRIMARY_COLOR)
    c.rect(0, page_height - 18 * mm, page_width, 18 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(MARGIN, page_height - 12 * mm, event["name"])
    c.setFont("Helvetica", 9)
    subtitle = event.get("location") or ""
    if event.get("event_date"):
        date_text = _event_date_label(event)
        subtitle = f"{subtitle}  |  {date_text}" if subtitle else date_text
    c.drawString(MARGIN, page_height - 16.5 * mm, subtitle)
    c.setFont("Helvetica", 8)
    c.drawRightString(
        page_width - MARGIN, page_height - 12 * mm, f"Página {page_num}/{page_count}"
    )


# --------------------------------------------------------------------------
# PDF DE CONTINGÊNCIA, plano de emergência offline
# --------------------------------------------------------------------------

CONTINGENCY_MARGIN = 15 * mm
CONTINGENCY_HEADER_HEIGHT = 22 * mm
CONTINGENCY_COLUMNS = 2
CONTINGENCY_ROW_HEIGHT = 6.5 * mm
CONTINGENCY_COLUMN_GAP = 10 * mm


def generate_contingency_pdf(event, guests_alphabetical):
    """
    Gera um PDF minimalista de contingência: lista em ORDEM ALFABÉTICA
    contendo apenas Nome e Mesa de cada convidado, sem QR Code, sem
    dados de contato, pronto para imprimir rapidamente e permitir
    check-in manual a caneta caso o sistema fique indisponível durante
    o evento (falha de energia, rede, etc.).
    """
    try:
        os.makedirs(config.EXPORTS_DIR, exist_ok=True)
        output_path = os.path.join(config.EXPORTS_DIR, f"{event['id']}_contingencia.pdf")

        page_width, page_height = A4
        usable_height = page_height - CONTINGENCY_MARGIN - CONTINGENCY_HEADER_HEIGHT
        rows_per_column = max(1, int(usable_height / CONTINGENCY_ROW_HEIGHT))
        rows_per_page = rows_per_column * CONTINGENCY_COLUMNS
        column_width = (
            page_width - (2 * CONTINGENCY_MARGIN) - CONTINGENCY_COLUMN_GAP
        ) / CONTINGENCY_COLUMNS

        total = len(guests_alphabetical)
        page_count = max(1, -(-total // rows_per_page))  # ceil division

        c = canvas.Canvas(output_path, pagesize=A4)
        guest_index = 0

        for page_num in range(page_count):
            _draw_contingency_header(c, event, page_width, page_height, page_num + 1, page_count, total)

            for col in range(CONTINGENCY_COLUMNS):
                col_x = CONTINGENCY_MARGIN + col * (column_width + CONTINGENCY_COLUMN_GAP)
                for row in range(rows_per_column):
                    if guest_index >= total:
                        break
                    guest = guests_alphabetical[guest_index]
                    row_y = (
                        page_height
                        - CONTINGENCY_HEADER_HEIGHT
                        - CONTINGENCY_MARGIN
                        - (row + 1) * CONTINGENCY_ROW_HEIGHT
                    )
                    _draw_contingency_row(c, col_x, row_y, column_width, guest, guest_index)
                    guest_index += 1

            _draw_signature_footer(c, page_width, CONTINGENCY_MARGIN)
            c.showPage()

        c.save()
        return output_path
    except Exception as exc:  # noqa: BLE001
        raise PDFGenerationError(f"Falha ao gerar PDF de contingência: {exc}") from exc


def _draw_contingency_row(c, x, y, width, guest, index):
    # Zebra striping leve para facilitar a leitura em listas longas
    if index % 2 == 0:
        c.setFillColor(colors.HexColor("#F2F4F7"))
        c.rect(x, y - 1.5 * mm, width, CONTINGENCY_ROW_HEIGHT, stroke=0, fill=1)

    name = guest.get("full_name") or ""
    table_label = guest.get("table_number") or config.DEFAULT_TABLE_LABEL

    c.setFont("Helvetica-Bold", 9)
    table_width = c.stringWidth(table_label, "Helvetica-Bold", 9) + 2 * mm
    max_name_width = width - table_width - 2 * mm

    c.setFont("Helvetica", 9.5)
    while c.stringWidth(name, "Helvetica", 9.5) > max_name_width and len(name) > 3:
        name = name[:-2] + "…"

    c.setFillColor(colors.HexColor("#1F2937"))
    c.drawString(x + 1 * mm, y, name)

    c.setFillColor(PRIMARY_COLOR)
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(x + width - 1 * mm, y, table_label)


def _draw_contingency_header(c, event, page_width, page_height, page_num, page_count, total_guests):
    c.setFillColor(PRIMARY_COLOR)
    c.rect(0, page_height - 18 * mm, page_width, 18 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(CONTINGENCY_MARGIN, page_height - 8 * mm, f"LISTA DE CONTINGÊNCIA: {event['name']}")
    c.setFont("Helvetica", 8.5)
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.drawString(
        CONTINGENCY_MARGIN,
        page_height - 13 * mm,
        f"Ordem alfabética  ·  {total_guests} convidados  ·  Gerado em {generated_at}",
    )
    c.setFont("Helvetica", 8)
    c.drawRightString(
        page_width - CONTINGENCY_MARGIN, page_height - 8 * mm, f"Página {page_num}/{page_count}"
    )
