# Security blockers — V0.1

Status após a rodada 5: SEC-004 foi revisado e concluído localmente com contador PostgreSQL compartilhado. SEC-007 permanece bloqueador por não haver execução remota comprovada. Um item somente pode ser concluído após implementação, testes, documentação mínima, revisão do responsável e revisão de Segurança, sem achado ALTO relacionado aberto.

| ID | Status atual | Motivo resumido |
| --- | --- | --- |
| SEC-001 | Concluído localmente | `_load_players` foi corrigido; capability hash/expiração/revogação/escopo passaram em E2E PostgreSQL real. |
| SEC-002 | Concluído localmente | HTTP chama Engine, persiste snapshot canônico e bloqueia estratégias; E2E PostgreSQL passou. |
| SEC-003 | Concluído localmente | Origin é rejeitada antes de `accept`, há timeout/cleanup e E2E entrega evento por WebSocket após outbox. |
| SEC-004 | Concluído localmente | Contador PostgreSQL atômico com TTL, chaves hashadas e prova real entre duas instâncias; falha é fechada. |
| SEC-005 | Concluído localmente | Migrações e E2E PostgreSQL provaram rollback, idempotência, dois starts e lease/SKIP LOCKED. |
| SEC-006 | Concluído | CORS por allowlist, sem cookies/credentials, postura Bearer e testes revisados por Segurança. |
| SEC-007 | Em progresso | DSNs foram separados e CI ampliada; falta execução remota comprovada. |
| SEC-008 | Concluído localmente | `npm audit`, `pip-audit`, lint e build foram executados com êxito; a execução remota continua sob SEC-007. |

**Decisão de produto registrada na Rodada 2:** um torneio só inicia com pelo menos 2 participantes confirmados; a capacidade é somente o máximo. Consulte `PROJECT_CORE.md`, seções 6 e 8.

## Critical deploy blockers

### SEC-001 — Autorização do organizador

- **Status:** concluído localmente — a leitura materializa membros antes da consulta de regras; a regressão cobre 0/1/2/muitos e UUIDs isolados. O E2E PostgreSQL cobre capability com hash, expiração, revogação e sala errada.
- **Severidade:** ALTO; **bloqueia deploy:** sim.
- **Responsável:** Backend (Terra / High). **Revisores:** Segurança, Banco + Realtime.
- **Módulos esperados:** `apps/backend/`, `database/migrations/`, `docs/adr/` se a escolha de identidade for relevante.
- **Dependências:** contrato de `Tournament` e `Player` em [contracts.md](../docs/contracts.md).
- **Descrição / ameaça:** implementar prova de autorização por sala para iniciar, remover, alterar configuração e encerrar inscrições; mitiga tomada de controle via URL, payload ou papel fornecido pelo cliente.
- **Aceite:** participante recebe `403` em toda ação administrativa; organizador autorizado age apenas em sua sala; segredo/token não é registrado ou retornado indevidamente.
- **Testes:** autorização positiva/negativa, IDOR entre torneios, expiração/revogação conforme mecanismo escolhido e logs sem credenciais.

### SEC-002 — Autoridade do servidor e integração do Game Engine

- **Status:** concluído localmente — o E2E PostgreSQL confirma HTTP → Engine → snapshot `v1`/`tournament_state` → evento/outbox em uma transação. Não há rota para receber resultado oficial do cliente.
- **Severidade:** ALTO; **bloqueia deploy:** sim.
- **Responsáveis:** Game Engine (Sol / High) e Backend (Terra / High). **Revisores:** Segurança, QA.
- **Módulos esperados:** `packages/game-engine/`, `apps/backend/`, `packages/shared-types/` quando os contratos forem estáveis, `tests/`.
- **Dependências:** contratos de domínio; SEC-005 para persistir transições concorrentes.
- **Descrição / ameaça:** o backend recebe somente intenções e executa o Engine; cliente não informa resultados, vidas, BYE, vencedor, chaveamento ou avanço. Estratégias são validadas e congeladas em snapshot ao iniciar.
- **Aceite:** toda mudança oficial vem de transição do Engine no servidor; distribuições obrigatórias somam 100%; Treino usa cópia isolada; não há endpoint que aceite estado final do cliente.
- **Testes:** payload manipulado, estados condicionais inválidos, estratégia após início, vitória/derrota/empate, eliminação, BYE, chaveamento e empates longos.

### SEC-003 — Realtime seguro e isolado

- **Status:** concluído localmente — o handshake valida Origin antes de aceitar, limita autenticação/resume, cancela tasks e remove a inscrição; tickets, replay, isolamento e publicação após outbox foram executados contra PostgreSQL real.
- **Severidade:** ALTO; **bloqueia deploy:** sim.
- **Responsável:** Banco + Realtime (Terra / High). **Revisores:** Backend, Segurança.
- **Módulos esperados:** `realtime/`, `database/migrations/`, `apps/backend/`, documentação de transporte/ADR.
- **Dependências:** SEC-001, SEC-002 e SEC-005.
- **Descrição / ameaça:** selecionar transporte e definir canais por torneio. Apenas o servidor publica eventos competitivos oficiais; clientes assinam somente o que podem ver e enviam intenções validadas.
- **Aceite:** isolamento entre torneios, emissão oficial exclusiva do servidor, reconexão não duplica efeito e eventos têm ordem/idempotência verificável.
- **Testes:** assinatura/acesso indevido, evento oficial forjado, replay, duplicação, reconexão e acesso cruzado de sala.

### SEC-004 — Códigos opacos e proteção contra abuso

