# Rodada 2 — relatório consolidado

## Decisão

**BLOQUEADO PARA INTEGRAÇÃO FUNCIONAL COMPLETA E DEPLOY PÚBLICO.** A Rodada 2 entregou os componentes da cadeia, mas ainda não sua execução única e durável: o Backend não persiste o snapshot canônico nem registra realtime PostgreSQL.

## Contratos unificados

- `Tournament`: UUID hifenizado é o identificador interno canônico; código opaco é somente acesso público.
- Início exige pelo menos 2 participantes confirmados; capacidade continua sendo apenas máximo.
- `Strategy`: usa exclusivamente `initial`, `lost_to_*`, `won_against_*` e `tied_with_*`; `tied_on_*` é rejeitado.
- Snapshot oficial: schema v1/kind `tournament_state`, serializado e restaurado somente pela API do Engine.

## Entregas e limites

| Área | Entrega | Limite que impede integração |
| --- | --- | --- |
| Engine | Snapshots estritos/restauráveis, UUID canônico, 33 testes. | Backend não usa o serializador canônico. |
| Backend | Adapter real local, mínimo 2, DTO canônico, CORS, rate limit administrativo. | Store/capability/snapshot ainda em memória; não há transação/outbox/ticket operando. |
| Banco + Realtime | Migration 0002, capability/ticket/snapshot, FKs compostas, endpoint WS e outbox. | Não aplicado em PostgreSQL real; não registrado pelo Backend. |
| DevOps | Next 16, lockfile, CI ampliada, Docker Engine importável. | DSN da CI é incompatível com `psycopg.connect()`; auditorias/CI completas sem evidência remota. |

## QA e Segurança

- QA: 72 testes aprovados e 1 PostgreSQL ignorado; confirmou fluxo local em memória e rejeição de estado oficial do cliente.
- Segurança: fechou **SEC-006**. Manteve SEC-001, 002, 003, 004, 005, 007 e 008 abertos.
- Bloqueadores prioritários: snapshot Backend incompatível, persistência em memória, websocket não registrado, ausência de transação/idempotência, limiter não compartilhado e CI PostgreSQL inválida.

## Validação local no navegador

- Backend: `http://127.0.0.1:8000/health` respondeu `200` com `{"status":"ok"}`.
- Frontend: `http://127.0.0.1:3000` abriu no navegador e respondeu `200`.
- A página atual é a casca técnica vazia (`<main />`), portanto não há fluxo de torneio, tela ou responsividade de produto para validar visualmente.
- A automação de navegador confirmou título e renderização sem página de erro visível. Ela não expôs uma API de console nesta sessão; a verificação de rede disponível foi o HTTP local acima.
- O preview permanece local, não publicado: o proprietário pode abrir `http://127.0.0.1:3000` enquanto os processos desta sessão estiverem ativos.

## Próxima ordem obrigatória

1. Backend corrige IDs de jogador e usa `tournament_state_to_snapshot()` / `tournament_state_from_snapshot()`.
2. Backend implementa repositório PostgreSQL transacional: lock, idempotency key, Engine, snapshot, transição, evento e outbox em um commit.
3. Backend registra WebSocket, emite ticket persistido, aplica rate limit antes de handshake e inicia worker outbox.
4. Banco/QA aplicam migrations e executam isolamento/concorrência contra PostgreSQL real.
5. DevOps normaliza DSN para `psycopg`, prova CI completa e auditorias.
6. Segurança e QA reavaliam antes de liberar Frontend funcional, Treino, painel do organizador ou Animação.
