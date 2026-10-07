"""Server-owned clock for public presentation; competitive results stay in Engine."""

from __future__ import annotations

from datetime import datetime, timedelta


OPENING_DELAY_SECONDS = 3
# Allow durable publication and concurrent authorization checks for 40 viewers
# before the shared visual clock starts. This lead is not divided by speed.
DELIVERY_BUFFER_MS = 2500
PER_EVENT_DELIVERY_BUDGET_MS = 750
BETWEEN_ROUNDS_MS = 0


def event_duration_ms(event_type: str, movement: float, countdown: float) -> float:
    movement = movement if movement in (0.5, 1, 2, 4, 8) else 1
    countdown = countdown if countdown in (0.5, 1, 2, 4, 8) else 1
    return {
        "player_waiting": 900 / movement,
        "second_chance_selected": 1400 / movement,
        "match_started": 900 / movement,
        "round_resolved": 1950 / countdown + 350 / movement,
        "heart_lost": 200 / movement,
        "player_eliminated": 700 / movement,
        "match_completed": 750 / movement,
        "player_advanced": 900 / movement,
        "bye": 900 / movement,
        # Full local champion cue (~7s), then silver and bronze reveal.
        "champion": 7500 + 900 + 900,
    }.get(event_type, 0)


def schedule_events(
    events: list[tuple[str, dict[str, object]]],
    *,
    now: datetime,
    movement: float,
    countdown: float,
    minimum_delay_seconds: float = 1,
) -> tuple[list[tuple[str, dict[str, object]]], datetime]:
    """Stamp one transition with absolute UTC times shared by all spectators."""
    now_ms = int(now.timestamp() * 1000)
    at_ms = now_ms + DELIVERY_BUFFER_MS
    scheduled = []
    for index, (event_type, payload) in enumerate(events):
        # The durable outbox publishes one event at a time. At 8x, visual
        # phases can be shorter than one database/realtime round-trip; reserve
        # enough lead time for each later event instead of stamping it in the
        # past before it can even be delivered.
        at_ms = max(at_ms, now_ms + DELIVERY_BUFFER_MS + index * PER_EVENT_DELIVERY_BUDGET_MS)
        scheduled.append((event_type, {**payload, "presentationAtMs": at_ms}))
        at_ms += round(event_duration_ms(event_type, movement, countdown))
    next_at = now + timedelta(milliseconds=max(
        minimum_delay_seconds * 1000, at_ms - now_ms + BETWEEN_ROUNDS_MS,
    ))
    return scheduled, next_at
