"""
qrcode_utils.py
Geração de imagens de QR Code para os convidados. Cada QR Code contém
apenas o UUID único do convidado (não dados pessoais), garantindo que a
validação no check-in seja feita sempre consultando o banco de dados.
"""

import os

import qrcode
from qrcode.constants import ERROR_CORRECT_M

import config


class QRCodeGenerationError(Exception):
    pass


def generate_guest_qrcode(event_id, guest_id):
    """
    Gera e salva a imagem PNG do QR Code de um convidado em:
    data/qrcodes/<event_id>/<guest_id>.png

    O conteúdo codificado é o próprio UUID do convidado, prefixado para
    evitar colisão com QR Codes de outros contextos que porventura sejam
    lidos pela câmera (ex: QR Codes de propaganda no ambiente do evento).

    Retorna o caminho absoluto do arquivo gerado.
    """
    try:
        event_dir = os.path.join(config.QRCODES_DIR, event_id)
        os.makedirs(event_dir, exist_ok=True)

        payload = f"CHECKIN:{guest_id}"

        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(payload)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#000000", back_color="#FFFFFF")

        file_path = os.path.join(event_dir, f"{guest_id}.png")
        img.save(file_path)
        return file_path
    except Exception as exc:  # noqa: BLE001 - queremos capturar qualquer falha de geração
        raise QRCodeGenerationError(
            f"Falha ao gerar QR Code para o convidado {guest_id}: {exc}"
        ) from exc


def extract_guest_id_from_payload(raw_value):
    """
    Recebe o texto bruto lido pela câmera/scanner e extrai o UUID do
    convidado, validando o prefixo esperado. Retorna None se o formato
    for inválido (ex: QR Code de outro contexto, não relacionado ao sistema).
    """
    if not raw_value:
        return None
    raw_value = raw_value.strip()
    prefix = "CHECKIN:"
    if not raw_value.startswith(prefix):
        return None
    guest_id = raw_value[len(prefix):].strip()
    return guest_id or None
