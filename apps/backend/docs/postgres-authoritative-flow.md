# Fluxo autoritativo PostgreSQL

`DATABASE_URL` é obrigatório no serviço FastAPI e seleciona
`PostgresTournamentStore`; sua ausência interrompe a inicialização. O adaptador
em memória só existe quando um teste unitário o injeta explicitamente
na factory. As migrations Alembic devem estar aplicadas antes de iniciar a API.

## Início idempotente

`POST /v1/tournaments/{code}/admin/start` aceita somente `{}` e uma
`Idempotency-Key` UUID. Em uma transação PostgreSQL, o backend bloqueia o
torneio, valida a capability persistida, reserva a chave, executa o Engine e
persiste snapshots de jogador/estratégia, transição, snapshot oficial, evento e
outbox. O snapshot é gerado por `tournament_state_to_snapshot()` e restaurado
por `tournament_state_from_snapshot()` antes do commit. A mesma chave concluída
retorna a resposta durável sem executar o Engine novamente.

## Realtime

`REALTIME_TICKET_SIGNING_KEY` é obrigatório no caminho PostgreSQL. Tickets de
cinco minutos são emitidos somente após autorização persistida e gravados em
`realtime_access_tickets`. O backend registra `/v1/realtime`, limita a conexão
antes do `accept`, valida Origin/ticket/capability e executa o worker de outbox.
O worker usa `SKIP LOCKED`, publica somente depois do commit e permite entrega
at-least-once.

## Rate limiting compartilhado

`shared_rate_limit_buckets` usa contador PostgreSQL de janela fixa com TTL e
`INSERT … ON CONFLICT` atômico, portanto múltiplas instâncias da API compartilham
o mesmo orçamento. As chaves persistidas são hashes de `operação + sujeito`;
endereços IP e bearers em texto nunca são armazenados. A API usa somente o peer
ASGI e ignora `X-Forwarded-For`/`Forwarded`. Em falha do banco/limiter, HTTP
responde 503 e o handshake WebSocket é fechado com 1013 antes de `accept`.

A suíte opt-in `apps/backend/tests/test_postgres_e2e.py` requer
`RPS_TEST_DATABASE_URL` isolada e prova a cadeia HTTP → Engine → snapshot
canônico → transição/evento/outbox, expiração/revogação de capability,
isolamento por UUID, concorrência/idempotência/rollback e orçamento compartilhado
entre duas instâncias.
