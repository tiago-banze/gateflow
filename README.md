# Sistema de Gestão de Eventos e Check-in de Convidados

Sistema completo, pronto para produção, para gestão de eventos e check-in
de convidados via tablet Android (ou qualquer navegador), operado por
porteiros na portaria de um evento.

- **Backend:** Python + Flask + SQLite (modo WAL, para escrita concorrente
  segura entre múltiplos tablets na mesma rede).
- **Frontend:** HTML + CSS + JavaScript puro (Web), responsivo, servido
  pelo próprio backend Flask — nenhuma instalação necessária no tablet,
  basta abrir o navegador (Chrome) e acessar o IP do computador que roda
  o backend.
- **Sem dados mockados.** Todo o fluxo funciona com dados reais, gravados
  no SQLite local.
- **Sem serviços em nuvem.** Tudo roda 100% localmente, na sua rede.

---

## 1. Estrutura do Projeto

```
checkin_system/
├── backend/
│   ├── app.py                # Rotas da API Flask e páginas
│   ├── database.py           # Camada de dados (SQLite, modo WAL)
│   ├── qrcode_utils.py       # Geração de QR Codes por convidado
│   ├── pdf_generator.py      # Geração do PDF de convites (grade)
│   ├── event_status.py       # Cálculo de status do evento (Próximo/Andamento/Encerrado)
│   ├── security.py           # Proteção contra força bruta no login
│   ├── text_utils.py         # Slugify para nomes de arquivo (PDF dinâmico)
│   ├── ssl_utils.py          # Geração automática de certificado HTTPS (necessário p/ câmera)
│   ├── config.py             # Configurações e caminhos
│   ├── requirements.txt      # Dependências Python
│   └── data/                 # Criado automaticamente ao rodar
│       ├── eventos.db        # Banco de dados SQLite
│       ├── secret.key        # Chave de sessão (login) persistida
│       ├── certs/            # Certificado HTTPS autoassinado (cert.pem, key.pem)
│       ├── qrcodes/          # Imagens PNG de QR Code por evento/convidado
│       ├── exports/          # PDFs de convites gerados
│       └── uploads/          # Pasta temporária de upload de planilhas
├── frontend/
│   ├── templates/
│   │   ├── index.html               # Landing pública
│   │   ├── login.html               # Tela de login
│   │   ├── admin_events.html        # Painel Geral de Eventos (Admin)
│   │   ├── admin_event_detail.html  # Gerenciamento de um evento específico
│   │   ├── admin_users.html         # Gerenciamento de usuários
│   │   ├── checkin_events.html      # Painel Geral de Eventos (Porteiro)
│   │   ├── checkin.html             # Tela de check-in de um evento específico
│   │   ├── error_403.html           # Acesso negado
│   │   └── error_404.html           # Evento/página não encontrado
│   └── static/
│       ├── css/style.css
│       └── js/ (common.js, admin_events.js, admin_event_detail.js,
│               admin_users.js, checkin_events.js, checkin.js)
├── modelo_convidados.xlsx    # Planilha modelo (30 convidados de exemplo, com coluna Mesa)
└── README.md
```

---

## 2. Instalação (uma única vez)

Requer **Python 3.10+** instalado no computador que ficará na portaria
(o "servidor"). Não é necessário instalar nada nos tablets.

```bash
cd checkin_system/backend
python3 -m venv venv

# Linux/Mac
source venv/bin/activate
# Windows
venv\Scripts\activate

pip install -r requirements.txt
```

## 3. Executando o sistema

> **Quer começar do zero, sem nenhum evento/convidado/usuário antigo?**
> Antes do primeiro `python3 app.py`, apague a pasta `backend/data/` (ou,
> se ela ainda não existir, não precisa fazer nada — ela é criada vazia
> automaticamente). Isso remove o banco `eventos.db`, os QR Codes e a
> chave de sessão salva. Na próxima execução, o sistema recria tudo do
> zero e gera os dois usuários padrão (`admin`/`porteiro`) novamente.
> ```bash
> rm -rf backend/data
> python3 backend/app.py
> ```

```bash
cd checkin_system/backend
python3 app.py
```

O terminal exibirá algo como:

