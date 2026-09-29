# AGENTS.md

## RPS: Animal Showdown

Este arquivo estabelece regras de trabalho para agentes que atuam neste repositório.

---

# 1. Leitura obrigatória

Antes de realizar mudanças relevantes, leia:

1. `PROJECT_CORE.md`
2. `README.md`
3. este arquivo

`PROJECT_CORE.md` é a principal fonte de requisitos funcionais.

---

# 2. Regra principal

Não invente requisitos.

Não altere regras centrais silenciosamente.

Quando houver conflito entre implementação e especificação:

1. identifique;
2. registre;
3. proponha solução;
4. preserve o comportamento existente até que a decisão seja resolvida.

---

# 3. Prioridades

Priorizar nesta ordem:

1. correção;
2. segurança;
3. integridade do Game Engine;
4. simplicidade;
5. testabilidade;
6. manutenção;
7. performance;
8. polimento visual.

Durante os primeiros 10 dias, priorizar uma versão pública e jogável.

Evitar overengineering.

---

# 4. Segurança

Nunca:

- commitar senhas;
- commitar tokens;
- commitar secrets;
- colocar credenciais reais em `.env.example`;
- confiar em valores críticos enviados pelo frontend.

O backend deve ser autoridade para:

- resultados;
- vidas;
- estratégia oficial;
- chaveamento;
- vencedor.

Mudanças sensíveis devem ser revisadas pelo agente de Segurança.

---

# 5. Game Engine

O Game Engine deve ser o mais desacoplado possível da interface.

Regras devem ser testáveis independentemente do frontend.

Incluir testes para:

- vitória;
- derrota;
- empate;
- perda de coração;
- eliminação;
- BYE;
- estratégias condicionais;
- sequências longas de empate;
- chaveamento.

---

# 6. Internacionalização

Não espalhar strings de interface diretamente pelos componentes.

Usar estrutura de internacionalização desde o início.

Idiomas:

- `pt-BR`
- `en`
- `zh-CN`

---

# 7. Git

O repositório Git já existe.

NÃO execute `git init`.

Antes de alterações relevantes:

- verificar `git status`;
- preservar histórico existente;
- evitar commits destrutivos;
- não utilizar force push sem autorização.

Commits devem ser pequenos e descritivos.

---

# 8. Docker

A infraestrutura deve considerar Docker desde a fundação.

Manter:

- `.dockerignore`;
- Dockerfiles simples;
- desenvolvimento local reproduzível.

Evitar complexidade desnecessária na V0.1.

---

# 9. Documentação

Documentar decisões importantes.

Documentos recomendados:

- arquitetura;
- Game Engine;
- segurança;
- i18n;
- deploy;
- decisões arquiteturais;
- convenções.

Atualizar documentação quando comportamento importante mudar.

---

# 10. Responsabilidades dos agentes

## Coordenador

Arquitetura, planejamento, integração e roteamento.

## Frontend

Interface, UX e responsividade.

## Animação

Arena, movimento e experiência visual.

## Backend

APIs, salas, regras de acesso e autoridade do servidor.

## Game Engine

Regras oficiais do jogo.

## Banco + Realtime

Persistência e sincronização.

## QA

Testes e regressão.

## DevOps

Containers, ambientes e deploy.

## Segurança

Revisão transversal.

---

# 11. Estratégia de modelos

## Sol

Preferencial:

- Coordenador;
- Game Engine;
- Segurança.

## Terra

Preferencial:

- Frontend;
- Backend;
- Animação;
- Banco/Realtime;
- QA;
- DevOps.

## Luna

Preferencial para subtarefas mecânicas.

---

# 12. Escalonamento

O Coordenador pode escalar:

`Luna → Terra → Sol`

quando houver:

- falha repetida;
- alta complexidade;
- risco;
- alteração estrutural;
- problema crítico.

Também pode rebaixar quando a tarefa seguinte for simples.

Registrar decisões relevantes.

---

# 13. Critério de conclusão

Uma tarefa não está concluída apenas porque o código compila.

Verificar quando aplicável:

- comportamento;
- testes;
- segurança;
- responsividade;
- documentação;
- regressão.

---

# PROMPT INICIAL — AGENTE BOOTSTRAP / SCAFFOLDING

Você é o agente Bootstrap/Scaffolding do projeto **RPS: Animal Showdown**.

O repositório Git já existe.

NÃO execute `git init`.

Sua missão nesta etapa é preparar uma fundação técnica profissional para que os demais agentes consigam trabalhar sem conflitos.

## Antes de fazer qualquer alteração

Leia integralmente:

1. `PROJECT_CORE.md`
2. `README.md`
3. `AGENTS.md`

