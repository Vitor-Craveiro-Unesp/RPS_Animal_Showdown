# Rodada 5 — relatório consolidado

## Decisão

**BLOQUEADO.** SEC-004 foi concluído localmente e não há achado ALTO novo. SEC-007 continua aberto: este checkout não possui remote Git configurado, a conta local do GitHub CLI tem token inválido e as mudanças permanecem não commitadas. Portanto não existe como obter uma execução remota segura sem ação do proprietário.

## SEC-004 — rate limiting compartilhado

- Tecnologia: PostgreSQL já previsto pelo produto; nenhum Redis/serviço adicional foi introduzido.
- Storage: tabela `shared_rate_limit_buckets`, criada pela migration `0004_rate_limits`.
- Semântica: janela fixa, `INSERT … ON CONFLICT` atômico, TTL por `expires_at`, uma linha por operação e hash SHA-256 do sujeito.
- Chaves: IP do peer ASGI (`ip:`); ações com bearer também cobram `credential:<SHA-256>`. Cabeçalhos `X-Forwarded-For` e `Forwarded` são ignorados para não aceitar spoofing.
- Cobertura: criação, join/código inválido, autenticação de participante, administração inválida, estratégia/treino, ticket realtime, handshake e reconnect.
- Falha: **fail-closed** — HTTP devolve 503 com retry curto; WebSocket fecha 1013 antes de `accept`. Não há fallback em memória no caminho durável.
- Prova PostgreSQL real: duas instâncias lógicas partilharam o mesmo orçamento abaixo/no limite/acima e voltaram a aceitar após expiração: **1 passed**.

## QA e segurança

- Revisão de Segurança: SQL parametrizado, hashes persistidos, contador atômico, IP não spoofável pela app e falha fechada. SEC-004 pode ser concluído localmente.
- Regressão PostgreSQL integrada: **100 passed**, 30 avisos de depreciação/cache não bloqueantes.
- Backend sem banco opt-in: **19 passed, 7 skipped**.
- `git diff --check`: passou.

## SEC-007 — CI remota

O workflow continua corretamente configurado com actions por SHA, `contents: read`, PostgreSQL 16, migrations, testes, lint/build e auditorias. Não houve execução remota: `git remote -v` não retorna remote e `gh auth status` informa token inválido. Nenhum commit ou push foi criado automaticamente.

Para o proprietário, após revisar as mudanças:

```powershell
git add .
git commit -m "feat: durable tournament foundation and shared rate limiting"
git remote add origin <URL_DO_REPOSITORIO>
gh auth login -h github.com
git push -u origin main
gh run list --limit 1
```

Não executar `git add .` sem revisar o conjunto amplo de arquivos não versionados.

## Gate e navegador

Frontend funcional **não está liberado** enquanto SEC-007 estiver aberto. O frontend local segue HTTP 200 e visualmente vazio; o health do backend segue HTTP 200. Não houve deploy, commit ou alteração visual nesta rodada.
