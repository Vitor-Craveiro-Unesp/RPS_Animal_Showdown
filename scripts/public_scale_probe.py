"""Manual production-scale probe. Never persists bearer tokens or changes game rules.

Run only for an explicitly requested live test. The probe honors Retry-After and
prints sanitized observations for a human-written test report.
"""

from __future__ import annotations

import json
import argparse
import statistics
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import httpx
from websockets.sync.client import connect


API = "http://127.0.0.1:8200/v1"
WS = "ws://127.0.0.1:8200/v1/realtime"
ORIGIN = "http://127.0.0.1:3200"
ANIMALS = [
    "eagle", "panda", "kangaroo", "otter", "monkey", "rooster", "bull",
    "tiger", "elephant", "bear", "octopus", "llama", "white_tailed_deer",
    "camel", "goat", "lizard", "angora_cat", "zebra", "macaw", "crane",
]
STRATEGY_KEYS = [
    "initial", "lost_to_rock", "lost_to_paper", "lost_to_scissors",
    "won_against_rock", "won_against_paper", "won_against_scissors",
    "tied_with_rock", "tied_with_paper", "tied_with_scissors",
]
STRATEGY = {key: {"rock": 33, "paper": 33, "scissors": 34} for key in STRATEGY_KEYS}


def emit(kind: str, **fields: object) -> None:
    print(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "kind": kind, **fields}, ensure_ascii=False), flush=True)


class Probe:
    def __init__(self) -> None:
        self.http = httpx.Client(timeout=35, headers={"Origin": ORIGIN})
        self.latencies: dict[str, list[float]] = {}
        self.errors: list[dict[str, object]] = []
        self.rate_limits: list[dict[str, object]] = []
        self.clock_offset_ms = 0.0
        # Like browser fetch(), ticket HTTP must not pause WebSocket reception.
        self.renewal_workers = ThreadPoolExecutor(max_workers=8)

    def request(self, method: str, path: str, category: str, *, token: str | None = None,
                data: dict[str, object] | None = None, idempotency_key: str | None = None) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        for attempt in range(4):
            started = time.monotonic()
            try:
                response = self.http.request(method, API + path, json=data, headers=headers)
            except httpx.HTTPError as error:
                self.errors.append({"category": category, "exception": type(error).__name__})
                if attempt == 3:
                    raise
                emit("transport_retry", category=category, exception=type(error).__name__)
                time.sleep(5)
                continue
            self.latencies.setdefault(category, []).append(round((time.monotonic() - started) * 1000))
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                try:
                    wait = min(610, max(1, int(retry_after))) + 2
                except ValueError:
                    wait = 62
                self.rate_limits.append({"category": category, "retry_after_s": retry_after})
                emit("rate_limit_wait", category=category, retry_after_s=retry_after)
                if attempt == 3:
                    break
                time.sleep(wait)
                continue
            if response.status_code >= 400:
                self.errors.append({"category": category, "status": response.status_code,
                                    "detail": response.text[:160]})
            return response
        return response

    def required(self, method: str, path: str, category: str, *, expected: int,
                 token: str | None = None, data: dict[str, object] | None = None,
                 idempotency_key: str | None = None) -> dict[str, object]:
        response = self.request(method, path, category, token=token, data=data,
                                idempotency_key=idempotency_key)
        if response.status_code != expected:
            raise RuntimeError(f"{category}: HTTP {response.status_code}: {response.text[:180]}")
        return response.json() if response.content else {}

    def summary(self) -> dict[str, object]:
        return {
            "latency_ms": {name: {"count": len(values), "median": round(statistics.median(values)),
                                  "max": max(values)} for name, values in self.latencies.items()},
            "errors": self.errors,
            "rate_limits": self.rate_limits,
        }


