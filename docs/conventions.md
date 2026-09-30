# Development conventions

## Source ownership

- Keep UI work in `apps/frontend`.
- Keep HTTP, authorization and orchestration work in `apps/backend`.
- Keep official rules and state transitions in `packages/game-engine`.
- Add only stable, shared contracts to `packages/shared-types`.
- Record schema changes in `database/migrations`.

## Quality

- TypeScript uses strict mode; Python is formatted with four spaces.
- Add tests with behavior, particularly engine tests independent of interface code.
- Do not add frontend literals for interface text; use the i18n structure described in [i18n.md](i18n.md).
- Keep commits small and descriptive; this bootstrap intentionally creates no commit.

## Configuration

Use `.env` locally, never commit it, and update `.env.example` only with safe placeholders and documented variable names.
