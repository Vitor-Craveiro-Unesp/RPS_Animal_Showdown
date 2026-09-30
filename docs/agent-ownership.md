# Divisão de trabalho entre agentes

Esta matriz reduz conflitos de edição. `PROJECT_CORE.md` continua sendo a fonte de requisitos; mudanças que atravessam áreas devem ser alinhadas pelo Coordenador e revisadas por Segurança quando afetarem autoridade, dados ou exposição pública.

| Agente | Modelo / esforço padrão | Dono primário | Não deve alterar sem coordenação |
| --- | --- | --- | --- |
| Coordenador | Sol / High | `docs/`, ADRs, plano e integração entre áreas | regras oficiais sem decisão registrada |
| Game Engine | Sol / High | `packages/game-engine/`, seus testes | rotas HTTP, persistência e UI |
| Backend | Terra / High | `apps/backend/` | regras duplicadas do Engine, migrations de outro agente |
| Banco + Realtime | Terra / High | `database/migrations/`, `realtime/` | decisões de identidade e regras do Engine |
| Frontend | Terra / Medium | `apps/frontend/`, catálogos de locale | resultado oficial, vidas e chaveamento no cliente |
| Animação | Terra / Medium | `apps/frontend/src/features/animation/` | estado oficial, contratos ou fluxo de dados |
| QA | Terra / High | `tests/`, cenários de regressão e documentação de teste | código de produção, salvo correções explicitamente delegadas |
| DevOps | Terra / High | Dockerfiles, Compose, CI e documentação de deploy | segredos, regras de domínio ou migrations |
| Segurança | Sol / High | revisão transversal e registros de risco | não implementa fluxos amplos sem delegação explícita |

## Arquivos compartilhados

- `README.md`, `PROJECT_CORE.md`, `AGENTS.md`, `package.json`, `.env.example` e `docker-compose.yml` exigem aviso prévio ao Coordenador.
- `packages/shared-types/` só recebe contratos que já tenham sido acordados entre os donos que os consomem.
- O Frontend e Animação dividem `apps/frontend/`: o Coordenador deve separar os componentes/rotas antes de trabalho simultâneo nessa área.

## Ordem de dependências

O contrato do Game Engine vem antes das rotas oficiais. Os contratos de API e eventos são definidos em conjunto por Backend, Banco + Realtime e Frontend antes da integração. QA e Segurança podem revisar desde o primeiro PR.

## Padrão de relatório de tarefa

Todo agente encerra uma tarefa com: ID da tarefa, arquivos alterados, testes executados e resultado, riscos, pendências e saída de `git status`. Bloqueadores SEC exigem também confirmação de revisão de Segurança.
