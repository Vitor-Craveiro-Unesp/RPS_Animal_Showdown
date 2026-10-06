# Pódio e repetição — relatório A–W

Data: 2026-10-05. Escopo: alteração funcional solicitada após Segunda Chance
Zumbi. Rodada 7.1 não iniciada. Nenhum deploy, commit, push ou force push.

## A. Regra Zumbi final

Entrada inicial ímpar gera exatamente uma Segunda Chance, após os confrontos
normais da primeira rodada. Apenas um perdedor daquela rodada pode ser sorteado.
Mesmo ID, nome, animal e estratégia; vidas completas na partida especial.
O marcador 🧟 acompanha esse participante na execução. Fases posteriores com
número ímpar usam BYE; não há segunda ressurreição.

## B. Semifinais

Duas semifinais reais definem os dois finalistas e os dois candidatos ao bronze.
Snapshot público expõe semifinalist_ids e semifinal_loser_ids sem estratégias.

## C. Disputa de terceiro

Partida oficial :third-place antes da Grande Final, com os dois perdedores,
mesmo formato/estratégias e vidas completas. Vencedor do bronze não avança
para a final. Evento player_advanced não é emitido para essa vitória.

## D. Grande Final

Somente os dois vencedores das semifinais (ou a progressão normal nos casos
reduzidos) disputam a final. Começa após a conclusão do bronze, quando existente.

## E. Primeiro lugar

first_place é o vencedor da final, igual a champion_id.

## F. Segundo lugar

second_place é o perdedor da final.

## G. Terceiro lugar

third_place é o vencedor do bronze quando há duas semifinais. Com dois,
é nulo. Com três, é o único não finalista. Uma fase posterior de três possui
uma semifinal e um BYE; seu único perdedor fica em terceiro, sem partida extra.

## H. Pódio

Pódio funcional com mascote/nome, ouro acima e prata/bronze abaixo. Renderização
derivada exclusivamente do servidor. Controles administrativos aparecem junto
ao pódio, após a apresentação terminar; participantes não recebem esses controles.
Polimento premium permanece adiado para a rodada autorizada pelo proprietário.

## I. Modelo de tournament run

Migração 0006: tournament_runs, current_run_id, official_matches.run_id.
Cada run possui UUID, número, timestamps, início do intervalo de eventos,
snapshot e colocações. FKs compostas impedem vinculação entre salas diferentes.
IDs das partidas incluem a execução e são validados no Engine.

## J. Histórico

Run finalizada não é sobrescrita. Match/round ledger, eventos, transições e
snapshot final ficam preservados. Só o snapshot materializado de recuperação
é substituído pela versão corrente. Migração usa o snapshot de maior versão
nas salas antigas. Downgrade com runs existentes é recusado.

## K. Repetir torneio

POST admin/repeat, exclusivo do organizador. Exige execução atual finalizada.
Nova execução inicia diretamente, sem novo cadastro/READY e sem início automático
ao terminar a anterior. Botão Voltar ao painel não inicia competição.

## L. Reset de estado

Novo bracket, partidas, corações, rodada, campeão, pódio, espera e Zumbi.
Fila de animação, celebração e eventos visíveis são reconciliados por run.
Participantes, nomes, animais, estratégias e configurações permanecem.

## M. Novo sorteio

Embaralhamento server-side com SystemRandom; espera, Zumbi e jogadas novamente
sorteados pelo servidor/Engine. Resultados podem coincidir, sem garantia artificial
de diferença. A demonstração produziu pódios e sorteados diferentes.

## N. Idempotência

Lock da sala + Idempotency-Key + expected_run_id + fingerprint. Duplo pedido
concorrente retorna uma única execução. Retry antigo não cria outra run mesmo
depois da execução seguinte terminar. Outra aba com referência antiga recebe 409.

## O. Segurança

Autenticação, capability, revogação e ownership revalidados dentro da transação.
Estado/estratégias retornados pelo adapter são verificados; avanço não aceita run
divergente. Teste de adapter malformado confirma rollback. Agente de Segurança
revisou os deltas finais: nenhum bloqueador restante. Rate limiting preservado.

## P. Snapshot

Schema v3: run_id e pódio, além do bracket. Projeção pública contém semifinalistas,
perdedores, bronze, final e campeão, sem estratégias privadas. HTTP acrescenta
run_start_sequence em leitura consistente. Snapshots legados v1/v2 continuam
recuperáveis sem inserir bronze retroativamente.

## Q. Realtime/replay