```
>> Sistema de Check-in disponível na rede local em: http://<IP-DESTE-COMPUTADOR>:5000
>> Rodando em HTTP. Para a câmera do leitor de QR Code funcionar em cada
>> tablet/computador, configure UMA VEZ por aparelho (veja o README,
>> seção 'Câmera não funciona pelo IP da rede'):
>>   chrome://flags/#unsafely-treat-insecure-origin-as-secure
>> Painel Administrativo (Multi-Eventos): /admin   |   Painel do Porteiro (Multi-Eventos): /checkin
```

Descubra o IP local do computador (ex: `192.168.1.10`):
- **Windows:** `ipconfig` (procure "Endereço IPv4")
- **Mac/Linux:** `ifconfig` ou `ip addr` (procure "inet")

Certifique-se de que o computador e os tablets estão **na mesma rede
Wi-Fi**.

## 4. Acessando pelos dispositivos

- **No computador do organizador (Admin):** abra `http://localhost:5000/admin`
- **Em cada tablet Android do porteiro:** abra o Chrome e acesse
  `http://<IP-DO-COMPUTADOR>:5000/checkin`

Múltiplos tablets podem acessar `/checkin` simultaneamente. Quando um
porteiro faz o check-in de um convidado, os demais tablets refletem a
mudança em poucos segundos (sincronização automática por polling).

## 4.0.1. Câmera não funciona pelo IP da rede (leia isto antes de testar o scanner)

Navegadores modernos (Chrome, Safari, Firefox) **bloqueiam o acesso à
câmera** em páginas servidas por `http://` que não sejam `localhost` —
mesmo que o usuário aceite a permissão. Como o sistema roda no IP da rede
local (ex: `192.168.1.10`), o leitor de QR Code não funciona "de fábrica"
nesse endereço.

**Testamos duas soluções. Recomendamos a primeira — é mais confiável:**

### ✅ Opção recomendada: liberar o site nas flags do Chrome (uma vez por aparelho)

Isso NÃO envolve certificado, NÃO mostra nenhum aviso de "conexão não
segura", e funciona de forma permanente depois de configurado:

1. No Chrome de cada tablet/telemóvel/computador que vai usar a câmera
   (só os do **porteiro** precisam disso — quem só usa o Admin não precisa),
   digite na barra de endereço: `chrome://flags/#unsafely-treat-insecure-origin-as-secure`
2. No campo de texto que aparece, digite o endereço completo do backend,
   **incluindo `http://` e a porta** — ex: `http://192.168.1.10:5000`
   (se tiver mais de um endereço, separe por vírgula)
3. Ao lado, mude o menu suspenso de "Default" para **"Enabled"**
4. Toque no botão azul **"Relaunch"** que aparece embaixo (o Chrome
   reinicia sozinho)
5. Acesse `http://192.168.1.10:5000/checkin` normalmente — a câmera agora
   funciona sem nenhum aviso.

> Isso precisa ser feito **uma vez em cada aparelho** que vai escanear QR
> Code. Se o IP do computador-servidor mudar (ex: trocou de rede), repita
> o passo 2 com o novo IP.

### ⚠️ Opção alternativa (não recomendada): HTTPS automático

O sistema também sabe gerar um certificado HTTPS autoassinado sozinho,
mas em testes reais isso se mostrou pouco confiável: em Chrome
corporativo/gerenciado (comum em computadores de empresa/escola), o botão
"Continuar mesmo assim" do aviso de certificado pode ficar **bloqueado
por política**, travando o acesso por completo — foi exatamente o que
aconteceu nos nossos testes. Por isso, essa opção vem **desligada por
padrão**. Só ative se souber que o Chrome dos seus aparelhos não tem essa
restrição:

```bash
CHECKIN_ENABLE_HTTPS=1 python3 app.py
```

Se ativar e o navegador mostrar "Sua conexão não é privada" /
`ERR_CERT_AUTHORITY_INVALID`, toque em **"Avançado"** e depois em
**"Continuar para \<IP\> (não seguro)"**. Se esse botão não aparecer ou
não funcionar mesmo depois de tocar, **não insista** — desligue essa
opção (rode `python3 app.py` sem a variável) e use a Opção recomendada
acima.

## 4.1. Login e Controle de Acesso

O sistema agora exige autenticação. Na primeira execução, dois usuários
padrão são criados automaticamente e exibidos **uma única vez** no terminal:

