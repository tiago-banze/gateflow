"""
email_service.py
Motor de notificacoes transacionais por e-mail (Fase 5, Pilar 4).

Servico de SMTP simples e robusto: nunca lanca excecao para o chamador
em caso de falha de envio (e-mail e um "melhor esforco", nunca deve
derrubar um fluxo critico como a confirmacao de um pagamento M-Pesa) --
falhas sao logadas e reportadas via retorno (ok: bool, error: str|None).

Configuracao via variaveis de ambiente (ver .env.example):
    SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_USE_TLS,
    SMTP_FROM_ADDRESS, SMTP_FROM_NAME
"""

import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("gateflow.email")


class EmailNotConfiguredError(Exception):
    """SMTP nao foi configurado (sem SMTP_HOST) -- nao e um erro de envio, so ausencia de config."""
    pass


def _get_smtp_config():
    host = os.environ.get("SMTP_HOST")
    if not host:
        return None
    return {
        "host": host,
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "username": os.environ.get("SMTP_USERNAME"),
        "password": os.environ.get("SMTP_PASSWORD"),
        "use_tls": os.environ.get("SMTP_USE_TLS", "true").strip().lower() != "false",
        "from_address": os.environ.get("SMTP_FROM_ADDRESS", "bilhetes@gateflow.co.mz"),
        "from_name": os.environ.get("SMTP_FROM_NAME", "GateFlow"),
    }


def is_configured():
    return _get_smtp_config() is not None


def send_email(to_address, subject, body_text, attachments=None):
    """
    Envia um e-mail transacional simples.

    `attachments` (opcional): lista de tuplas (filename, bytes, mimetype)
    ex: [("bilhetes.pdf", pdf_bytes, "application/pdf")]

    Retorna (ok: bool, error: str|None). NUNCA lanca excecao.
    """
    cfg = _get_smtp_config()
    if not cfg:
        logger.info("SMTP nao configurado (SMTP_HOST ausente) -- e-mail para %s NAO enviado.", to_address)
        return False, "SMTP nao configurado."

    if not to_address:
        return False, "Endereco de destino ausente."

    try:
        msg = MIMEMultipart()
        msg["From"] = f"{cfg['from_name']} <{cfg['from_address']}>"
        msg["To"] = to_address
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

        for filename, content_bytes, mimetype in (attachments or []):
            part = MIMEApplication(content_bytes, Name=filename)
            part["Content-Disposition"] = f'attachment; filename="{filename}"'
            msg.attach(part)

        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as server:
            if cfg["use_tls"]:
                server.starttls()
            if cfg["username"] and cfg["password"]:
                server.login(cfg["username"], cfg["password"])
            server.sendmail(cfg["from_address"], [to_address], msg.as_string())

        logger.info("E-mail enviado para %s: %s", to_address, subject)
        return True, None
    except Exception as exc:  # noqa: BLE001 - e-mail nunca pode derrubar o fluxo que o chamou
        logger.warning("Falha ao enviar e-mail para %s: %s", to_address, exc)
        return False, str(exc)


def send_ticket_email(to_address, buyer_name, event_name, order_code, pdf_path):
    """Envia o e-mail de confirmacao de compra com o PDF dos bilhetes em anexo (Modelo B, pos-pagamento M-Pesa)."""
    subject = f"Os seus bilhetes: {event_name}"
    body = (
        f"Ola {buyer_name},\n\n"
        f"O pagamento do seu pedido {order_code} foi confirmado com sucesso.\n"
        f"Os seus bilhetes para {event_name} estao em anexo neste e-mail, em PDF.\n\n"
        f"Apresente o QR Code de cada bilhete na entrada do evento.\n\n"
        f"Bom evento!\nEquipa GateFlow"
    )
    attachments = None
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            attachments = [(os.path.basename(pdf_path), f.read(), "application/pdf")]
    return send_email(to_address, subject, body, attachments)


def send_courtesy_invite_email(to_address, guest_name, event_name, pdf_path):
    """Envia o e-mail com o convite de Cortesia/VIP em PDF (Modelo A)."""
    subject = f"O seu convite: {event_name}"
    body = (
        f"Ola {guest_name},\n\n"
        f"Voce recebeu um convite de cortesia para {event_name}.\n"
        f"O seu convite com QR Code esta em anexo, em PDF.\n\n"
        f"Apresente o QR Code na entrada do evento.\n\n"
        f"Ate la!\nEquipa GateFlow"
    )
    attachments = None
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            attachments = [(os.path.basename(pdf_path), f.read(), "application/pdf")]
    return send_email(to_address, subject, body, attachments)


def send_rsvp_invite_email(to_address, guest_name, event_name, rsvp_url):
    """Envia o e-mail de convite com o link pessoal de confirmação de presença (RSVP)."""
    subject = f"Confirme a sua presença: {event_name}"
    body = (
        f"Ola {guest_name},\n\n"
        f"Voce esta convidado(a) para {event_name}.\n"
        f"Por favor confirme a sua presenca (e quantos acompanhantes vai levar) atraves do link abaixo:\n\n"
        f"{rsvp_url}\n\n"
        f"Aguardamos a sua resposta!\nEquipa GateFlow"
    )
    return send_email(to_address, subject, body)


def send_rsvp_reminder_email(to_address, guest_name, event_name, event_date_label, maps_url, qr_path):
    """Envia o lembrete do dia do evento, com o QR Code de acesso em anexo."""
    subject = f"Está quase na hora: {event_name}"
    body = (
        f"Ola {guest_name},\n\n"
        f"Um lembrete de que {event_name} sera {event_date_label}.\n"
        + (f"Localizacao: {maps_url}\n" if maps_url else "")
        + f"O seu QR Code de acesso esta em anexo -- apresente-o na entrada.\n\n"
        f"Ate la!\nEquipa GateFlow"
    )
    attachments = None
    if qr_path and os.path.exists(qr_path):
        with open(qr_path, "rb") as f:
            attachments = [(os.path.basename(qr_path), f.read(), "image/png")]
    return send_email(to_address, subject, body, attachments)
