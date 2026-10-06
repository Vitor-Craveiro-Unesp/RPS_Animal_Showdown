# Rodada 6.6 — Segunda Chance Zumbi

## A. Regra anterior encontrada

O motor escolhia um BYE aleatório em toda fase ímpar, inclusive a primeira. O vencedor de cada partida e o BYE formavam a fase seguinte.

## B. Nova regra implementada

Novos torneios inicialmente ímpares sorteiam um participante aguardando. Todos os outros disputam os confrontos iniciais. Ao terminar o último desses confrontos, o servidor escolhe um perdedor e cria a partida oficial de Segunda Chance contra quem aguardou. Somente o vencedor entra com os vencedores iniciais na fase seguinte.

## C. Sorteio do participante aguardando

`start_tournament` usa o RandomSource recebido pelo servidor. Produção usa SystemRandomSource; testes usam fontes determinísticas/seeds. O ID sorteado fica no snapshot `waiting_player_id`; não é um BYE inicial. Nenhum campo de comando permite ao organizador escolher o aguardando.

## D. Seleção do perdedor

O conjunto elegível é derivado dos perdedores das partidas ordinárias da primeira fase. A escolha e a criação da partida especial são uma única transição imutável. Não existe estado persistido entre a última derrota e a seleção. A projeção pública inclui `eligible_loser_ids` para auditoria.

## E. Status Zumbi

`second_chance_player_id` registra o sorteado. A projeção deriva `players[].second_chance`; nenhum animal canônico é alterado. Arena, chaveamento, campeão e log apresentam o emoji original acrescido de 🧟. O indicador permanece nas fases seguintes e no histórico.

## F. Corações

A partida especial chama `start_match` com o mesmo `hearts_per_match`: MD1=1, MD3=2, MD5=3, MD7=4. Ambos começam completos; a derrota original continua com zero no registro original. Não há vantagem mecânica do Zumbi.

## G. Estratégia

Os mesmos objetos Competitor/Strategy congelados são reutilizados. Validação compara cada competidor da partida ao canônico. PostgreSQL continua comparando estratégias do documento com os snapshots privados bloqueados. As rotas de edição continuam fechadas após Start.

## H. Game Engine

Mudanças em `models.py`, `tournament.py`, `snapshots.py`; mesma função de RPS, probabilidades, condições, empate e perda de coração. O novo validador rejeita vencedor como Zumbi, seleção em fase posterior, partida duplicada, jogadores incorretos e estratégia divergente.

## I. Bracket

| Inscritos | Primeira fase | Progressão após Segunda Chance | Partidas totais |
|---|---|---|---|
| 3 | 1 ordinária + 1 especial | 2 → campeão | 3 |
| 5 | 2 ordinárias + 1 especial | 3 → 2 → campeão | 5 |
| 7 | 3 ordinárias + 1 especial | 4 → 2 → campeão | 7 |
| 9 | 4 ordinárias + 1 especial | 5 → 3 → 2 → campeão | 9 |
| 4 (controle) | 2 ordinárias | 2 → campeão | 3 |

Cada fase posterior ímpar tem somente um BYE local à fase, escolhido pelo mecanismo anterior. Nunca há nova ressurreição. A partida especial usa ID estável `<tournament-id>:r1:second-chance`, fica ao final da fase 1 e tem título próprio no bracket.

## J. Eventos

Eventos adicionais: `player_waiting`, `second_chance_selected`, `second_chance_match_started`, `second_chance_completed`, `player_eliminated_definitively`. Eventos existentes de rodada, coração, eliminação, vitória, avanço e campeão permanecem. Nenhum evento oficial nasce no cliente. Os novos passos de apresentação são silenciosos; nenhum novo efeito sonoro foi adicionado.

## K. Snapshot

Schema v2 exige os dois novos campos por fase e exige participante aguardando em torneios inicialmente ímpares. Snapshot privado preserva histórico e estratégias. HTTP/WS usam whitelist: IDs, nomes, animal, status, vidas e resultados; sem probabilidades, condições de estratégia ou credenciais.

Snapshots v1 de torneios antigos com BYE inicial continuam sendo lidos e reserializados como v1 até o campeão. Não se converte uma partida já iniciada à regra nova. A revisão de segurança encontrou e foi corrigida uma permissividade de v2 na ausência dos campos; testes de adulteração cobrem remoção e anulação deles.

## L. PostgreSQL/idempotência

Sem nova tabela/migração: o documento versionado e as tabelas de partidas já comportam o confronto especial. Lock `FOR UPDATE SKIP LOCKED` na raiz, snapshot, partidas, jogada, eventos e outbox continuam na mesma transação. ID/sequence/versão e chaves únicas preservados. Dois workers concorrentes produzem uma única transição.

Outbox tem entrega **at-least-once**: o mesmo pacote pode ser reenviado após falha. A garantia é um registro oficial por evento e deduplicação por ID/sequência no consumidor, não entrega de rede exatamente uma vez.