| Perfil    | Usuário    | Senha padrão       |
|-----------|-----------|---------------------|
| Admin     | `admin`    | `TrocarSenha@123`  |
| Porteiro  | `porteiro` | `TrocarSenha@123`  |

> ⚠️ **Troque essas senhas antes de usar em produção.** Não há tela de troca
> de senha na interface ainda; para trocar, gere um novo hash e atualize
> diretamente no banco (`backend/data/eventos.db`, tabela `users`) com:
> ```python
> from werkzeug.security import generate_password_hash
> print(generate_password_hash("SuaNovaSenhaForte"))
> ```
> e faça um `UPDATE users SET password_hash='<hash>' WHERE username='admin';`

**Regras de permissão:**
- **Admin**: acesso total — cria/exclui eventos, importa planilhas, exporta
  PDF de convites, gerencia usuários, e também pode acessar o Painel do
  Porteiro.
- **Porteiro**: acesso restrito — só visualiza convidados e faz check-in.
  Qualquer tentativa de acessar `/admin`, `/admin/eventos/<id>`,
  `/admin/usuarios` ou as rotas administrativas da API retorna **403
  Forbidden** — mesmo trocando a URL manualmente na barra do navegador.

A sessão de login dura 8 horas de inatividade e é preservada entre reinícios
do servidor (chave secreta salva em `backend/data/secret.key`).

**Proteção contra força bruta:** após 5 tentativas de login falhas para o
mesmo usuário+IP em 15 minutos, o login fica bloqueado por 15 minutos. O
contador é reiniciado a cada login bem-sucedido.

## 4.2. Estrutura Multi-Eventos

O sistema não fica mais amarrado a um único evento. Tanto o Admin quanto o
Porteiro, ao fazer login, caem em um **Painel Geral de Eventos** listando
todos os eventos cadastrados, cada um com um status calculado automaticamente
a partir da data de hoje:

- 🔵 **Evento Próximo** — data no futuro
- 🟢 **Evento em Andamento** — data é hoje
- ⚪ **Evento Encerrado** — data já passou

Ao clicar em "Gerenciar" (Admin) ou "Trabalhar neste Evento" (Porteiro), o
usuário é levado para as telas daquele evento específico:

- `GET /admin/eventos/<event_id>` — gerenciamento (importar, exportar PDF, convidados)
- `GET /checkin/<event_id>` — tela de check-in (busca + leitor de QR Code)

> **Nota sobre o formato do ID:** as rotas usam `event_id` como string
> (UUID), não `<int:id_evento>` como um índice sequencial. Isso é
> intencional — UUIDs não são adivinháveis/enumeráveis por um atacante
> trocando números na URL, o que é mais seguro do que IDs sequenciais.

## 4.3. Gerenciamento de Usuários

Em `/admin/usuarios`, qualquer usuário com perfil "Admin" pode criar novos
perfis de acesso preenchendo: Nome completo, Usuário (login), Tipo de acesso
(Admin ou Porteiro) e uma senha provisória (mínimo 8 caracteres). Não há
distinção especial entre "o primeiro admin" e admins criados depois — todos
com papel `admin` têm as mesmas permissões.

## 4.4. Alocação de Mesas (casamentos, jantares de gala)

Cada convidado agora pode ter uma **Mesa** associada (texto livre — ex:
"Mesa 05", "Mesa VIP"):

- **Na planilha `.xlsx`**: adicione uma coluna **Mesa** (veja
  `modelo_convidados.xlsx`, já atualizado com 30 convidados de exemplo).
  Essa coluna é **opcional** — planilhas antigas sem ela continuam
  funcionando normalmente; qualquer célula vazia ou coluna ausente vira
  automaticamente `"Não definida"`.
- **Cadastro manual**: em `/admin/eventos/<id>`, o card "Cadastrar Convidado
  Manualmente" tem um campo Mesa (também opcional).
- **No Painel do Porteiro**: a Mesa aparece destacada em cada card de
  convidado (mesmo antes do check-in, para consulta rápida). Ao confirmar
  o check-in — pelo botão ou pelo QR Code — um **banner grande em tela
  cheia** mostra o nome do convidado e a Mesa em destaque, para o porteiro
  informar verbalmente na hora ("seu check-in foi feito, sua mesa é a X").
  O banner fecha sozinho após alguns segundos ou ao tocar em "OK".
