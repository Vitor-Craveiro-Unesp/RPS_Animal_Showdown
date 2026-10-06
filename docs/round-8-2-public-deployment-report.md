# Rodada 8.2 — Relatório de deploy público

Data: 2026-10-06

## Publicação

| Componente | Provedor | Status |
| --- | --- | --- |
| Frontend | Vercel | Publicado e respondendo `200` |
| API e WebSocket | Render (Free) | Publicado, health check em `/health` respondendo `200` |
| PostgreSQL | Supabase (Free) | Conectado; migrations até `0006_tournament_runs (head)` |

O frontend e o backend usam HTTPS em produção e o realtime usa WSS. A origem
CORS liberada no backend é o domínio de produção do frontend, sem curinga.

## Configuração aplicada

- Vercel: raiz em `apps/frontend`, com a URL interna da API e a URL pública do
  realtime configuradas nos ambientes de produção e preview.
- Render: serviço Python na raiz do repositório, build das dependências do
  backend e do Game Engine, e monitoramento por `/health`.
- Supabase: conexão via session pooler com TLS; nenhuma credencial foi salva no
  repositório.
- O comando de início usa `PYTHONPATH=.` para que o pacote local `realtime`
  esteja disponível ao processo do backend. O mesmo comando foi registrado em
  `render.yaml` para manter a infraestrutura reproduzível.
- As migrations foram aplicadas manualmente antes da publicação. O plano Free
  do Render não oferece pre-deploy command.

## Validação pública executada

| Checagem | Resultado |
| --- | --- |
| `GET https://rps-animal-showdown-api.onrender.com/health` | `200` com `{"status":"ok"}` |
| Homepage pública do Vercel | `200` |
| Preflight CORS de criação de torneio | `200`, com a origem pública exata |
| Criar torneio sem conta | aprovado |
| Entrar com código, nome e animal | aprovado |
| Configurar estratégia e confirmar READY | aprovado |
| Atualização do painel do organizador em realtime | aprovado (`1/8`, `Pronto`) |
| Sala de espera e Animal Rush | aprovados |
| Console dos fluxos públicos exercitados | sem erros ou avisos |

Torneio de validação criado: `RPS-LM4BXPRQ7EWC8V4A`. Ele foi mantido em sala de
espera; nenhum torneio de usuários foi iniciado pelo procedimento de deploy.

## Testes locais finais

- `npm --prefix apps/frontend run lint` — aprovado.
- `npm --prefix apps/frontend test -- --run` — 25 aprovados, 0 falhas.
- `npm --prefix apps/frontend run build` — aprovado, incluindo TypeScript.
- `python -m pytest -q apps/backend/tests realtime/tests packages/game-engine/tests database/migrations/tests` — 190 aprovados, 25 ignorados, 0 falhas.
- As quatro advertências conhecidas são de depreciação de `on_event` no
  FastAPI; não bloqueiam a execução e não foram alteradas nesta rodada.

## Limites conhecidos do plano gratuito

- A instância gratuita do Render pode hibernar por inatividade e a primeira
  solicitação posterior pode levar cerca de 50 segundos.
- O banco Supabase e os provedores de hospedagem usam seus limites gratuitos
  vigentes; capacidade e observabilidade avançada ficam fora desta rodada.

## Resultado

**DEPLOY PÚBLICO APROVADO** para a versão atual, com os limites do plano
gratuito acima documentados.
