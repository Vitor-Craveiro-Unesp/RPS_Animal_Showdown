"""Local source-layout test bootstrap; production installs the Engine package."""

from __future__ import annotations

import sys
import os
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPOSITORY_ROOT / "apps" / "backend"
ENGINE_ROOT = REPOSITORY_ROOT / "packages" / "game-engine"
for source_root in (str(BACKEND_ROOT), str(ENGINE_ROOT)):
    if source_root not in sys.path:
        sys.path.insert(0, source_root)

# Importing the ASGI entry point is part of these isolated unit tests.  Give
# that unused module-level entry point inert, non-routable durable settings;
# every test app itself injects InMemoryTournamentStore explicitly.
os.environ.setdefault("DATABASE_URL", "postgresql://unit-test.invalid/rps_unit")
os.environ.setdefault("REALTIME_TICKET_SIGNING_KEY", "unit-test-signing-key-not-a-secret")
