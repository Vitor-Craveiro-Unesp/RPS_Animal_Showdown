# Realtime — decisão e protocolo V0.1

## Transporte escolhido: WebSocket nativo do FastAPI

Para V0.1, o transporte é **WebSocket nativo hospedado pelo backend FastAPI**, com PostgreSQL como ledger de eventos e outbox. Supabase Realtime não será usado nesta fase. A escolha mantém autorização de canal, execução do Engine, transação e publicação oficial no mesmo limite de confiança; também evita uma conta/projeto externo antes do deploy. Uma migração futura deve preservar este contrato.

## Isolamento e publicação oficial (SEC-003)

Há um único canal público por torneio: `tournament/{uuid-canônico}/official-events`. Código de acesso nunca é nome de canal. Antes da assinatura, o socket valida `Origin` contra allowlist, recebe rate limit e exige ticket curto emitido pelo backend. O ticket validado deve conter `subject_id`, `tournament_id`, papel (`organizer`, `participant` ou `spectator`), expiração e ID de revogação. A conexão começa sem assinatura com `authenticate`, depois aceita `resume`.

O ticket prova acesso a uma sala, não direito administrativo: identidade, revogação e autoridade do organizador continuam em SEC-001. Sem grant da sala, o servidor retorna erro genérico. Após controles, o WebSocket é somente servidor → cliente. Intenções seguem HTTP validado; não existe frame de cliente para evento, resultado, corações, vencedor, BYE, avanço ou chaveamento. Apenas o publisher interno lê `realtime_outbox`.

Cada envelope contém `eventId` UUID, `tournamentId`, `sequence` crescente por torneio, `eventType` e `payload` público derivado do estado oficial. Estratégias privadas, credenciais, tickets e RNG nunca entram no payload.

## Reconexão e duplicação

Após autenticar, o cliente envia `{ "type": "resume", "afterSequence": N }`. O servidor carrega eventos da sala acima de N em ordem, e só então entrega eventos ao vivo. A entrega é **at-least-once**: uma corrida de replay/live pode repetir evento. Cliente persiste a maior sequência por torneio, ignora `eventId` repetido e sequência menor/igual; diante de lacuna, pede replay. `EventCursor` implementa e testa essa regra.

## Transação, concorrência e idempotência (SEC-005)

Para toda intenção que muda estado oficial, o backend deve executar uma transação curta:

1. Autenticar/autorizar sujeito na sala.
2. Inserir/ler `idempotency_commands` por `(tournament_id, actor_subject_id, operation, idempotency_key)`. A mesma chave com fingerprint diferente falha; comando concluído retorna resposta persistida sem rodar Engine novamente.
3. Executar `SELECT ... FROM tournaments WHERE id = :id FOR UPDATE`; toda query é escopada por `tournament_id`.
4. Validar versão/estado, rodar Engine no servidor, incrementar `state_version` uma vez, gravar transição e eventos com sequências reservadas.
5. Gravar uma linha outbox por evento e completar comando; fazer `COMMIT` antes de WebSocket.
6. Publishers usam `FOR UPDATE SKIP LOCKED`, emitem e marcam `published_at`. Lease vencido permite nova tentativa; UUID/sequência tornam repetição segura.

O banco força chave idempotente escopada, transição única por versão e sequência única por sala. Constraints não substituem lock, predicado de versão, autorização ou validação do Engine.

## Implementação executável da Rodada 2

`realtime/websocket.py` oferece `register_realtime_endpoint(app, ...)`, a ser chamada explicitamente na factory FastAPI do Backend. O endpoint é `GET` WebSocket `/v1/realtime`; ele exige, nesta ordem:

1. `Origin` presente na allowlist exata, **antes de `accept`**;
2. em até 10 segundos, `{ "type": "authenticate", "ticket": "…", "channel": "tournament/{uuid}/official-events" }`;
3. validação HMAC do ticket **e** consulta persistida de ticket/capability não expirada ou revogada;
4. em até 10 segundos, `{ "type": "resume", "afterSequence": N }`.

Depois da assinatura, aceita `resume` e `{ "type": "renew", "ticket": "..." }`; qualquer tentativa de publicar evento fecha o socket com `1008`. A renovação exige ticket válido no banco, mesma sala/sujeito/papel e expiração posterior. Tem intervalo mínimo de 30 segundos, verificado antes da consulta ao banco, e não reinicia cursor, assinatura ou orçamento de replay. A resposta `renewed` informa `expiresInMs`, usado pelo navegador para renovar 60–75 segundos antes da expiração sem depender do relógio local. A revalidação/revogação continua a cada cinco segundos.

