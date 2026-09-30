# Rodada 1 — relatório consolidado

## Decisão

**BLOQUEADO PARA INTEGRAÇÃO FUNCIONAL E DEPLOY PÚBLICO.** O Engine isolado pode ser integrado após uma rodada de compatibilidade, mas Backend, Banco e Realtime ainda não têm uma cadeia autoritativa, transacional e executável de ponta a ponta.

## Entregas por frente

| Frente | Entrega | Evidência de teste | Estado |
| --- | --- | --- | --- |
| Game Engine | Regras puras, RNG injetável, estratégias, batalha, torneio, BYE e treino isolado. | 24 testes unitários aprovados. | Pronto para integração técnica, não para produção. |
| Backend | DTOs estritos, capability local de organizador, códigos de 80 bits, limiter local e gateway futuro. | 8 testes HTTP aprovados. | Em progresso; gateway/persistência não integrados. |
| Banco + Realtime | Alembic, ledger/outbox, protocolo de canal e ADR WebSocket nativo. | 10 testes de protocolo e 6 testes textuais de schema aprovados. | Em progresso; não aplicado contra PostgreSQL nem exposto por WebSocket. |
| DevOps | SHA pinning, permissões mínimas, lockfile e `npm ci`. | Instalação limpa aprovada. | Em progresso; lint/build/testes/audit impedem release. |

## Bloqueadores de integração, em ordem

1. Unificar `Tournament` por UUID e autorização/capability persistida entre Backend e migration.
2. Criar adaptador Backend → Engine e normalizar `tied_on_*` para o nome canônico do Engine, com testes de conversão.
3. Persistir snapshots oficiais reconstruíveis de estratégia/estado; iniciar e avançar em transação com idempotência.
4. Corrigir rate limit para ocorrer antes de validação de capability em rotas administrativas e torná-lo compartilhado/durável.
5. Corrigir FK de comando/transição para preservar o escopo de torneio.
6. Implementar ticket, handshake WebSocket, validação de Origin, replay/outbox e publisher do servidor.
7. Definir e implementar SEC-006 (CORS/CSRF/sessão).
8. Corrigir lint/build, ampliar CI para executar todas as suítes/migrations e remover vulnerabilidade alta de dependência.

## Conflitos e decisões

- **Contrato:** Backend usa código como identidade enquanto Banco/Realtime usam UUID; o UUID deve ser a identidade interna, com código apenas como acesso público.
- **Estratégia:** condições de empate usam nomes divergentes; o contrato canônico deve ser o do Engine e o Backend deve adaptar/validar explicitamente.
- **Regra em aberto:** o Core não define mínimo de participantes. O Engine exige dois e o Backend permite um; o Coordenador deve pedir decisão de produto antes de liberar `start`.
- **Incidental:** `next build` alterou o arquivo não rastreado `apps/frontend/tsconfig.json`; não foi revertido para evitar sobrescrever uma alteração sem baseline. Frontend deve revisar essa alteração junto do reparo de ESLint.

## Próxima rodada recomendada

1. Backend + Banco + Game Engine, em sequência coordenada, resolvem os itens 1–5.
2. Banco + Realtime implementa transporte real depois de receber identidade/ticket do Backend.
3. DevOps e Frontend resolvem lint, teste CI e dependência vulnerável.
4. Segurança e QA repetem auditoria de integração antes de liberar Frontend, Treino, painel do organizador ou Animação.

## Gate

Nenhum SEC foi fechado. `SEC-001` a `SEC-006` e `SEC-008` bloqueiam deploy público; `SEC-007` permanece aberto até a CI validar efetivamente as suítes relevantes.
