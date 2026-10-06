# Rodada 8.5.1 — Estabilização final da V1

Data: 2026-10-06  
Ambiente público: `https://rps-animal-showdown.vercel.app` + API Render

## Escopo

Esta rodada foi limitada à recuperação realtime do painel do organizador e ao
CTA da Home. Nenhuma regra de torneio, formato melhor-de-1/3/5/7, autoridade do
servidor, Game Engine, áudio ou catálogo de animais foi alterado.

## Correção aplicada

- Após um `Start` aceito pelo backend, o painel organizador busca e aplica
  imediatamente o snapshot oficial autenticado antes de depender do próximo
  handshake WebSocket.
- O cliente diferencia três estados reais: `Conectando`, `Sincronizado`
  (snapshot oficial disponível enquanto a reconexão ocorre) e `Ao vivo`
  (assinatura WebSocket confirmada). Um snapshot posterior não substitui mais
  o estado `Ao vivo` de um socket já inscrito.
- Enquanto estiver sincronizado por snapshot ou em fallback, a tela continua
  atualizando o snapshot oficial. O browser nunca calcula resultados,
  estratégias, vidas ou chaveamento.
- O CTA da Home aceita quebra de linha controlada em viewport estreito,
  preservando os três botões com o mesmo tamanho visual e sem cortar o texto.

## Validação pública

Torneio de validação: `RPS-LYETDHZ6HCBWACEE`.

- Participantes: `Estabilidade Águia` (🦅) e `Estabilidade Tigre` (🐯).
- Ambos completaram escolha de animal, estratégia e `READY`.
- O organizador iniciou o torneio. A Arena, o chaveamento, os 14 eventos
  oficiais e o pódio foram renderizados a partir do estado oficial.
- Na primeira sincronização a tela mostrou `Sincronizado`; após a assinatura
  WebSocket confirmou `Tempo real: Ao vivo`.
- Recarregamentos/reconexões do organizador: **5/5 PASS**. Em cada ciclo o
  painel recuperou o pódio e exibiu `Tempo real: Ao vivo` sem ação duplicada.
- Participante 1: **PASS**, `Tempo real: Ao vivo` após recarga.
- Participante 2: **PASS**, `Tempo real: Ao vivo` após recarga.
- Console: **PASS** — sem erros ou avisos nas três sessões verificadas.
- Health público: **PASS** — frontend e `/health` responderam HTTP 200.

## CTA e responsividade

Em 360 px, 390 px e desktop, os três CTAs foram medidos sem overflow interno.
O botão principal ficou integralmente legível em PT-BR, English, 简体中文 e
العربية الفصحى; em telas estreitas, o texto pode ocupar duas linhas sem ser
cortado.

## Testes automatizados

- Frontend: **31 passed, 0 failed**.
- Lint frontend: **PASS**.
- Build de produção Next.js com URLs seguras simuladas: **PASS**.
- Backend + realtime + Game Engine + migrations: **197 passed, 25 skipped,
  4 avisos conhecidos de depreciação FastAPI**.
- Os 25 skips continuam dependentes exclusivamente de um PostgreSQL isolado
  não configurado; nenhum banco público foi usado como substituto.

## Commits e deploy

- `b04cfcf fix: stabilize organizer realtime sync`
- `185c249 fix: preserve live realtime state after snapshot`

Os dois commits foram enviados para `main` e a versão pública foi validada
após o deploy automático.

## Gate final

- Organizer realtime: **PASS**
- Organizer `Conectando`: **RESOLVIDO**
- Reproduções após correção: **5/5 PASS**
- Refresh/reconnect organizer: **PASS**
- Realtime participante: **PASS**
- Botão Home PT/EN/中文/العربية: **PASS**
- Mobile 360/390 e desktop: **PASS**
- Regressões críticas, altas ou de regras: **0 abertas**
- Deploy público: **PASS**

**V1 APROVADA.** As limitações de evidência física já registradas na Rodada
8.5 (áudio/touch em dispositivo real e banco PostgreSQL isolado local) seguem
como itens não bloqueadores e não foram mascaradas por esta rodada.

**Etapa 8: CONCLUÍDA.**
