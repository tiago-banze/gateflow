"""
whatsapp_service.py
Estrutura base para envio dos bilhetes via WhatsApp (fallback inteligente
de entrega). Mesmo padrão de sms_service.py: define a INTERFACE que
qualquer gateway real (WhatsApp Business Cloud API da Meta, Twilio, ou
outro agregador) deve implementar, mais um provider "console" padrão
(loga a mensagem em vez de enviar de verdade) usado enquanto nenhum
gateway real estiver configurado.

Para plugar um gateway real:
  1. Criar uma função `_send_via_<provider>(to_msisdn, message,
     media_url=None)` que faça a chamada HTTP real, seguindo o mesmo
     padrão de tratamento de erros de sms_service.py: nunca lançar
     exceção para fora, sempre retornar (ok, error).
  2. Registrar o provider em PROVIDERS abaixo.
  3. Definir WHATSAPP_PROVIDER=<nome> nas variáveis de ambiente.

Enquanto só o provider "console" estiver ativo, send_whatsapp() SEMPRE
retorna ok=False -- isso é PROPOSITAL: o fluxo de entrega em app.py
(_deliver_order_confirmation) usa esse retorno para cair automaticamente
no fallback de e-mail, exatamente como pedido (WhatsApp -> e-mail ->
download direto no sistema, este último sempre disponível de qualquer
forma).
"""

import logging
import os

logger = logging.getLogger("gateflow.whatsapp")


def _send_via_console(to_msisdn, message, media_url=None):
    """Provider padrão (sem gateway externo): só loga a mensagem. Não conta como envio real -- ver docstring do módulo."""
    logger.info("[WHATSAPP-CONSOLE] Para %s: %s%s", to_msisdn, message, f" (anexo: {media_url})" if media_url else "")
    return False, "whatsapp_provider_not_configured"


# Registrar aqui novos gateways reais conforme forem integrados, ex:
# PROVIDERS = {"console": _send_via_console, "meta_cloud_api": _send_via_meta_cloud_api}
PROVIDERS = {
    "console": _send_via_console,
}


def get_active_provider_name():
    return os.environ.get("WHATSAPP_PROVIDER", "console").strip().lower()


def send_whatsapp(to_msisdn, message, media_url=None):
    """
    Envia uma mensagem de WhatsApp pelo provider ativo (ver
    WHATSAPP_PROVIDER). Retorna (ok: bool, error: str|None). Nunca lança
    exceção -- WhatsApp, como e-mail e SMS, é um canal de melhor esforço
    e não pode derrubar o fluxo principal (confirmação de pagamento) se
    falhar.
    """
    provider_name = get_active_provider_name()
    provider_fn = PROVIDERS.get(provider_name)
    if not provider_fn:
        logger.warning("Provider de WhatsApp desconhecido: %s (usando console como fallback)", provider_name)
        provider_fn = _send_via_console

    try:
        return provider_fn(to_msisdn, message, media_url=media_url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao enviar WhatsApp para %s via %s: %s", to_msisdn, provider_name, exc)
        return False, str(exc)


def send_ticket_whatsapp(to_msisdn, buyer_name, event_name, order_code, tickets_url):
    message = (
        f"Olá {buyer_name}! O seu pagamento para *{event_name}* foi confirmado.\n"
        f"Pedido: {order_code}\n"
        f"Baixe os seus bilhetes aqui: {tickets_url}"
    )
    return send_whatsapp(to_msisdn, message, media_url=tickets_url)


def send_rsvp_invite_whatsapp(to_msisdn, guest_name, event_name, rsvp_url):
    message = (
        f"Olá {guest_name}! Você está convidado(a) para *{event_name}*.\n"
        f"Por favor confirme a sua presença aqui: {rsvp_url}\n"
        f'Pode responder também aqui mesmo no WhatsApp: envie "1" para confirmar ou "2" para recusar.'
    )
    return send_whatsapp(to_msisdn, message)


def send_rsvp_reminder_whatsapp(to_msisdn, guest_name, event_name, event_date_label, maps_url, qr_url):
    message = (
        f"Olá {guest_name}! Está quase na hora de *{event_name}*.\n"
        f"Horário: {event_date_label}\n"
        + (f"Localização: {maps_url}\n" if maps_url else "")
        + f"O seu QR Code de acesso: {qr_url}\n"
        f"Apresente este código na entrada. Até lá!"
    )
    return send_whatsapp(to_msisdn, message, media_url=qr_url)