## M. Restart/recuperação

Testes reconstroem o estado após cada jogada, antes/depois da seleção, durante a partida especial e após seu resultado. Teste PostgreSQL cria novos workers/repositórios/engines a cada avanço e mantém histórico. A fronteira “primeira fase concluída antes da seleção” não é commitável: seleção e criação fazem parte da mesma transação; rollback mantém o estado anterior.

## N. Realtime/replay/reconnect

Novos eventos percorrem as tabelas, outbox e canal autenticado existentes. Testes recuperam eventos a partir do cursor da seleção e reconectam um WebSocket autenticado confirmando a próxima sequência. A fila visual rejeita ID/sequência repetidos e descarta passos anteriores ao snapshot reconciliado.

## O. Idiomas

Textos centralizados em `catalog.ts`: PT-BR, EN, chinês simplificado e árabe. Novos textos de aguardando, seleção, partida especial, retorno, Zumbi e eliminação definitiva. Estrutura RTL existente preservada; nenhuma string nova de interface isolada no componente.

## P. Testes 3/5/7/9 participantes

`test_second_chance.py`: produto cartesiano de 3/5/7/9 e controles pares 2/4/6/8 com 1/2/3/4 corações, restore a cada transição, identidade, estratégia, conjunto elegível, corações completos, uma única partida especial, derrota preservada e um campeão. Seeds adicionais comprovam empate e vitória de ambos os lados.

`test_postgres_e2e.py`: 3/5/7/9 e controle 4 com PostgreSQL real, workers concorrentes, recuperação, animal original, projeção pública, sequência, replay e reconnect WebSocket. Banco QA isolado `rps_round7_qa`; testes de limpeza nunca apontados para banco normal/demo.

## Q. E2E manual

Concluído localmente: sala `RPS-N527A5G73YB7ESR9`, sete inscritos, MD3, 2×. Organizador criado e Start acionado pela UI; participantes de teste inscritos por HTTP com estratégia uniforme e READY, sem manipular o banco. Sete READY confirmados no painel.

- Aguardando: Zumbi QA 3, canguru 🦘 (evento #2).
- Confrontos ordinários: águia × panda, lontra × tigre, elefante × urso. Perdedores: águia, lontra e urso.
- Selecionado: Zumbi QA 4, lontra 🦦🧟 (#32); partida especial #33 contra o canguru.
- Snapshot público da transição de seleção confirmou **2 e 2 corações** para a nova partida.
- Lontra venceu a Segunda Chance (#42), canguru eliminado definitivamente (#43).
- Lontra avançou com 🧟, derrotou o elefante e perdeu a final contra Zumbi QA 5, tigre 🐯, campeão (#69).
- Snapshot final schema 2; somente um evento de cada seleção/início/resultado especial; derrota original preservada no bracket.
- UI observada em PT/EN/ZH/AR; `dir=rtl` confirmado em árabe. Console final sem erros registrados. Tela final e bracket deixados abertos.

A primeira tentativa carregava o motor antigo instalado no container; foi reconstruído o backend e esse torneio legado terminou normalmente pela regra anterior. Durante preparação, o limite de inscrições foi atingido: aguardada a janela original, sem desativar ou contornar proteção. Observação preexistente fora do escopo: após reload, o denominador de capacidade do painel voltou ao padrão 8, embora a sala criada tivesse capacidade 7; os sete participantes reais e a regra do servidor não foram afetados.

## R. Regressões e QA

- 155 testes de backend/motor/realtime/PostgreSQL passaram na execução final, incluindo os 36 testes de Segunda Chance.
- Frontend: 24 testes, lint dos fontes, TypeScript e build passaram. Lint completo passou com `--ignore-pattern '**/.pytest_cache/**'` (cache Python inacessível pelo usuário do container). Nenhum teste removido.
- `git diff --check` passou; apenas avisos de normalização LF/CRLF.
- Avisos de depreciação FastAPI `on_event` preexistentes.
- Revisão independente de segurança: achado corrigido e retestado, sem pendência adicional no escopo.
- Retomada final: marcador animal + 🧟 sem quebra e largura mínima de 220px somente nas colunas com Segunda Chance. Verificado no navegador; 24 testes frontend, lint, TypeScript e build novamente aprovados após esse ajuste. Backend não alterado na retomada.

## S. Git

Sem commit, push, reset ou deploy. Worktree já continha alterações extensas das rodadas anteriores, preservadas. Arquivos desta rodada: engine models/tournament/snapshots e testes, backend public_state/competitive_events e testes, cinematic-arena/presentation/catalog e teste, PROJECT_CORE/README e este relatório.

## T. Gate

**SEGUNDA CHANCE APROVADA** no escopo funcional e de segurança desta rodada. Testes e demonstração de sete até campeão concluídos. A observação preexistente de capacidade visual após reload foi registrada em Q, sem modificar funcionalidades adjacentes. Rodada 7.1 não iniciada. Aguardar aprovação do proprietário.
