# Rodada 8.4 — Teste público ponta a ponta

Data da validação: 2026-10-06  
Ambiente público: `https://rps-animal-showdown.vercel.app` + API Render

## A. Resumo executivo

Os fluxos públicos essenciais foram exercitados com sessões independentes de organizador e participantes. Os torneios com 2, 3, 4 e 5 participantes concluíram corretamente, incluindo tempo real, chaveamento ímpar, Segunda Chance Zumbi, disputa de terceiro lugar, final, pódio, reconexão e repetição. Não foi encontrado bloqueador de produção. O gate final é **TESTE PÚBLICO PONTA A PONTA COM AJUSTES**, pois há lacunas de evidência de mobile, áudio perceptível, todos os formatos em E2E público e PostgreSQL isolado.

## B. Estado inicial

- Branch: `main`.
- Frontend e backend públicos disponíveis antes do teste.
- Não foram realizadas mudanças de regra, redesign, deploy manual ou uso de banco de produção para testes automatizados.

## C. URLs testadas

- Frontend: `https://rps-animal-showdown.vercel.app`.
- Saúde da API: `https://rps-animal-showdown-api.onrender.com/health`.
- Realtime: WebSocket público da API, exercitado pelos painéis de organizador e participantes.

## D. Cold start

**Não testado.** Não foi forçada inatividade do Render apenas para provocar cold start.

## E. Torneio 2 participantes

**PASSOU.** Código `RPS-XYPPPBCELSBE4HMP`; participantes `E2E Águia` (🦅) e `E2E Tigre` (🐯). Ambos entraram pelo código público, escolheram animal, configuraram estratégia e chegaram a READY. O organizador recebeu o estado 2/2 em tempo real e o torneio terminou com pódio.

## F. Torneio 3 participantes

**PASSOU.** Código `RPS-4TV7KSJ7UM99Q6D7`; participantes `Ímpar Panda` (🐼), `Ímpar Leão` (🦁) e `Ímpar Polvo` (🐙). O torneio ímpar concluiu com pódio correto.

## G. Torneio 4 participantes

**PASSOU.** Código `RPS-FRAEJTEBBJF2EUSE`; participantes `Quatro Canguru`, `Quatro Elefante`, `Quatro Urso` e `Quatro Arara`. As duas semifinais, a disputa de terceiro lugar e a Grande Final ocorreram na ordem esperada.

## H. Torneio ímpar maior

**PASSOU.** Código `RPS-NPYNLTQMUYF8K746`; participantes `Cinco Galo`, `Cinco Touro`, `Cinco Cabra`, `Cinco Zebra` e `Cinco Tubarão`. O fluxo ímpar concluiu sem corromper chave, pódio ou eventos.

## I. Segunda Chance

**PASSOU.** Nos torneios ímpares de 3 e 5 participantes, houve uma única etapa de Segunda Chance, visível nos eventos e no chaveamento.

## J. Zumbi

**PASSOU.** O participante selecionado foi exibido com indicador zumbi e continuou no fluxo permitido. No torneio de 5 jogadores, `Touro🧟` avançou normalmente e recebeu BYE posterior válido.

## K. Áudio Zumbi

**PARCIAL.** O asset local público de zumbi respondeu 200 e a suíte automatizada cobre seu mapeamento e reinicialização por execução. A reprodução audível não pode ser capturada pelo controlador de navegador usado neste teste.

## L. Terceiro lugar

**PASSOU.** No torneio de 4 jogadores, a disputa `Elefante` versus `Urso` ocorreu antes da Grande Final e definiu corretamente o terceiro colocado.

## M. Grande Final

**PASSOU.** As finais foram emitidas depois das etapas necessárias e terminaram com os eventos de conclusão esperados.

## N. Pódio

**PASSOU.** Os pódios de 2, 3, 4 e 5 participantes foram renderizados com primeiro, segundo e terceiro lugares corretos.

## O. Repeat Tournament

**PASSOU.** O organizador acionou `Repetir Torneio`; os participantes foram preservados e uma nova sequência de eventos foi executada.

## P. Run history

**PARCIAL.** A nova execução substituiu a visualização corrente sem contaminação de eventos antigos. Não foi encontrada uma interface visual dedicada para navegar entre execuções históricas.

## Q. Reconnect organizer

**PASSOU.** Após recarregar o painel do organizador, um estado transitório de conexão foi seguido por snapshot completo e pódio correto, sem ação duplicada.

## R. Reconnect participant

**PASSOU.** Após recarregar um participante, sua identidade e estado de arena/pódio foram restaurados sem novo registro.

## S. Replay

**PARCIAL.** A reconexão e o snapshot foram validados em produção; a recuperação sob perda deliberada de cursor não foi controlável pela interface pública.

## T. Snapshot

**PASSOU.** Snapshots reconciliaram a tela do organizador e do participante após recarga.

## U. Áudio

**PARCIAL.** Os controles independentes de música e efeitos, os assets e testes automatizados foram validados. A percepção sonora pelo sistema de saída do navegador não é observável por esta automação.

## V. Background

**PARCIAL.** `/audio/background/background.mp3` respondeu 200 e os quatro estados de configuração (música/efeitos ligados ou desligados) foram exercitados na interface. A audição efetiva permanece dependente de teste humano.

## W. TTS

