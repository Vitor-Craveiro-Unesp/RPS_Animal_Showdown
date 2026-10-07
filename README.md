# RPS: Animal Showdown

**RPS: Animal Showdown** é um jogo de torneios baseado em Rock, Paper, Scissors, no qual cada participante escolhe um personagem animal e programa sua própria estratégia probabilística.

O objetivo é transformar Pedra, Papel e Tesoura em uma experiência estratégica, visual e cinematográfica.

## Status

🚧 Em desenvolvimento.

### Meta inicial

Entregar nos primeiros **10 dias** uma versão:

- pública;
- simples;
- jogável;
- utilizável.

Essa meta pressupõe desenvolvimento com agentes trabalhando em paralelo.

Depois disso, o projeto entra em uma fase de polimento visual, estabilidade, segurança e experiência cinematográfica.

## Como funciona

Cada participante:

1. entra em um torneio usando um código;
2. informa seu nome;
3. escolhe um animal em um mapa-múndi;
4. configura sua estratégia de Pedra, Papel e Tesoura;
5. pode utilizar o modo Treinar livre pela Home;
6. após READY, aguarda o organizador e pode jogar Animal Rush;
7. acompanha os duelos e o chaveamento em tempo real.

## Estratégia

As jogadas dos personagens não precisam utilizar probabilidades iguais.

Exemplo:

- Pedra: 50%
- Papel: 20%
- Tesoura: 30%

Além da estratégia inicial, o participante poderá definir comportamentos diferentes dependendo do resultado anterior.

Exemplos:

- perdeu para Pedra;
- ganhou de Papel;
- empatou em Tesoura.

Isso permite criar estratégias condicionais sem dar vantagens exclusivas aos personagens.

## Personagens

A primeira versão utilizará 26 animais.

A seleção será feita em um mapa-múndi interativo.

Cada emoji será posicionado aproximadamente sobre a região associada ao personagem.

O país ou região e o continente aparecem ao selecionar o animal.

