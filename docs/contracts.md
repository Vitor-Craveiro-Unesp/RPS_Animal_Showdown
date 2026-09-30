# Contratos de integração da V0.1

Este é o contrato de coordenação até que os tipos estáveis sejam implementados em `packages/shared-types/`. Não criar cópias incompatíveis em frontend, backend ou Engine.

| Contrato | Proprietário | Consumidores | Responsabilidade |
| --- | --- | --- | --- |
| `Tournament` | Backend + Banco | Frontend, Realtime | UUID interno canônico; código opaco é somente acesso público; capacidade, mínimo de 2 confirmados para iniciar, estado de inscrições e autoridade do organizador. |
| `Player` | Backend + Banco | Frontend, Engine | Identidade no torneio, personagem, estado de prontidão e vínculo com a estratégia. |
| `Strategy` | Game Engine | Backend, Frontend | Distribuições inicial e condicionais; validação de escolhas e soma 100%. Condições canônicas: `initial`, `lost_to_*`, `won_against_*`, `tied_with_*`. |
| `Match` / `MatchRound` | Game Engine | Backend, Realtime, Frontend | Estado da batalha, rodada, vidas, escolhas e transição válida. |
| `GameState` | Game Engine | Backend, Realtime | Estado oficial e imutável da transição concluída. |
| `GameEvent` | Backend + Realtime | Frontend | Evento público derivado do estado oficial, com sequência e escopo de torneio. |
| `AccessCapability` / `RealtimeTicket` | Backend + Banco + Realtime | Realtime | Credencial opaca persistida e ticket curto assinado; ambos vinculados ao UUID de torneio, sujeito, papel, expiração e revogação. |

## Regras de fronteira

- O Engine define modelos de domínio e transições; não conhece HTTP, bancos ou sockets.
- O Backend define DTOs de intenção, autentica/autoriza e traduz para o Engine.
- Realtime só emite `GameEvent` criado pelo servidor; não aceita eventos oficiais do cliente.
- Frontend representa estado e envia intenções. Não calcula nem persiste o resultado competitivo.
- Antes de adicionar tipos em `packages/shared-types/`, Backend, Game Engine e Frontend revisam o contrato e registram versionamento/compatibilidade.
- `tied_on_*` não é um alias aceito: Backend e testes devem usar exclusivamente `tied_with_rock`, `tied_with_paper` e `tied_with_scissors`.
- O código público é somente um mecanismo de entrada; não aparece como PK, FK, nome de canal ou identificador de evento. O UUID canônico é a identidade interna obrigatória.
- Uma capability é armazenada somente como hash e pode ser revogada. Um ticket de realtime curto contém `jti`, `subject_id`, `tournament_id`, `role`, `not_before` e `expires_at`; o handshake valida assinatura **e** a linha persistida, inclusive a capability de origem.
- Snapshots de estratégia, jogador, estado, partida e rodada são documentos canônicos validados pelo Engine, acompanhados de SHA-256 e vinculados por FKs compostas ao torneio. O Backend reconstrói o estado oficial a partir deles; o cliente nunca os fornece como verdade competitiva.

## Intenções permitidas vs. proibidas

| Cliente pode enviar | Cliente não pode enviar |
| --- | --- |
| entrar no torneio, salvar estratégia, marcar pronto, escolha de treino, reconectar | vencedor, resultado de rodada, corações restantes, BYE, avanço, chaveamento ou evento oficial |
