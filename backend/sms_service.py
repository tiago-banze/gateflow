"""
sms_service.py
Estrutura base para envio de SMS transacional (Fase 5, Pilar 4).

Este modulo define a INTERFACE que qualquer gateway de SMS local de
Mocambique (ex: Movitel, mCel/Tmcel, ou agregadores como Africa's
Talking) deve implementar, mais um provider "console" padrao (loga a
mensagem em vez de enviar de verdade) usado enquanto nenhum gateway
real estiver configurado -- assim o resto do sistema (checkout,
cortesias) ja pode chamar send_sms() hoje, sem esperar a integracao
final ser fechada com um fornecedor especifico.

Para plugar um gateway real:
  1. Criar uma funcao `_send_via_<provider>(to_msisdn, message)` que
     faca a chamada HTTP real (seguindo o mesmo padrao de tratamento
     de erros usado em mpesa_service.py: nunca lancar excecao para
     fora, sempre retornar (ok, error)).
  2. Registrar o provider em PROVIDERS abaixo.
  3. Definir SMS_PROVIDER=<nome> nas variaveis de ambiente.
"""

import logging
import os

logger = logging.getLogger("gateflow.sms")


class SmsProviderNotConfiguredError(Exception):
    pass


def _send_via_console(to_msisdn, message):
    """Provider padrao (sem custo, sem gateway externo): apenas loga a mensagem. Util em desenvolvimento/homologacao."""
    logger.info("[SMS-CONSOLE] Para %s: %s", to_msisdn, message)
    return True, None


# Registrar aqui novos gateways reais conforme forem integrados, ex:
# PROVIDERS = {"console": _send_via_console, "movitel": _send_via_movitel}
PROVIDERS = {
    "console": _send_via_console,
}


def get_active_provider_name():
    return os.environ.get("SMS_PROVIDER", "console").strip().lower()


def send_sms(to_msisdn, message):
    """
    Envia um SMS transacional pelo provider ativo (ver SMS_PROVIDER).
    Retorna (ok: bool, error: str|None). Nunca lanca excecao -- SMS,
    como e-mail, e um canal de melhor esforco e nao pode derrubar o
    fluxo principal (ex: confirmacao de pagamento) se falhar.
    """
    provider_name = get_active_provider_name()
    provider_fn = PROVIDERS.get(provider_name)
    if not provider_fn:
        logger.warning("Provider de SMS desconhecido: %s (usando console como fallback)", provider_name)
        provider_fn = _send_via_console

    try:
        return provider_fn(to_msisdn, message)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao enviar SMS para %s via %s: %s", to_msisdn, provider_name, exc)
        return False, str(exc)


def send_ticket_confirmation_sms(to_msisdn, event_name, order_code):
    message = f"GateFlow: pagamento confirmado. Pedido {order_code} para {event_name}. Bilhetes disponiveis no link enviado por e-mail."
    return send_sms(to_msisdn, message)


def send_rsvp_invite_sms(to_msisdn, guest_name, event_name, rsvp_url):
    message = f"Ola {guest_name}! Convite para {event_name}. Confirme presenca: {rsvp_url}"
    return send_sms(to_msisdn, message)


def send_rsvp_reminder_sms(to_msisdn, guest_name, event_name, event_date_label, qr_url):
    message = f"Ola {guest_name}! {event_name} e as {event_date_label}. Seu QR Code de acesso: {qr_url}"
    return send_sms(to_msisdn, message)
