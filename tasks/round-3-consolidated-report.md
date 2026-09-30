# Rodada 3 — relatório consolidado

## Decisão

**BLOQUEADO.** A cadeia PostgreSQL/realtime não atingiu o critério de sucesso: não houve execução contra PostgreSQL real e QA/Security encontraram um defeito que torna o repositório durável incapaz de carregar participantes.

## Entregas válidas

- Engine: snapshot v1 canônico, UUIDs hifenizados, round-trip JSON e 37 testes.
- Backend: repositório PostgreSQL, transação/idempotência/outbox, ticket e endpoint realtime implementados no código.
- Banco + Realtime: DSN normalizado, FKs compostas, testes de replay/outbox/claim concorrente e documentação de transação.
- DevOps: DSN libpq para psycopg, CI PostgreSQL configurada, Compose com chave realtime obrigatória e script de teste isolado.

## Bloqueadores encontrados na revisão

1. `PostgresTournamentStore._load_players()` sobrescreve o cursor de membros com a consulta de regras antes de `fetchall()`. O estado carregado tem `players={}`, quebrando autorização, capacidade e início com dois participantes.
2. Não há teste PostgreSQL E2E para HTTP → Engine → snapshot → transição/evento/outbox → WebSocket, nem corrida real de dois starts.
3. `DATABASE_URL` ausente seleciona silenciosamente store em memória; o perfil público precisa falhar fechado.
4. Limites para credenciais inválidas de participante ocorrem depois de autenticação; limiter é por processo e não cobre realtime adequadamente.
5. WebSocket aceita conexão antes de validar Origin, não tem timeout de autenticação/resume nem limpeza explícita de tasks pendentes.
6. PostgreSQL real, Alembic e auditorias online não puderam rodar localmente; CI remota ainda não possui evidência de execução bem-sucedida.

## Evidência

- 78 testes locais passaram; 3 testes PostgreSQL foram ignorados por ausência de `RPS_TEST_DATABASE_URL`.
- Lint, compilação Python e `git diff --check` passaram.
- O daemon Docker, PostgreSQL local, Alembic e psycopg não estão disponíveis no host.
- `npm audit` não alcançou o registry local.

## Próxima rodada obrigatória

1. Corrigir `_load_players` e adicionar E2E PostgreSQL que reproduza criação, dois jogadores, estratégia, start, snapshot, outbox e evento WebSocket.
2. Tornar `DATABASE_URL` obrigatório no perfil público/Compose; preservar memória somente em testes explicitamente selecionados.
3. Aplicar limiter antes de autenticação de participante e escolher armazenamento compartilhado para V0.1 distribuída.
4. Validar Origin antes de `accept()`, limitar/expirar handshake e cancelar tasks na desconexão.
5. Rodar migrations, concorrência e CI completos contra PostgreSQL real antes de nova revisão de Segurança/QA.
