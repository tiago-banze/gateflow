# GateFlow

Gestão de convidados e controlo de entrada para eventos: lista de convidados,
convites (WhatsApp / SMS / e-mail), confirmação de presença (RSVP), lembrete
com QR Code e check-in na portaria. **Não há venda de bilhetes nem pagamentos.**

Pensado para telemóvel (mobile-first); o computador serve para configuração.

## Perfis
| Perfil | O que faz |
|---|---|
| Admin | Gere utilizadores, eventos e feedbacks da plataforma |
| Organizador | Cria eventos, gere convidados, envia convites/lembretes, cria porteiros |
| Porteiro | Valida a entrada por QR Code (funciona com internet instável) |

## Correr localmente
```bash
cd backend
pip install -r ../requirements.txt
export SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')"
export GATEFLOW_ADMIN_USERNAME=admin
export GATEFLOW_ADMIN_PASSWORD='uma-senha-forte'   # obrigatória no 1.º arranque
python app.py
```
Não existem senhas por defeito: o primeiro admin só é criado se definires
`GATEFLOW_ADMIN_PASSWORD` (mín. 10 caracteres). Sem `DATABASE_URL` usa SQLite local.

## Envio real de mensagens
> **Desligado por defeito.** Enquanto `GATEFLOW_MESSAGING_ENABLED` não for `1`, os botões de envio
> (e-mail, WhatsApp, SMS) mostram "ainda não está disponível". O PDF de convites com QR Code funciona sempre.

Cada canal só está ativo com credenciais. Sem credenciais, o convidado fica
**"não enviado"** com o motivo; o sistema nunca finge sucesso.

| Canal | Variáveis |
|---|---|
| WhatsApp (Meta) | `WHATSAPP_PROVIDER=meta`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TEMPLATE_INVITE`, `WHATSAPP_TEMPLATE_REMINDER`, `WHATSAPP_TEMPLATE_LANG` |
| WhatsApp (Twilio) | `WHATSAPP_PROVIDER=twilio`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` |
| SMS (Twilio) | `SMS_PROVIDER=twilio`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_SMS_FROM` ou `TWILIO_MESSAGING_SERVICE_SID` |
| SMS (Africa's Talking) | `SMS_PROVIDER=africastalking`, `AT_USERNAME`, `AT_API_KEY`, `AT_SENDER_ID` |
| E-mail (Resend) | `EMAIL_PROVIDER=resend`, `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME` |
| E-mail (SMTP) | `EMAIL_PROVIDER=smtp`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `SMTP_FROM_ADDRESS`, `SMTP_FROM_NAME` |

Ordem: WhatsApp → (se falhar) SMS; e-mail em paralelo. Fora da janela de 24 h
o WhatsApp exige **templates aprovados** pela Meta (nomes em `WHATSAPP_TEMPLATE_*`).
Webhook de respostas: `/webhooks/whatsapp` com `WHATSAPP_VERIFY_TOKEN` e
assinatura `WHATSAPP_APP_SECRET`.

Outras variáveis: `GATEFLOW_PUBLIC_BASE_URL` (URL público usado nos links),
`GATEFLOW_TZ_OFFSET_HOURS` (por defeito 2, Maputo), `RATELIMIT_STORAGE_URI`.

## Lista de convidados
Importe por **.xlsx**, **.csv** ou **colando** do Excel; há modelos para descarregar. Colunas:
`Nome Completo, Email, Telefone, Categoria, Grupo, Acompanhantes` (só o nome é obrigatório).
Mostra uma **pré-visualização** (novos / a atualizar / sem alterações) antes de gravar; quem já
existe (mesmo e-mail, ou nome+telefone) é **atualizado**, nunca duplicado. Segurança: só .xlsx/.csv,
máx. 2 MB e 2000 linhas, conteúdo verificado (não só a extensão), sem macros/ligações externas,
fórmulas neutralizadas, nada é gravado em disco.

## Portaria
- **Câmara contínua:** abre uma vez e valida QR após QR; o mesmo código é ignorado durante 4 s.
- **Leitor USB/Bluetooth:** ligue um leitor 2D em modo "teclado" (HID, sufixo Enter, por defeito);
  basta ter a página aberta. Precisa de leitor **2D/QR** (os de laser 1D não leem QR). Exemplos:
  Zebra DS2208, Honeywell Voyager 1450g, Netum/Eyoyo 2D sem fios.
- Cada convidado pode cobrir várias pessoas (acompanhantes): o ecrã mostra "3 pessoas".
- "Mesa" é configurável por evento (Mesa, Zona, Sector, Categoria, Sala, Fila); a categoria do
  QR (VIP, Imprensa, Staff…) aparece no bilhete PDF e na leitura.

## Eventos e retenção
As listas mostram por defeito só os eventos por realizar (5 de cada vez, "Ver mais"); "Encerrados" e
"Todos" são escolhas explícitas. Eventos encerrados há mais de 365 dias são apagados automaticamente
(convidados, respostas e QR Codes incluídos). Ajuste com `GATEFLOW_RETENTION_DAYS` (0 desativa).

## Segurança
Cookies de sessão HttpOnly/SameSite, verificação de Origin em pedidos de
escrita, cabeçalhos de segurança, webhook com HMAC, isolamento por
organizador, rate limiting no login e sem credenciais no repositório.

## Deploy
Ver `DEPLOY_VERCEL_NEON.md`.
