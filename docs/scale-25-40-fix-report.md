# Estabilidade para grupos de 25–40 jogadores — 2026-10-07

## Correções

- O handshake WebSocket consultava o limitador PostgreSQL de forma síncrona dentro do event loop ASGI. Conectar/reconectar espectadores podia interromper temporariamente a entrega aos demais. Essa consulta agora roda em thread, preservando a falha fechada quando o limitador está indisponível.
- Tickets continuam válidos por cinco minutos, mas são renovados na mesma conexão. O navegador solicita outro ticket 60–75 s antes da expiração e espera confirmação do servidor. A renovação não altera identidade, sala, papel, cursor ou orçamento de replay; exige expiração posterior e respeita intervalo mínimo de 30 s antes de consultar o banco. Revogação permanece verificada a cada cinco segundos.
- Limites por IP foram dimensionados para todos os 40 jogadores no mesmo Wi-Fi. Inscrições: 120/10 min. Estratégia/READY: 240/min. Autenticação de participantes: 1.200/min. Emissão de tickets: 240/min. Handshakes: 160/min. Limites por capability continuam 20/min para ações/consultas e 30/min para tickets. Emissão e handshake não compartilham mais o mesmo contador.
- A resposta administrativa de participantes inclui `capacity`; recarregar o painel preserva o denominador correto.
- O protocolo rejeita mensagens de controle anteriores à autenticação com fechamento 1008, sem erro de chave inexistente.
- A margem de entrega anterior à apresentação passou de 1,2 s para 2,5 s, independente da velocidade. O relógio continua compartilhado; a mudança acrescenta tempo de preparação entre transições, não altera regras ou duração das animações. O ensaio de 40 com margem antiga ainda apresentou até 644 ms de atraso e motivou esta correção adicional.
- O orçamento incremental para cada evento posterior no lote passou de 300 para 750 ms. A margem base sozinha não cobria publicação sequencial durante renovação simultânea; essa segunda alteração protege especialmente 8×, cujas fases visuais são mais curtas que uma consulta ao banco sob carga.

Os BYEs registrados no teste anterior obedecem ao PROJECT_CORE: segunda chance somente na primeira fase de torneios inicialmente ímpares; fases posteriores ímpares usam BYE. Nenhuma regra competitiva foi modificada.

## Verificações automatizadas

- 231 testes passaram em backend, Game Engine e realtime, incluindo chaves de 25/32/40 jogadores com 1–4 vidas e margem de entrega. Após o ajuste incremental, os cinco testes de timing passaram novamente, incluindo um novo caso (232 casos no conjunto). Permanecem quatro avisos de depreciação de `on_event` do FastAPI, sem falha de execução.
- Ao expandir os testes, a expectativa de total de partidas listava apenas tamanhos pequenos com disputa de bronze. Foi generalizada pela redução do número de classificados até as semifinais; nenhuma regra do motor foi alterada.
- 20 testes de integração PostgreSQL passaram em banco isolado.
- 76 testes de frontend passaram. Build de produção, TypeScript e lint passaram.
- Revisão por agente de Segurança: sem bloqueadores; a recomendação de validar o tipo da primeira mensagem foi incorporada e testada.

## Ensaio local com conexões reais

PostgreSQL 16 em container exclusivo `rps-scale-test-pg`, porta 55434. Banco do ensaio: `rps_scale_live`; banco separado para testes automatizados: `rps_scale_test`. Backend na porta 8200, sem alteração de dados públicos. Uma conexão por jogador mais uma do organizador. Todos usam a mesma origem/IP, estratégia uniforme, uma vida e velocidade 8×/8×. O coletor renova cada ticket durante o combate para exercitar o novo protocolo.

| Participantes | Conexões | Eventos por conexão | Resultado | Reconexões | Renovação confirmada |
| --- | --- | --- | --- | --- | --- |
| 25 | 26 | 177 | Concluído | 0 | 26/26 |
| 40 | 41 | 251 | Concluído | 0 | 82/82 (duas por conexão) |

