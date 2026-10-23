# Segurança, passos a fazer (fora do código)

O histórico antigo do Git contém chaves, certificados, a base de dados antiga (convidados) e uma senha padrão.
O código atual já está limpo. Faça isto por ordem:

1. **Vercel → Settings → Environment Variables:** troque `SECRET_KEY` por um valor novo
   (gerar: `python -c "import secrets;print(secrets.token_hex(32))"`) e faça Redeploy.
   Isto termina todas as sessões antigas.
2. **Senhas:** troque a senha de `admin`, `porteiro` e de qualquer conta que existisse nos testes.
3. **Neon → Settings:** gere nova senha da base de dados (Reset password) e atualize `DATABASE_URL` na Vercel.
4. **Certificados:** `key.pem` antigo não é usado na Vercel; não reutilize.
5. **Limpar o histórico (escolha uma):**
   - *Mais simples:* crie um repositório novo no GitHub (privado), e na pasta do projeto:
     `rmdir /s /q .git` → `git init` → `git add -A` → `git commit -m "GateFlow"` →
     `git branch -M main` → `git remote add origin URL-NOVO` → `git push -u origin main`.
     Depois apague o repositório antigo e reconecte a Vercel ao novo.
   - Manter o repositório: `pip install git-filter-repo` e
     `git filter-repo --invert-paths --path backend/data --path backend/.env.example` e `git push --force origin main`.
6. Deixe o repositório **privado** (Settings → Danger Zone → Change visibility).

Variáveis úteis: `GATEFLOW_TRUST_PROXY=1` (só se hospedar fora da Vercel, atrás de proxy fiável).
