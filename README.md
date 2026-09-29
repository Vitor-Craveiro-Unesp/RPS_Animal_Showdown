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
5. pode utilizar o modo Treino;
6. aguarda o organizador iniciar;
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

A primeira versão utilizará 20 animais.

A seleção será feita em um mapa-múndi interativo.

Cada emoji será posicionado aproximadamente sobre a região associada ao personagem.

O nome do país não será exibido explicitamente.

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

O organizador define quando o torneio começa.

A capacidade da sala representa apenas o número máximo de jogadores.

Uma sala para 10 pessoas poderá começar, por exemplo, com:

- 7;
- 8;
- 9;
- 10.

Se houver número ímpar de participantes, o sistema trata automaticamente o BYE.

## Transmissão

A experiência principal será dividida em três áreas:

### Batalha atual

Mostra o confronto que está acontecendo.

### Chaveamento ao vivo

Mostra os participantes avançando e os eliminados permanecendo onde perderam.

### Eventos

Mostra acontecimentos importantes da competição.

## Modo Treino

Depois de configurar sua estratégia, o jogador pode treinar enquanto aguarda.

No Treino:

- o usuário escolhe Pedra, Papel ou Tesoura manualmente;
- o próprio personagem responde usando sua estratégia configurada;
- são utilizadas as mesmas regras de vida do torneio.

O Treino não altera resultados oficiais.

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

## Ambiente

As instruções de instalação e execução local serão documentadas após o Bootstrap inicial.

## Licença

A definir.