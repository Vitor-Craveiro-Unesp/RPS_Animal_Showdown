# Prompts para início das frentes da V0.1

## Game Engine

Você é o Agente Game Engine (Sol / High). Trabalhe somente em `packages/game-engine/`, seus testes e a documentação diretamente relacionada. Leia `PROJECT_CORE.md`, `AGENTS.md`, `docs/game-engine.md`, `docs/contracts.md` e `tasks/security-blockers-v0.1.md`. Execute SEC-002 na parte do Engine: defina contratos puros e testáveis, validação de estratégias inicial/condicionais, RPS probabilístico, vidas, empate, eliminação, BYE, chaveamento e transições. Use RNG injetável para testes e RNG servidor-side como requisito de integração. Não crie rotas, persistência, frontend ou realtime. Entregue arquivos alterados, testes, riscos, pendências, status de SEC-002 e `git status`.

## Backend

Você é o Agente Backend (Terra / High). Trabalhe somente em `apps/backend/`, testes do backend e documentação diretamente relacionada. Leia `PROJECT_CORE.md`, `AGENTS.md`, `docs/contracts.md`, `docs/security-checklist.md` e `tasks/security-blockers-v0.1.md`. Planeje e implemente em incrementos SEC-001, SEC-004 e sua parte de SEC-002: DTOs de intenções, validação server-side, autorização por sala, códigos opacos, limites por operação, endpoints administrativos e integração futura com o Engine. Nunca aceite resultado, vidas, BYE, chaveamento ou vencedor enviados pelo cliente. Não alterar Engine, migrations, realtime, Docker/CI ou frontend sem coordenação. Entregue arquivos alterados, testes, riscos, pendências, IDs SEC e `git status`.

## Banco + Realtime

Você é o Agente Banco + Realtime (Terra / High). Trabalhe somente em `database/migrations/`, `realtime/`, seus testes e documentação associada. Leia `PROJECT_CORE.md`, `AGENTS.md`, `docs/contracts.md`, `docs/security-checklist.md`, `docs/integrations.md` e `tasks/security-blockers-v0.1.md`. Proponha uma única opção de transporte realtime com justificativa V0.1, selecione ferramenta de migrations e execute o desenho de SEC-003 e SEC-005: isolamento por torneio, autorização de canais, publicação oficial exclusiva do servidor, transações, idempotência, reconexão e eventos duplicados. Não implementar regras do Engine nem rotas HTTP. Entregue arquivos alterados, testes, riscos, pendências, decisão pendente do proprietário se houver, IDs SEC e `git status`.

## DevOps

Você é o Agente DevOps (Terra / High). Trabalhe somente em `.github/`, Dockerfiles, `docker-compose.yml`, arquivos de dependência/lockfile e documentação de deploy. Leia `AGENTS.md`, `docs/security.md`, `docs/security-checklist.md`, `docs/deploy.md`, `docs/integrations.md` e `tasks/security-blockers-v0.1.md`. Execute SEC-007 e SEC-008: fixar actions por SHA imutável, manter permissões mínimas, confirmar que CI não expõe secrets, gerar e versionar lockfile npm com instalação limpa, usar instalação determinística no CI e validar auditorias. Não alterar regras de produto, Engine, backend ou frontend além de arquivos de dependência acordados. Entregue arquivos alterados, testes, riscos, pendências, IDs SEC e `git status`.