**PARCIAL.** O botão de narração aparece e a suíte cobre a descrição científica canônica. Não houve captura de áudio perceptível nesta execução.

## X. PT-BR

**PASSOU.** Todos os fluxos principais foram executados em português, sem chaves de tradução expostas.

## Y. EN

**PASSOU.** Arena, pódio, chaveamento e eventos foram exibidos em inglês; nomes fornecidos por participantes permaneceram intactos.

## Z. 中文

**PASSOU.** A interface e os eventos apareceram em chinês simplificado, sem vazamento de chave de tradução.

## AA. العربية / RTL

**PASSOU.** A interface principal foi renderizada em árabe com direção RTL, mantendo chave e eventos legíveis e sem overflow horizontal no desktop testado.

## AB. Mobile

**Não testado.** A tentativa de emular 390×844 não alterou o viewport DOM do controlador (permaneceu com 1265 px); não há evidência suficiente para aprovar responsividade mobile.

## AC. Desktop

**PASSOU.** A interface foi validada no viewport desktop disponível, incluindo lobby, arena, chaveamento, pódio, treino e Animal Rush.

## AD. Wide screen

**PARCIAL.** O desktop de 1265 px não apresentou overflow. Um viewport widescreen dedicado não foi disponibilizado pela automação.

## AE. Velocidades

**PARCIAL.** A velocidade 8x foi executada em produção nos torneios. A suíte automatizada cobre 0,5x, 1x, 2x, 4x e 8x; as demais não receberam execução E2E pública manual nesta rodada.

## AF. Bo1/3/5/7

**PARCIAL.** Bo1 foi exercitado em produção. As regras Bo3, Bo5 e Bo7 estão cobertas pelos testes automatizados, mas não foram todas percorridas em E2E público manual nesta rodada.

## AG. Animal Rush

**PASSOU.** Antes do início oficial, um participante abriu o minigame, acertou um desafio (pontuação e sequência aumentaram) e recebeu novo desafio. Ao iniciar o torneio oficial, a tela foi interrompida corretamente para a arena.

## AH. Treinar

**PASSOU.** Sem criar torneio, foi possível escolher Tigre, treinador Alien, três corações, estratégia e iniciar treino. Uma rodada Pedra versus Pedra foi registrada.

## AI. Authorization

**PASSOU.** As ações oficiais foram realizadas somente pelo painel organizador. A cobertura de autorização pública e de token de organizador da Rodada 8.3 continua válida.

## AJ. Cross-tournament isolation

**PARCIAL.** A separação é coberta pelos testes existentes e não houve mistura de eventos nos múltiplos torneios criados. Não foi executada uma tentativa agressiva adicional de token de um torneio em outro contra a produção.

## AK. Console

**PASSOU.** Não foram encontrados erros ou avisos de console nos painéis do organizador, participantes e treino amostrados.

## AL. Network

**PASSOU (fluxos cobertos).** As chamadas de API, assets essenciais e conexões realtime necessárias aos cenários concluíram sem 404 inesperado ou falha de rede observada.

## AM. Render logs

**PASSOU.** Os logs mostraram requisições esperadas, WebSockets aceitos/abertos e respostas usuais. Não foram observadas exceções de aplicação, falhas de banco, transações ou worker.

## AN. PostgreSQL test DB

**Não configurado.** `RPS_TEST_DATABASE_URL` não foi fornecida e o Docker local não estava acessível. O banco público não foi usado como substituto, preservando a segurança dos dados de produção.

## AO. Automated tests

- Backend, realtime, game engine e migrações: `197 passed, 25 skipped, 4 warnings`.
- Frontend: `25 passed`.
- Lint frontend: passou.
- Build frontend com URLs públicas simuladas: passou.
- `npm audit --omit=dev --audit-level=high`: 0 vulnerabilidades.
- `python -m pip check`: sem dependências quebradas.
- Os 25 skips dependem exclusivamente do banco PostgreSQL isolado não configurado.

## AP. Bugs encontrados

- **Baixo impacto:** durante cadastro em rajada no torneio de 5 jogadores, o limitador público foi acionado e o frontend exibiu mensagem genérica de falha em vez de informar que era necessário aguardar e tentar novamente.

## AQ. Bugs corrigidos

Nenhuma correção foi necessária: não foi encontrado defeito bloqueador ou crítico que impedisse a validação dos fluxos previstos.

## AR. Bugs restantes

- Melhorar a mensagem de rate limit para uma orientação explícita de nova tentativa.
- Completar evidência em dispositivo/viewport mobile real.
- Configurar `RPS_TEST_DATABASE_URL` isolada para executar os 25 testes de PostgreSQL atualmente ignorados.
- Complementar esta rodada com verificação humana de áudio e TTS audíveis.

## AS. Commits/deploys

- Base validada: `b27da34` (hardening público) e `3caac9d` (registro de validação do hardening).
- Esta rodada adiciona exclusivamente este relatório; não houve alteração de runtime nem deploy manual necessário.

## AT. Gate final

**TESTE PÚBLICO PONTA A PONTA COM AJUSTES**.

Os cenários críticos de jogo público, realtime, recuperação, chaveamento ímpar, Segunda Chance, zumbi, terceiro lugar, pódio, idiomas e treino passaram. As pendências são de evidência e experiência de baixo impacto, não falhas bloqueadoras encontradas no produto.
