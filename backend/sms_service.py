"""
sms_service.py
Envio REAL de SMS transacional (convites e lembretes).

Providers suportados (escolha com a variável SMS_PROVIDER; se não for
definida, é detetado automaticamente pelas credenciais presentes):

  twilio         TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN e
                 TWILIO_SMS_FROM (número) ou TWILIO_MESSAGING_SERVICE_SID
  africastalking AT_USERNAME, AT_API_KEY (e opcional AT_SENDER_ID).
                 Com AT_USERNAME=sandbox usa o ambiente de testes.
  console        APENAS desenvolvimento: escreve no log e conta como enviado.

Sem credenciais, is_configured() é False e send_sms() devolve
(False, "SMS não configurado") -- nunca finge que enviou.
Regra: nenhuma função lança exceção; todas devolvem (ok, erro).
"""

import logging
import os

import requests

logger = logging.getLogger("gateflow.sms")

HTTP_TIMEOUT_SECONDS = 8


def _env(name):
    return (os.environ.get(name) or "").strip()


def get_active_provider_name():
    explicit = _env("SMS_PROVIDER").lower()
    if explicit:
        return explicit
    if _env("TWILIO_ACCOUNT_SID") and _env("TWILIO_AUTH_TOKEN") and (
        _env("TWILIO_SMS_FROM") or _env("TWILIO_MESSAGING_SERVICE_SID")
    ):
        return "twilio"
    if _env("AT_USERNAME") and _env("AT_API_KEY"):
        return "africastalking"
    return ""


def is_configured():
    return get_active_provider_name() in PROVIDERS


def _send_via_console(to_msisdn, message):
    logger.info("[SMS-CONSOLE] Para +%s: %s", to_msisdn, message)
    return True, None


def _send_via_twilio(to_msisdn, message):
    sid, token = _env("TWILIO_ACCOUNT_SID"), _env("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        return False, "Credenciais Twilio em falta."
    data = {"To": f"+{to_msisdn}", "Body": message}
    if _env("TWILIO_MESSAGING_SERVICE_SID"):
        data["MessagingServiceSid"] = _env("TWILIO_MESSAGING_SERVICE_SID")
    elif _env("TWILIO_SMS_FROM"):
        data["From"] = _env("TWILIO_SMS_FROM")
    else:
        return False, "Defina TWILIO_SMS_FROM ou TWILIO_MESSAGING_SERVICE_SID."
    response = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        data=data, auth=(sid, token), timeout=HTTP_TIMEOUT_SECONDS,
    )
    if response.status_code in (200, 201):
        return True, None
    try:
        detail = response.json().get("message", response.text[:200])
    except ValueError:
        detail = response.text[:200]
    return False, f"Twilio {response.status_code}: {detail}"


def _send_via_africastalking(to_msisdn, message):
    username, api_key = _env("AT_USERNAME"), _env("AT_API_KEY")
    if not username or not api_key:
        return False, "Credenciais Africa's Talking em falta."
    base = "https://api.sandbox.africastalking.com" if username == "sandbox" else "https://api.africastalking.com"
    payload = {"username": username, "to": f"+{to_msisdn}", "message": message}
    if _env("AT_SENDER_ID"):
        payload["from"] = _env("AT_SENDER_ID")
    response = requests.post(
        f"{base}/version1/messaging",
        data=payload, timeout=HTTP_TIMEOUT_SECONDS,
        headers={"apiKey": api_key, "Accept": "application/json"},
    )
    if response.status_code not in (200, 201):
        return False, f"Africa's Talking {response.status_code}: {response.text[:200]}"
    try:
        recipients = response.json()["SMSMessageData"]["Recipients"]
    except (ValueError, KeyError, TypeError):
        return False, "Resposta inesperada do Africa's Talking."
    if recipients and str(recipients[0].get("status", "")).lower() == "success":
        return True, None
    status = recipients[0].get("status") if recipients else "sem destinatários"
    return False, f"Africa's Talking: {status}"


PROVIDERS = {
    "console": _send_via_console,
    "twilio": _send_via_twilio,
    "africastalking": _send_via_africastalking,
}


def send_sms(to_msisdn, message):
    """Envia um SMS pelo provider ativo. Devolve (ok, erro). Nunca lança exceção."""
    provider_name = get_active_provider_name()
    provider_fn = PROVIDERS.get(provider_name)
    if not provider_fn:
        return False, "SMS não configurado."
    try:
        return provider_fn(to_msisdn, message)
    except requests.RequestException as exc:
        logger.warning("Falha de rede ao enviar SMS via %s: %s", provider_name, exc)
        return False, "Falha de ligação ao serviço de SMS."
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao enviar SMS via %s: %s", provider_name, exc)
        return False, str(exc)[:200]


def send_rsvp_invite_sms(to_msisdn, guest_name, event_name, rsvp_url):
    return send_sms(to_msisdn, f"Ola {guest_name}! Convite para {event_name}. Confirme presenca: {rsvp_url}")


def send_rsvp_reminder_sms(to_msisdn, guest_name, event_name, event_date_label, qr_url):
    return send_sms(
        to_msisdn,
        f"Ola {guest_name}! {event_name} e a {event_date_label}. O seu QR Code de acesso: {qr_url}",
    )
