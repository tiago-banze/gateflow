# Guia de Deploy: Vercel + Neon.tech

Este guia parte do princípio de que a pasta `checkin_system/` (a que
contém `backend/`, `frontend/`, `api/` e `vercel.json`) vai ser a **raiz
do repositório Git** que você conecta na Vercel. Se o seu Git já tem
outras pastas em volta, tudo bem -- você só vai configurar o "Root
Directory" da Vercel para apontar para `checkin_system/` (passo 3.2).

---

## 1. Criar o banco no Neon.tech

1. Crie uma conta em https://neon.tech e um novo **Project**.
2. Escolha uma região próxima dos seus usuários (ex: mais perto de
   Moçambique/África costuma ser Europa -- `eu-central-1` ou similar).
3. Depois do projeto criado, vá em **Connection Details** / **Dashboard**
   e copie a **Connection string** no formato:
   ```
   postgresql://usuario:senha@ep-xxxxx-xxxxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
   Guarde essa string -- é o valor da variável `DATABASE_URL` que você
   vai usar nos passos 3 e 4. (Se o Neon te der o prefixo `postgres://`
   em vez de `postgresql://`, não se preocupe: `config.py` já normaliza
   isso automaticamente.)
4. **Importante:** o Neon "dorme" bancos no plano gratuito após um
   período de inatividade -- a primeira requisição depois de um período
   ocioso pode demorar alguns segundos a mais (cold start do próprio
   banco). Isso é normal e não indica um problema na sua aplicação.

## 2. Organizar os arquivos locais e subir para o GitHub

1. Dentro de `checkin_system/backend/`, **apague a pasta `venv/`** (ou
   garanta que o `.gitignore` incluído a exclui -- já está configurado
   para isso). Ela é enorme e é recriada automaticamente pela Vercel a
   partir do `requirements.txt`.
2. Confira que existe um arquivo `.gitignore` na raiz de
   `checkin_system/` (já incluído) excluindo `venv/`, `backend/data/`,
   `__pycache__/` e `.env`.
3. Inicialize o repositório (se ainda não existir) e suba para o GitHub:
   ```bash
   cd checkin_system
   git init
   git add .
   git commit -m "Preparação para deploy: Vercel + Neon PostgreSQL"
   git branch -M main
   git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
   git push -u origin main
   ```

## 3. Conectar o repositório na Vercel e configurar variáveis de ambiente

1. Em https://vercel.com, clique em **Add New... -> Project** e importe
   o repositório do GitHub que você acabou de criar.
2. **Root Directory:** se `checkin_system/` não for a raiz do seu
   repositório, clique em "Edit" ao lado de Root Directory e aponte para
   a pasta `checkin_system` (ou o caminho equivalente, ex:
   `sistema_checkin_eventos/checkin_system`).
3. **Framework Preset:** deixe como "Other" (a Vercel vai detectar o
   `vercel.json` e usar `@vercel/python` automaticamente).
4. Antes de clicar em Deploy, configure em **Environment Variables**:

   | Nome | Valor | Obrigatória |
   |---|---|---|
   | `DATABASE_URL` | a connection string do Neon (passo 1.3) | Sim |
   | `SECRET_KEY` | uma string aleatória longa (gere com `python -c "import secrets; print(secrets.token_hex(32))"`) | Sim |
   | `GATEFLOW_PUBLIC_BASE_URL` | a URL final do site, ex: `https://seu-projeto.vercel.app` (dá pra atualizar depois de saber a URL definitiva) | Recomendada |
   | `GATEFLOW_TICKET_SECRET` | outra string aleatória longa (`secrets.token_hex(32)`) | Recomendada |
   | `RATELIMIT_STORAGE_URI` | deixe em branco para usar o padrão em memória (ver aviso na seção 5) | Opcional |

   Marque cada uma para os três ambientes (**Production**, **Preview**,
   **Development**) se pretende testar Preview Deployments também.
5. Clique em **Deploy**. O primeiro deploy já vai tentar criar as
   tabelas automaticamente (o `app.py` roda `db.init_db()` no
   import) -- mas o passo 4 abaixo é a forma recomendada de garantir
   isso acontece de forma controlada, ANTES do tráfego real chegar.