- **No PDF de convites**: a Mesa aparece em negrito logo abaixo do nome de
  cada convidado, no cartão com o QR Code.

## 4.5. Plataforma Multi-Tenant — Organizadores, Módulo A e Módulo B

O GateFlow deixou de ser um sistema de evento único e virou uma
plataforma com 4 papéis: **Admin** (Super Admin, controle total),
**Organizador** (cadastro autônomo, dono dos próprios eventos),
**Porteiro** (check-in) e **Cliente** (schema pronto, fluxo de compra
chega em fase futura).

**Cadastro de Organizador:** `/organizador/cadastro` — qualquer pessoa
cria a própria conta, sem precisar que o Super Admin cadastre
manualmente. Login em `/login?intent=organizador`.

**Isolamento multi-tenant:** um Organizador só gerencia (edita, importa
convidados, etc.) os eventos que ele mesmo criou — reforçado no SQL de
cada rota, não só na interface. Ele **vê** os eventos de outros
Organizadores na listagem (para dar volume à plataforma), mas com os
botões de gerenciamento desabilitados e um badge "Outro Organizador".

**Dois módulos de evento**, escolhidos na criação:
- **Módulo A — Convites/Lista Fechada** (casamentos, festas privadas):
  igual ao fluxo original — lista de convidados, QR Code, check-in.
  Tem uma flag de pagamento (`is_paid`): o painel de convidados e a
  portaria só liberam depois que o Super Admin confirma o pagamento
  (`PUT /api/admin/events/<id>/mark-paid` — substituto manual até a
  integração real de pagamento numa fase futura).
- **Módulo B — Evento Público/Bilheteria** (shows, conferências):
  captura lotação por setores (VIP/Normal/Total — o sistema valida que
  a soma bate exatamente), contato e logo opcional. Venda de bilhetes
  em si ainda não existe — chega em fase futura.

**Modelo de planilha:** botão de download em `/api/events/template-xlsx`
gera um `.xlsx` já formatado com as colunas exigidas pelo importador.

Suíte de testes completa em `backend/tests/` — veja
`backend/tests/README.md` para rodar.

## 4.6. Motor de Bilheteria (Fase 3) — Módulo B

Organizadores emitem **lotes de bilhetes físicos** para eventos do Módulo B:

- **Estoque atômico**: a checagem de vagas e a criação dos bilhetes
  acontecem numa única transação `BEGIN IMMEDIATE` — testado com 30
  threads concorrentes disputando 10 vagas: exatamente 10 vencem, zero
  overbooking, sempre.
- **Escassez por setor**: VIP esgotado sugere Normal (e vice-versa);
  ambos esgotados bloqueia tudo e orienta contato direto com o
  organizador. O evento muda visualmente para "Esgotado" na listagem.
- **Anti-fraude**: cada bilhete tem uma assinatura HMAC-SHA256 (chave
  em `GATEFLOW_TICKET_SECRET`, ou gerada/persistida automaticamente em
  `data/ticket_secret.key`) embutida no QR Code. Adulterar qualquer
  campo (ID, evento, tipo VIP/Normal) invalida a assinatura.
- **Taxa de impressão**: 5 MT por bilhete (configurável via
  `GATEFLOW_TICKET_FEE`), confirmada manualmente pelo Super Admin
  (`PUT /api/admin/ticket-batches/<id>/mark-paid`) até a integração
  real de pagamento numa fase futura.
- **PDF físico**: grid 2 colunas x 4 linhas por A4, com marcas de corte
  pontilhadas, QR Code, tipo em destaque e ID único por bilhete.

## 5. Fluxo de uso

### Painel Administrativo (`/admin`)
1. Ao logar, você cai no **Painel Geral de Eventos** — lista todos os eventos
   com status (Próximo / Em Andamento / Encerrado).
2. Crie um novo evento pelo formulário no topo (nome, local, data/hora, descrição).
3. Clique em "Gerenciar" no evento desejado para entrar em `/admin/eventos/<id>`.
4. Importe a planilha `.xlsx` de convidados (veja `modelo_convidados.xlsx`
   como referência de formato — colunas obrigatórias: **Nome Completo,
   Email, Telefone, Cargo/Tipo**). Convidados já existentes **para este
   mesmo evento** (identificados por e-mail, ou por Nome+Telefone quando
   não há e-mail) são automaticamente pulados — você pode reimportar a
   mesma planilha corrigida sem gerar duplicados.
