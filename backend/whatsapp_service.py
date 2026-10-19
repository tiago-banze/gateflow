"""
whatsapp_service.py
Envio REAL de mensagens WhatsApp (convites e lembretes).

Providers (variável WHATSAPP_PROVIDER; se vazia, deteta pelas credenciais):

  meta     WhatsApp Business Cloud API (Meta).
           WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID
           Opcional: WHATSAPP_TEMPLATE_INVITE / WHATSAPP_TEMPLATE_REMINDER
           (nome dos templates aprovados na Meta) e WHATSAPP_TEMPLATE_LANG
           (por omissão "pt_PT").
           IMPORTANTE: a Meta só permite texto livre dentro de 24h depois de
           o contacto lhe escrever. Para iniciar conversa (convites) é
           obrigatório um TEMPLATE aprovado. Os templates recebem, por
           ordem, estes parâmetros de corpo:
             convite : {{1}} nome, {{2}} evento, {{3}} link de confirmação
             lembrete: {{1}} nome, {{2}} evento, {{3}} data/hora, {{4}} link do QR Code
  twilio   TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM
           (ex: "whatsapp:+14155238886"). Sandbox ou número aprovado.
  console  APENAS desenvolvimento: escreve no log e conta como enviado.

Sem credenciais devolve (False, "WhatsApp não configurado") para o sistema
cair no canal seguinte (SMS/e-mail). Nenhuma função lança exceção.
"""

import logging
import os

import requests

logger = logging.getLogger("gateflow.whatsapp")

HTTP_TIMEOUT_SECONDS = 8
META_GRAPH_VERSION = "v20.0"


def _env(name):
    return (os.environ.get(name) or "").strip()


def get_active_provider_name():
    explicit = _env("WHATSAPP_PROVIDER").lower()
    if explicit:
        return explicit
    if _env("WHATSAPP_TOKEN") and _env("WHATSAPP_PHONE_NUMBER_ID"):
        return "meta"
    if _env("TWILIO_ACCOUNT_SID") and _env("TWILIO_AUTH_TOKEN") and _env("TWILIO_WHATSAPP_FROM"):
        return "twilio"
    return ""


def is_configured():
    return get_active_provider_name() in PROVIDERS


def _send_via_console(to_msisdn, message, template=None):
    logger.info("[WHATSAPP-CONSOLE] Para +%s: %s", to_msisdn, message)
    return True, None


def _send_via_meta(to_msisdn, message, template=None):
    token, phone_id = _env("WHATSAPP_TOKEN"), _env("WHATSAPP_PHONE_NUMBER_ID")
    if not token or not phone_id:
        return False, "Credenciais WhatsApp (Meta) em falta."

    if template and template.get("name"):
        body = {
            "messaging_product": "whatsapp",
            "to": to_msisdn,
            "type": "template",
            "template": {
                "name": template["name"],
                "language": {"code": _env("WHATSAPP_TEMPLATE_LANG") or "pt_PT"},
                "components": [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(p)} for p in template.get("params", [])],
                }],
            },
        }
    else:
        body = {
            "messaging_product": "whatsapp",
            "to": to_msisdn,
            "type": "text",
            "text": {"body": message, "preview_url": True},
        }

    response = requests.post(
        f"https://graph.facebook.com/{META_GRAPH_VERSION}/{phone_id}/messages",
        json=body, headers={"Authorization": f"Bearer {token}"}, timeout=HTTP_TIMEOUT_SECONDS,
    )
    if response.status_code in (200, 201):
        return True, None
    try:
        detail = response.json().get("error", {}).get("message", response.text[:200])
    except ValueError:
        detail = response.text[:200]
    return False, f"WhatsApp {response.status_code}: {detail}"


def _send_via_twilio(to_msisdn, message, template=None):
    sid, token = _env("TWILIO_ACCOUNT_SID"), _env("TWILIO_AUTH_TOKEN")
    sender = _env("TWILIO_WHATSAPP_FROM")
    if not sid or not token or not sender:
        return False, "Credenciais Twilio WhatsApp em falta."
    if not sender.startswith("whatsapp:"):
        sender = f"whatsapp:{sender}"
    response = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        data={"To": f"whatsapp:+{to_msisdn}", "From": sender, "Body": message},
        auth=(sid, token), timeout=HTTP_TIMEOUT_SECONDS,
    )
    if response.status_code in (200, 201):
        return True, None
    try:
        detail = response.json().get("message", response.text[:200])
    except ValueError:
        detail = response.text[:200]
    return False, f"Twilio WhatsApp {response.status_code}: {detail}"


PROVIDERS = {
    "console": _send_via_console,
    "meta": _send_via_meta,
    "twilio": _send_via_twilio,
}


def send_whatsapp(to_msisdn, message, template=None):
    """Envia uma mensagem WhatsApp. Devolve (ok, erro). Nunca lança exceção."""
    provider_name = get_active_provider_name()
    provider_fn = PROVIDERS.get(provider_name)
    if not provider_fn:
        return False, "WhatsApp não configurado."
    try:
        return provider_fn(to_msisdn, message, template=template)
    except requests.RequestException as exc:
        logger.warning("Falha de rede ao enviar WhatsApp via %s: %s", provider_name, exc)
        return False, "Falha de ligação ao serviço de WhatsApp."
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao enviar WhatsApp via %s: %s", provider_name, exc)
        return False, str(exc)[:200]


def send_rsvp_invite_whatsapp(to_msisdn, guest_name, event_name, rsvp_url):
    message = (
        f"Olá {guest_name}! Você está convidado(a) para *{event_name}*.\n"
        f"Confirme a sua presença aqui: {rsvp_url}\n"
        f'Também pode responder neste chat: envie "1" para confirmar ou "2" para recusar.'
    )
    template = None
    if _env("WHATSAPP_TEMPLATE_INVITE"):
        template = {"name": _env("WHATSAPP_TEMPLATE_INVITE"), "params": [guest_name, event_name, rsvp_url]}
    return send_whatsapp(to_msisdn, message, template=template)


def send_rsvp_reminder_whatsapp(to_msisdn, guest_name, event_name, event_date_label, maps_url, qr_url):
    message = (
        f"Olá {guest_name}! Está quase na hora de *{event_name}*.\n"
        f"Horário: {event_date_label}\n"
        + (f"Localização: {maps_url}\n" if maps_url else "")
        + f"O seu QR Code de acesso: {qr_url}\n"
        f"Apresente este código na entrada. Até lá!"
    )
    template = None
    if _env("WHATSAPP_TEMPLATE_REMINDER"):
        template = {
            "name": _env("WHATSAPP_TEMPLATE_REMINDER"),
            "params": [guest_name, event_name, event_date_label, qr_url],
        }
    return send_whatsapp(to_msisdn, message, template=template)
