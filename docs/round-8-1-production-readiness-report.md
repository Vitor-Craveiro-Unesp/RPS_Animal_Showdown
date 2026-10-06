# Rodada 8.1 — Preparação para produção

Data: 2026-10-05. Esta rodada não realizou deploy, push, criação de conta,
DNS, OAuth público ou migration remota.

## A. Resumo executivo

O repositório está preparado para a passagem Vercel + Render + Supabase. Foram
eliminados os fallbacks silenciosos de produção para `localhost`, o CORS passa a
falhar fechado em produção, o blueprint Render e a documentação de handoff
foram criados e a vulnerabilidade alta do lockfile foi corrigida.

## B. Estado inicial

O worktree já continha alterações de rodadas anteriores, preservadas sem reset.
O frontend usava rewrite same-origin e WebSocket configurável, mas o rewrite
aceitava fallback local no build de produção; o backend também mantinha origem
local quando `ALLOWED_ORIGINS` não era informado.

## C. Arquitetura encontrada

Monorepo com Next.js/React em `apps/frontend`, FastAPI em `apps/backend`,
Engine Python em `packages/game-engine`, Alembic em `database/migrations` e
WebSocket próprio em `realtime`. PostgreSQL é a autoridade durável.

## D. Frontend

Chamadas HTTP usam `/api/*` e são encaminhadas por rewrite do Next; não há URL
de API exposta ao navegador. `NEXT_PUBLIC_REALTIME_URL` é a única URL pública
necessária ao cliente. Em build de produção, falta de URL ou protocolo não
seguro faz o build falhar. Vercel deve receber HTTPS para o rewrite e WSS para
o socket.

## E. Backend

O entrypoint é `app.main:app`. O comando Render documentado é
`uvicorn app.main:app --app-dir apps/backend --host 0.0.0.0 --port $PORT`.
`DATABASE_URL` e `REALTIME_TICKET_SIGNING_KEY` são obrigatórios no caminho
durável. Não há dependência funcional de filesystem persistente.

## F. Game Engine

Permanece isolado e autoritativo. Nenhuma regra de RPS, corações, estratégia,
Segunda Chance, pódio, runs, treino ou Animal Rush foi alterada.

## G. PostgreSQL/Supabase

Supabase será usado como PostgreSQL gerenciado. Supabase Auth e Supabase
Realtime não são usados atualmente. O serviço aceita DSN PostgreSQL para
`psycopg`; Alembic usa `postgresql+psycopg://`.

## H. Migrations

Alembic possui revisões `0001` a `0006`, em ordem. Aplicar `alembic upgrade
head` como passo explícito pré-deploy, com credencial de migration separada.
Não há migration automática no startup.

## I. Google Auth

Substituído na Rodada 8.1.1: Google Auth foi cancelado por decisão de produto.
Organizadores podem criar torneios anonimamente e são autorizados por organizer
capability token emitido pelo backend.

## J. CORS

`ALLOWED_ORIGINS` aceita somente origens HTTP(S) exatas sem caminho e rejeita
`*`. Com `APP_ENV=production`, sua ausência impede o startup. O CORS continua
sem cookies (`allow_credentials=False`) e as capabilities continuam em header.

## K. WebSocket/WSS

O WebSocket é configurado por `NEXT_PUBLIC_REALTIME_URL`; produção exige WSS
no build. O endpoint valida Origin, aplica rate limit pré-aceite, valida ticket
curto/persistido e só aceita comandos de resume.

## L. Realtime, replay e snapshot

O cliente usa reconnect exponencial, cursor, deduplicação e snapshot fallback.
O ledger e o outbox são PostgreSQL; payloads são projeções públicas e não
incluem estratégia privada, tickets, credenciais ou RNG.

## M. Security

Autoridade oficial continua no backend/Engine. Há rate limits compartilhados
em PostgreSQL, capabilities com hash, tickets revogáveis, validação Pydantic,
SQL parametrizado e CORS/Origin allowlist. Não foram introduzidas decisões de
produto ou permissões novas.

## N. Secrets

Nenhum `.env`, chave privada, token ou arquivo de credencial rastreado foi
encontrado. `.env*`, `*.log` e `*.tsbuildinfo` estão ignorados. A varredura de
padrões encontrou apenas o identificador interno `task_name`, não um segredo.

