# ADR-001: Simple monorepo with separated application boundaries

**Status:** Accepted for bootstrap

## Decision

Use one Git repository with `apps/frontend`, `apps/backend`, `packages/game-engine`, `packages/shared-types`, `database`, and `realtime` as explicit boundaries.

## Rationale

It keeps V0.1 coordination and local development simple while making Game Engine independence and backend authority visible. It also limits merge conflicts by giving specialist agents clear locations.

## Consequences

The frontend uses npm workspaces. Python dependencies remain scoped to the backend for now. A future extraction is possible only after contracts stabilize; do not introduce cross-boundary dependencies casually.
