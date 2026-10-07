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
