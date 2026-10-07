from datetime import UTC, datetime

from app.presentation_timing import (
    DELIVERY_BUFFER_MS, OPENING_DELAY_SECONDS, PER_EVENT_DELIVERY_BUDGET_MS,
    event_duration_ms, schedule_events,
)


def test_server_stamps_one_monotonic_timeline_for_all_viewers():
    now = datetime(2026, 10, 6, tzinfo=UTC)
    events = [("match_started", {}), ("round_resolved", {}), ("heart_lost", {})]
    scheduled, next_at = schedule_events(events, now=now, movement=1, countdown=1)
    starts = [payload["presentationAtMs"] for _, payload in scheduled]
    assert starts[1] - starts[0] == 900
    assert starts[2] - starts[1] == 3100
    assert next_at.timestamp() * 1000 > starts[2] + 650
    assert not any("presentationAtMs" in payload for _, payload in events)


def test_timing_respects_both_speed_controls_and_opening_delay():
    assert OPENING_DELAY_SECONDS == 3
    assert event_duration_ms("round_resolved", 2, 0.5) == 1950 / 0.5 + 1150 / 2
    assert event_duration_ms("final_started", 1, 1) == 0
    assert event_duration_ms("champion", 1, 1) == 9300
    now = datetime(2026, 10, 6, tzinfo=UTC)
    _, next_at = schedule_events([("round_resolved", {})], now=now, movement=8, countdown=8, minimum_delay_seconds=4)
    assert (next_at - now).total_seconds() == 4


def test_every_speed_pair_preserves_event_order_and_delivery_lead():
    now = datetime(2026, 10, 6, tzinfo=UTC)
    events = [(kind, {}) for kind in (
        "match_started", "round_resolved", "heart_lost", "player_eliminated",
        "match_completed", "player_advanced", "podium_decided", "champion",
    )]
    for movement in (0.5, 1, 2, 4, 8):
        for countdown in (0.5, 1, 2, 4, 8):
            scheduled, next_at = schedule_events(events, now=now, movement=movement, countdown=countdown)
            now_ms = int(now.timestamp() * 1000)
            for index, (kind, payload) in enumerate(scheduled):
                at_ms = payload["presentationAtMs"]
                assert at_ms >= now_ms + DELIVERY_BUFFER_MS + index * PER_EVENT_DELIVERY_BUDGET_MS
                if index:
                    prior_kind, prior_payload = scheduled[index - 1]
                    assert at_ms >= prior_payload["presentationAtMs"] + round(
                        event_duration_ms(prior_kind, movement, countdown)
                    )
            final_kind, final_payload = scheduled[-1]
            assert next_at.timestamp() * 1000 >= (
                final_payload["presentationAtMs"] + event_duration_ms(final_kind, movement, countdown)
            )
