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
import ticket_security

# Layout da grade: 2 colunas x 4 linhas por página (8 convites por página)
COLUMNS = 2
ROWS = 4
MARGIN = 15 * mm
CARD_SPACING = 6 * mm

PRIMARY_COLOR = colors.HexColor(config.COLOR_PRIMARY)

# Assinatura do Administrador, aplicada no rodapé de TODAS as páginas de
# TODOS os PDFs gerados (convites e contingência), como marca de
# autenticidade do documento. Se o arquivo não existir, simplesmente não
# desenha nada — nunca quebra a geração do PDF por causa disso.
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
    disco) -- mesmo padrão já usado para bilhetes em
    `_generate_ticket_qr_image` logo abaixo. Não depender de um arquivo
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


def _draw_card(c, x, y, card_width, card_height, guest, qr_image_path):
    """Desenha um único cartão de convite (nome + cargo + QR Code) no PDF."""
    # Moldura do cartão
    c.setStrokeColor(PRIMARY_COLOR)
    c.setLineWidth(1)
    c.roundRect(x, y, card_width, card_height, 4 * mm, stroke=1, fill=0)

    padding = 5 * mm
    qr_size = card_height - (2 * padding)

    # QR Code do lado esquerdo do cartão -- gerado em memória a partir
    # do guest_id (ver _generate_guest_qr_image acima), nunca lido de
    # disco: assim funciona igual em desenvolvimento local e em produção
    # serverless, e nunca sai "faltando" por um arquivo que não existe
    # mais nesta instância.
    try:
        qr_buffer = _generate_guest_qr_image(guest["id"])
        qr_img = ImageReader(qr_buffer)
        c.drawImage(
            qr_img,
            x + padding,
            y + padding,
            width=qr_size,
            height=qr_size,
            preserveAspectRatio=True,
        )
    except Exception:
        # Se a imagem falhar por qualquer motivo, seguimos sem travar o PDF inteiro
        pass

    # Textos à direita do QR Code
    text_x = x + padding + qr_size + (4 * mm)
    text_max_width = card_width - (text_x - x) - padding

    c.setFillColor(PRIMARY_COLOR)
    c.setFont("Helvetica-Bold", 12)
    name_lines = _wrap_text(c, guest["full_name"], "Helvetica-Bold", 12, text_max_width)
    text_y = y + card_height - padding - 12
    for line in name_lines[:2]:
        c.drawString(text_x, text_y, line)
        text_y -= 14

    # Mesa: destacada em negrito, logo abaixo do nome, para ser fácil de
    # ler rapidamente na entrada (casamentos, jantares de gala, etc.)
    text_y -= 3
    c.setFillColor(PRIMARY_COLOR)
    c.setFont("Helvetica-Bold", 11)
    table_label = guest.get("table_number") or config.DEFAULT_TABLE_LABEL
    c.drawString(text_x, text_y, f"Mesa: {table_label}")

    c.setFillColor(colors.HexColor("#555555"))
    c.setFont("Helvetica", 10)
    role_text = guest.get("role") or "Convidado"
    c.drawString(text_x, y + padding + 4, role_text)


def _wrap_text(c, text, font_name, font_size, max_width):
    """Quebra o texto em múltiplas linhas para caber na largura do cartão."""
    words = text.split()
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
    return lines


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
                    _draw_card(c, x, y, card_width, card_height, guest, qr_path)
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
        subtitle = f"{subtitle}  |  {event['event_date']}" if subtitle else event["event_date"]
    c.drawString(MARGIN, page_height - 16.5 * mm, subtitle)
    c.setFont("Helvetica", 8)
    c.drawRightString(
        page_width - MARGIN, page_height - 12 * mm, f"Página {page_num}/{page_count}"
    )


# --------------------------------------------------------------------------
# PDF DE CONTINGÊNCIA — plano de emergência offline
# --------------------------------------------------------------------------

CONTINGENCY_MARGIN = 15 * mm
CONTINGENCY_HEADER_HEIGHT = 22 * mm
CONTINGENCY_COLUMNS = 2
CONTINGENCY_ROW_HEIGHT = 6.5 * mm
CONTINGENCY_COLUMN_GAP = 10 * mm