## O. Variáveis de ambiente

Inventário completo e matriz dev × produção estão em
[production-readiness.md](deployment/production-readiness.md). Valores reais
continuam exclusivamente nos secret managers das plataformas.

## P. Docker

Compose e Dockerfiles continuam focados em desenvolvimento reproduzível e
executam como usuários não-root. O Compose usa `APP_ENV=development`; o banco
expõe somente loopback. Docker não é exigido pela Vercel.

## Q. Vercel readiness

**READY.** Root Directory: `apps/frontend`; Next detectado sem `vercel.json`.
Configurar `API_INTERNAL_BASE_URL` HTTPS e `NEXT_PUBLIC_REALTIME_URL` WSS antes
do build.

## R. Render readiness

**READY COM AJUSTE EXTERNO.** `render.yaml` define build, start, health e
variáveis secretas sem valores. Configurar uma única instância e os segredos na
plataforma após obter a URL Supabase.

## S. Health check

`GET /health` retorna somente `{"status":"ok"}`; não expõe configuração,
tokens, estado do banco ou stack trace.

## T. Logging

Logs seguros cobrem configuração da aplicação, início/fim dos workers,
criação/início de torneio, conexão/desconexão WebSocket e falhas classificadas
de outbox/progressão. Não registram bearer tokens, estratégias ou secrets.

## U. Assets estáticos

Há 27 áudios de animais, quatro efeitos (`countdown_beep`, `heart_break`,
`champion`, `podium`) e `background/background.mp3`. O build de produção do
Next concluiu com os assets locais; nenhum asset foi buscado nesta rodada.

## V. Build

Build otimizado de produção passou em container efêmero com URLs HTTPS/WSS de
exemplo. Rotas estáticas geradas: `/` e `/patrocinar`.

## V.1 Correção adicional de hidratação

A inspeção final do navegador identificou uma divergência SSR/cliente causada
pela leitura antecipada de preferências locais de áudio. As preferências agora
são restauradas somente após a hidratação, preservando o mesmo comportamento
de opt-out e eliminando o erro de console após recompilar o frontend.

## W. Testes

- suíte local: **189 passed, 25 skipped** (as 25 exigiam DSN PostgreSQL
  isolado);
- PostgreSQL isolado: as 25 provas opt-in foram executadas contra
  `rps_production_readiness_test`, migration `0006_tournament_runs`, sem
  entradas em `lastfailed`;
- frontend: lint, TypeScript e os **23 testes** passaram;
- `npm audit --omit=dev --audit-level=high`: **0 vulnerabilidades** após
  atualizar somente `source-map-js` no lockfile;
- `pip-audit` não foi executado localmente porque o módulo não está instalado;
  o workflow CI já o instala e executa contra `apps/backend/requirements.txt`.

## X. Git

`git status` já era sujo antes da rodada e foi preservado. `git diff --check`
foi executado ao final. Não houve commit, push ou reset.

## Y. Caveat de backend single-instance

Classificação **C**: seguro para MVP com uma instância Render. Replay é
durável, mas o fanout ao vivo é local ao processo. Antes de escalar
horizontalmente, substituir o fanout por broker compartilhado.

## Z. Blockers

Não há blocker técnico local para iniciar a Rodada 8.2. Dependências externas
ainda não configuradas: projeto Supabase, serviço Render, projeto Vercel,
domínios e segredo de realtime.

## AA. Ajustes restantes

1. Validar o IP confiável fornecido pelo proxy Render antes de confiar em
   cabeçalhos de encaminhamento para rate limit por cliente.
2. Executar `pip-audit` no CI/ambiente de deploy com a ferramenta instalada.

## AB. Checklist da Rodada 8.2

Seguir a ordem documentada em
[production-readiness.md](deployment/production-readiness.md#ordem-para-a-rodada-82):
banco → migrations → Render → URL HTTPS/health → Vercel → CORS exato → WSS →
smoke test.

## AC. Gate final

**PRONTO PARA DEPLOY COM AJUSTES MENORES.** A infraestrutura local, build,
configuração por ambiente, health check, CORS, WebSocket e documentação estão
prontos. A configuração de contas/URLs reais pertence à Rodada 8.2; Google
Auth foi cancelado na Rodada 8.1.1.
