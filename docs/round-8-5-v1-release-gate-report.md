# Rodada 8.5 — Fechamento da Etapa 8 e gate da V1

Data: 2026-10-06  
Ambientes: `https://rps-animal-showdown.vercel.app` e `https://rps-animal-showdown-api.onrender.com`

## A. Resumo executivo

Foi corrigida a única falha de UX identificada na Rodada 8.4: uma resposta HTTP 429 agora é apresentada como orientação amigável e localizada, sem alterar qualquer limite de segurança. Foram produzidas evidências novas de responsividade em viewport móvel emulado, reprodução solicitada de áudio pelo navegador e smoke público mínimo. O gate permanece **VERSÃO PÚBLICA V1 COM AJUSTES**, pois não há dispositivo com saída de áudio/touch real disponível, o PostgreSQL isolado não está configurado e uma sessão de organizador deste smoke ficou em reconexão enquanto um participante estava ao vivo.

## B. Estado inicial

- Branch inicial: `main`, limpa, no commit `3f18366`.
- Referências revisadas: relatórios das Rodadas 8.3 e 8.4.
- Frontend e `/health` público responderam HTTP 200.

## C. Pendências recebidas da 8.4

1. UX de rate limit genérica.
2. Evidência mobile insuficiente.
3. Evidência perceptiva de áudio/TTS insuficiente.
4. 25 testes PostgreSQL ignorados por falta de banco isolado.

## D. Rate limit UX

**PASS.** A página classifica `429` separadamente em todas as ações que recebem resposta HTTP e exibe mensagem amigável. Erros não-429 continuam usando a mensagem de conexão genérica. Nenhum limite, cabeçalho, algoritmo ou regra do backend foi alterado.

## E. Traduções do rate limit

**PASS.** A mensagem está centralizada em i18n para PT-BR, EN, 中文 e العربية. O teste de frontend confirma as quatro cópias; a interface árabe mantém `dir="rtl"`.

## F. Mobile

**PASS — EMULATED DEVICE.** Com override de viewport 390×844 (layout observado em 390 px e, em telas com barra disponível, 375 px), Home, criação, entrada, seleção de animal e estratégia não tiveram overflow horizontal. Inputs, selects e CTAs permaneceram visíveis e utilizáveis. A transição 844×390 → 390×844 preservou a página sem overflow.

## G. Touch

**PARTIAL — EMULATED POINTER.** Cliques automatizados confirmaram navegação, seleção de animal, controles de idioma e estratégia sem depender de hover. Não havia dispositivo touch real disponível; não é declarado teste físico de toque.

## H. Áudio background

**PARTIAL.** O arquivo local `background.mp3` existe, é servido publicamente e o `AudioManager` o cria em canal único, com loop e volume limitado. Os controles independentes de música foram exercitados na UI. A audição humana não pode ser capturada pela automação.

## I. Áudio animais

**PARTIAL.** Em produção, clicar em Tigre selecionou o animal e iniciou `A_tiger.mp3` (`paused: false`, sem mute). A suíte valida todos os 26 IDs, troca do som anterior e uso exclusivo de assets locais. A confirmação auditiva humana permanece pendente.

## J. Áudio Zumbi

**PARTIAL.** A suíte confirma que vencedor zumbi usa `A_zumbie.mp3` e não volta ao som normal até reset da execução. O fluxo visual Zumbi já foi aprovado na 8.4; não houve captura de saída sonora audível.

## K. Countdown

**PARTIAL.** Testes cobrem a ordem 3→2→1, o asset `countdown_beep.mp3` e todas as velocidades 0,5x/1x/2x/4x/8x. A sincronização perceptiva não é observável no controlador.

## L. Heart break

**PARTIAL.** O teste assegura que `heart_lost` usa somente `heart_break.mp3`, uma eliminação não recebe efeito próprio e o treinamento aciona a perda de coração pelo estado oficial. Sem captura auditiva.

## M. Champion

**PARTIAL.** Os testes asseguram `champion.mp3` como primeira pista de campeão, sem efeito de vitória genérico. Sem captura auditiva.

## N. Podium

**PARTIAL.** A fila automatizada assegura que `champion.mp3` precede e interrompe antes de `podium.mp3`, evitando sobreposição caótica. Sem captura auditiva.

## O. Audio ON/OFF

**PASS.** A suíte validou as quatro combinações independentes: efeitos/música desligados, somente música, somente efeitos e ambos ligados. Os controles públicos refletem os estados locais do jogador.

## P. TTS PT-BR

