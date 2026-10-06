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
Na borda HTTP, somente `hearts_required` de 1 a 4 é aceito, correspondendo
exatamente aos formatos aprovados melhor de 1, 3, 5 e 7.

## Progressão competitiva

Após o início, um worker do backend seleciona um torneio `running` elegível
com `FOR UPDATE SKIP LOCKED` e resolve **uma** rodada por transação. A cada
passo, ele confere o snapshot canônico e os snapshots imutáveis das estratégias,
chama `play_active_match_round()` do Game Engine e grava versão, transição,
snapshot, partida, rodada, eventos oficiais e outbox no mesmo commit. Empates
geram nova rodada sem perder coração. A cadência mínima de um segundo entre
rodadas evita um ciclo ocupado. Após oito empates consecutivos, `next_transition_at`
impõe uma espera exponencial até uma hora, persistida no banco; uma rodada
decisiva restabelece a cadência normal. Isso não limita nem altera os resultados
do Engine. Após reinício, o worker retoma o último snapshot confirmado. O lock e as restrições
de versão/rodada impedem que dois workers resolvam a mesma rodada.

Somente o snapshot canônico **mais recente** permanece em
`official_state_snapshots`. O digest de cada transição, o ledger de eventos e
`official_match_rounds` preservam o histórico. A projeção pública de cada
partida inclui apenas sua troca mais recente, evitando copiar todo o histórico
em cada evento realtime. A sala não perde a sequência de eventos nem a
capacidade de recuperação por snapshot.

O backend deriva os eventos `match_started`, `round_resolved`, `heart_lost`,
`player_eliminated`, `match_completed`, `player_advanced`, `bye` e `champion`
da transição oficial. A projeção pública usada em `round_resolved` e em
`GET /v1/tournaments/{code}/official-state` é uma lista explícita de campos;
ela nunca serializa o snapshot privado do Engine nem expõe probabilidades,
condições de estratégia, capabilities ou tokens. O endpoint de fallback exige
capability de organizador ou participante da própria sala.

## Realtime

`REALTIME_TICKET_SIGNING_KEY` é obrigatório no caminho PostgreSQL. Tickets de
cinco minutos são emitidos somente após autorização persistida e gravados em
`realtime_access_tickets`. O backend registra `/v1/realtime`, limita a conexão
antes do `accept`, valida Origin/ticket/capability e executa o worker de outbox.
O worker usa `SKIP LOCKED`, publica somente depois do commit e permite entrega
at-least-once. Dentro de cada torneio, ele só seleciona o próximo evento se
todos os eventos anteriores já foram publicados; isso preserva a sequência
para WebSocket, replay e deduplicação. O cliente usa o snapshot autenticado
como fallback e mantém um cursor de sequência ao reconectar. O replay lê lotes
de até 250 eventos por consulta, sem materializar todo o histórico numa só
tupla; o fanout de produção não retém uma segunda cópia dos eventos em memória.
Cada conexão aceita no máximo três pedidos de replay e envia até mil eventos
históricos; ao atingir o orçamento, fecha com 1013 para o cliente reconectar
com o cursor já avançado. A fila live por assinante guarda no máximo 256 eventos;
uma lacuna é recuperada pelo replay durável. Tickets/capabilities são
revalidados durante o replay e a cada cinco segundos de conexão, limitando o
tempo de acesso após revogação e fazendo o socket renovar ticket expirado.
Se ticket/WebSocket falhar, o frontend consulta periodicamente o snapshot
oficial a cada 15 segundos. O limite de autenticação distingue orçamento
compartilhado por IP (120/min) e por capability (20/min), permitindo usuários
atrás do mesmo IP sem enfraquecer o limite individual. A V0.1 ainda pressupõe **uma instância backend**: o fanout ao vivo é
local ao processo. Escalar para várias instâncias exige um broker compartilhado.

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
entre duas instâncias. Ela também percorre chaveamentos de três (BYE) e quatro
participantes até campeão, verifica sequência/replay e retoma a execução com
uma nova instância do repositório após uma rodada confirmada. Verifica também
o backoff após empates longos e que apenas o snapshot atual é mantido. Nunca aponte
`RPS_TEST_DATABASE_URL` para o banco de desenvolvimento: o fixture limpa
`tournaments` no banco informado.
