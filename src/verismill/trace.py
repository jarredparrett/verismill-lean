"""Observability substrate for the realism foundry.

One event envelope for every loop in the climb — L0 builder gates, L1 climb
rounds, L2 meta revisions, L3 task-integrity probes. Every loop emits the same
shape onto a single hash-chained JSONL bus (same pattern as runtime/eventlog);
rollups and detectors read the bus, never the producers.

Declared semantics — this module is the contract, mirroring the liveness lesson
from the defect-mining task itself:

- A heartbeat event fresher than ``max_age_s`` means the climb is ALIVE, even
  when no accept/reject has landed recently. A quiet bus is the working state.
- A stall is declared only by ``detect_stall`` reading the bus — a producer
  never times itself.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import time
from pathlib import Path

GENESIS = "sha256:" + "0" * 64

LOOP_IDS = frozenset({"L0", "L1", "L2", "L3", "SYS"})
ROLES = frozenset({
    "orchestrator", "spec_author", "builder", "judge", "auditor",
    "profiler", "toolsmith", "probe", "system",
})
EVENT_TYPES = frozenset({
    # L1 climb loop
    "proposal", "build", "gate", "judge_trial", "judge_batch",
    "tell", "promotion", "accept", "reject",
    # SYS liveness + dataset assembly + session capture + bundle export
    "heartbeat", "status", "stall", "dataset", "session", "package",
    # L3 task integrity
    "probe",
})

_ENVELOPE_KEYS = {
    "event_id", "ts", "loop_id", "role", "event_type", "spec_version",
    "input_hashes", "output_refs", "verdicts", "prev_hash", "event_hash",
}


def _sha(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode()).hexdigest()


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class TraceBus:
    """Append-only hash-chained event bus. The clock is injectable so tests
    (and any byte-sensitive consumers) can pin timestamps.

    session_id, when given, stamps every event this bus emits with the agent
    session that produced it — the join key that lets the dataset attach the
    session's reasoning (see sessions.py) to the outcomes recorded here.
    Events written before this field existed simply lack it; validation
    treats it as optional."""

    def __init__(self, path: str | Path, clock=time.time,
                 session_id: str | None = None):
        self.path = Path(path)
        self.clock = clock
        self.session_id = session_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prev = GENESIS
        if self.path.exists():
            with self.path.open() as f:
                for line in f:
                    if line.strip():
                        self._prev = json.loads(line)["event_hash"]

    def emit(
        self,
        loop_id: str,
        role: str,
        event_type: str,
        *,
        spec_version: str | None = None,
        inputs: dict | None = None,
        outputs: dict | None = None,
        verdicts: dict | None = None,
    ) -> dict:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.clock()))
        payload = {
            "ts": ts,
            "loop_id": loop_id,
            "role": role,
            "event_type": event_type,
            "spec_version": spec_version,
            "input_hashes": inputs or {},
            "output_refs": outputs or {},
            "verdicts": verdicts or {},
            "prev_hash": self._prev,
        }
        if self.session_id is not None:
            payload["session_id"] = self.session_id
        event = dict(payload)
        event["event_id"] = _sha(_canonical(payload))
        event["event_hash"] = _sha(_canonical(payload) + event["event_id"])
        _validate(event)
        with self.path.open("a") as f:
            f.write(json.dumps(event, sort_keys=True) + "\n")
        self._prev = event["event_hash"]
        return event

    # -- reading ----------------------------------------------------------

    @staticmethod
    def read(path: str | Path) -> list[dict]:
        events = []
        with Path(path).open() as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)
                    _validate(event)
                    events.append(event)
        return events

    @staticmethod
    def verify(path: str | Path) -> bool:
        """Re-hash the chain; any tampering with history breaks it."""
        prev = GENESIS
        try:
            with Path(path).open() as f:
                for line in f:
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if event["prev_hash"] != prev:
                        return False
                    payload = {k: event[k] for k in event
                               if k not in ("event_id", "event_hash")}
                    if event["event_id"] != _sha(_canonical(payload)):
                        return False
                    if event["event_hash"] != _sha(_canonical(payload) + event["event_id"]):
                        return False
                    prev = event["event_hash"]
        except (OSError, KeyError, json.JSONDecodeError):
            return False
        return True


def _validate(event: dict) -> None:
    missing = _ENVELOPE_KEYS - set(event)
    if missing:
        raise ValueError(f"event missing keys: {sorted(missing)}")
    if event["loop_id"] not in LOOP_IDS:
        raise ValueError(f"unknown loop_id: {event['loop_id']!r}")
    if event["role"] not in ROLES:
        raise ValueError(f"unknown role: {event['role']!r}")
    if event["event_type"] not in EVENT_TYPES:
        raise ValueError(f"unknown event_type: {event['event_type']!r}")
    for key in ("input_hashes", "output_refs", "verdicts"):
        if not isinstance(event[key], dict):
            raise ValueError(f"{key} must be a dict")


# -- rollups and detectors ---------------------------------------------------


def rollup(events: list[dict]) -> dict:
    """Per-loop event tallies plus the climb's accept/reject posture."""
    by_loop: dict[str, dict[str, int]] = {}
    accepts = rejects = 0
    for e in events:
        by_loop.setdefault(e["loop_id"], {})
        by_loop[e["loop_id"]][e["event_type"]] = (
            by_loop[e["loop_id"]].get(e["event_type"], 0) + 1
        )
        if e["event_type"] == "accept":
            accepts += 1
        elif e["event_type"] == "reject":
            rejects += 1
    return {
        "events": len(events),
        "by_loop": by_loop,
        "accepts": accepts,
        "rejects": rejects,
        "consecutive_rejects": consecutive_rejects(events),
        "last_event": events[-1] if events else None,
    }


def consecutive_rejects(events: list[dict]) -> int:
    """Rejections since the most recent accept (0 if the last decision was an
    accept or no decision has landed yet)."""
    n = 0
    for e in reversed(events):
        if e["event_type"] == "accept":
            break
        if e["event_type"] == "reject":
            n += 1
    return n


def is_alive(events: list[dict], now: float, max_age_s: float) -> bool:
    """Declared liveness: a heartbeat fresher than max_age_s means alive,
    regardless of how quiet the decision events have been."""
    heartbeats = [e for e in events if e["event_type"] == "heartbeat"]
    if not heartbeats:
        return False
    last_ts = _parse_ts(heartbeats[-1]["ts"])
    return (now - last_ts) <= max_age_s


def detect_stall(events: list[dict], *, max_consecutive_rejects: int) -> dict | None:
    """The stall detector — the ONLY thing allowed to declare a stall.

    Fires when the climb has burned `max_consecutive_rejects` rounds without an
    accept. Returns a stall-event verdicts payload (for the orchestrator to
    emit), or None while the climb is healthy.
    """
    n = consecutive_rejects(events)
    if n < max_consecutive_rejects:
        return None
    return {
        "stalled": True,
        "consecutive_rejects": n,
        "threshold": max_consecutive_rejects,
        "since_accept": _last_of_type(events, "accept"),
    }


def _last_of_type(events: list[dict], event_type: str) -> dict | None:
    for e in reversed(events):
        if e["event_type"] == event_type:
            return e
    return None


def _parse_ts(ts: str) -> float:
    return calendar.timegm(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
