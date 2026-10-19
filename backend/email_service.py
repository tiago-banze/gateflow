"""
email_service.py
Envio REAL de e-mails transacionais (convites, lembretes, cortesias).

Providers (EMAIL_PROVIDER; se vazio, deteta pelas credenciais):

  resend  RESEND_API_KEY  (API HTTPS -- a opção mais simples na Vercel)
  smtp    SMTP_HOST, SMTP_PORT (587), SMTP_USERNAME, SMTP_PASSWORD,
          SMTP_USE_TLS (true)

Remetente: EMAIL_FROM_ADDRESS (ou SMTP_FROM_ADDRESS) e EMAIL_FROM_NAME
(por omissão "GateFlow"). Sem provider configurado, send_email() devolve
(False, "E-mail não configurado") -- nunca finge que enviou.
Nenhuma função lança exceção.
"""

import base64
import html
import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

logger = logging.getLogger("gateflow.email")

HTTP_TIMEOUT_SECONDS = 10
SMTP_TIMEOUT_SECONDS = 10


def _env(name, default=""):
    return (os.environ.get(name) or default).strip()


def get_active_provider_name():
    explicit = _env("EMAIL_PROVIDER").lower()
    if explicit in ("resend", "smtp"):
        return explicit
    if _env("RESEND_API_KEY"):
        return "resend"
    if _env("SMTP_HOST"):
        return "smtp"
    return ""


def is_configured():
    return bool(get_active_provider_name())


def _sender():
    address = _env("EMAIL_FROM_ADDRESS") or _env("SMTP_FROM_ADDRESS") or _env("SMTP_USERNAME") or "convites@gateflow.app"
    name = _env("EMAIL_FROM_NAME") or _env("SMTP_FROM_NAME") or "GateFlow"
    return name, address


def _send_via_resend(to_address, subject, body_text, body_html, attachments):
    name, address = _sender()
    payload = {
        "from": f"{name} <{address}>",
        "to": [to_address],
        "subject": subject,
        "text": body_text,
    }
    if body_html:
        payload["html"] = body_html
    if attachments:
        payload["attachments"] = [
            {"filename": filename, "content": base64.b64encode(content).decode("ascii")}
            for filename, content, _mimetype in attachments
        ]
    response = requests.post(
        "https://api.resend.com/emails", json=payload,
        headers={"Authorization": f"Bearer {_env('RESEND_API_KEY')}"}, timeout=HTTP_TIMEOUT_SECONDS,
    )
    if response.status_code in (200, 201):
        return True, None
    return False, f"Resend {response.status_code}: {response.text[:200]}"


def _send_via_smtp(to_address, subject, body_text, body_html, attachments):
    name, address = _sender()
    host = _env("SMTP_HOST")
    port = int(_env("SMTP_PORT", "587"))
    use_tls = _env("SMTP_USE_TLS", "true").lower() != "false"

    msg = MIMEMultipart("mixed")
    msg["From"] = f"{name} <{address}>"
    msg["To"] = to_address
    msg["Subject"] = subject
    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        alternative.attach(MIMEText(body_html, "html", "utf-8"))
    msg.attach(alternative)
    for filename, content, _mimetype in (attachments or []):
        part = MIMEApplication(content, Name=filename)
        part["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(part)

    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=SMTP_TIMEOUT_SECONDS)
    else:
        server = smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT_SECONDS)
    with server:
        if port != 465 and use_tls:
            server.starttls()
        if _env("SMTP_USERNAME") and _env("SMTP_PASSWORD"):
            server.login(_env("SMTP_USERNAME"), _env("SMTP_PASSWORD"))
        server.sendmail(address, [to_address], msg.as_string())
    return True, None


def send_email(to_address, subject, body_text, attachments=None, body_html=None):
    """
    Envia um e-mail. `attachments`: lista de (nome, bytes, mimetype).
    Devolve (ok, erro). Nunca lança exceção.
    """
    provider = get_active_provider_name()
    if not provider:
        return False, "E-mail não configurado."
    if not to_address:
        return False, "Endereço de e-mail em falta."
    try:
        if provider == "resend":
            ok, error = _send_via_resend(to_address, subject, body_text, body_html, attachments)
        else:
            ok, error = _send_via_smtp(to_address, subject, body_text, body_html, attachments)
        if ok:
            logger.info("E-mail enviado para %s (%s): %s", to_address, provider, subject)
        else:
            logger.warning("E-mail para %s falhou (%s): %s", to_address, provider, error)
        return ok, error
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao enviar e-mail para %s via %s: %s", to_address, provider, exc)
        return False, str(exc)[:200]