5. O sistema gera automaticamente um QR Code único por convidado.
6. Clique em "Baixar Documento de Convites" para obter o PDF pronto para
   impressão, com nome, cargo e QR Code de cada convidado. **O nome do
   arquivo é gerado dinamicamente a partir do nome do evento** — ex:
   "Workshop de Inovação 2026" vira `Workshop_de_Inovacao_2026.pdf`
   (acentos, espaços e caracteres especiais são removidos automaticamente).
7. Em "👥 Usuários" (aba no topo), crie novos usuários admin/porteiro.

### Painel do Porteiro (`/checkin`)
1. Ao logar, você cai no **Painel Geral de Eventos** — mesma lista, com o
   botão "Trabalhar neste Evento".
2. Clique no evento em andamento para entrar em `/checkin/<id>`.
3. Busque o convidado pelo nome e toque em "Check-in", **ou**
4. Toque no botão flutuante da câmera (📷) e aponte para o QR Code do
   convidado (impresso ou na tela do smartphone dele).
5. O cartão do convidado muda para verde claro assim que o check-in é
   confirmado. Se o QR Code já tiver sido lido antes, o sistema avisa
   que o check-in já foi realizado.

---

## 5.1. Compatibilidade com o app Android (APK)

Se você já compilou o wrapper Android entregue anteriormente, ele **continua
funcionando sem nenhuma alteração** — é só uma WebView carregando esta mesma
interface. A única mudança perceptível é que, ao abrir o app, ele vai cair
na tela de login em vez de ir direto para o painel.

**Sobre a câmera dentro do app:** o WebView usado pelo APK é um motor
separado do Chrome do aparelho — a flag `chrome://flags` configurada no
navegador **não necessariamente** se aplica dentro do app (isso varia por
aparelho/fabricante, não é garantido). Por isso, para o APK, o caminho
recomendado é o oposto do navegador: **ligar o HTTPS automático no
servidor** e apontar o app para `https://`. Diferente do navegador (onde
o aviso de certificado pode ficar bloqueado por política), o app já foi
programado para aceitar esse certificado autoassinado automaticamente,
sem pedir nenhum clique — então não sofre do mesmo problema.

1. No computador, rode o servidor com `CHECKIN_ENABLE_HTTPS=1 python3 app.py`
2. No app, em "Configurar servidor", digite o endereço **com `https://`
   explícito** — ex: `https://192.168.1.10:5000` (o app não adiciona
   `https://` sozinho, você precisa digitar)

## 6. Notas técnicas importantes

- O banco SQLite roda em **modo WAL**, permitindo leitura e escrita
  concorrentes de múltiplos porteiros sem bloqueios.
- Cada QR Code contém apenas um identificador único (UUID) do convidado
  — nenhum dado pessoal fica exposto no próprio código.
- Todas as rotas da API tratam exceções e retornam mensagens de erro
  claras em JSON (`{"success": false, "error": "..."}`), nunca quebrando
  a interface do porteiro.
- **Todas as consultas SQL usam parâmetros (`?`) do driver `sqlite3`** —
  nunca concatenação de strings — o que já elimina a classe de vulnerabilidade
  de SQL Injection.
- **Senhas nunca são armazenadas em texto puro**: usa-se
  `werkzeug.security.generate_password_hash` (PBKDF2) e
  `check_password_hash` na verificação.
- **IDs de evento e convidado são UUIDs** (não sequenciais), o que já
  dificulta enumeração; além disso, toda rota autenticada valida a sessão
  via `session["user_id"]` assinada pela `SECRET_KEY` do servidor — não é
  possível forjar acesso apenas adivinhando um ID.
- Nenhuma nova dependência pip foi adicionada: a autenticação usa apenas
  `flask.session` (nativo) e `werkzeug.security` (já vem junto do Flask),
  então o `requirements.txt` continua exatamente o mesmo.
- Para produção contínua (evento de vários dias, uso intenso), recomenda-se
  rodar o Flask atrás de um servidor WSGI como `waitress` ou `gunicorn`
  em vez do servidor de desenvolvimento embutido. Exemplo com waitress:
  ```bash
  pip install waitress
  python3 -c "from waitress import serve; from app import app; serve(app, host='0.0.0.0', port=5000)"
  ```
