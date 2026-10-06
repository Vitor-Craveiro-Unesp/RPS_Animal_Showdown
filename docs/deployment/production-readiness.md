# Preparação para produção

Este documento prepara a Rodada 8.2; ele não autoriza nem realiza deploy.

## Arquitetura planejada

- **Vercel:** `apps/frontend`, Next.js. O navegador usa as rotas same-origin
  `/api/*`; os rewrites do servidor Next encaminham para o backend.
- **Render:** FastAPI em `apps/backend`, uma única instância para o MVP.
- **Supabase:** somente PostgreSQL gerenciado nesta fase. O realtime é o
  WebSocket nativo do FastAPI, não Supabase Realtime.
- **PostgreSQL:** origem de verdade para torneios, capabilities, rate limits,
  snapshots, ledger de eventos e outbox.

## Variáveis de ambiente

| Grupo | Variável | Uso | Produção | Visibilidade |
| --- | --- | --- | --- | --- |
| Backend | `APP_ENV` | Separa desenvolvimento de produção; produção exige CORS explícito | `production` | servidor |
| Backend/Banco | `DATABASE_URL` | conexão do backend e migrations; aceita `postgresql://` ou `postgresql+psycopg://` no app, use a forma SQLAlchemy para Alembic | obrigatória | secreta |
| Backend/Realtime | `REALTIME_TICKET_SIGNING_KEY` | HMAC de tickets curtos de WebSocket | obrigatória, 32+ bytes aleatórios | secreta |
| Backend/CORS | `ALLOWED_ORIGINS` | lista CSV de origens HTTP(S) exatas do frontend | obrigatória | servidor |
| Render | `PORT` | porta injetada pelo Render para Uvicorn | fornecida pela plataforma | servidor |
| Vercel | `API_INTERNAL_BASE_URL` | URL HTTPS pública do Render usada somente pelo rewrite do Next | obrigatória no build | servidor Vercel |
| Navegador | `NEXT_PUBLIC_REALTIME_URL` | URL WSS pública do WebSocket FastAPI | obrigatória no build | pública |
| Local Compose | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT`, `BACKEND_PORT`, `FRONTEND_PORT` | somente desenvolvimento local | não usar | local |
| Organizer capability | nenhuma variável fixa | token opaco emitido pelo backend por torneio; somente o hash é persistido | não configurar manualmente | segredo local do navegador |

`NEXT_PUBLIC_*` entra no bundle do navegador e nunca deve conter segredos.
O arquivo `.env.example` contém apenas valores locais ou placeholders. Arquivos
`.env*`, logs e artefatos de build são ignorados pelo Git.

## Regras HTTP, CORS e WebSocket

Em desenvolvimento: `http://` e `ws://` são permitidos por configuração local.
No build de produção, o Next falha se `API_INTERNAL_BASE_URL` não for HTTPS ou
se `NEXT_PUBLIC_REALTIME_URL` não for WSS. O backend falha ao iniciar em
`APP_ENV=production` sem `ALLOWED_ORIGINS`; curingas e caminhos são recusados.

O WebSocket exige Origin exata, rate limit antes de `accept`, ticket assinado,
ticket persistido não revogado e cursor de replay. O cliente reconecta com
backoff, deduplica `eventId`/sequência e busca snapshot se detectar lacuna.

## Migrations e banco

As migrations são Alembic em `database/migrations/versions`, na ordem
`0001` até `0006`. Antes de iniciar o serviço de produção, execute uma única
ação explícita, com credencial de migration separada:

```sh
DATABASE_URL='postgresql+psycopg://...' python -m alembic -c database/migrations/alembic.ini upgrade head
```

Não execute migrations automaticamente no startup da API. O banco da aplicação
deve receber uma credencial de menor privilégio que a credencial de migration.

## Render

`render.yaml` descreve o serviço sem valores secretos. O diretório raiz é o
repositório; o comando de produção é:

```sh
uvicorn app.main:app --app-dir apps/backend --host 0.0.0.0 --port $PORT
```

Use `GET /health` como health check. Ele retorna somente `{"status":"ok"}`.
Configure inicialmente **uma instância**. Antes de escalar horizontalmente,
substitua o fanout ao vivo em memória por broker compartilhado; o replay
PostgreSQL já é durável.

## Vercel

Defina o Root Directory como `apps/frontend` (ou use o monorepo com os comandos
equivalentes da raiz). O framework é Next.js, sem `vercel.json` necessário.
Antes do build, defina:

```text
API_INTERNAL_BASE_URL=https://YOUR_RENDER_SERVICE.onrender.com
NEXT_PUBLIC_REALTIME_URL=wss://YOUR_RENDER_SERVICE.onrender.com/v1/realtime
```

O rewrite same-origin protege o navegador de conhecer a URL interna da API e
mantém as chamadas HTTP em `/api/*`.

## Organizador sem conta

Google Auth foi cancelado por decisão de produto. Organizadores criam torneios
anonimamente e recebem uma capability opaca emitida pelo backend. O browser a
mantém em `sessionStorage` para sobreviver a refreshes na mesma aba; ela nunca
entra em URL, HTML público, snapshots, eventos, logs ou payloads de
participantes. O PostgreSQL guarda somente o hash e a validade da capability.

Para o MVP, apagar o storage, trocar de navegador ou perder a capability remove
o acesso administrativo. Não há recuperação por e-mail e isso é intencional.

## Ordem para a Rodada 8.2

1. Criar/confirmar projeto Supabase e obter a URL PostgreSQL.
2. Executar `alembic upgrade head` com credencial de migration.
3. Criar serviço Render a partir de `render.yaml` e configurar os três segredos.
4. Obter a URL HTTPS do Render e conferir `/health`.
5. Criar projeto Vercel, configurar `API_INTERNAL_BASE_URL` e
   `NEXT_PUBLIC_REALTIME_URL`, e publicar o frontend.
6. Atualizar `ALLOWED_ORIGINS` no Render para a URL HTTPS exata da Vercel e
   redeployar o backend.
7. Na Rodada 8.3, validar WSS, proxy, origem real e o comportamento da
   capability de organizador em produção.
8. Executar o smoke test público da Rodada 8.4.

## Plano atualizado da Rodada 8

1. **8.1** — preparação para produção (concluída).
2. **8.1.1** — organizador sem conta e autorização por capability (concluída
   localmente; consulte `round-8-1-1-anonymous-organizer-report.md`).
3. **8.2** — Vercel + Render + Supabase/PostgreSQL e primeiro deploy público.
4. **8.3** — validação de segurança em produção: CORS definitivo, WSS,
   capability de organizador e hardening.
5. **8.4** — teste público ponta a ponta.
6. **8.5** — correções finais e gate.

Google Auth não faz parte desse plano.

## Itens que exigem confirmação externa

- URL pública final do Vercel e do Render;
- comportamento de IP encaminhado pelo proxy do Render antes de confiar em
  cabeçalhos de proxy para rate limiting;
- projeto/backup/retensão do Supabase;
- política de expiração/revogação da capability após observação em produção.
