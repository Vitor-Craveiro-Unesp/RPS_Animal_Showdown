# Checklist de integrações externas

Nenhuma conta, chave, domínio ou integração externa foi configurada pelo Bootstrap. O desenvolvimento não deve ser bloqueado por elas.

| Dependência | Classificação | Uso e condição |
| --- | --- | --- |
| Node.js, Python e Docker | Necessária agora | Ambiente local e CI; não requer conta externa. |
| PostgreSQL local | Necessária agora | Serviço Compose para desenvolvimento e testes de integração. |
| GitHub Actions | Necessária durante os primeiros 10 dias | CI básico ao enviar o repositório ao GitHub; exige permissões do repositório, não segredos. |
| Realtime | Já escolhido | WebSocket nativo do FastAPI, com PostgreSQL para ledger/replay e outbox. Supabase Realtime não é utilizado nesta fase. |
| Vercel | Apenas no deploy | Hospedagem sugerida para o frontend; exige conta/projeto do proprietário. |
| Supabase ou PostgreSQL gerenciado | Apenas no deploy | Banco e, se escolhido, realtime; exige projeto, acesso restrito e segredos fora do Git. |
| Domínio, DNS e TLS | Apenas no deploy | Dependem do proprietário e da decisão de hospedagem. |
| Observabilidade/erros | Apenas no deploy | Selecionar depois de definir ambiente de produção; não registrar dados sensíveis. |
| WhatsApp comercial | Necessária durante os primeiros 10 dias para a página de patrocínio | Depende do número/link comercial confirmado pelo proprietário; manter como configuração, não hard-code. |
| QR Code | Opcional/futura | Pode ser gerado localmente quando o fluxo de acesso por código estiver pronto; não exige serviço externo. |
| Áudio, logos e ativos visuais | Opcional/futura | Só integrar após licenças e ativos aprovados; não bloqueia V0.1 jogável. |

## Decisões pendentes do proprietário

Confirmar o provedor de produção, proprietário das contas, domínio, número comercial de WhatsApp e, caso Supabase seja adotado, a organização/projeto que receberá as credenciais. Nenhum desses dados deve ser colocado em arquivos versionados.
