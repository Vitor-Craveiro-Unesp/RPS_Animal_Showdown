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
    assert starts[2] - starts[1] == 2300
    assert next_at.timestamp() * 1000 == starts[2] + 200
    assert not any("presentationAtMs" in payload for _, payload in events)


def test_timing_respects_both_speed_controls_and_opening_delay():
    assert OPENING_DELAY_SECONDS == 3
    assert event_duration_ms("round_resolved", 2, 0.5) == 1950 / 0.5 + 350 / 2
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


def test_delivery_margin_covers_measured_40_viewer_delay_at_fastest_speed():
    now = datetime(2026, 10, 6, tzinfo=UTC)
    scheduled, _ = schedule_events([("round_resolved", {})], now=now, movement=8, countdown=8)
    # Prior 1.2s lead was exceeded by 644ms in the real 41-connection probe.
    latest_measured_arrival_ms = int(now.timestamp() * 1000) + 1200 + 644
    assert scheduled[0][1]["presentationAtMs"] - latest_measured_arrival_ms >= 500


def test_batch_lead_covers_publication_backlog_during_mass_ticket_renewal():
    now = datetime(2026, 10, 6, tzinfo=UTC)
    events = [(kind, {}) for kind in ("round_resolved", "heart_lost", "player_eliminated")]
    scheduled, _ = schedule_events(events, now=now, movement=8, countdown=8)
    # The third event was 516ms late with 2.5s base + 300ms per event.
    measured_arrival_ms = int(now.timestamp() * 1000) + 2500 + 2 * 300 + 516
    assert scheduled[2][1]["presentationAtMs"] - measured_arrival_ms >= 300


def test_normal_round_targets_five_second_cycle_and_three_second_reveal_gap():
    now = datetime(2026, 10, 6, tzinfo=UTC)
    events = [("round_resolved", {}), ("heart_lost", {})]
    first, next_at = schedule_events(events, now=now, movement=1, countdown=1)
    second, _ = schedule_events(events, now=next_at, movement=1, countdown=1)
    cycle_ms = second[0][1]["presentationAtMs"] - first[0][1]["presentationAtMs"]
    assert cycle_ms == 5000
    assert cycle_ms - 1950 == 3050  # The existing countdown is 3 * 650ms.
    assert DELIVERY_BUFFER_MS == 2500
    assert PER_EVENT_DELIVERY_BUDGET_MS == 750