def generate_contingency_pdf(event, guests_alphabetical):
    """
    Gera um PDF minimalista de contingência: lista em ORDEM ALFABÉTICA
    contendo apenas Nome e Mesa de cada convidado — sem QR Code, sem
    dados de contato — pronto para imprimir rapidamente e permitir
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


# --------------------------------------------------------------------------
# FASE 3 — PDF FÍSICO DE BILHETES (grid com marcas de corte)
# --------------------------------------------------------------------------

TICKET_COLUMNS = 2
TICKET_ROWS = 4
TICKET_MARGIN = 12 * mm
TICKET_SPACING = 6 * mm
TICKET_VIP_COLOR = colors.HexColor("#B8860B")  # dourado — destaque visual do setor VIP
TICKET_NORMAL_COLOR = colors.HexColor("#004E92")


def _generate_ticket_qr_image(ticket_id, signature):
    """Gera a imagem do QR Code de UM bilhete em memória (sem salvar em disco)."""
    payload = ticket_security.build_ticket_qr_payload(ticket_id, signature)
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M, box_size=10, border=3)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#000000", back_color="#FFFFFF")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def generate_tickets_pdf(event, batch, tickets):
    """
    Gera o PDF físico dos bilhetes de um lote: grid 2x4 por página A4,
    com linhas pontilhadas de guia de corte entre os bilhetes, cada um
    com Nome do Evento, Organizador, tipo em destaque ([VIP]/[NORMAL]),
    ID único e QR Code com a assinatura criptográfica anti-fraude.
    """
    try:
        os.makedirs(config.EXPORTS_DIR, exist_ok=True)
        output_path = os.path.join(config.EXPORTS_DIR, f"{batch['id']}_bilhetes.pdf")

        page_width, page_height = A4
        header_height = 16 * mm
        usable_width = page_width - (2 * TICKET_MARGIN)
        usable_height = page_height - (2 * TICKET_MARGIN) - header_height

        cell_width = (usable_width - (TICKET_SPACING * (TICKET_COLUMNS - 1))) / TICKET_COLUMNS
        cell_height = (usable_height - (TICKET_SPACING * (TICKET_ROWS - 1))) / TICKET_ROWS

        c = canvas.Canvas(output_path, pagesize=A4)

        per_page = TICKET_COLUMNS * TICKET_ROWS
        total_tickets = len(tickets)
        page_count = max(1, -(-total_tickets // per_page))

        ticket_index = 0
        for page_num in range(page_count):
            _draw_ticket_page_header(c, event, page_width, page_height, page_num + 1, page_count, total_tickets)

            for row in range(TICKET_ROWS):
                for col in range(TICKET_COLUMNS):
                    if ticket_index >= total_tickets:
                        break
                    ticket = tickets[ticket_index]
                    x = TICKET_MARGIN + col * (cell_width + TICKET_SPACING)
                    y = (
                        page_height
                        - TICKET_MARGIN
                        - header_height
                        - (row + 1) * cell_height
                        - row * TICKET_SPACING
                    )
                    _draw_ticket_cell(c, x, y, cell_width, cell_height, event, ticket)
                    ticket_index += 1

            _draw_ticket_crop_marks(c, page_width, page_height, header_height)
            _draw_signature_footer(c, page_width, TICKET_MARGIN)
            c.showPage()

        c.save()
        return output_path
    except Exception as exc:  # noqa: BLE001
        raise PDFGenerationError(f"Falha ao gerar PDF de bilhetes: {exc}") from exc


def _draw_ticket_page_header(c, event, page_width, page_height, page_num, page_count, total_tickets):
    c.setFillColor(PRIMARY_COLOR)
    c.rect(0, page_height - 14 * mm, page_width, 14 * mm, stroke=0, fill=1)
    logo_path = os.path.join(config.BASE_DIR, "assets", "GateFlow.png")
    text_x = TICKET_MARGIN
    if os.path.exists(logo_path):
        try:
            logo_h = 9 * mm
            reader = ImageReader(logo_path)
            logo_w = reader.getSize()[0] / reader.getSize()[1] * logo_h
            c.drawImage(reader, TICKET_MARGIN, page_height - 11.5 * mm, width=logo_w, height=logo_h,
                        preserveAspectRatio=True, mask="auto")
            text_x = TICKET_MARGIN + logo_w + 3 * mm
        except Exception:  # noqa: BLE001 - logo ausente/corrompida nunca deve quebrar a emissão do bilhete
            pass
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(text_x, page_height - 9 * mm, f"BILHETES: {event['name']}")
    c.setFont("Helvetica", 8)
    c.drawRightString(
        page_width - TICKET_MARGIN, page_height - 9 * mm,
        f"{total_tickets} bilhete(s)  .  Página {page_num}/{page_count}",
    )


def _draw_ticket_cell(c, x, y, width, height, event, ticket):
    is_vip = ticket["ticket_type"] == "VIP"
    accent_color = TICKET_VIP_COLOR if is_vip else TICKET_NORMAL_COLOR

    # Borda pontilhada (guia de corte) delimitando CADA bilhete individualmente
    c.setDash(3, 2)
    c.setStrokeColor(colors.HexColor("#AAAAAA"))
    c.setLineWidth(0.75)
    c.rect(x, y, width, height, stroke=1, fill=0)
    c.setDash()  # volta para linha sólida nos elementos seguintes

    padding = 4 * mm
    qr_size = height - (2 * padding)

    ticket_buffer = _generate_ticket_qr_image(ticket["id"], ticket["signature"])
    qr_image = ImageReader(ticket_buffer)
    c.drawImage(qr_image, x + padding, y + padding, width=qr_size, height=qr_size, preserveAspectRatio=True)

    text_x = x + padding + qr_size + (4 * mm)
    text_max_width = width - (text_x - x) - padding
    text_y = y + height - padding - 10

    # Tipo do bilhete em destaque visual, bem grande e na cor do setor
    c.setFillColor(accent_color)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(text_x, text_y, f"[ {ticket['ticket_type']} ]")
    text_y -= 16

    # Nome do evento (quebra em até 2 linhas se necessário)
    c.setFillColor(colors.HexColor("#1F2937"))
    c.setFont("Helvetica-Bold", 10)
    for line in _wrap_text(c, event["name"], "Helvetica-Bold", 10, text_max_width)[:2]:
        c.drawString(text_x, text_y, line)
        text_y -= 12

    # Nome do Organizador/Empresa
    c.setFillColor(colors.HexColor("#555555"))
    c.setFont("Helvetica", 8.5)
    organizer_name = event.get("organizer_display_name") or ""
    for line in _wrap_text(c, organizer_name, "Helvetica", 8.5, text_max_width)[:1]:
        c.drawString(text_x, text_y, line)
    text_y -= 12

    # ID único do bilhete (curto, só os primeiros 8 caracteres, para caber e ainda ser rastreável)
    c.setFillColor(colors.HexColor("#999999"))
    c.setFont("Helvetica", 7)
    short_id = ticket["id"][:8].upper()
    c.drawString(text_x, y + padding, f"ID: {short_id}")


def _draw_ticket_crop_marks(c, page_width, page_height, header_height):
    """
    Desenha marcas de corte (crop marks) nas bordas externas da grade —
    pequenos traços fora da área impressa, no padrão gráfico usado para
    guiar o corte físico com tesoura/guilhotina.
    """
    mark_length = 3 * mm
    c.setStrokeColor(colors.HexColor("#888888"))
    c.setLineWidth(0.5)

    usable_width = page_width - (2 * TICKET_MARGIN)
    usable_height = page_height - (2 * TICKET_MARGIN) - header_height
    cell_width = (usable_width - (TICKET_SPACING * (TICKET_COLUMNS - 1))) / TICKET_COLUMNS
    cell_height = (usable_height - (TICKET_SPACING * (TICKET_ROWS - 1))) / TICKET_ROWS

    # Marcas verticais no topo/base de cada coluna
    for col in range(TICKET_COLUMNS + 1):
        x = TICKET_MARGIN + col * (cell_width + TICKET_SPACING)
        if col == TICKET_COLUMNS:
            x = TICKET_MARGIN + TICKET_COLUMNS * cell_width + (TICKET_COLUMNS - 1) * TICKET_SPACING
        c.line(x, page_height - TICKET_MARGIN - header_height + mark_length, x, page_height - TICKET_MARGIN - header_height)
        c.line(x, TICKET_MARGIN, x, TICKET_MARGIN - mark_length)


def _wrap_text(c, text, font_name, font_size, max_width):
    """Quebra o texto em múltiplas linhas para caber na largura disponível."""
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


# --------------------------------------------------------------------------
# FASE 5 - RELATORIO FINANCEIRO (PDF)
# --------------------------------------------------------------------------

def generate_financial_report_pdf(event, summary, transactions):
    """Gera o relatorio financeiro em PDF de um evento: resumo (bruto, taxa, liquido) e tabela de transacoes M-Pesa."""
    try:
        os.makedirs(config.EXPORTS_DIR, exist_ok=True)
        output_path = os.path.join(config.EXPORTS_DIR, f"{event['id']}_financeiro.pdf")
        page_width, page_height = A4
        margin = 15 * mm
        c = canvas.Canvas(output_path, pagesize=A4)

        c.setFillColor(PRIMARY_COLOR)
        c.rect(0, page_height - 20 * mm, page_width, 20 * mm, stroke=0, fill=1)
        logo_path = os.path.join(config.BASE_DIR, "assets", "GateFlow.png")
        text_x = margin
        if os.path.exists(logo_path):
            try:
                logo_h = 11 * mm
                reader = ImageReader(logo_path)
                logo_w = reader.getSize()[0] / reader.getSize()[1] * logo_h
                c.drawImage(reader, margin, page_height - 15.5 * mm, width=logo_w, height=logo_h,
                            preserveAspectRatio=True, mask="auto")
                text_x = margin + logo_w + 4 * mm
            except Exception:  # noqa: BLE001
                pass
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(text_x, page_height - 12 * mm, "Relatorio Financeiro")
        c.setFont("Helvetica", 9)
        c.drawString(text_x, page_height - 17 * mm, event["name"])

        y = page_height - 30 * mm
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, y, "Resumo")
        y -= 7 * mm

        rows = [
            ("Receita Bruta (total cobrado dos compradores)", f"{summary['gross_revenue']:.2f} MT"),
            ("Taxa de Servico GateFlow (5%)", f"{summary['platform_fee']:.2f} MT"),
            ("Valor Liquido do Organizador", f"{summary['net_organizer']:.2f} MT"),
            ("Pedidos Pagos", str(summary["paid_orders_count"])),
            ("Bilhetes Vendidos", str(summary["tickets_sold"])),
        ]
        c.setFont("Helvetica", 10)
        for label, value in rows:
            c.drawString(margin, y, label)
            c.drawRightString(page_width - margin, y, value)
            y -= 6 * mm

        y -= 6 * mm
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, y, "Transacoes M-Pesa")
        y -= 7 * mm

        col_x = [margin, margin + 32 * mm, margin + 62 * mm, margin + 92 * mm, margin + 122 * mm]
        headers = ["Pedido", "Comprador", "MSISDN", "Valor", "Estado"]
        c.setFont("Helvetica-Bold", 8)
        for header, x in zip(headers, col_x):
            c.drawString(x, y, header)
        y -= 4.5 * mm
        c.line(margin, y, page_width - margin, y)
        y -= 4 * mm

        c.setFont("Helvetica", 8)
        for tx in transactions:
            if y < margin + 10 * mm:
                c.showPage()
                y = page_height - margin
            c.drawString(col_x[0], y, str(tx.get("order_code") or "")[:16])
            c.drawString(col_x[1], y, str(tx.get("buyer_name") or "")[:18])
            c.drawString(col_x[2], y, str(tx.get("customer_msisdn") or "-"))
            c.drawString(col_x[3], y, f"{tx.get('total_amount', 0):.2f} MT")
            c.drawString(col_x[4], y, str(tx.get("order_status") or ""))
            y -= 5.5 * mm

        c.setFont("Helvetica-Oblique", 7)
        c.setFillColor(colors.grey)
        c.drawString(margin, margin, f"Gerado em {datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')} por GateFlow")

        c.save()
        return output_path
    except Exception as exc:  # noqa: BLE001
        raise PDFGenerationError(f"Falha ao gerar relatorio financeiro: {exc}") from exc