class Viewer(threading.Thread):
    def __init__(self, probe: Probe, code: str, tournament_id: str, token: str, name: str,
                 stop: threading.Event) -> None:
        super().__init__(name=name, daemon=True)
        self.probe, self.code, self.tournament_id = probe, code, tournament_id
        self.token, self.stop = token, stop
        self.events: dict[int, dict[str, object]] = {}
        self.event_types: Counter[str] = Counter()
        self.reconnects = 0
        self.renewals = 0
        self.exceptions: list[str] = []
        self.ready = threading.Event()

    def run(self) -> None:
        last_sequence = 0
        while not self.stop.is_set():
            try:
                ticket_response = self.probe.required("POST", f"/tournaments/{self.code}/realtime/ticket",
                                                      "ticket", expected=200, token=self.token)
                ticket = ticket_response["ticket"]
                with connect(WS, origin=ORIGIN, open_timeout=25, close_timeout=3) as socket:
                    socket.send(json.dumps({"type": "authenticate", "ticket": ticket,
                                            "channel": f"tournament/{self.tournament_id}/official-events"}))
                    confirmation = json.loads(socket.recv(timeout=20))
                    if confirmation.get("type") != "subscribed":
                        raise RuntimeError(f"subscription: {confirmation.get('type')}")
                    socket.send(json.dumps({"type": "resume", "afterSequence": last_sequence}))
                    self.ready.set()
                    # Exercise authenticated renewal early in the test, then
                    # keep the normal one-minute margin before expiry.
                    renew_at = time.monotonic() + 35
                    renewal_request = None
                    while not self.stop.is_set():
                        if time.monotonic() >= renew_at:
                            renewal_request = self.probe.renewal_workers.submit(
                                self.probe.required, "POST", f"/tournaments/{self.code}/realtime/ticket",
                                "ticket", expected=200, token=self.token,
                            )
                            renew_at = float('inf')
                        if renewal_request is not None and renewal_request.done():
                            socket.send(json.dumps({"type": "renew", "ticket": renewal_request.result()["ticket"]}))
                            renewal_request = None
                        try:
                            frame = json.loads(socket.recv(timeout=0.25))
                        except TimeoutError:
                            continue
                        if frame.get("type") == "renewed":
                            self.renewals += 1
                            renew_at = time.monotonic() + max(30, frame["expiresInMs"] / 1000 - 60)
                            continue
                        if frame.get("type") == "replay-reset":
                            self.exceptions.append("replay-reset")
                        if frame.get("type") != "official-event":
                            continue
                        sequence = int(frame["sequence"])
                        self.event_types[str(frame.get("eventType"))] += 1
                        self.events.setdefault(sequence, {
                            "received_at_ms": round(time.time() * 1000),
                            "presentation_at_ms": frame.get("payload", {}).get("presentationAtMs"),
                            "event_type": frame.get("eventType"),
                        })
                        last_sequence = max(last_sequence, sequence)
            except Exception as error:
                self.exceptions.append(type(error).__name__ + ": " + str(error)[:100])
                self.reconnects += 1
                if not self.stop.is_set():
                    time.sleep(3)

    def summary(self) -> dict[str, object]:
        sequences = sorted(self.events)
        gaps = [number for number in range(sequences[0], sequences[-1] + 1) if number not in self.events] if sequences else []
        lateness = [round(item["received_at_ms"] - self.probe.clock_offset_ms - item["presentation_at_ms"])
                    for item in self.events.values() if isinstance(item["presentation_at_ms"], int)]
        latest = sorted(({
            "sequence": sequence, "event_type": item["event_type"],
            "late_ms": round(item["received_at_ms"] - self.probe.clock_offset_ms - item["presentation_at_ms"]),
        } for sequence, item in self.events.items() if isinstance(item["presentation_at_ms"], int)),
            key=lambda item: item["late_ms"], reverse=True)[:3]
        return {"count": len(sequences), "first_sequence": sequences[0] if sequences else None,
                "last_sequence": sequences[-1] if sequences else None, "gaps": gaps[:20],
                "reconnects": self.reconnects, "renewals": self.renewals, "exceptions": self.exceptions[:10],
                "late_delivery_count": sum(value > 0 for value in lateness),
                "latest_deliveries": latest,
                "delivery_minus_schedule_ms": {"min": min(lateness), "median": round(statistics.median(lateness)),
                                               "max": max(lateness)} if lateness else None,
                "event_types": dict(self.event_types)}


