# Rodada 8.3 — Hardening de Produção

Data: 2026-10-06  
Escopo: aplicação pública RPS: Animal Showdown, sem alterar regras do jogo, chaveamento, áudio, i18n ou produto.

## A. Organizer token

- **PASS** — O organizador recebe uma capability aleatória somente na resposta de criação; ela não aparece em URL, logs da aplicação, estado público ou snapshots.
- **PASS** — O backend persiste somente o digest SHA-256 da capability, aplica expiração de 12 horas e revogação, e valida escopo, papel e torneio no servidor. A comparação em memória usa comparação de tempo constante; o armazenamento persistente faz busca pelo digest de uma capability de alta entropia.
- **PASS** — Todos os endpoints administrativos foram testados para rejeitar capability ausente (`401`) e capability de outro torneio (`403`): configuração, fechamento de inscrições, remoção, início e revogação.
- **PASS** — A sessão do navegador permanece em `sessionStorage`, não em query string, cookie ou `localStorage`; o risco de XSS é reduzido também pela CSP estrita descrita em G.

## B. CORS

- **PASS** — Produção exige `ALLOWED_ORIGINS`, normaliza uma lista explícita e rejeita curingas.
- **PASS** — O deploy usa a origem pública exata do frontend; `allow_credentials` permanece desligado e somente `Authorization` e `Content-Type` são aceitos.
- **PASS** — Preflight e origem negada já foram exercitados no smoke público da Rodada 8.2; os testes de fronteira confirmam que apenas a origem permitida recebe `Access-Control-Allow-Origin`.

## C. WebSocket seguro

- **PASS** — A URL pública é WSS e o build de produção falha sem `NEXT_PUBLIC_REALTIME_URL` com protocolo `wss:`.
- **PASS** — O handshake valida `Origin` antes de aceitar a conexão. O ticket é assinado por HMAC, de curta duração (cinco minutos), persistido, revogável e revalidado durante a sessão.
- **PASS** — Inscrições são delimitadas ao torneio e papel do ticket; replay possui orçamento e eventos oficiais usam projeção pública que exclui estratégia e condições privadas.
- **PASS** — A configuração da CSP libera conexão apenas para a própria origem e para o WSS configurado; em desenvolvimento preserva os sockets locais explícitos.

## D. Secrets e variáveis de ambiente

- **PASS** — A inspeção de arquivos rastreados encontrou somente `.env.example`; nenhum `.env` real está versionado.
- **PASS** — As variáveis de produção esperadas continuam fora do repositório: banco, origem permitida e chave de assinatura realtime. A chave realtime é obrigatória e requer tamanho mínimo no modo de produção.
- **PASS** — A auditoria estática localizou apenas geração de token do servidor e fixtures de teste, não valores reais. O histórico de arquivos de ambiente contém apenas o exemplo seguro.
- **DECISÃO** — Não houve rotação durante esta rodada: não foi detectada exposição de segredo real no código ou histórico auditado. Caso uma credencial seja compartilhada fora do canal seguro, a rotação no provedor continua sendo necessária.

## E. Rate limiting

- **PASS** — Limites persistidos no PostgreSQL cobrem criação, entrada, estratégia, ações administrativas, treino, autenticação de jogador e handshake realtime.
- **PASS** — Em produção a indisponibilidade do limitador falha fechada; o limitador em memória é restrito a injeção de testes.
- **RISCO LOW** — A identificação por IP não confia em cabeçalhos encaminhados sem uma configuração explícita de proxy confiável. Isso evita spoofing, mas usuários atrás de um mesmo proxy podem compartilhar uma cota até que uma política de proxy confiável seja configurada.

## F. Entrada, validação e XSS

- **PASS** — Intenções de API são validadas no backend com modelos tipados; nome do participante é normalizado e limitado.
- **PASS** — A nova borda rejeita corpos declarados acima de 64 KiB para `/v1/*` com `413`, incluindo `no-store` na resposta.
- **PASS** — A busca não encontrou `dangerouslySetInnerHTML`, `innerHTML`, `eval` ou `new Function` no frontend. Os nomes são renderizados como texto React; os testes cobrem texto com HTML aparente, Unicode e emoji.

## G. Headers e CSP

