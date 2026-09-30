# ADR-003 — WebSocket nativo para realtime na V0.1

- **Status:** Aceito para implementação local; revisão de Segurança obrigatória antes de deploy público.
- **Data:** 2026-09-29
- **Decisores:** Banco + Realtime (proposta); Backend e Segurança (revisão).

## Contexto e decisão

O produto exige atualização de painel/chaveamento em tempo real, mas resultado oficial pertence ao backend/Engine. A arquitetura admitia Supabase Realtime ou WebSockets e exigia uma única escolha. Foi escolhido WebSocket hospedado pelo backend FastAPI, com PostgreSQL para ledger ordenado e outbox. O servidor é o único publisher e cada socket obtém acesso apenas ao canal do torneio concedido.

O protocolo completo está em [`realtime/README.md`](../../realtime/README.md); Alembic é a ferramenta de migration em [`database/migrations/README.md`](../../database/migrations/README.md).

## Consequências

- Menos contas, políticas e caminhos de confiança na V0.1.
- Backend deve implementar handshake, tickets, rate limit, allowlist de Origin, publisher outbox e observabilidade antes da exposição pública.
- Entrega é at-least-once; clientes deduplicam UUID/sequência.
- Escala horizontal depende de lease/`SKIP LOCKED`, não de afinidade.
- Supabase pode ser reavaliado somente preservando autorização por torneio, publisher exclusivo do servidor e semântica de reconexão.

## Decisão pendente do proprietário

Antes do deploy público, confirmar provedor/conta de produção para FastAPI e PostgreSQL, domínios permitidos e retenção de eventos. Não é necessária conta Supabase para esta decisão V0.1.
