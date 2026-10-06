# Rodada 8.1.1 — Organizador sem conta

Data: 2026-10-05. Esta rodada é estritamente local; não realizou deploy,
push, OAuth, criação de conta ou alteração de regras do jogo.

## A. Estado inicial

O repositório já tinha uma capability de organizador implementada: o backend
emitia um token aleatório, persistia apenas seu hash e protegia os endpoints
`/admin/*`. O worktree pré-existente foi preservado.

## B. Google Auth encontrado

Não havia OAuth, SDK, callback, provider Supabase Auth ou tela de login Google
executável. Havia somente referências de planejamento na documentação e no
`.env.example`; elas foram removidas ou substituídas.

## C–D. Componentes e fluxo

Home → Criar torneio → configurações → criar → painel do organizador ocorre
sem cadastro. A criação retorna o código público e, somente para o criador, a
capability administrativa. Participantes continuam: código → nome → animal →
estratégia → READY, sem conta.

## E–G. Organizer token, geração e backend

`secrets.token_urlsafe(32)` gera uma capability opaca de alta entropia por
torneio. Ela não é derivada do código público. O PostgreSQL armazena apenas
`secret_hash` SHA-256, com expiração e revogação; a comparação é segura. O
modelo em memória aplica o mesmo contrato para testes locais.

## H. Armazenamento frontend

O acesso foi encapsulado em `apps/frontend/src/app/organizer-session.mjs` e
fica em `sessionStorage`: sobrevive a F5 na mesma aba, não entra em URL, HTML
público ou payload de participante e não é exibido ao usuário. Para o MVP,
apagar a sessão, trocar de navegador ou perder o token remove o acesso; não há
recuperação por e-mail.

## I–K. Autorização, realtime e projeções públicas

O backend é a autoridade: participantes, token errado, token de outro torneio,
código público e ausência de token são recusados antes de qualquer mutação
administrativa. Start, configuração, remover participante, fechar inscrições e
repeat exigem capability. Tickets WebSocket derivam de capability validada e
não incluem o token. Snapshots, replay e eventos usam projeções públicas, sem
token, hash ou estratégia privada.

## L. Rate limiting

`POST /v1/tournaments` permanece limitado a cinco criações por hora por IP;
em produção o contador é compartilhado no PostgreSQL e falha fechado.

## M–N. Banco e Supabase

Não foi necessária migration nova: `0002_auth_snapshots` já cria
`tournament_access_capabilities`, e `0003_ticket_grant_integrity` reforça o
escopo por torneio, sujeito e papel. Supabase continua sendo somente o
PostgreSQL gerenciado planejado, não Supabase Auth.

## O–P. Ambiente e documentação

`.env.example` não contém Google/OAuth ou token fixo de organizador. A
documentação de produção, README e o relatório 8.1 registram a decisão:
Google Auth foi cancelado por decisão de produto e a capability emitida pelo
backend é a autorização do organizador.

## Q–R. Testes e build

- Frontend: lint, TypeScript e **25 testes** passaram.
- Backend, Engine, realtime e contratos de migration locais: **184 passaram**;
  as seis provas PostgreSQL opt-in foram então executadas no banco isolado.
- PostgreSQL isolado: capability persistida/hasheada e limitada à sala, repeat
  entre runs e as seis constraints: **8 passaram**.
- Build otimizado do Next: passou com URLs HTTPS/WSS de exemplo.
- `npm audit --omit=dev --audit-level=high`: zero vulnerabilidades.
- `git diff --check`: passou.
- Teste manual: criar torneio sem login abriu o painel do organizador e o
  refresh manteve a authorization local no mesmo navegador; console sem erros.

## S. Segurança

Não há token em logs de criação, snapshots públicos, eventos, WebSocket ou
URLs. O código público não equivale a uma senha. A capability é específica do
torneio e permanece válida entre runs, sem rotação silenciosa no repeat.

## T. Limitações

Capabilities expiram e não possuem recuperação para o MVP. A sessão local é
deliberadamente por aba: protege contra exposição por URL e atende ao refresh
normal; persistência entre navegadores/dispositivos não é oferecida.

## U. Git

O worktree já estava alterado antes da rodada. Nenhum reset, commit ou push foi
feito.

## V. Gate

**ORGANIZADOR ANÔNIMO APROVADO.**