- **PASS** — Frontend: CSP com `default-src 'self'`, `object-src 'none'`, `frame-ancestors 'none'`, `base-uri 'self'`, `form-action 'self'`, fontes/mídias/imagens locais e `connect-src` estrito. Não há `unsafe-eval`; os únicos `unsafe-inline` são os blocos necessários do bootstrap/estilos do Next.
- **PASS** — Frontend: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Permissions-Policy` restritiva e `Cross-Origin-Opener-Policy: same-origin`.
- **PASS** — API: os mesmos cabeçalhos defensivos essenciais; respostas `/v1/*` têm `Cache-Control: no-store, private, max-age=0` e `Pragma: no-cache` para não reter capabilities ou tickets.
- **DECISÃO** — HSTS é gerenciado pela plataforma Vercel. O domínio é compartilhado sob `vercel.app`; adicionar `includeSubDomains` pela aplicação seria mais amplo que o domínio controlado pelo projeto.

## H. CSRF

- **PASS** — O fluxo autenticado usa capability Bearer no cabeçalho `Authorization`, não cookies. CORS não aceita credenciais; portanto não existe sessão cookie a proteger com token CSRF.

## I. Logs e observabilidade

- **PASS** — Fluxos críticos registram identificadores operacionais, não bearer token, ticket, string de conexão ou segredo.
- **PASS** — A revisão de código confirmou que capacidade, estratégia e estado privado não são incluídos nos eventos públicos. Erros HTTP usam respostas controladas; a produção mantém `debug=False`.
- **NOTA** — Os logs do provedor devem continuar com retenção mínima e acesso restrito. A aplicação não deve ser instrumentada com captura de payloads de autorização.

## J. Erros e debug

- **PASS** — Exploradores interativos `/docs`, `/redoc` e `/openapi.json` são desativados quando `APP_ENV=production`; continuam disponíveis no desenvolvimento local.
- **PASS** — Realtime fecha tentativas inválidas com códigos genéricos, sem enumerar tickets, torneios ou capabilities.

## K. Dependências

- **PASS** — `npm audit --omit=dev --audit-level=high`: `0 vulnerabilities`.
- **PASS** — `pip check`: sem requisitos quebrados.
- **PASS** — `pip-audit -r apps/backend/requirements.txt`: nenhuma vulnerabilidade conhecida.
- **PASS** — O CI já executa auditoria Python e validações de projeto.

## L. Infraestrutura

- **PASS** — Vercel força build de produção com URL HTTPS interna e URL WSS pública válidas. Render expõe o backend por HTTPS/WSS e faz health check em `/health`.
- **PASS** — Banco permanece externo ao frontend e credenciais não chegam ao bundle.
- **RISCO LOW** — O plano gratuito do backend pode sofrer cold start; é um risco de disponibilidade/latência, não de integridade de jogo ou exposição de dados.

## M. Verificação de regras críticas

- **PASS** — Nenhuma regra de melhor de 1/3/5/7, vidas, estratégia, BYE, zumbi ou resultado foi movida para o frontend.
- **PASS** — O backend e o Game Engine continuam sendo a autoridade de resultados, corações, chaveamento e campeão.

## N. Testes executados

| Verificação | Resultado |
| --- | --- |
| Testes backend, realtime, engine e migrações | 196 passed, 25 skipped |
| Testes frontend | 25 passed |
| Lint frontend | pass |
| Build production frontend | pass |
| `compileall` Python | pass |
| Testes específicos de HTTP/realtime/tickets | 55 passed |

Os 25 testes ignorados exigem `RPS_TEST_DATABASE_URL`, um banco PostgreSQL de teste isolado, que não foi configurado nesta máquina. Eles não representam falha de teste nem autorizam apontar a suíte para o banco de produção.

## O. Alterações realizadas

1. Desativada a documentação interativa da API em produção.
2. Adicionados headers defensivos na API e no frontend.
3. Adicionada CSP com destinos estritos para conteúdo e realtime.
4. Adicionada prevenção explícita de cache de respostas de API com capabilities/tickets.
5. Adicionado limite de corpo público de 64 KiB para `/v1/*`.
6. Acrescentados testes para headers, cache, limite de corpo, documentação de produção, escopo administrativo e renderização segura de nome.

## P. Verificação pública pós-deploy

Após o deploy deste commit, validar novamente: frontend HTTPS, `/health`, headers, preflight CORS, uma conexão WSS autenticada, criação/entrada/READY e atualização realtime. O resultado da validação será incluído antes do fechamento da rodada.

## Q. Riscos residuais

- **LOW** — Cotação por IP sem cabeçalho de proxy confiável, documentada em E.
- **LOW** — Cold start do plano gratuito, documentado em L.
- **LOW (dívida técnica)** — Avisos de depreciação do ciclo `on_event` do FastAPI; não altera comportamento ou segurança nesta rodada e deve migrar para lifespan em manutenção futura.

## Gate

Pendente da validação pública do deploy deste commit.
