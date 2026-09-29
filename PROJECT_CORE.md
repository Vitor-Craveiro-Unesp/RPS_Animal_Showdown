# RPS: Animal Showdown — PROJECT CORE

## 1. Identidade do projeto

**Nome oficial:** RPS: Animal Showdown

**RPS** significa:

- Rock
- Paper
- Scissors

O projeto é um site de torneios gamificados de Pedra, Papel e Tesoura, com personagens animais, estratégia probabilística, chaveamento em tempo real e apresentação visual semelhante a uma transmissão de campeonato.

O produto não deve ser apresentado como um simples sorteio.

O foco da comunicação deve ser:

- competição;
- estratégia;
- personagens;
- duelos;
- chaveamento;
- eliminação;
- campeonato;
- campeão.

---

# 2. Objetivo do produto

Transformar Pedra, Papel e Tesoura em uma experiência estratégica e cinematográfica.

Cada participante:

1. entra em um torneio usando um código;
2. informa seu nome;
3. escolhe um personagem animal;
4. configura a estratégia probabilística do personagem;
5. aguarda o organizador;
6. pode utilizar o modo Treino;
7. acompanha o campeonato em tempo real.

Depois que o organizador inicia, as batalhas acontecem automaticamente.

---

# 3. Tipos de acesso

O sistema terá três experiências principais.

## Participante

Pode:

- entrar usando código;
- informar nome;
- escolher personagem;
- configurar estratégia;
- usar o modo Treino;
- acompanhar o torneio.

## Organizador

Pode:

- criar torneio;
- configurar regras;
- definir capacidade máxima;
- acompanhar inscritos;
- acompanhar status de configuração;
- remover participantes quando necessário;
- iniciar o torneio;
- acompanhar o andamento.

## Espectador / Telão

Mostra a experiência cinematográfica:

- batalha atual;
- chaveamento;
- eventos.

---

# 4. Página inicial

A página inicial deverá oferecer três ações principais:

- **Entrar no torneio**
- **Criar torneio**
- **Ser patrocinador**

---

# 5. Criação do torneio

Ao criar um torneio, o sistema gera um código de acesso.

Exemplo:

`RPS847`

Os participantes utilizam esse código para entrar.

Também poderá ser gerado um QR Code para facilitar o ingresso pelo celular.

---

# 6. Capacidade da sala

O organizador define uma capacidade máxima.

Exemplo:

`Máximo: 10 jogadores`

Essa quantidade NÃO representa o número mínimo necessário para começar.

O organizador poderá iniciar com:

- 7;
- 8;
- 9;
- 10;

ou outra quantidade compatível com a capacidade definida.

O início é sempre uma decisão do organizador.

---

# 7. Painel em tempo real do organizador

O organizador precisa visualizar em tempo real quem está inscrito.

Para cada participante, mostrar pelo menos:

- nome;
- personagem;
- status.

Estados possíveis:

- entrou;
- escolhendo personagem;
- configurando estratégia;
- pronto;
- desconectado.

Exemplo:

`Vitor — 🐯 — Pronto`

`Benjamin — 🐼 — Configurando`

O organizador não deve precisar atualizar manualmente a página.

---

# 8. Início do torneio

Quando o organizador clicar em:

**INICIAR TORNEIO**

o sistema deverá:

1. encerrar novas inscrições;
2. considerar os participantes confirmados;
3. bloquear alterações das estratégias oficiais;
4. criar o chaveamento;
5. tratar eventuais BYEs;
6. iniciar a experiência do torneio.

---

# 9. Número ímpar de jogadores

Quando houver número ímpar de participantes, um jogador poderá avançar automaticamente.

Esse avanço é um BYE.

O sistema decide aleatoriamente quem recebe o BYE.

O organizador não escolhe manualmente.

---

# 10. Catálogo inicial

A primeira versão utilizará **20 personagens animais**.

Cada personagem terá um emoji diferente.

Personagens NÃO são exclusivos.

Duas ou mais pessoas podem selecionar o mesmo animal.

O personagem é identidade visual.

A estratégia diferencia os jogadores.

---

# 11. Catálogo inicial de animais

