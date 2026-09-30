# Rodada 4 — relatório consolidado

## Decisão

**BLOQUEADO.** A cadeia durável foi comprovada localmente, mas `SEC-004` continua ALTO: o rate limiting é somente por processo e não atende o cenário de múltiplas instâncias previsto. `SEC-007` também continua aberto sem execução remota comprovada da CI. Deploy público permanece proibido.

## Evidência PostgreSQL real

- Docker Desktop 4.59.0 e PostgreSQL 16.15 foram iniciados localmente via `docker compose`; o serviço não publica porta no host.
- O banco `rps_animal_showdown` executou migrations `0001` a `0003`; a revisão `0002` foi encurtada para caber no limite padrão de 32 caracteres do Alembic.
- Migrações: upgrade, downgrade/reupgrade, FKs compostas e associação cross-tournament passaram.
- E2E HTTP → Engine → snapshot canônico → commit → outbox → worker → WebSocket: **4 passed**.
- Suíte PostgreSQL de migration/realtime: **5 passed**. Suíte integrada: **95 passed**.

## Correções e garantias

- `_load_players` fazia `fetchall()` depois de reutilizar o cursor para regras. Agora materializa participantes antes da segunda query; há regressão para 0/1/2/muitos e isolamento UUID.
- Perfil durável exige `DATABASE_URL`; a store em memória depende de injeção explícita nos testes unitários.
- Capabilities persistentes são hashadas, expiram, podem ser revogadas e são isoladas por torneio.
- Start é transacional e idempotente; dois starts concorrentes não duplicam evento/outbox. Falha do Engine não deixa start/snapshot/evento/outbox parcial.
- WebSocket rejeita Origin antes do accept, possui timeout de auth/resume, cleanup explícito e replay. Outbox adota semântica at-least-once com deduplicação por evento/sequence no cliente.

## QA e segurança

- `npm run lint` e `npm run build` em `apps/frontend`: passaram.
- `npm audit --omit=dev --audit-level=high`: nenhuma vulnerabilidade.
- `python -m pip_audit -r requirements.txt`: nenhuma vulnerabilidade conhecida.
- `git diff --check`: passou.
- `SEC-001`, `SEC-002`, `SEC-003`, `SEC-005`, `SEC-006` e `SEC-008`: concluídos localmente e registrados no backlog.
- `SEC-004`: aberto/ALTO — limitar em memória não funciona entre instâncias; requer backend compartilhado simples antes do release.
- `SEC-007`: aberto — CI está configurada com PostgreSQL e actions por SHA, mas não há prova de run remoto neste checkout.

## Navegador

- `http://127.0.0.1:3000/`: HTTP 200, mas ainda apresenta tela vazia (somente o controle do Next.js). Não foi criado frontend funcional.
- `http://127.0.0.1:8000/health`: HTTP 200, `{\"status\":\"ok\"}`. O processo local pode não refletir alterações sem reinício; a prova oficial desta rodada foi executada em containers de teste.

## Próxima rodada

Não liberar frontend funcional, criação/entrada, painel do organizador, estratégia, Treino ou mapa-múndi enquanto SEC-004 permanecer ALTO. A próxima rodada deve implementar e testar um limiter compartilhado compatível com a topologia de V0.1 e obter execução remota da CI.
