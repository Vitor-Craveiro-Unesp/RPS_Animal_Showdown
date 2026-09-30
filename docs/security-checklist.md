# Segurança — modelo de ameaças e gate de release

Este documento operacional complementa [security.md](security.md) e não altera as regras de produto em [PROJECT_CORE.md](../PROJECT_CORE.md).

O backlog com dono, dependências e critérios verificáveis está em [tasks/security-blockers-v0.1.md](../tasks/security-blockers-v0.1.md).

## Modelo de ameaças inicial

| Elemento | Definição |
| --- | --- |
| Ativos | Integridade de resultados, estratégias, autoridade do organizador, dados do torneio, banco, segredos e disponibilidade. |
| Atores | Participante, organizador, espectador, atacante anônimo e usuário malicioso de outro torneio. |
| Fronteira principal | Todo dado que chega por HTTP, WebSocket, URL, armazenamento do navegador ou realtime é uma intenção não confiável. |

| Ameaça prioritária | Controle obrigatório para V0.1 |
| --- | --- |
| Resultado, vidas, BYE ou chaveamento forjados | O backend executa o Engine e persiste a transição oficial; o cliente não envia estados finais. |
| Estratégia alterada após início | Validar servidor-side e aplicar bloqueio transacional no início do torneio. |
| Controle indevido de torneio | Autorização real por sala para toda ação do organizador; URL e interface não são autorização. |
| Enumeração/brute force de código | Código opaco, não sequencial, mensagens neutras e rate limiting em entrada/criação. |
| Acesso cruzado entre torneios | Escopo de sala em cada consulta/evento e autorização antes de leitura ou mutação. |
| Realtime forjado ou repetido | Apenas servidor publica eventos oficiais; autenticar assinatura, validar sequência e tornar comandos idempotentes. |
| Corrida ao iniciar/processar partida | Transações, versão/lock de estado e uma única transição oficial por partida. |
| XSS por nomes, patrocínio ou traduções | Renderização textual padrão, validação de URLs e nunca HTML arbitrário. |
| DoS por empates ilimitados | Processar uma rodada por unidade de trabalho, com limites de payload, rate limit e observabilidade. |
| Vazamento de segredo | Segredos fora do Git e imagens; redigir logs e restringir variáveis `NEXT_PUBLIC_*` a dados públicos. |

## Regras obrigatórias por área

- **Frontend:** envie intenções, nunca resultados; não use HTML perigoso; trate qualquer texto/URL remoto como não confiável; não exponha segredo em `NEXT_PUBLIC_*`.
- **Backend:** valide esquema, estado, identidade e escopo de sala em toda rota; use queries parametrizadas/ORM; aplique CORS por allowlist e rate limits.
- **Game Engine:** aceite apenas dados de domínio validados; injete RNG nos testes e use RNG servidor-side em produção; nunca execute loop síncrono ilimitado de empates.
- **Banco + Realtime:** use menor privilégio, consultas com escopo de torneio, transações/idempotência; clientes não publicam eventos competitivos oficiais.
- **DevOps:** não copie `.env`, não registre segredos, mantenha imagens/dependências atualizadas e separe credenciais por ambiente.

## Pendências bloqueadoras de deploy público

Os itens abaixo são **ALTOS** até serem implementados e revisados:

1. Autenticação/autorização real de organizador e isolamento por torneio.
2. Códigos de torneio opacos, rate limiting e proteção contra abuso.
3. Validação server-side completa e integração do Engine como única autoridade de estado oficial.
4. Transações/idempotência para início, estratégia e progressão de partidas.
5. Autorização do realtime, publicação exclusiva do servidor e defesa contra replay/duplicação.
6. CORS de produção restritivo, postura de CSRF conforme o método de autenticação e logs redigidos.
7. Gestão de segredos, permissões mínimas de banco, varredura de dependências e configuração separada de produção.

## Checklist antes da primeira publicação

- [ ] Engine e integração backend passam testes de vitória, derrota, empate, vidas, eliminação, BYE, estratégias condicionais, chaveamento e empates longos.
- [ ] Nenhum endpoint aceita resultado, coração, avanço ou vencedor enviados pelo cliente.
- [ ] Organizador autenticado/autorizado; participantes e espectadores isolados por torneio.
- [ ] Códigos não previsíveis e endpoints críticos com rate limiting.
- [ ] CORS restrito ao(s) domínio(s) esperado(s); cookies, se usados, usam `Secure`, `HttpOnly`, `SameSite` e CSRF quando aplicável.
- [ ] Realtime autenticado, com autorização de canal, ordem/idempotência e publicação oficial somente pelo servidor.
- [ ] Banco com usuário de aplicação de menor privilégio, migrations auditáveis e backup testado.
- [ ] Segredos somente no provedor de ambiente; `.env`, imagens, logs e CI revisados.
- [ ] `npm audit` e `pip-audit` avaliados; vulnerabilidades altas/críticas corrigidas ou formalmente bloqueadas.
- [ ] Entradas e URLs externas validadas; uploads continuam desativados ou têm validação de tipo, tamanho e armazenamento seguro.
- [ ] Smoke tests de autenticação, autorização, fluxo de torneio e erros em produção concluídos.

## Marcos de nova revisão

Segurança deve revisar novamente: após autenticação/autorização; após seleção de realtime; após integrar Engine e backend; antes do primeiro deploy público; antes de uploads de logo; e antes de pagamentos futuros.
