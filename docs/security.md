# Security baseline

## Non-negotiable authority

The backend is authoritative for official strategy state, random choices, hearts, results, bracket and champion. Treat every client request as an untrusted intent.

## Bootstrap controls

- `.env` files are ignored; `.env.example` uses local, intentionally non-production values only.
- Compose configuration receives environment values rather than hard-coded operational credentials.
- The frontend and backend are separate processes and containers.
- Application containers run without root privileges; PostgreSQL is internal to the Compose network by default.
- During bootstrap the backend exposed only liveness. The first development round added development-only intent endpoints and an in-memory organizer capability; these are not deploy-ready and remain tracked in `SEC-001`, `SEC-002` and `SEC-004`.
- Uploads remain out of scope; public deployment is blocked until the controls listed below are implemented and reviewed.

## Required review before product routes

- identity model and organizer authorization;
- opaque, rate-limited tournament access codes;
- CORS allowlist and browser-origin policy;
- request schema validation, authorization per room and abuse controls;
- CSRF posture if cookie authentication is selected;
- websocket/Supabase authorization and event visibility;
- secrets management, logging redaction and dependency scanning;
- database least privilege and migration permissions.

The threat model, delivery gate and agent rules are maintained in [security-checklist.md](security-checklist.md).
