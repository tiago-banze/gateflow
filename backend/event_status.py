"""
event_status.py
Calcula o status apresentável de um evento (Próximo / Em Andamento /
Encerrado) a partir da data cadastrada, comparando com a data de hoje.
Mantido separado do database.py porque é lógica de apresentação, não de
persistência, o "hoje" muda a cada chamada, não faz sentido guardá-lo.
"""

import os
from datetime import datetime, timedelta

# Fuso horário do negócio (Moçambique = UTC+2). Em servidores serverless o relógio
# é UTC, o que antecipava/atrasava o 'hoje' em 2 horas. Configurável.
TZ_OFFSET_HOURS = float(os.environ.get("GATEFLOW_TZ_OFFSET_HOURS", "2"))


def local_today():
    return (datetime.utcnow() + timedelta(hours=TZ_OFFSET_HOURS)).date()

def utc_iso_to_local(iso_value):
    """Converte um timestamp UTC guardado na BD para a hora local do evento (Moçambique)."""
    if not iso_value:
        return None
    try:
        return datetime.fromisoformat(str(iso_value).replace("Z", "")) + timedelta(hours=TZ_OFFSET_HOURS)
    except ValueError:
        return None


def local_time_label(iso_value):
    local = utc_iso_to_local(iso_value)
    return local.strftime("%d/%m/%Y %H:%M") if local else ""


STATUS_PROXIMO = "proximo"
STATUS_ANDAMENTO = "andamento"
STATUS_ENCERRADO = "encerrado"

STATUS_LABELS = {
    STATUS_PROXIMO: "Evento Próximo",
    STATUS_ANDAMENTO: "Evento em Andamento",
    STATUS_ENCERRADO: "Evento Encerrado",
}

STATUS_CSS_CLASS = {
    STATUS_PROXIMO: "status-proximo",
    STATUS_ANDAMENTO: "status-andamento",
    STATUS_ENCERRADO: "status-encerrado",
}


def _parse_event_date(event_date_str):
    """
    Extrai a data (sem hora) de uma string de evento, aceitando tanto o
    formato do <input type="datetime-local"> ("YYYY-MM-DDTHH:MM") quanto
    variações com segundos. Retorna None se não for possível interpretar
    (nesse caso o evento é tratado como "Próximo" por segurança, para não
    esconder um evento real por causa de um dado malformado).
    """
    if not event_date_str:
        return None
    try:
        return datetime.fromisoformat(event_date_str).date()
    except ValueError:
        pass
    # Fallback: tenta ler apenas os 10 primeiros caracteres (YYYY-MM-DD)
    try:
        return datetime.strptime(event_date_str[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def compute_event_status(event_date_str, today=None):
    """
    Retorna um dict {code, label, css_class} com o status do evento.
    `today` pode ser injetado (útil em testes); por padrão usa date.today().
    """
    today = today or local_today()
    event_date = _parse_event_date(event_date_str)

    if event_date is None or event_date > today:
        code = STATUS_PROXIMO
    elif event_date == today:
        code = STATUS_ANDAMENTO
    else:
        code = STATUS_ENCERRADO

    return {
        "code": code,
        "label": STATUS_LABELS[code],
        "css_class": STATUS_CSS_CLASS[code],
    }


def attach_status(events):
    """Adiciona o campo 'status' a cada evento de uma lista (in-place e retorna a lista)."""
    for event in events:
        event["status"] = compute_event_status(event.get("event_date"))
    return events


def is_past(event_date_str, today=None):
    """Atalho: True se a data do evento já passou (não é hoje nem futuro)."""
    return compute_event_status(event_date_str, today=today)["code"] == STATUS_ENCERRADO


def sort_events_for_display(events):
    """
    Ordena eventos para exibição nos painéis (Admin e Porteiro).

    Regra de negócio (avaliada e validada, ver observação abaixo): NÃO é
    uma ordenação ingênua por data crescente, porque isso colocaria
    eventos MUITO ANTIGOS no topo da lista (a data mais antiga é a "menor"
    numericamente). O que faz sentido operacionalmente numa portaria é:

      1º) Eventos futuros ou de hoje, do mais PRÓXIMO de agora para o mais
          distante, é isso que o porteiro/admin precisa ver primeiro,
          para agir.
      2º) Eventos já encerrados, do mais RECENTE para o mais antigo, úteis
          para consulta/relatório, mas não precisam competir por atenção
          com o que está em andamento ou por vir.

    Retorna uma NOVA lista ordenada (não altera a lista original).
    """
    def sort_key(event):
        status_code = event.get("status", {}).get("code") or compute_event_status(event.get("event_date"))["code"]
        timestamp = _to_sortable_timestamp(event.get("event_date"))
        if status_code == STATUS_ENCERRADO:
            return (1, -timestamp)  # grupo 2: timestamp maior (mais recente) => chave menor => vem primeiro dentro do grupo
        return (0, timestamp)  # grupo 1: timestamp menor (mais próximo) => vem primeiro dentro do grupo

    return sorted(events, key=sort_key)


def _to_sortable_timestamp(event_date_str):
    """Converte a data do evento em um número comparável (epoch) para ordenação. Retorna 0 (mínimo) se não for possível interpretar."""
    if not event_date_str:
        return 0
    try:
        return datetime.fromisoformat(event_date_str).timestamp()
    except ValueError:
        pass
    try:
        return datetime.strptime(event_date_str[:10], "%Y-%m-%d").timestamp()
    except (ValueError, TypeError):
        return 0
