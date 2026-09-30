# Architecture

## Scope

This document records the foundation selected for V0.1. Product behavior remains governed by [PROJECT_CORE.md](../PROJECT_CORE.md).

## Repository boundaries

| Area | Location | Responsibility |
| --- | --- | --- |
| Frontend | `apps/frontend` | Next.js/React presentation, responsive views and localized UI. |
| Backend | `apps/backend` | FastAPI HTTP boundary, access rules and official orchestration. |
| Game Engine | `packages/game-engine` | Pure, independently tested tournament rules. |
| Shared contracts | `packages/shared-types` | Stable cross-boundary data contracts only. |
| Database | `database/migrations` | Reviewable schema history. |
| Realtime | `realtime` | Protocol documentation and eventual transport integration. |

## Authority flow

`Frontend intent → Backend validation → Game Engine transition → Persistence → Realtime event → Frontend rendering`

The backend remains authoritative for official random selections, strategy locking, lives, results, bracket progression and champion. The frontend can simulate training only in an isolated state that never changes official state.

## Local services

`docker-compose.yml` starts the frontend, backend and PostgreSQL. Realtime is not provisioned yet because the product permits either Supabase Realtime or WebSockets and choosing one now would be premature. See [deploy.md](deploy.md).

## Parallel ownership

Agents should work in their primary area to avoid collisions. Changes crossing the backend/Game Engine, database/realtime, or security boundaries require explicit review and a documented decision when behavior changes.

The detailed ownership matrix and sequencing are maintained in [agent-ownership.md](agent-ownership.md) and [v0.1-plan.md](v0.1-plan.md).