- **Status:** concluído localmente após revisão de Segurança — o caminho durável usa `shared_rate_limit_buckets` no PostgreSQL, com upsert atômico, TTL e chaves hashadas por operação/sujeito. Duas instâncias compartilharam orçamento em teste PostgreSQL real; indisponibilidade retorna 503/1013 sem fallback local.
- **Severidade:** ALTO; **bloqueia deploy:** sim.
- **Responsável:** Backend (Terra / High). **Revisores:** Segurança, Banco + Realtime.
- **Módulos esperados:** `apps/backend/`, `database/migrations/`, `tests/`, decisão documentada.
- **Dependências:** modelo de persistência de torneio.
- **Descrição / ameaça:** gerar códigos não sequenciais e com entropia apropriada; limitar criação, entrada, tentativas de código, estratégia, ações administrativas e conexão/reconexão realtime. Mitiga enumeração, brute force e spam.
- **Aceite:** respostas a códigos inválidos não facilitam enumeração; limites são específicos por operação e não bloqueiam uso normal; limites funcionam entre instâncias se houver escala horizontal.
- **Testes:** geração não previsível, tentativas repetidas, criação abusiva, respostas neutras e recuperação após janela de limite.

## Required before public release

### SEC-005 — Concorrência, transações e idempotência

- **Status:** concluído localmente — PostgreSQL 16.15 executou upgrade, downgrade/reupgrade, FKs compostas, idempotência de start concorrente, rollback e dois workers com `SKIP LOCKED`; a entrega de outbox é at-least-once com deduplicação por evento no cliente.
- **Severidade:** MÉDIO; **bloqueia deploy:** sim, por suportar SEC-002 e SEC-003.
- **Responsável:** Banco + Realtime (Terra / High). **Revisores:** Backend, Game Engine, Segurança.
- **Módulos esperados:** `database/migrations/`, `apps/backend/`, `realtime/`, `tests/`.
- **Dependências:** modelo de persistência e transições do Engine.
- **Descrição / ameaça:** proteger início duplicado, salvamento duplicado, avanço simultâneo, evento repetido e reconexão. Usar transações, constraints, versionamento/idempotency keys ou locks somente onde necessários.
- **Aceite:** uma partida só avança uma vez; início é atômico; repetição de request é segura; duas instâncias não produzem vencedores distintos.
- **Testes:** dois cliques em iniciar, requests idênticos, corrida de avanço, evento duplicado, reconexão e processamento concorrente.

### SEC-006 — CORS, CSRF e postura de sessão

- **Status:** concluído — allowlist explícita, curinga rejeitado, sem credentials/cookies e postura Bearer revisada por Segurança.
- **Severidade:** MÉDIO; **bloqueia deploy:** sim.
- **Responsáveis:** Backend (Terra / High) e Segurança (Sol / High). **Revisor:** DevOps.
- **Módulos esperados:** `apps/backend/`, `.env.example`, `docs/security.md`, documentação de deploy.
- **Dependências:** decisão de autenticação e domínios de ambiente.
- **Descrição / ameaça:** configurar allowlist por ambiente e definir proteção CSRF se credenciais forem cookies. Mitiga origem não autorizada e ações cross-site.
- **Aceite:** produção não usa origem coringa em rotas sensíveis; métodos/headers/credentials são mínimos; cookies, se usados, têm flags adequadas e CSRF é testado.
- **Testes:** origens permitidas/negadas, preflight, requisição com credentials e ataque CSRF conforme o mecanismo escolhido.

### SEC-007 — CI de menor privilégio e actions imutáveis

- **Status:** em progresso — actions pinadas, CI ampliada e DSNs separados; a execução remota do pipeline ainda não foi comprovada.
- **Severidade:** MÉDIO; **bloqueia deploy:** sim.
- **Responsável:** DevOps (Terra / High). **Revisor:** Segurança.
- **Módulos esperados:** `.github/workflows/`, `.github/dependabot.yml`, documentação de deploy.
- **Dependências:** nenhuma.
- **Descrição / ameaça:** fixar actions externas por SHA, conservar comentários de versão humana, manter `contents: read` e não disponibilizar secrets a código de pull request não confiável.
- **Aceite:** actions usam SHA imutável; permissões explícitas são mínimas; checks de auditoria funcionam e falhas altas são visíveis.
- **Testes:** revisão do YAML e execução em branch/PR controlado.

### SEC-008 — Lockfiles e auditoria reproduzível

- **Status:** concluído localmente — lockfile, lint e build do frontend, `npm audit --omit=dev --audit-level=high` e `python -m pip_audit -r requirements.txt` passaram. A execução de GitHub Actions continua pendente sob SEC-007.
- **Severidade:** BAIXO; **bloqueia deploy:** sim, como requisito de reprodutibilidade.
- **Responsável:** DevOps (Terra / Medium-High). **Revisores:** Frontend, Segurança.
- **Módulos esperados:** `package-lock.json`, `package.json`, `.github/workflows/ci.yml`, Dockerfile do frontend.
- **Dependências:** instalação inicial de dependências do frontend.
- **Descrição / ameaça:** versionar lockfile, trocar instalações de CI para modo reproduzível e avaliar vulnerabilidades relevantes.
- **Aceite:** lockfile versionado; CI usa instalação determinística; auditorias são executadas; vulnerabilidades altas/críticas são corrigidas ou bloqueiam a release.
- **Testes:** instalação limpa e build/lint a partir do lockfile.

## Gate de publicação

**Não realizar deploy público da V0.1 enquanto SEC-001, SEC-002, SEC-003 ou SEC-004 estiverem abertos, nem enquanto qualquer tarefa marcada como bloqueadora de deploy não atender sua Definition of Done.** Ambiente local ou staging controlado é permitido apenas para validação e sem exposição de segredos/dados reais.