1. Estados Unidos — Águia — 🦅
2. China — Panda — 🐼
3. Austrália — Canguru — 🦘
4. Canadá — Castor — 🦫
5. Japão — Macaco japonês — 🐵
6. França — Galo — 🐓
7. Espanha — Touro — 🐂
8. Índia — Tigre — 🐯
9. Tailândia — Elefante — 🐘
10. Rússia — Urso — 🐻
11. Peru — Lhama — 🦙
12. Turquia — Lobo — 🐺
13. Arábia Saudita — Camelo — 🐪
14. Paquistão — Markhor/Cabra — 🐐
15. Indonésia — Dragão de Komodo — 🦎
16. Nepal — Vaca — 🐄
17. Botsuana — Zebra — 🦓
18. Madagascar — Lêmure — 🐒
19. Uganda — Grou-coroado — 🐦
20. Quênia — Leão — 🦁

O catálogo interno poderá registrar o país para posicionamento no mapa, mas o nome do país não precisa ser exibido ao usuário.

---

# 12. Seleção pelo mapa-múndi

A escolha do personagem será realizada através de um mapa-múndi interativo.

Cada emoji deverá aparecer aproximadamente sobre o país associado ao personagem.

O nome do país NÃO deve aparecer explicitamente.

A associação fica implícita pela localização do animal.

Ao tocar ou clicar no emoji, mostrar apenas informações relacionadas ao personagem.

Exemplo:

`🐼 Panda`

`[ ESCOLHER ]`

Como personagens podem ser repetidos, nenhum animal fica indisponível porque outra pessoa já o escolheu.

---

# 13. Estratégia probabilística

Cada personagem escolhe entre:

- Pedra;
- Papel;
- Tesoura.

O jogador define probabilidades.

Exemplo:

- Pedra: 50%
- Papel: 20%
- Tesoura: 30%

A soma deve ser sempre:

`100%`

Cada jogada individual pode ser modelada como uma distribuição categórica.

Ao observar várias rodadas, as contagens das escolhas podem ser modeladas por uma multinomial.

---

# 14. Estratégia condicional

O participante poderá configurar uma distribuição diferente para cada situação relevante da rodada anterior.

Estados:

## Estratégia inicial

Usada na primeira rodada.

## Perdeu para Pedra

## Perdeu para Papel

## Perdeu para Tesoura

## Ganhou de Pedra

## Ganhou de Papel

## Ganhou de Tesoura

## Empatou em Pedra

## Empatou em Papel

## Empatou em Tesoura

Para cada estado, o usuário define:

- probabilidade de Pedra;
- probabilidade de Papel;
- probabilidade de Tesoura.

Total:

`100%`

---

# 15. Igualdade dos personagens

Nenhum animal terá habilidade própria na primeira versão.

Todos possuem as mesmas possibilidades.

Isso evita desbalanceamento.

A diferença está somente na estratégia configurada pelo participante.

---

# 16. Sistema de vidas

As batalhas utilizam corações.

A quantidade de corações não é fixa.

O organizador define conforme o formato desejado.

Exemplos:

## Melhor de 3

Cada personagem começa com:

`❤️ ❤️`

Primeiro a conseguir 2 vitórias vence.

## Melhor de 5

Cada personagem começa com:

`❤️ ❤️ ❤️`

Primeiro a conseguir 3 vitórias vence.

A quantidade de corações equivale à quantidade de vitórias necessárias para ganhar a série.

---

# 17. Resultado de uma rodada

Se A vencer:

- B perde um coração.

Se B vencer:

- A perde um coração.

Se houver empate:

- ninguém perde coração.

---

# 18. Empates

Não há limite obrigatório de empates.

Se ocorrer:

- ninguém perde vida;
- a batalha continua;
- uma nova rodada acontece.

---

# 19. Eliminação

Quando um personagem fica sem corações:

- é eliminado;
- permanece visualmente onde perdeu no chaveamento;
- o vencedor avança.

O eliminado poderá aparecer:

- dessaturado;
- caído;
- com opacidade reduzida;
- com marca de eliminação;
- com caveira.

---

# 20. Uma batalha por vez

Somente uma dupla luta de cada vez.

Exemplo:

- partida 1 — jogando;
- partida 2 — aguardando;
- partida 3 — aguardando;
- partida 4 — aguardando.

A próxima começa somente depois da conclusão da atual.

---

# 21. Chaveamento vivo

O chaveamento deverá atualizar em tempo real.

Mostrar:

- quem aguarda;
- quem está lutando;
- quem venceu;
- quem morreu/eliminou;
- quem avançou;
- próximas fases.

---