Em toda saída, as tarefas pendentes de recepção/fanout são canceladas e a fila é removida da assinatura. O endpoint não conhece código público de torneio. Os testes de conexão verificam Origin, isolamento entre UUIDs, replay, renovação e publicação forjada.

O limitador PostgreSQL do handshake roda em thread, assim como a verificação de tickets; nenhuma dessas operações bloqueia o event loop que entrega eventos aos espectadores já conectados. A implantação permanece com **um worker** enquanto o fanout for local ao processo.

`realtime/postgres.py` traz `PostgresRealtimeStore` para ticket/replay duráveis e `PostgresOutboxWorker` com `FOR UPDATE SKIP LOCKED` e lease. O worker só publica depois do commit da transição e marca `published_at` após entrega. Falhas liberam a lease e a entrega permanece at-least-once. `DatabaseBackedEventStream` combina replay PostgreSQL com fanout local do worker.

O schema também vincula cada ticket ao grant persistido completo
`(tournament_id, capability_id, subject_id, role)`, não somente ao UUID da
capability. Assim um ticket não pode assumir outro sujeito/papel, inclusive
dentro da mesma sala. Os instantes de emissão, `not_before` e expiração usam a
mesma precisão de segundos dos claims assinados, evitando uma corrida de
subsegundo entre o relógio da aplicação e o `CURRENT_TIMESTAMP` do banco.

## Contrato PostgreSQL para o Backend

O Backend permanece proprietário da intenção HTTP e chama o repositório
transacional. Para uma mutação oficial, ele deve fornecer ao repositório o UUID
canônico do torneio, sujeito autorizado, operação, `Idempotency-Key`, fingerprint
SHA-256 e o snapshot canônico retornado pelo Engine. O repositório deve, no mesmo
commit, gravar `idempotency_commands`, `official_transitions`,
`official_state_snapshots`, `official_game_events` e `realtime_outbox`; a resposta
persistida é a única resposta a ser reutilizada para a mesma chave. Nenhum destes
documentos pode ser composto a partir de resultado, vida, vencedor ou chaveamento
enviado pelo cliente.

Para registrar realtime, o Backend cria `PostgresRealtimeStore(DATABASE_URL)`,
`DatabaseBackedEventStream`, `TicketVerifier` e chama
`register_realtime_endpoint`. Também emite a linha de
`realtime_access_tickets` depois de validar a capability persistida. O worker usa
um `worker_id` único por processo, chama `publish_one(stream)` continuamente e só
deve iniciar depois que migrations forem aplicadas. O código público nunca entra
em consultas internas, nomes de canal ou payloads de eventos.

### DSNs

`PostgresRealtimeStore` aceita tanto a URL de SQLAlchemy
`postgresql+psycopg://…` como a URL libpq `postgresql://…` e normaliza antes de
chamar `psycopg.connect`. Porém `psycopg.connect` em si não aceita a forma
SQLAlchemy. Assim, `RPS_TEST_DATABASE_URL` é sempre `postgresql://…`; Alembic
recebe a forma `postgresql+psycopg://…` derivada por `realtime.dsn`. O job de CI
deve preservar essa separação.

## Limites/pendências de integração

- O Backend deve emitir capabilities/tickets após sua autorização persistida, instanciar `TicketVerifier`/`PostgresRealtimeStore`, registrar o router e executar o worker. Esta tarefa não modificou `apps/backend/` para não tomar posse da fronteira HTTP.
- O limiter de conexão/reconexão precisa ser o limiter compartilhado do Backend, antes de `websocket.accept()`. CORS/CSRF/sessão pertencem à SEC-006 e continuam pendentes.
- `DatabaseBackedEventStream` é apropriado para uma única instância V0.1. Antes de escalar horizontalmente, trocar o fanout local por um broker compartilhado; o replay do PostgreSQL já é durável.
- Tipos de `eventType` serão fechados com o contrato estável do Game Engine; não transportarão estado competitivo recebido do navegador.
- Retenção de eventos, métricas/alertas de outbox e o provedor de produção são pendências antes do deploy público; até lá, manter histórico do torneio para replay.

## Verificação local

```powershell
python -m unittest discover realtime/tests -v
python -m unittest discover database/migrations/tests -v
$env:RPS_TEST_DATABASE_URL = "postgresql://rps_test:local-development-only@localhost:5432/rps_animal_showdown_test"
python -m pytest -q database/migrations/tests/test_postgres_constraints.py
```