**PARTIAL.** O botão não altera a seleção; o teste valida a frase com nome comum e nome científico. A voz depende da voz instalada no navegador/SO.

## Q. TTS EN

**PARTIAL.** Cobertura automatizada de en-US e nome científico; sem voz audível capturável.

## R. TTS 中文

**PARTIAL.** Cobertura automatizada de zh-CN e nome científico; a disponibilidade de voz depende do navegador/SO.

## S. TTS العربية

**PARTIAL.** Cobertura automatizada de ar-SA e nome científico; a disponibilidade de voz depende do navegador/SO.

## T. PostgreSQL isolated test setup

**NOT CONFIGURED.** `RPS_TEST_DATABASE_URL` não foi fornecida. A tentativa de usar Docker local falhou por acesso negado ao daemon. Nenhuma alternativa paga foi criada e o banco de produção não foi usado.

## U. PostgreSQL test results

**NOT EXECUTED.** `0 passed`, `0 failed`, `25 skipped` por ausência do banco isolado, não por falha da aplicação.

## V. Migrations

**PARTIAL.** A cobertura de migrações sem PostgreSQL passou na suíte geral. A execução fresh database até a migration head continua pendente do banco isolado.

## W. Frontend tests

**PASS.** `28 passed`, `0 failed`, `0 skipped`; inclui classificação de 429 e presença das quatro traduções. Lint passou. Build de produção passou com URLs seguras de exemplo.

## X. Backend tests

**PASS.** `197 passed`, `0 failed`, `25 skipped`, com quatro avisos conhecidos de depreciação `FastAPI on_event`. A resposta 429 e `Retry-After` receberam asserções adicionais; o teste existente cobre recuperação posterior da janela.

## Y. Security regression

**PASS.** A mudança é somente de apresentação. Rate limiter, headers, CORS, WSS, CSP, organizer capability, regras e autoridade do servidor não foram alterados. `npm audit --omit=dev --audit-level=high` retornou 0 vulnerabilidades e `pip check` não encontrou requisitos quebrados.

## Z. Public smoke test

**PARTIAL.** A criação pública sem login concluiu após cold start do backend e gerou o código `RPS-ZMDJQEPBUG9XFUCS`. Dois participantes distintos entraram, escolheram Tigre/Panda, salvaram estratégia e chegaram a READY; o participante recebeu a Arena e o evento `Torneio iniciado`. No mesmo smoke, o painel do organizador ficou em `Tempo real: Conectando` após iniciar, embora o participante estivesse `Ao vivo` e sem erros de console. A reconexão do organizador havia passado na Rodada 8.4 e este código não toca realtime, mas a observação deve ser acompanhada.

## AA. Console/network

**PARTIAL.** Os tabs amostrados não tiveram erros ou warnings no console. Frontend e health da API responderam 200. Não houve 5xx, CORS, mixed content ou 404 de asset observados no fluxo. A conexão do organizador no smoke é a ressalva desta seção.

## AB. Bugs encontrados

- **MEDIUM (a investigar):** uma sessão de organizador do smoke público permaneceu em reconexão após Start, enquanto o participante recebeu a Arena via realtime. Não foi reproduzido na validação ampla da 8.4 e não há alteração de realtime nesta rodada.
- **LOW:** a validação auditiva humana e touch físico não é possível pelo controlador atual.

## AC. Bugs corrigidos

- **LOW:** respostas HTTP 429 deixaram de aparecer como erro genérico de conexão.
- A solução preserva a proteção do backend e apresenta cópia localizada em quatro idiomas.

## AD. Bugs restantes

- Investigar a sessão de organizador em `Conectando` observada no smoke antes do gate máximo.
- Executar os 25 testes PostgreSQL com `RPS_TEST_DATABASE_URL` realmente isolada.
- Realizar checklist humano de áudio/TTS e touch em dispositivo físico.

## AE. Commits

- `95696f6 fix: localize rate limit feedback`
- Este relatório será registrado no commit de fechamento da Rodada 8.5.

## AF. Deploy

**PASS.** O push para `main` foi realizado e a aplicação pública serviu o smoke após o push. Não houve deploy manual de backend, pois não houve mudança de backend de runtime.

## AG. Gate final da V1

**VERSÃO PÚBLICA V1 COM AJUSTES**.

Não há BLOCKER ou HIGH identificado. O gate máximo não é emitido porque a investigação de realtime do organizador e as evidências de ambiente (áudio/touch e PostgreSQL isolado) ainda precisam ser concluídas. A Etapa 8 não inicia uma etapa nova automaticamente.
