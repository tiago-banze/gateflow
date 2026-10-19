"""
notifications.py
Orquestra o envio de convites e lembretes aos convidados pelos canais
disponíveis, devolvendo SEMPRE o resultado verdadeiro de cada canal.

Regra de entrega:
  1. Se o convidado tem telemóvel válido: WhatsApp; se falhar -> SMS.
  2. Se tem e-mail: e-mail (em paralelo ao telemóvel).
  3. "Entregue" só quando pelo menos um canal confirmou o envio.
  4. Sem telemóvel nem e-mail -> não enviado (motivo explícito).
"""

import logging
from concurrent.futures import ThreadPoolExecutor

import email_service
import sms_service
import whatsapp_service
from qrcode_utils import generate_guest_qrcode_bytes
from text_utils import normalize_msisdn

logger = logging.getLogger("gateflow.notifications")

MAX_BATCH_SIZE = 12  # convidados por pedido (limite de tempo de uma função serverless)
BATCH_WORKERS = 6


def channel_status():
    """Estado real de cada canal, para a interface mostrar o que está ativo."""
    return {
        "whatsapp": {"configured": whatsapp_service.is_configured(), "provider": whatsapp_service.get_active_provider_name()},
        "sms": {"configured": sms_service.is_configured(), "provider": sms_service.get_active_provider_name()},
        "email": {"configured": email_service.is_configured(), "provider": email_service.get_active_provider_name()},
    }


def any_channel_configured():
    return any(c["configured"] for c in channel_status().values())


def _friendly_error(errors):
    if not errors:
        return None
    return " | ".join(f"{channel}: {message}" for channel, message in errors.items())


def _finish(sent_channels, errors):
    return {
        "delivered": bool(sent_channels),
        "channels": sent_channels,
        "errors": errors,
        "error_summary": None if sent_channels else _friendly_error(errors),
    }


def deliver_invite(guest, event_name, rsvp_url):
    """Envia o convite com o link pessoal de RSVP."""
    sent, errors = [], {}
    phone = normalize_msisdn(guest.get("phone"))
    email = (guest.get("email") or "").strip()

    if not phone and not email:
        errors["contacto"] = "Sem telemóvel nem e-mail válidos."
        return _finish(sent, errors)

    if phone:
        ok, error = whatsapp_service.send_rsvp_invite_whatsapp(phone, guest["full_name"], event_name, rsvp_url)
        if ok:
            sent.append("whatsapp")
        else:
            errors["whatsapp"] = error
            ok, error = sms_service.send_rsvp_invite_sms(phone, guest["full_name"], event_name, rsvp_url)
            if ok:
                sent.append("sms")
            else:
                errors["sms"] = error
    elif guest.get("phone"):
        errors["telemóvel"] = "Número de telemóvel inválido."

    if email:
        ok, error = email_service.send_rsvp_invite_email(email, guest["full_name"], event_name, rsvp_url)
        if ok:
            sent.append("email")
        else:
            errors["email"] = error

    return _finish(sent, errors)


def deliver_reminder(guest, event_name, date_label, maps_url, qr_url):
    """Envia o lembrete do dia (horário, localização e QR Code de acesso)."""
    sent, errors = [], {}
    phone = normalize_msisdn(guest.get("phone"))
    email = (guest.get("email") or "").strip()

    if not phone and not email:
        errors["contacto"] = "Sem telemóvel nem e-mail válidos."
        return _finish(sent, errors)

    if phone:
        ok, error = whatsapp_service.send_rsvp_reminder_whatsapp(
            phone, guest["full_name"], event_name, date_label, maps_url, qr_url
        )
        if ok:
            sent.append("whatsapp")
        else:
            errors["whatsapp"] = error
            ok, error = sms_service.send_rsvp_reminder_sms(phone, guest["full_name"], event_name, date_label, qr_url)
            if ok:
                sent.append("sms")
            else:
                errors["sms"] = error
    elif guest.get("phone"):
        errors["telemóvel"] = "Número de telemóvel inválido."

    if email:
        try:
            qr_bytes = generate_guest_qrcode_bytes(guest["id"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha ao gerar QR para e-mail do convidado %s: %s", guest["id"], exc)
            qr_bytes = None
        ok, error = email_service.send_rsvp_reminder_email(
            email, guest["full_name"], event_name, date_label, maps_url, qr_bytes
        )
        if ok:
            sent.append("email")
        else:
            errors["email"] = error

    return _finish(sent, errors)


def run_batch(guests, worker):
    """Executa `worker(guest)` em paralelo limitado; devolve lista de (guest, resultado)."""
    if not guests:
        return []
    with ThreadPoolExecutor(max_workers=min(BATCH_WORKERS, len(guests))) as pool:
        return list(zip(guests, pool.map(worker, guests)))