## 4. Rodar a migração/criação inicial das tabelas no Neon

Antes (ou logo depois) do primeiro deploy, rode isso **da sua máquina
local**, uma única vez, para criar as tabelas e os usuários padrão
diretamente no Neon:

```bash
cd checkin_system/backend
python -m venv venv_migracao   # ambiente isolado só para este passo, opcional
source venv_migracao/bin/activate  # Windows: venv_migracao\Scripts\activate
pip install -r requirements.txt

export DATABASE_URL="postgresql://usuario:senha@ep-xxxxx.neon.tech/neondb?sslmode=require"
python migrate_neon.py
```

Saída esperada:
```
Conectando ao PostgreSQL (Neon)... OK.
Criando/migrando tabelas (idempotente, seguro rodar mais de uma vez)... OK.
Nenhum usuário encontrado -- criando usuários padrão... OK.
========================================================================
!! USUÁRIOS PADRÃO CRIADOS — TROQUE AS SENHAS IMEDIATAMENTE APÓS O LOGIN !!
   Admin      -> usuário: admin      senha: TrocarSenha@123
   Porteiro   -> usuário: porteiro   senha: TrocarSenha@123
========================================================================
Banco Neon pronto para uso em produção.
```

Depois de rodar isso, acesse `https://seu-projeto.vercel.app/login`,
entre com o usuário `admin` e **troque a senha padrão imediatamente**
em `/admin/usuarios`.

## 5. Gerar o QR Code oficial do site

Duas formas, sem precisar de nada além do que já está no projeto:

- **Localmente**, a qualquer momento:
  ```bash
  cd checkin_system/backend
  python generate_site_qr.py --url https://seu-projeto.vercel.app --out qrcode_site.png
  ```
- **Pelo próprio site**, já logado como admin, acessando (no navegador
  ou salvando o link):
  ```
  https://seu-projeto.vercel.app/admin/qrcode-site
  ```
  Isso baixa o PNG diretamente, sempre gerado na hora (não fica salvo
  em disco no servidor).

---

## ⚠️ Avisos importantes sobre o ambiente serverless

Vale a pena ler antes de colocar o sistema em uso real:

1. **Logo de evento (Módulo B):** já ajustado nesta rodada para ser
   guardado como base64 dentro do próprio banco Postgres (não mais em
   disco) -- funciona corretamente em produção sem configuração
   adicional.
2. **QR Code de convidado, PDFs de convite/contingência, importação de
   planilha .xlsx:** também já ajustados para nunca depender de um
   arquivo sobrevivendo entre requisições diferentes -- ou são gerados
   em memória (QR Code) ou são gravados e lidos de volta dentro da
   MESMA requisição (`/tmp`, que funciona para isso).
3. **Rate limiting (`Flask-Limiter`)** usa armazenamento em memória por
   padrão (`memory://`), que **não é compartilhado entre instâncias
   serverless diferentes** -- na prática, o limite de requisições passa
   a ser "por instância", não global. Isso não quebra nada, só torna o
   limite menos rígido do que era rodando num único processo local. Se
   isso for crítico para você, configure `RATELIMIT_STORAGE_URI` para
   apontar para um Redis (ex: Upstash, que tem integração nativa com a
   Vercel) -- fica fora do escopo desta rodada, mas é uma troca de uma
   variável de ambiente quando você tiver o Redis provisionado.
4. **Cold starts:** a primeira requisição depois de um período sem uso
   pode demorar 1-3 segundos a mais (a função Python "acorda" + o banco
   Neon também pode estar "dormindo"). Chamadas seguintes são rápidas.
5. **SSL/certificado autoassinado** (`ssl_utils.py`) só é usado quando
   você roda `python app.py` localmente pela rede Wi-Fi (para os
   tablets dos porteiros acessarem via HTTPS num IP local) -- na
   Vercel, o HTTPS já é gerenciado automaticamente pela plataforma, essa
   parte do código simplesmente não é executada em produção.
