# Pódio e execuções independentes

## Engine e bronze

Snapshot v3 inclui run_id e first_place/second_place/third_place derivados do
bracket validado. Duas semifinais de quatro participantes geram uma partida
identificada por :third-place antes da final, com os perdedores e vidas completas.
Ela não integra advancing_ids. Finalistas são exclusivamente os vencedores das
semifinais. As estratégias são os mesmos objetos congelados da inscrição.

Com dois não há bronze. Com três, o único não finalista recebe bronze. Com uma
fase posterior de três, BYE leva um jogador à final e o perdedor da semifinal
única recebe bronze. Não é inventado um confronto nem um segundo Zumbi.
Snapshots antigos v1/v2 continuam recuperáveis, sem inserir retroativamente
partidas de bronze nas competições antigas.

## Persistência e migração

0006_tournament_runs adiciona runs numeradas por sala, timestamps, início do
intervalo de eventos, snapshot completo e três colocações. current_run_id e
official_matches.run_id usam FKs compostas com tournament_id. Match IDs são
namespaced por run. Eventos e versões continuam globalmente crescentes na sala.
O snapshot materializado mais recente é substituível; snapshots finais de runs
e o ledger de transições, partidas, rounds e eventos são preservados.

A migração escolhe o snapshot de maior versão de cada sala legada (inclusive
bancos antigos que ainda guardam vários snapshots cumulativos). Não remove
histórico. Downgrade é permitido somente sem runs; com histórico é recusado:
usar backup anterior à migração.
Nos registros legados, started_at usa created_at como aproximação; não se
inventam colocações históricas ausentes.

## Repetição e segurança

POST /v1/tournaments/{code}/admin/repeat exige capability do organizador,
Idempotency-Key UUID e expected_run_id. Dentro da mesma transação, bloqueia sala,
revalida capability/ownership/revogação, exige run encerrada e confere fingerprint.
Mesmo comando retorna a mesma resposta; outra aba com run antiga recebe 409.
Criação, snapshot, partidas, evento e outbox são atômicos.

Participantes, mascotes, nomes e configurações são preservados. Estratégias vêm
de official_player_snapshots com digest conferido, não de input do cliente.
SystemRandom sorteia a nova ordem, e o Engine sorteia espera/Zumbi/jogadas.
Repetição não exige nova inscrição nem READY. O participante não recebe botão
administrativo. O backend PostgreSQL é obrigatório para repetir; adapter
in-memory de testes retorna 503 nesse endpoint.

## Realtime e apresentação

Cada payload identifica runId. HTTP fornece run_id e run_start_sequence em uma
leitura consistente. Replay público filtra o intervalo da run atual; um cursor
anterior recebe replay-reset com afterSequence imediatamente anterior ao início.
O ledger antigo continua consultável no banco, não é apagado pelo filtro.

Frontend troca a execução, limpa fila/animação/celebração anterior, preserva
cursor global e rejeita payload antigo por versão/run. Snapshot não recalcula
resultados. Outbox continua at-least-once com deduplicação, não promete entrega
exatamente uma vez pela rede. Bronze/final/pódio não adicionam efeitos sonoros.
Os efeitos existentes de partida/coração/eliminação/campeão são reutilizados.

PT-BR, EN, 中文 e العربية recebem os mesmos controles e textos; RTL permanece.
Pódio funcional é deliberadamente simples. Polimento premium da Rodada 7.1
permanece fora do escopo.