# 22. Movimento dos personagens

O vencedor não deve simplesmente sumir de uma posição e aparecer na próxima.

A intenção é mostrar o personagem andando pelo caminho do chaveamento.

Fluxo:

1. termina o duelo;
2. derrotado permanece onde caiu;
3. vencedor comemora;
4. vencedor começa a caminhar;
5. percorre o trilho;
6. chega à próxima posição;
7. aguarda o próximo adversário.

---

# 23. Tela do torneio

A tela de transmissão será dividida em 3 áreas.

## Área 1 — Batalha atual

Principal.

Mostrar:

- personagens;
- nomes;
- corações;
- contagem;
- escolhas;
- resultado;
- empates;
- perda de vida;
- vitória.

## Área 2 — Chaveamento ao vivo

Mostrar:

- estrutura do torneio;
- participantes;
- eliminados;
- vencedores;
- movimento pelo chaveamento.

## Área 3 — Eventos / status

Mostrar mensagens como:

- entrou na arena;
- empate;
- perdeu coração;
- venceu;
- avançou;
- BYE;
- próximo duelo.

---

# 24. Experiência cinematográfica

Fluxo esperado de cada confronto:

1. destaque da dupla;
2. personagens chegam à arena;
3. exibição de nomes e vidas;
4. contagem;
5. jogadas;
6. resultado;
7. perda de coração se houver;
8. nova rodada ou eliminação;
9. vitória;
10. atualização do chaveamento;
11. deslocamento;
12. próxima batalha.

---

# 25. Contagem regressiva

A batalha utilizará:

`3`

`2`

`1`

O organizador poderá configurar a velocidade.

Exemplos:

- normal;
- metade do tempo;
- 1/4 do tempo.

Também poderá controlar velocidade de outras animações relevantes.

---

# 26. Áudio da contagem

Cada etapa da contagem utiliza som de:

**BEEP**

---

# 27. Sons de Pedra, Papel e Tesoura

Não tocar os sons das duas escolhas simultaneamente.

Depois da revelação:

## Se houver vencedor

Tocar somente o som correspondente ao elemento vencedor.

Exemplo:

Pedra × Tesoura

Som:

**Pedra**

## Se houver empate

Tocar o som do elemento empatado.

Exemplo:

Papel × Papel

Som:

**Papel**

---

# 28. Som de coração

Quando um personagem perde uma vida:

tocar efeito de:

**coração quebrando**

---

# 29. Som dos animais

O som específico do animal será utilizado principalmente quando ele vencer o duelo.

Exemplo:

Tigre vence:

tocar rugido do tigre.

Esse som funciona como uma assinatura de vitória.

---

# 30. Ordem sonora da eliminação

Quando a rodada final elimina alguém:

1. resultado visual;
2. som do coração quebrando;
3. eliminação;
4. som do animal vencedor;
5. vencedor avança.

O coração quebrando deve acontecer antes do som do animal.

---

# 31. Música e efeitos

O organizador poderá configurar separadamente:

- efeitos sonoros;
- música de fundo.

Ambos podem ser ligados ou desligados.

---

# 32. Modo Treino

Quando o participante terminar sua configuração e estiver aguardando os demais, poderá acessar:

**TREINO**

Nesse modo:

- o participante enfrenta seu próprio personagem;
- a pessoa escolhe manualmente;
- o personagem utiliza a estratégia configurada.

Botões:

- Pedra;
- Papel;
- Tesoura.

---

# 33. Regras do Treino

O Treino deve usar exatamente as mesmas regras do torneio atual.

Exemplos:

Se o torneio possui 2 corações:

o Treino possui 2.

Se possui 3:

o Treino possui 3.

Também respeitar:

- estratégia condicional;
- empates;
- perda de coração;
- condição de vitória.

---

# 34. Isolamento do Treino

Treino NÃO altera:

- classificação;
- chaveamento;
- vidas oficiais;
- resultados;
- seed;
- estado competitivo.

É apenas uma simulação.

---

# 35. Encerramento do Treino

Quando o organizador iniciar o torneio:

- o Treino termina automaticamente;
- o jogador é levado de volta à experiência oficial.

---

# 36. Estatísticas do Treino

Poderá mostrar:

- quantidade de rodadas;
- vitórias do usuário;
- vitórias do personagem;
- empates;
- frequência observada de Pedra;
- frequência observada de Papel;
- frequência observada de Tesoura.