def run_stage(probe: Probe, size: int, movement: str, countdown: str) -> None:
    created = probe.required("POST", "/tournaments", "create", expected=201,
                             data={"capacity": size, "hearts_required": 1,
                                   "sound_effects_enabled": True, "background_music_enabled": True,
                                   "movement_speed": movement, "countdown_speed": countdown})
    code = str(created["tournament_code"])
    room_id = str(created["tournament_id"])
    organizer_token = str(created["organizer_access_token"])
    emit("stage_created", size=size, code=code, movement=movement, countdown=countdown)
    def join(index):
        joined = probe.required("POST", "/tournaments/join", "join", expected=201,
                                data={"tournament_code": code,
                                      "display_name": f"QA-{size}-{index + 1:02d}",
                                      "animal_id": ANIMALS[index % len(ANIMALS)]})
        return {"token": str(joined["player_access_token"]), "id": str(joined["player"]["player_id"])}
    with ThreadPoolExecutor(max_workers=8) as executor:
        players = list(executor.map(join, range(size)))
    emit("joined", size=size, count=len(players))
    def ready(player):
        token = player["token"]
        probe.required("PUT", f"/tournaments/{code}/players/me/strategy", "strategy", expected=204,
                       token=token, data=STRATEGY)
        probe.required("POST", f"/tournaments/{code}/players/me/ready", "ready", expected=204,
                       token=token, data={})
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(ready, players))
    emit("ready", size=size, count=len(players))
    participants = probe.required("GET", f"/tournaments/{code}/admin/participants", "participants",
                                  expected=200, token=organizer_token)
    participant_rows = participants.get("participants", [])
    emit("lobby_checked", size=size, code=code, participant_count=len(participant_rows),
         ready_count=sum(bool(row.get("ready")) for row in participant_rows),
         statuses=dict(Counter(str(row.get("membership_status")) for row in participant_rows)),
         capacity_field=participants.get("capacity"))
    stop = threading.Event()
    viewers = [Viewer(probe, code, room_id, credential, label, stop) for label, credential in
               [("organizer", organizer_token)] + [(f"player_{i+1}", p["token"]) for i, p in enumerate(players)]]
    for viewer in viewers:
        viewer.start()
    for viewer in viewers:
        if not viewer.ready.wait(timeout=30):
            emit("viewer_not_ready", size=size, viewer=viewer.name, errors=viewer.exceptions[:3])
    sent_at = round(time.time() * 1000)
    probe.required("POST", f"/tournaments/{code}/admin/start", "start", expected=200,
                   token=organizer_token, data={}, idempotency_key=str(uuid4()))
    emit("started", size=size, code=code, sent_at_ms=sent_at)
    deadline = time.monotonic() + 900
    final_state: dict[str, object] = {}
    completion_seen = False
    while time.monotonic() < deadline:
        time.sleep(10)
        request_sent_ms = time.time() * 1000
        response = probe.request("GET", f"/tournaments/{code}/official-state", "official_state",
                                 token=players[0]["token"])
        request_received_ms = time.time() * 1000
        if response.status_code != 200:
            continue
        final_state = response.json()
        if "server_received_at_ms" in final_state and "server_time_ms" in final_state:
            probe.clock_offset_ms = ((request_sent_ms - final_state["server_received_at_ms"])
                                     + (request_received_ms - final_state["server_time_ms"])) / 2
        presentation = final_state.get("presentation_state") or {}
        status = presentation.get("status") if isinstance(presentation, dict) else None
        emit("progress", size=size, status=final_state.get("status"),
             min_events=min(len(v.events) for v in viewers), max_events=max(len(v.events) for v in viewers),
             renewals=sum(v.renewals for v in viewers), reconnects=sum(v.reconnects for v in viewers))
        if final_state.get("status") == "completed" and not presentation and all(v.event_types["champion"] for v in viewers):
            completion_seen = True
            time.sleep(5)
            break
    stop.set()
    for viewer in viewers:
        viewer.join(timeout=5)
    combined = set.intersection(*(set(viewer.events) for viewer in viewers))
    spreads = [max(viewer.events[sequence]["received_at_ms"] for viewer in viewers)
               - min(viewer.events[sequence]["received_at_ms"] for viewer in viewers)
               for sequence in sorted(combined)]
    worst_sequence = sorted(combined)[spreads.index(max(spreads))] if spreads else None
    emit("stage_result", size=size, code=code, completion_seen=completion_seen,
         official_status=final_state.get("status"),
         presentation_status=(final_state.get("presentation_state") or {}).get("status"),
         champion_id=final_state.get("champion_id"),
         viewer_count=len(viewers), worst_spread_sequence=worst_sequence,
         worst_spread_event=viewers[0].events.get(worst_sequence, {}).get("event_type"),
         common_events=len(combined),
         viewer_spread_ms={"median": round(statistics.median(spreads)), "max": max(spreads)} if spreads else None,
         viewers={viewer.name: viewer.summary() for viewer in viewers},
         requests=probe.summary())
    assert completion_seen, "Tournament did not finish in observation window"
    assert len(participant_rows) == size and participants.get("capacity") == size
    assert all(len(v.events) == len(combined) and not v.summary()["gaps"] for v in viewers), "Viewer event loss"
    assert all(v.renewals for v in viewers), "Renewal was not exercised"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api', default=API)
    parser.add_argument('--ws', default=WS)
    parser.add_argument('--origin', default=ORIGIN)
    parser.add_argument('--sizes', type=int, nargs='+', default=[25, 40])
    parser.add_argument('--speed', choices=['0.5', '1', '2', '4', '8'], default='8')
    parser.add_argument('--allow-public', action='store_true')
    args = parser.parse_args()
    if not args.allow_public and any(urlparse(url).hostname not in ('127.0.0.1', 'localhost') for url in (args.api, args.ws)):
        parser.error('Public testing requires explicit --allow-public')
    API, WS, ORIGIN = args.api.rstrip('/'), args.ws, args.origin
    probe = Probe()
    try:
        for size in args.sizes:
            run_stage(probe, size, args.speed, args.speed)
    except Exception as error:
        emit("probe_stopped", exception=type(error).__name__, detail=str(error)[:300], requests=probe.summary())
        raise
    finally:
        probe.renewal_workers.shutdown(wait=False, cancel_futures=True)
        probe.http.close()
