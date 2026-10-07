# Sincronização da apresentação oficial

O backend continua sendo a autoridade para resultados, vidas e chaveamento. Cada
evento oficial recebe `presentationAtMs`, um horário absoluto do servidor. O
frontend usa esse horário para apresentar as fases; a chegada do WebSocket não
é o início da animação.

As velocidades de movimento e contagem são independentes. O backend reserva
antecedência para a publicação sequencial do outbox, inclusive em 8×, e só
resolve a próxima jogada depois do fim da apresentação anterior. O frontend
calibra o relógio antes da primeira jogada com `server_received_at_ms` e
`server_time_ms` no snapshot. Os quatro horários (envio/recebimento no cliente
e recebimento/envio no servidor) descontam o processamento do backend da
estimativa, mantendo uma referência estável para a execução. O painel do
organizador também recupera o estado oficial após recarregar. Snapshots
repetidos não reiniciam a
animação; uma desconexão curta não descarta eventos já agendados. Uma nova
versão oficial ou uma nova execução recompõe a apresentação a partir do
snapshot autorizado.

Se um evento do WebSocket chegar antes do primeiro snapshot, o horário de
chegada serve apenas como referência provisória. O primeiro snapshot válido
substitui essa estimativa pela calibração de quatro horários; iniciar o
torneio no painel também faz essa calibração imediatamente.

Animações de contagem, corações e movimento usam a duração da fase agendada,
não tempos CSS fixos. Se uma fase começar alguns quadros atrasada, o movimento
é posicionado no progresso correspondente ao relógio oficial.

Essa antecedência é uma margem, não garantia contra perda prolongada de rede.
Se o navegador receber eventos depois do horário programado, ele avança para
o estado oficial atual em vez de reproduzir jogadas antigas fora de tempo.

Os testes de timing cobrem todas as 25 combinações de 0,5×, 1×, 2×, 4× e 8×.

## Grupos de 25–40 participantes

A margem base de entrega é 2,5 s e não é dividida pela velocidade escolhida.
Ela absorve publicação persistente e verificações simultâneas de autorização:
no ensaio de 41 conexões, a margem anterior de 1,2 s foi excedida em até 644 ms.
Além disso, cada evento posterior do lote recebe pelo menos 750 ms de margem
incremental para publicação sequencial; 300 ms não cobriam o pico observado
durante a renovação simultânea de 41 conexões. As durações visuais continuam
respeitando as velocidades; existe uma pausa
de preparação maior entre transições para todos receberem o mesmo horário.

Os tickets de cinco minutos são renovados no mesmo WebSocket, antes de vencer,
sem parar o fluxo ou reiniciar a apresentação. A renovação mantém a identidade
e a sala e exige nova autorização persistida. Se falhar, a recuperação por
snapshot/replay continua disponível. O limitador do handshake roda fora do
event loop para que a entrada ou reconexão de outros espectadores não pause a
transmissão.

Os limites agregados por IP consideram todos os participantes no mesmo Wi-Fi:
120 inscrições/10 min, 240 ações de estratégia/prontidão/min, 1.200 consultas
autenticadas de participante/min, 240 emissões de ticket/min e 160 handshakes/min.
Os limites individuais continuam 20 ações/consultas por capability/min e 30
emissões de ticket por capability/min. Emissão e handshake usam buckets
independentes. Não se deve desativar o limitador para comportar o grupo.

O painel recupera `capacity` junto da lista autenticada de participantes, para
preservar o total correto após recarregar. BYEs posteriores à primeira fase
continuam conforme `PROJECT_CORE.md`; não são uma falha de transporte.

O coletor `scripts/public_scale_probe.py` usa por padrão backend local isolado,
abre uma conexão por participante mais o organizador, exercita renovação e
registra sequência, diferença de chegada e atraso com calibração de relógio.
Ele exige `--allow-public` para qualquer destino não local. Testa término pelo
estado oficial depois de encerrar o contexto transitório de apresentação.