---

# 37. Responsividade

O projeto deve funcionar desde o início em:

- celular;
- tablet;
- notebook;
- desktop;
- TV;
- projetor/telão.

---

# 38. Celular

Prioridades:

- entrar por código;
- selecionar animal;
- configurar estratégia;
- utilizar Treino;
- assistir ao torneio.

A interface deve se reorganizar para tela vertical.

---

# 39. Desktop

Priorizar a exibição simultânea das três áreas:

- batalha;
- chaveamento;
- eventos.

---

# 40. TV / Telão

Modo de visualização otimizado para:

- leitura à distância;
- acompanhamento coletivo;
- batalha;
- chaveamento;
- eventos.

---

# 41. Idiomas

O sistema terá três idiomas:

- Português do Brasil — `pt-BR`
- Inglês — `en`
- Chinês simplificado — `zh-CN`

Toda a interface deve mudar conforme o idioma escolhido.

Isso inclui:

- menus;
- botões;
- configurações;
- mensagens;
- status;
- batalha;
- Treino;
- organizador;
- espectador;
- eventos;
- campeão.

Internacionalização deve fazer parte da arquitetura desde o início.

Não espalhar textos literais pelo código.

---

# 42. Patrocínio

O modelo de monetização será baseado inicialmente em um único patrocinador.

Evitar:

- vários banners;
- pop-ups;
- anúncios durante a batalha;
- publicidade invasiva.

Utilizar um formato semelhante a campeonato:

**Patrocinado por**

`[NOME]`

`[LOGO]`

---

# 43. Patrocinador inicial

Enquanto não existir patrocinador comercial:

**Patrocinado por**

**Vitor Marchetti Craveiro**

A área reservada para logo permanece vazia enquanto não houver uma logo.

---

# 44. Patrocinador futuro

Quando uma marca contratar o espaço:

mostrar:

- nome da marca;
- logo.

De forma discreta.

Não competir visualmente com:

- arena;
- chaveamento;
- controles.

---

# 45. Página “Ser patrocinador”

Na primeira versão, não é necessário construir sistema automático de reserva e pagamento.

Mostrar:

- explicação do patrocínio;
- benefícios;
- exemplos visuais;
- botão **Quero patrocinar**.

O botão deve abrir WhatsApp para contato comercial.

---

# 46. Segurança

Resultados oficiais nunca devem depender exclusivamente do navegador do participante.

O servidor/backend deve ser autoridade para:

- escolhas aleatórias;
- probabilidades;
- vidas;
- resultado;
- chaveamento;
- vencedor;
- estados oficiais.

---

# 47. Segurança transversal

Existirá um agente específico de Segurança da Informação.

Ele atua transversalmente durante todo o projeto.

Revisa:

- arquitetura;
- backend;
- frontend;
- Game Engine;
- realtime;
- banco;
- DevOps;
- releases.

---

# 48. Pontos mínimos de segurança

Verificar continuamente:

- autenticação;
- autorização;
- SQL Injection;
- XSS;
- CSRF;
- rate limiting;
- abuso de códigos de sala;
- alteração indevida de estratégia;
- manipulação de resultados;
- exposição de segredos;
- variáveis de ambiente;
- permissões;
- uploads;
- APIs;
- logs;
- dependências vulneráveis.

---

# 49. Arquitetura sugerida

## Frontend

- Next.js
- React
- TypeScript

## Animações

- Framer Motion
- GSAP quando justificado

## Backend

- FastAPI/Python ou alternativa tecnicamente justificada

## Banco

- PostgreSQL

## Realtime

- Supabase Realtime
- ou WebSockets

## Hospedagem inicial

- Vercel
- Supabase

## Código

- Git
- GitHub

## Containers

- Docker

A implementação final deve priorizar:

- simplicidade;
- segurança;
- baixo custo;
- facilidade de manutenção;
- entrega rápida da V0.1.

---

# 50. Agentes

## Coordenador

Responsável por:

- arquitetura;
- planejamento;
- integração;
- distribuição;
- revisão;
- roteamento de modelos.

## Frontend

Responsável por:

- site;
- componentes;
- telas;
- responsividade;
- UX.

## Animação

Responsável por:

- arena;
- movimento;
- corações;
- mortes;
- transições;
- chaveamento animado.

## Backend

Responsável por:

- APIs;
- códigos;
- salas;
- usuários;
- regras de acesso;
- autoridade de servidor.

## Game Engine

Responsável por:

- RPS;
- probabilidades;
- estados condicionais;
- vidas;
- empates;
- BYE;
- chaveamento;
- vencedor.

## Banco + Realtime

Responsável por:

- banco;
- migrations;
- sincronização;
- realtime.

## QA

Responsável por:

- testes;
- regressão;
- edge cases;
- bugs.

## DevOps

Responsável por:

- Docker;
- GitHub;
- deploy;
- ambientes;
- CI/CD.

## Segurança

Agente transversal.

---

# 51. Agente Bootstrap

Antes do desenvolvimento, utilizar um agente temporário chamado:

**Bootstrap / Scaffolding**

Responsável pela fundação do repositório.

Deve criar e configurar:

- estrutura de diretórios;
- README;
- documentação;
- `.gitignore`;
- `.dockerignore`;
- `.env.example`;
- Dockerfiles;
- docker-compose;
- scripts;
- base de configuração;
- templates;
- documentação para os agentes.

Ele NÃO deve implementar todo o produto.

---

# 52. Estratégia de modelos no Codex

## GPT-5.6 Sol

Padrão:

- Coordenador;
- Game Engine;
- Segurança.

Nível recomendado:

High.

Segurança poderá usar esforço máximo em auditorias críticas.

## GPT-5.6 Terra

Padrão:

- Backend;
- Banco + Realtime;
- Frontend;
- Animação;
- QA;
- DevOps.

Usar Medium ou High conforme necessidade.

## GPT-5.6 Luna

Utilizar em subtarefas:

- boilerplate;
- lint;
- renomeações;
- tarefas repetitivas;
- testes mecânicos;
- traduções;
- pequenas alterações.

---

# 53. Roteamento automático de modelos

O Coordenador também atua como roteador.

Princípio:

**usar o modelo mais barato que consiga realizar a tarefa com segurança e qualidade.**

Escalonar:

`Luna → Terra → Sol`

quando houver:

- complexidade alta;
- risco;
- falhas repetidas;
- impacto estrutural;
- ambiguidade importante;
- dificuldade técnica.

Rebaixar:

`Sol → Terra → Luna`

quando a tarefa seguinte for simples.

Mudanças relevantes de modelo devem ser registradas com:

- tarefa;
- modelo;
- motivo;
- resultado.

---

# 54. Cronograma

A meta inicial pressupõe uso dos agentes trabalhando em paralelo.

Sem agentes, o prazo não deve ser considerado equivalente.

---

# 55. Primeiros 10 dias

Meta:

colocar no ar uma versão:

- pública;
- simples;
- jogável;
- utilizável.

Priorizar funcionamento.

Sempre que viável, incluir:

- criação de torneio;
- código;
- entrada;
- seleção de personagem;
- estratégia;
- painel do organizador;
- realtime;
- Treino;
- vidas;
- Game Engine;
- chaveamento funcional;
- idiomas;
- deploy.

Não bloquear a V0.1 por falta de animação cinematográfica avançada.

---

# 56. Fase posterior

Após os primeiros 10 dias, começar polimento.

Objetivo:

criar uma versão:

- bonita;
- robusta;
- estável;
- segura;
- responsiva;
- cinematográfica;
- com aparência de produto final.

Prioridades:

- animações;
- personagens andando;
- eliminações;
- áudio;
- UX;
- performance;
- estabilidade;
- segurança;
- testes;
- acabamento.

---

# 57. Princípios de desenvolvimento

1. Primeiro funcionar.
2. Depois polir.
3. Evitar overengineering.
4. Segurança desde o início.
5. Backend é autoridade do jogo.
6. Game Engine deve ser testável separadamente.
7. Internacionalização desde o início.
8. Não armazenar segredos no Git.
9. Documentar mudanças importantes.
10. Não alterar regras de produto silenciosamente.
11. Preferir soluções simples na V0.1.
12. Todo agente deve ler este documento antes de decisões relevantes.

---

# 58. Fonte da verdade

`PROJECT_CORE.md` é a principal fonte de requisitos do produto.

Se uma implementação entrar em conflito com este documento:

1. identificar o conflito;
2. registrar;
3. discutir tecnicamente;
4. atualizar conscientemente a implementação ou o documento.

Nenhum agente deve modificar regras centrais silenciosamente.