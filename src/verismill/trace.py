"""Append-only, hash-chained events for persisted experiments."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

GENESIS = "sha256:" + "0" * 64

LOOP_IDS = frozenset({"L0", "L1", "L2", "L3", "SYS"})
ROLES = frozenset({
    "orchestrator", "spec_author", "builder", "judge", "auditor",
    "researcher", "fixer",
    "development_judge", "blind_judge",
})
EVENT_TYPES = frozenset({
    # Experiment lifecycle. Scores and acceptance are verdict payloads on an
    # evaluation event, never a second competing event/state machine.
    "experiment", "transition", "research", "rubric", "candidate",
    "agent_run", "development", "tell", "repair_asserted", "repair_resolved",
    "evaluation", "report", "rerun",
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

    """

    def __init__(self, path: str | Path, clock=time.time):
        self.path = Path(path)
        self.clock = clock
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