No ensaio de 25: inscrição e READY de todos aceitos sem 429, capacidade 25 retornada, nenhuma lacuna; diferença de chegada mediana 11 ms, máxima 200 ms.

### Resultado final com 40 jogadores

Torneio `RPS-64TYKZ2C8BMBVATL`, iniciado às 15:47:53 UTC e observado até 15:53:30 UTC. Configuração final: 2,5 s de margem base e 750 ms incrementais por evento. Todos os 40 chegaram a READY; a API retornou capacidade 40. As 41 conexões receberam exatamente as sequências 1–251, sem lacunas, exceções, reconexões, HTTP de erro ou 429. Houve duas renovações por conexão, atravessando a expiração dos tickets originais.

- Diferença de chegada entre observadores: mediana 18 ms; máxima 364 ms.
- **Nenhum evento chegou depois do horário de apresentação.** A menor antecedência observada foi 990 ms. Logo, a diferença de chegada ficou dentro da janela de agendamento, sem exigir recuperação de uma fase já iniciada neste ensaio.
- Medianas HTTP: inscrição 456 ms, estratégia 787 ms, READY 689 ms, ticket 532 ms, snapshot 352 ms. Maior emissão de ticket: 2.185 ms; maior READY: 1.053 ms. Renovação assíncrona não interrompeu a recepção.
- [Métricas sanitizadas](evidence/scale-40-2026-10-07.json), sem tokens.

O ensaio de 25 precedeu os ajustes adicionais de margem. O de 40 acima é o ensaio completo da configuração final; os testes determinísticos cobrem também 25 e 32 jogadores.

### Ensaios intermediários e diagnóstico

O primeiro ensaio de 40 terminou com 251 eventos em todas as 41 conexões, sem perdas, erros HTTP, 429 ou reconexões. O pico de 2.668 ms foi invalidado como medida de transmissão: o coletor fazia a solicitação HTTP de renovação dentro da thread receptora, bloqueando sua própria leitura. O navegador já realiza essa solicitação de forma assíncrona. O coletor foi corrigido para manter a recepção ativa durante a renovação e o ensaio de 40 foi repetido.

Com o coletor corrigido e ainda com a margem anterior de 1,2 s, o torneio `RPS-794TQNZ5V79B66RC` terminou com 258 eventos por conexão, sem perda, reconexão, erro HTTP ou 429. Todas as 41 conexões renovaram. Diferença de chegada mediana: 16 ms; máxima: 575 ms. Maior atraso em relação ao horário programado: 644 ms. Esta execução identificou a necessidade de aumentar a antecedência, além das correções de transporte.

Com 2,5 s base e ainda 300 ms incrementais, `RPS-Q4HMUYTBWSHQ8AKE` terminou com 271 eventos em todas as conexões, 82 renovações e nenhuma queda, perda ou falha HTTP. A diferença máxima de chegada foi 344 ms, porém houve atraso máximo de 516 ms em relação ao horário visual. Consulta somente-leitura ao banco confirmou o evento 41 (`player_eliminated`) com marcação de publicação 154 ms após seu horário visual, no lote 39–44 durante a renovação de tickets. A marcação de publicação ocorre após o fanout; não é medição do horário exato de envio, mas evidencia demora de processamento do lote. A suíte de testes também executou no mesmo computador nos primeiros 76 s desse ensaio. O orçamento incremental foi ampliado para 750 ms e o teste repetido sem essa carga concorrente adicional.

## Limites da evidência

As conexões do ensaio são clientes de protocolo no mesmo computador, não 40 navegadores ou celulares. Tempos locais não são garantia dos mesmos tempos no Render/Supabase e não devem ser comparados diretamente com o pico público anterior. As 25 combinações de velocidades da apresentação continuam cobertas por testes determinísticos. A travessia da expiração original e a rejeição de revogação/troca de identidade são cobertas por testes do protocolo.

A publicação e uma verificação pública posterior com múltiplos dispositivos permanecem necessárias para validar a infraestrutura de produção. O fanout atual requer um único worker do backend.