Considere `PROJECT_CORE.md` a principal fonte de requisitos do produto.

Não implemente o produto completo nesta etapa.

Não invente funcionalidades.

Não remova ou altere regras existentes sem justificativa explícita.

---

## Objetivo

Preparar a estrutura inicial do repositório para a V0.1 pública e jogável planejada para os primeiros 10 dias.

Priorize:

- simplicidade;
- segurança;
- baixo custo;
- velocidade de desenvolvimento;
- manutenção;
- trabalho paralelo entre agentes.

---

## Primeiro passo

Antes de modificar qualquer arquivo:

1. examine a estrutura atual do repositório;
2. execute `git status`;
3. identifique arquivos existentes;
4. preserve tudo que já estiver versionado;
5. não sobrescreva arquivos relevantes sem necessidade.

---

## Crie uma estrutura de projeto adequada

Projete uma estrutura clara que comporte:

- frontend;
- backend;
- Game Engine;
- shared types;
- banco;
- realtime;
- internacionalização;
- testes;
- scripts;
- documentação;
- configuração;
- infraestrutura.

Evite criar diretórios sem função real.

---

## Prepare a documentação

Crie ou organize documentos para:

- arquitetura;
- regras do Game Engine;
- segurança;
- internacionalização;
- deploy;
- decisões arquiteturais;
- convenções de desenvolvimento.

Não duplique desnecessariamente o conteúdo do `PROJECT_CORE.md`.

Use links entre os documentos quando apropriado.

---

## Prepare os arquivos fundamentais do repositório

Inclua, conforme necessário:

- `.gitignore`
- `.dockerignore`
- `.env.example`
- Dockerfiles
- `docker-compose.yml`
- configuração de editor quando útil
- configurações de lint/format
- scripts iniciais
- arquivos de configuração necessários

O `.env.example` deve conter somente nomes de variáveis e valores fictícios seguros.

Nunca adicionar credenciais reais.

---

## Docker

Prepare uma base simples e reproduzível para desenvolvimento.

Considere os componentes previstos no core.

Não crie uma infraestrutura exageradamente complexa.

Se Docker não for necessário para algum componente nesta fase, documente isso em vez de forçar uma solução.

---

## Git

O repositório já está inicializado.

Não altere histórico.

Não execute force push.

Não faça commit automaticamente, salvo se houver instrução explícita posterior.

Ao terminar, deixe as mudanças prontas para revisão.

---

## GitHub

Prepare apenas o que fizer sentido nesta fase, como:

- `.github/`
- templates;
- workflow de validação básica;
- CI inicial.

Evite automações complexas antes de existir código suficiente para justificá-las.

---

## Segurança

A fundação deve seguir princípios de segurança desde o início.

Considere:

- secrets;
- variáveis de ambiente;
- dependências;
- CORS;
- autenticação futura;
- separação frontend/backend;
- autoridade do servidor.

Não implemente autenticação complexa apenas por antecipação se ainda não for necessária.

Documente decisões.

---

## Internacionalização

A arquitetura deve prever desde o início:

- Português do Brasil;
- Inglês;
- Chinês simplificado.

Evite qualquer estrutura que obrigue refatoração grande depois.

---

## Game Engine

Crie espaço próprio para o Game Engine.

Ele deve poder ser:

- testado separadamente;
- utilizado pelo backend;
- independente da camada visual.

Não implemente ainda toda a lógica do jogo.

---

## Trabalho paralelo

A estrutura deve permitir que agentes diferentes trabalhem em:

- frontend;
- backend;
- Game Engine;
- animações;
- realtime;
- banco;
- testes;

com mínimo risco de conflito.

---

## Não faça nesta etapa

Não implemente:

- interface completa;
- animações finais;
- sistema completo de torneio;
- mapa-múndi final;
- catálogo visual completo;
- pagamentos;
- sistema completo de patrocínio;
- funcionalidades não solicitadas.

Esta etapa é de fundação.

---

## Ao terminar

Entregue um relatório contendo:

### 1. Estrutura criada

Mostre a árvore principal do projeto.

### 2. Arquivos criados

Explique brevemente os mais importantes.

### 3. Decisões técnicas

Liste decisões arquiteturais tomadas.

### 4. Decisões adiadas

Liste assuntos que conscientemente não foram definidos ainda.

### 5. Riscos

Identifique riscos encontrados.

### 6. Segurança

Liste pontos que precisam de revisão pelo agente de Segurança.

### 7. Próximos agentes

Recomende quais agentes devem trabalhar em seguida e em qual ordem.

### 8. Git

Mostre o resultado final de `git status`.

Não faça commit automaticamente.