Sequência e versão globais monotônicas; event IDs e outbox preservados.
Replay público somente da run corrente, com replay-reset para cursor antigo.
Eventos históricos continuam no banco. Frontend rejeita frames obsoletos.
Participante conectado saiu do primeiro pódio e acompanhou a segunda execução
sem recadastro; reload recuperou o segundo pódio sem repetir histórico visual.

## R. Idiomas

PT-BR, EN, 中文 e العربية centralizados no catálogo. Títulos do pódio e partidas
verificados no navegador nos quatro idiomas; main dir=rtl confirmado em árabe.
Nomes dos participantes permanecem os nomes cadastrados. Controles não vazam
para a visão do participante. Áudio continua independente e é preservado na
repetição; os quatro pares ON/OFF têm testes.

## S. Testes automatizados

Validação final: **212 testes Python passaram** (Engine, backend, PostgreSQL,
realtime e migrações), **29 testes frontend passaram**, lint, TypeScript e
build passaram. git diff --check passou. Avisos Python são de depreciação
preexistente do lifecycle on_event do FastAPI (100 avisos), não falhas.
Banco de QA dedicado: rps_round7_qa na instância isolada 55433.
Nunca foram truncadas tabelas do ambiente normal.

Cobertura nova: pódio/ordem/vidas/recuperação para 2–9 e 15 participantes nos
quatro formatos; ressurreição única; independência; estratégias/configurações
conservadas; histórico; concorrência; retry; revogação; ownership; replay;
rollback de run adulterada; áudio; proteção de downgrade e FK entre salas.

## T. E2E da primeira execução

Sala RPS-5PAFUK76T92QJKU5 criada no navegador, sete participantes READY,
Melhor de 3, velocidades 2×, música e efeitos ligados. Seis inscrições de fixture
pela API; sétima pela UI, incluindo estratégia/READY e sala de espera.
Início oficial clicado no painel do organizador.

- Run: 73071a16-f583-4220-aaf1-d793b2117400.
- UTC: 17:23:01.622809 → 17:23:37.830879.
- Aguardando: Podio QA 4, lontra.
- Zumbi: Podio QA 7, cavalo.
- Ouro: Podio QA 6, arara.
- Prata: Podio QA 2, panda.
- Bronze: Podio QA 3, canguru.

Uma seleção Zumbi, um bronze, uma final e um pódio, confirmados no ledger.
Pódio observado em organizador e participante; participante sem botão Repetir.

## U. E2E da repetição

Clique real em Repetir Torneio após observar o pódio. Novo estado recebido em
ambas as abas conectadas, sem reload para iniciar a nova competição.

- Run: 4aa733d7-cd1f-4478-8c99-eb1559bff30d.
- UTC: 17:25:04.105938 → 17:25:38.815013.
- Aguardando: Podio QA 2, panda.
- Zumbi: Podio QA 3, canguru.
- Ouro: Podio QA 3, canguru 🧟.
- Prata: Podio QA 5, tigre.
- Bronze: Podio QA 6, arara.

Novo bracket, mesma sala/sete participantes. Uma seleção Zumbi/bronze/final/pódio
por run. Ambas as execuções e seus pódios continuam no PostgreSQL. Segundo
pódio observado e recuperado após reinício local/reload; console consultado sem
erros. Abas do organizador e participante mantidas para inspeção.

## V. Git

Working tree já estava modificado por rodadas anteriores. Alterações existentes
preservadas, sem reset/checkout destrutivo, commit ou push. git diff --check
sem erros de whitespace; avisos de conversão LF/CRLF são do Git no Windows.
Arquivos desta entrega: Engine models/tournament/snapshots e testes; backend
gateway/models/main/postgres_store/public_state/competitive_events e testes;
migração 0006 e testes; realtime postgres/websocket; frontend página/arena,
áudio/apresentação/tests, estilos e catálogo; core/README e estes documentos.

## W. Gate

**PÓDIO E REPETIÇÃO APROVADOS.**

Todos os critérios funcionais desta entrega foram verificados. Revisão de
segurança concluída sem bloqueadores, E2E com duas execuções finalizado,
histórico preservado e serviços locais ativos. Aguardar aprovação do proprietário.
Não iniciar Rodada 7.1.

Observação fora deste escopo, já identificada na rodada anterior: após reload,
o painel pode exibir a capacidade padrão 8 em vez da capacidade cadastrada.
Nesta sala, ele exibiu 7/8 após recarregar; a capacidade configurada continua 7
no backend e as duas execuções preservaram os sete participantes. Não foi
alterada silenciosamente uma funcionalidade anterior para corrigir esse detalhe.
