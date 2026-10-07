# Teste público de escala — 9 e 20 participantes (2026-10-07)

Teste manual instrumentado da versão pública, sem alteração das regras ou do código do jogo. Foram usados o frontend da Vercel como entrada HTTP e o WebSocket de produção do Render. Três observadores autenticados (organizador e dois participantes) acompanharam cada torneio. Os tokens foram mantidos apenas em memória e não constam deste documento.

## Metodologia e limites

- Estratégia igual para todos: Pedra 33%, Papel 33%, Tesoura 34% nas dez condições.
- Uma vida por confronto; áudio habilitado; 9 participantes a 1×/1× e 20 participantes a 2×/2× (movimento/contagem).
- Inscrição, estratégia e READY foram submetidos por API, não por 9 ou 20 navegadores distintos. Assim, as medidas de sincronização aqui são de transporte/realtime, não uma medição visual quadro a quadro de todos os clientes.
- O coletor respeitou as respostas `429` e o cabeçalho `Retry-After`, sem contornar os limites do ambiente público.
- Latência HTTP mede tempo observado pelo cliente, incluindo rede e proxy da Vercel. Diferença entre observadores mede o horário de chegada da mesma sequência WebSocket em três conexões no mesmo computador; não mede diferenças de relógio entre dispositivos reais.

## Torneio com 9 participantes

- Código: `RPS-DP5FUWWD55VJ3MH3`.
- 9/9 inscritos e 9/9 em READY; nenhum erro HTTP nem limitação de taxa durante essa etapa.
- Resultado oficial: `completed`, com campeão definido.
- 76 eventos oficiais, sequências 1–76, recebidos pelos três observadores sem lacunas.
- Diferença de chegada do mesmo evento entre observadores: mediana 23 ms; máximo 120 ms.
- 6 eventos chegaram depois de `presentationAtMs` em cada observador; maior atraso 352–403 ms, conforme a conexão.
- Cada WebSocket sofreu uma desconexão abrupta (`ConnectionClosedError: no close frame received or sent`), reconectou e recuperou a sequência completa.
- O torneio gerou 2 eventos de BYE. Registrar apenas como comportamento observado; não classificar como erro sem comparar com a regra atual de chaveamento.
- Máximos de latência HTTP: criação 494 ms, inscrição 863 ms, estratégia 1.084 ms, READY 579 ms, início 779 ms, leitura de estado 1.005 ms.
- A resposta `GET /admin/participants` trouxe os nove participantes e seus estados, mas **não trouxe `capacity`**. Isso pode fazer o painel do organizador mostrar um denominador incorreto após recarregar.
- Limitação do coletor: ele esperava `presentation_state.status == completed`; o backend só fornece `presentation_state` enquanto uma transição ainda está em exibição. Portanto, `completion_seen: false` no log do coletor não indica falha do torneio; `official_status: completed` e o evento `champion` confirmam a conclusão.

## Torneio com 20 participantes

Código: `RPS-KPEKNQESP7B23TNY`.

- A 13ª inscrição recebeu HTTP `429` com `Retry-After: 591`. O coletor respeitou esse prazo e depois completou 20/20 inscrições; trata-se de proteção esperada, mas cria uma espera de aproximadamente dez minutos para um teste sequencial a partir de uma única origem.
- 20/20 estratégias salvas e 20/20 participantes em READY, sem erro nessa fase.
- A listagem administrativa também omitiu `capacity` neste torneio. O problema do denominador afeta, portanto, tanto a sala de 9 quanto a de 20 após uma possível atualização do painel.
- Torneio iniciado às 14:44 UTC; resultado oficial `completed`, com campeão definido.
- 128 eventos oficiais, sequências 1–128, recebidos pelos três observadores sem lacunas. Foram 19 confrontos, 27 rodadas resolvidas e 2 eventos de BYE (comportamento observado, ainda não classificado como erro de regra).
- Diferença de chegada do mesmo evento entre observadores: mediana 16 ms; **máximo 6.275 ms**. Esse pico é uma dessincronização real de entrega, embora os eventos tenham sido recuperados.
- Ressalva posterior do coletor original: as diferenças **entre conexões** usam o mesmo relógio e permanecem válidas, mas os atrasos absolutos em relação a `presentationAtMs` foram medidos sem calibrar o relógio cliente/servidor. Esses valores absolutos são estimativas; o coletor atualizado calibra os quatro horários HTTP e identifica a sequência do pior pico.
- O organizador recebeu 18 eventos depois de `presentationAtMs`, com maior atraso de 358 ms. Cada um dos dois participantes recebeu 25 eventos depois do horário programado, com maior atraso de 6.248 ms e 6.230 ms, respectivamente. O coletor não registrou qual sequência foi responsável pelo pico.
- Cada uma das três conexões WebSocket sofreu duas desconexões abruptas (`ConnectionClosedError: no close frame received or sent`), reconectou e recuperou todos os eventos. Duas reconexões em quinze minutos são compatíveis com tickets de cinco minutos, mas a causa exata do fechamento sem quadro de encerramento precisa ser confirmada em logs do Render.
- Nenhum erro HTTP além do `429` esperado na 13ª inscrição. Na execução completa dos dois torneios, máximos HTTP observados: inscrição 863 ms, estratégia 1.084 ms, READY 691 ms, início 779 ms, leitura de estado 1.136 ms.
- A limitação do coletor sobre `presentation_state` também vale para esta etapa: `completion_seen: false` não significa torneio incompleto; o estado oficial final, o campeão e o evento `champion` confirmam a conclusão.

## Achados para investigação posterior

1. **Pico de dessincronização em 20 participantes:** até 6,275 s entre observadores, apesar de a mediana ser 16 ms e não haver perda permanente. Correlacionar sequência, horário de reconexão e logs de publicação/outbox para separar atraso de rede, replay e agendamento.
2. **Encerramentos WebSocket abruptos:** uma reconexão por observador no teste de 9 e duas no de 20. Verificar se a expiração do ticket fecha a conexão sem handshake e se a interface preserva a apresentação durante o replay.
3. **Capacidade ausente na API administrativa:** a resposta de participantes omite `capacity`, enquanto o frontend só atualiza o denominador se esse campo existir. Após recarregar o painel, o estado inicial `8` pode gerar `9/8` ou `20/8`.
4. **Limite de inscrição em testes concentrados:** 12 inscrições por 10 minutos por origem exigiram espera de 591 s para completar 20. Isso é proteção esperada, não motivo para removê-la; considerar origem/ambiente de teste separado para ensaios de carga futuros.
5. **BYEs observados:** dois eventos em cada torneio. Confirmar se correspondem à regra vigente de segunda chance/chaveamento antes de propor mudança.

## Pendências de validação

- Repetir observação visual simultânea em navegadores/dispositivos independentes para confirmar sincronização de animação e áudio. Este teste mede apenas o transporte de eventos e a resposta HTTP.
- Investigar se a desconexão WebSocket observada é encerramento esperado por validade do ticket, instabilidade do Render ou outra causa. A retomada não perdeu eventos.
