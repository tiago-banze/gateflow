"""
reports.py
Geração do Relatório de Presença em CSV — usado depois que um evento
encerra, para o organizador exportar e enviar aos donos do evento quem
compareceu e quem faltou. CSV puro (biblioteca padrão do Python, sem
dependências novas) abre direto no Excel/Google Sheets.
"""

import csv
import io


def generate_attendance_report_csv(event, guests):
    """
    Gera o conteúdo CSV (como string) do relatório de presença de um
    evento: Nome, Cargo/Tipo, Mesa, Status (Presente/Ausente) e horário
    do check-in quando houve. Ordenado por status (presentes primeiro)
    e depois por nome.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")  # ; é mais compatível com Excel em PT-BR/locale MZ

    writer.writerow(["Relatório de Presença", event.get("name", "")])
    writer.writerow(["Data do Evento", event.get("event_date", "")])
    writer.writerow([])
    writer.writerow(["Nome Completo", "Cargo/Tipo", "Mesa", "Status", "Horário do Check-in"])

    sorted_guests = sorted(
        guests,
        key=lambda g: (0 if g.get("checked_in") else 1, (g.get("full_name") or "").lower()),
    )

    for guest in sorted_guests:
        status = "Presente" if guest.get("checked_in") else "Ausente"
        checkin_time = guest.get("checkin_time") or ""
        writer.writerow([
            guest.get("full_name", ""),
            guest.get("role", ""),
            guest.get("table_number", ""),
            status,
            checkin_time,
        ])

    total = len(guests)
    present = sum(1 for g in guests if g.get("checked_in"))
    writer.writerow([])
    writer.writerow(["Total de Convidados", total])
    writer.writerow(["Presentes", present])
    writer.writerow(["Ausentes", total - present])

    return buffer.getvalue()