O mapa de seleção usa SVGs locais com fronteiras e rótulos de países, gerados a partir de `apps/frontend/public/maps/world-map-countries.svg`. A arte é de [World.ie](https://world.ie/map/), baseada em dados de [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/); ambos a disponibilizam em domínio público. O script `scripts/localize-world-map.mjs` gera versões em inglês, português, chinês e árabe sem rótulos de continentes ou territórios não soberanos. No celular, o mapa pode ser deslocado e ampliado para leitura dos países.

Personagens podem ser repetidos.

Duas ou mais pessoas podem escolher o mesmo animal.

## Sistema de vidas

Os duelos utilizam corações.

Exemplo:

`❤️ ❤️ ❤️`

Quando um personagem perde uma rodada, perde um coração.

Empates não causam perda de vida.

Quando todos os corações acabam, o personagem é eliminado.

## Torneio

Qualquer pessoa pode criar um torneio sem cadastro, e-mail, senha ou Google
Auth. Ao criar, o backend emite uma capability secreta do organizador: o
navegador do criador a guarda apenas na sessão local e a apresenta ao backend
para iniciar, alterar ou repetir o torneio. O código público da sala permite
somente a entrada de participantes e nunca concede privilégios administrativos.
Se a sessão local for apagada ou o criador trocar de navegador, não há
recuperação de organizador no MVP.

O organizador define quando o torneio começa.

Ao avançar da escolha do animal para a estratégia, a inscrição aparece no
painel como **Montando estratégia**. Só após confirmar **Estou pronto** ela
passa a **Pronto**; apenas participantes prontos entram no chaveamento. O
servidor espera 3 segundos após o Start antes de resolver a primeira jogada.
Os eventos oficiais incluem horários de apresentação definidos no backend,
para que telas conectadas mostrem cada fase do duelo no mesmo instante, mesmo
quando recebem os eventos com latências diferentes.

A capacidade da sala representa apenas o número máximo de jogadores.

Uma sala para 10 pessoas poderá começar, por exemplo, com:

- 7;
- 8;
- 9;
- 10.

Novos torneios inicialmente ímpares usam a Segunda Chance Zumbi: um participante aguarda e enfrenta um dos perdedores iniciais sorteado pelo servidor. O vencedor segue; fases posteriores ímpares usam BYE local à fase. Consulte [Rodada 6.6](docs/round-6-6-report.md).

Um torneio exige pelo menos **2 participantes confirmados** para iniciar. A capacidade da sala continua sendo apenas o limite máximo.

## Transmissão

A experiência principal será dividida em três áreas:

### Batalha atual

Mostra o confronto que está acontecendo.

### Chaveamento ao vivo

Mostra os participantes avançando e os eliminados permanecendo onde perderam.

### Eventos

Mostra acontecimentos importantes da competição.

## Treinar livre e Animal Rush

O botão **Treinar** da Home oferece prática livre de Pedra, Papel e Tesoura sem exigir código de torneio.

Depois de configurar a estratégia oficial e confirmar READY, o participante entra na Sala de Espera e pode jogar **Animal Rush**. Nesse minigame local, deve escolher rapidamente o símbolo que vence Pedra, Papel ou Tesoura. Pontuação, sequência e dificuldade pertencem apenas ao minigame e nunca alteram o estado competitivo.

O canal realtime permanece ativo durante o Animal Rush. Quando o servidor inicia o torneio, os timers e o estado transitório do minigame são descartados e a interface muda imediatamente para a Arena oficial.

## Áudio

O sistema prevê:

- beep na contagem;
- som do elemento vencedor;
- som do elemento empatado quando houver empate;
- efeito de coração quebrado;
- som do animal quando ele vence o confronto;
- música de fundo opcional.

## Idiomas

O projeto terá suporte a:

- Português do Brasil;
- English;
- 简体中文.

A internacionalização deverá fazer parte da arquitetura desde o início.

## Dispositivos

O sistema será responsivo.

Suporte planejado:

- celular;
- tablet;
- computador;
- TV;
- projetor/telão.

## Patrocínio

O projeto utilizará um modelo discreto de patrocínio único.

Formato:

**Patrocinado por**

`[NOME]`

`[LOGO]`

Enquanto não houver patrocinador comercial:

**Patrocinado por Vitor Marchetti Craveiro**

## Tecnologias previstas

- Next.js
- React
- TypeScript
- FastAPI
- PostgreSQL
- Supabase
- Realtime / WebSockets
- Docker
- Git
- GitHub
- Vercel

A arquitetura definitiva deverá ser validada antes da implementação completa.

## Desenvolvimento com agentes

O projeto será desenvolvido com agentes especializados em:

- coordenação;
- frontend;
- animação;
- backend;
- Game Engine;
- banco e realtime;
- QA;
- DevOps;
- segurança.

Também será utilizado inicialmente um agente Bootstrap/Scaffolding para preparar a fundação do repositório.

## Segurança

O backend deverá ser a autoridade dos resultados oficiais.

O navegador não deve conseguir alterar diretamente:

- resultado;
- vidas;
- estratégia bloqueada;
- vencedor;
- chaveamento.

Um agente de Segurança da Informação acompanhará o projeto transversalmente.

## Documentação

A especificação completa está disponível em:

`PROJECT_CORE.md`

As regras dos agentes estarão em:

`AGENTS.md`

## Ambiente local

O Bootstrap inicial disponibiliza um ambiente de desenvolvimento com frontend, backend e PostgreSQL.

1. Copie `.env.example` para `.env` e mantenha somente valores locais.
2. Execute `docker compose up --build` na raiz do repositório.
3. Abra `http://localhost:3000`; a verificação do backend fica em `http://localhost:8000/health`.

O Docker Compose atual é uma base de desenvolvimento, não uma configuração de produção. Consulte [a arquitetura](docs/architecture.md), [o guia de deploy](docs/deploy.md) e [as decisões arquiteturais](docs/adr/README.md).

O plano de execução e os limites de trabalho por agente estão em [docs/v0.1-plan.md](docs/v0.1-plan.md) e [docs/agent-ownership.md](docs/agent-ownership.md). As integrações que dependem de contas ou decisões do proprietário estão em [docs/integrations.md](docs/integrations.md).

## Estrutura inicial

- `apps/frontend`: interface Next.js/React;
- `apps/backend`: API FastAPI e futura autoridade do servidor;
- `packages/game-engine`: regras oficiais independentes da interface;
- `packages/shared-types`: contratos estáveis compartilhados;
- `database/migrations`: histórico de mudanças de esquema;
- `realtime`: documentação e futura integração de sincronização;
- `docs`: arquitetura, segurança, i18n, deploy e convenções.

## Licença

A definir.
### Pódio e repetição

Torneios novos incluem bronze antes da final quando há duas semifinais.
Após o pódio, o organizador pode repetir com os mesmos inscritos/configurações
em uma nova execução independente, mantendo o histórico anterior.
Aplicar a migração 0006 antes de iniciar o backend atualizado.
Veja [contratos de pódio e runs](docs/podium-and-runs.md).
