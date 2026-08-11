# Testes Automatizados — GateFlow

Suíte de testes de integração (usa o `test_client` do Flask contra um
banco SQLite real, recriado do zero a cada suíte — não são mocks).

## Como rodar

```bash
cd backend
./tests/run_all_tests.sh
```

Ou individualmente:

```bash
cd backend
python3 tests/test_fase2_eventos_e_setores.py
```

> Cada teste apaga e recria `backend/data/` antes de rodar, então nunca
> rode a suíte contra um banco de produção com dados reais — sempre
> num ambiente de desenvolvimento/teste.

## O que cada suíte cobre

| Arquivo | Cobertura |
|---|---|
| `test_migracao_banco.py` | Migração do schema antigo → multi-tenant, preservando 100% dos dados existentes |
| `test_crud_e_seguranca_base.py` | CRUD de eventos/convidados, PDFs, bloqueio de check-in em evento passado, kill switch de sessões |
| `test_fase1_multitenant.py` | Cadastro de Organizador, login, isolamento multi-tenant, separação estrita de papéis |
| `test_fase2_database.py` | Funções de banco do Módulo A/B, validação de `event_module`, isolamento na edição |
| `test_fase2_eventos_e_setores.py` | Criação de evento Módulo A/B, **validação da soma VIP+Normal=Total**, isolamento de criação/edição entre Organizadores, bloqueio de edição em evento encerrado |
| `test_fase2_convidados_paywall.py` | Paywall (`is_paid`) bloqueando/liberando gestão de convidados, download+reimport do template Excel, isolamento |
| `test_fase2_upload_logo.py` | Upload de logo: validação real de conteúdo de imagem (não só extensão), limite de tamanho, isolamento |
| `test_fase3_ticketing.py` | Motor de bilheteria: bloqueio de estoque VIP/Normal/ambos, **concorrência real (30 threads, zero overbooking)**, unicidade/anti-fraude das assinaturas HMAC, geração e integridade do PDF em grid com marcas de corte |
| `test_fase2_paginas.py` | Renderização HTML de todas as páginas novas (paywall visível/oculto, Módulo B, 404 correto) |

## Por que isso importa

Cada uma dessas suítes existe porque encontrou (e provou a correção de)
um problema real durante o desenvolvimento — não são testes genéricos
de "caixa preta" escritos depois, por obrigação. Exemplos:
- `test_fase1_multitenant.py` pegou 2 rotas de API que vazavam dados
  entre Organizadores antes de irem para produção.
- `test_fase2_upload_logo.py` prova que um arquivo `.txt` renomeado
  para `.png` é rejeitado (validação por conteúdo, não por extensão).