# --------------------------------------------------------------------------
# Modelos de mensagem
# --------------------------------------------------------------------------

def _html_layout(title, intro_html, button_label=None, button_url=None, footer_html=""):
    button = ""
    if button_label and button_url:
        button = (
            f'<p style="margin:28px 0;"><a href="{html.escape(button_url, quote=True)}" '
            f'style="background:#0A7D5C;color:#ffffff;text-decoration:none;font-weight:700;'
            f'padding:14px 28px;border-radius:10px;display:inline-block;">{html.escape(button_label)}</a></p>'
        )
    return (
        '<div style="background:#F3F6F5;padding:24px 12px;font-family:Arial,Helvetica,sans-serif;">'
        '<div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:16px;'
        'padding:32px 28px;color:#0D1F2B;">'
        '<div style="font-size:18px;font-weight:800;color:#0A7D5C;margin-bottom:20px;">GateFlow</div>'
        f'<h1 style="font-size:22px;line-height:1.3;margin:0 0 16px;">{html.escape(title)}</h1>'
        f'<div style="font-size:15px;line-height:1.6;color:#33485A;">{intro_html}</div>'
        f"{button}"
        f'<div style="font-size:12px;color:#5B6F7D;margin-top:24px;">{footer_html}</div>'
        "</div></div>"
    )


def _read_file(path):
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            return os.path.basename(path), f.read()
    return None


def send_courtesy_invite_email(to_address, guest_name, event_name, pdf_path):
    """Convite de Cortesia/VIP em PDF (com QR Code) em anexo."""
    subject = f"O seu convite: {event_name}"
    body = (
        f"Olá {guest_name},\n\nRecebeu um convite para {event_name}.\n"
        f"O seu convite com QR Code está em anexo (PDF). Apresente o QR Code na entrada.\n\n"
        f"Até lá!\nEquipa GateFlow"
    )
    page = _html_layout(
        f"O seu convite para {event_name}",
        f"<p>Olá {html.escape(guest_name)},</p><p>O seu convite com QR Code está em anexo (PDF). "
        f"Apresente-o na entrada do evento.</p>",
    )
    attachments = None
    pdf = _read_file(pdf_path)
    if pdf:
        attachments = [(pdf[0], pdf[1], "application/pdf")]
    return send_email(to_address, subject, body, attachments, body_html=page)


def send_rsvp_invite_email(to_address, guest_name, event_name, rsvp_url):
    """Convite com o link pessoal de confirmação de presença (RSVP)."""
    subject = f"Confirme a sua presença: {event_name}"
    body = (
        f"Olá {guest_name},\n\nEstá convidado(a) para {event_name}.\n"
        f"Confirme a sua presença (e quantos acompanhantes vai levar) neste link:\n\n{rsvp_url}\n\n"
        f"Aguardamos a sua resposta!\nEquipa GateFlow"
    )
    page = _html_layout(
        f"Está convidado(a) para {event_name}",
        f"<p>Olá {html.escape(guest_name)},</p><p>Confirme a sua presença (e os acompanhantes) "
        f"no botão abaixo. Demora menos de 10 segundos.</p>",
        button_label="Confirmar presença", button_url=rsvp_url,
        footer_html=f"Se o botão não abrir, copie este link: {html.escape(rsvp_url)}",
    )
    return send_email(to_address, subject, body, body_html=page)


def send_rsvp_reminder_email(to_address, guest_name, event_name, event_date_label, maps_url, qr_png_bytes):
    """Lembrete do dia do evento, com o QR Code de acesso em anexo."""
    subject = f"Está quase na hora: {event_name}"
    body = (
        f"Olá {guest_name},\n\nLembrete: {event_name} é {event_date_label}.\n"
        + (f"Localização: {maps_url}\n" if maps_url else "")
        + "O seu QR Code de acesso está em anexo — apresente-o na entrada.\n\nAté lá!\nEquipa GateFlow"
    )
    where = (
        f'<p><a href="{html.escape(maps_url, quote=True)}">Ver localização no mapa</a></p>' if maps_url else ""
    )
    page = _html_layout(
        f"Está quase na hora: {event_name}",
        f"<p>Olá {html.escape(guest_name)},</p><p><strong>{html.escape(event_date_label)}</strong></p>{where}"
        f"<p>O seu QR Code de acesso está em anexo. Apresente-o na entrada.</p>",
    )
    attachments = [("qrcode-acesso.png", qr_png_bytes, "image/png")] if qr_png_bytes else None
    return send_email(to_address, subject, body, attachments, body_html=page)
