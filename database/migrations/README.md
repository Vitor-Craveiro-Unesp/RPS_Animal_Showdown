# Migrations de banco

**Ferramenta escolhida: Alembic + PostgreSQL.** Alembic foi escolhido porque o backend é Python/FastAPI, produz revisões ordenadas e auditáveis, pode executar SQL PostgreSQL explícito e não introduz um segundo runtime na V0.1. O schema não deve ser alterado manualmente como único registro.

## Uso local

Instale as dependências do serviço e do executor, defina `DATABASE_URL` **na
forma SQLAlchemy** e execute desta pasta:

```powershell
python -m pip install -r ../../apps/backend/requirements.txt -r requirements.txt
$env:DATABASE_URL = "postgresql+psycopg://rps_app:local-development-only@localhost:5432/rps_animal_showdown"
python -m alembic upgrade head
```

Há duas formas de URL que não podem ser misturadas:

| Consumidor | Variável/formato exigido | Exemplo |
| --- | --- | --- |
| Alembic / SQLAlchemy | `DATABASE_URL`, `postgresql+psycopg://…` | `postgresql+psycopg://rps_app:local-development-only@localhost:5432/rps_animal_showdown` |
| `psycopg.connect` (realtime e testes) | `RPS_TEST_DATABASE_URL`, `postgresql://…` | `postgresql://rps_app:local-development-only@localhost:5432/rps_animal_showdown_test` |

`realtime.dsn` converte explicitamente entre as duas formas quando uma fronteira
precisa chamar as duas bibliotecas. O teste de integração recebe somente o DSN
libpq e deriva o `DATABASE_URL` exclusivo do subprocesso Alembic.

Para revisar SQL sem conectar: `alembic upgrade head --sql`. Em produção, um executor de deploy com credencial de migration separada deve aplicar `alembic upgrade head` antes da aplicação. A imagem de desenvolvimento não executa migrations automaticamente.

## Regras e invariantes SEC-005

- Gere revisões novas em `versions/`; nunca edite revisão já aplicada.
- IDs são gerados pelo servidor. Código de acesso não é autorização.
- O Engine define significado de estado; migrations persistem apenas o envelope transacional.
- A revisão inicial cria agregado com `state_version`/`next_event_sequence`, chave idempotente escopada, uma transição por versão e uma sequência de evento única por torneio. As FKs de comando, evento e outbox incluem `tournament_id`, bloqueando referências cruzadas entre salas.
- A revisão `0002_authoritative_snapshots_and_access` acrescenta capability persistida com hash/revogação, tickets curtos, estratégias, snapshots congelados de jogador/estado, partidas e rodadas. UUID é a identidade interna; código público não é chave relacional.
- O Backend deve usar lock/transação descritos em [`realtime/README.md`](../../realtime/README.md). Constraints não substituem autorização nem validação do Engine.

## Teste de integração opcional

`database/migrations/tests/test_postgres_constraints.py` somente conecta quando
`RPS_TEST_DATABASE_URL` aponta para uma base **isolada de teste**, no formato
`postgresql://`. Ele executa `alembic upgrade head` e prova no PostgreSQL que:

- command e ticket de outro torneio são recusados pelas FKs compostas;
- replay só devolve eventos do UUID de torneio autorizado, em ordem;
- dois workers concorrentes reivindicam eventos diferentes com `SKIP LOCKED`.

Exemplo de execução:

```powershell
$env:RPS_TEST_DATABASE_URL = "postgresql://rps_test:local-development-only@localhost:5432/rps_animal_showdown_test"
python -m pytest -q database/migrations/tests/test_postgres_constraints.py
```
