"""Tests for the forge observability substrate (forge/trace.py)."""

from __future__ import annotations

import json

import pytest

from verismill import trace


@pytest.fixture
def bus_path(tmp_path):
    return tmp_path / "bus" / "events.jsonl"


@pytest.fixture
def fixed_clock():
    t = [1_700_000_000.0]

    def clock():
        return t[0]

    clock.tick = lambda s=60: t.__setitem__(0, t[0] + s)
    return clock


def test_emit_roundtrip_envelope(bus_path, fixed_clock):
    bus = trace.TraceBus(bus_path, clock=fixed_clock)
    event = bus.emit("L1", "orchestrator", "accept",
                     spec_version="v7",
                     inputs={"spec": "sha256:abc"},
                     verdicts={"accuracy": 0.52})
    events = trace.TraceBus.read(bus_path)
    assert len(events) == 1
    e = events[0]
    assert e == event
    assert e["loop_id"] == "L1"
    assert e["role"] == "orchestrator"
    assert e["event_type"] == "accept"
    assert e["spec_version"] == "v7"
    assert e["input_hashes"] == {"spec": "sha256:abc"}
    assert e["verdicts"] == {"accuracy": 0.52}
    assert e["event_id"].startswith("sha256:")
    assert e["prev_hash"] == trace.GENESIS


def test_chain_verifies_and_detects_tampering(bus_path, fixed_clock):
    bus = trace.TraceBus(bus_path, clock=fixed_clock)
    for i in range(3):
        bus.emit("L0", "builder", "gate", verdicts={"round": i})
    assert trace.TraceBus.verify(bus_path)
    lines = bus_path.read_text().splitlines()
    event = json.loads(lines[1])
    event["verdicts"]["round"] = 99  # tamper with history
    lines[1] = json.dumps(event, sort_keys=True)
    bus_path.write_text("\n".join(lines) + "\n")
    assert not trace.TraceBus.verify(bus_path)


def test_reopen_continues_chain(bus_path, fixed_clock):
    trace.TraceBus(bus_path, clock=fixed_clock).emit("L0", "builder", "build")
    bus2 = trace.TraceBus(bus_path, clock=fixed_clock)
    bus2.emit("L0", "builder", "gate")
    events = trace.TraceBus.read(bus_path)
    assert events[1]["prev_hash"] == events[0]["event_hash"]
    assert trace.TraceBus.verify(bus_path)


def test_deterministic_under_fixed_clock(tmp_path, fixed_clock):
    def make(path):
        bus = trace.TraceBus(path, clock=fixed_clock)
        bus.emit("L1", "spec_author", "proposal", spec_version="v1")
        bus.emit("SYS", "system", "heartbeat")
        return path.read_bytes()

    assert make(tmp_path / "a.jsonl") == make(tmp_path / "b.jsonl")


def test_validation_rejects_unknown_vocabulary(bus_path, fixed_clock):
    bus = trace.TraceBus(bus_path, clock=fixed_clock)
    with pytest.raises(ValueError, match="loop_id"):
        bus.emit("L9", "builder", "build")
    with pytest.raises(ValueError, match="role"):
        bus.emit("L0", "sneaky", "build")
    with pytest.raises(ValueError, match="event_type"):
        bus.emit("L0", "builder", "yolo")


def test_read_rejects_malformed(bus_path):
    bus_path.parent.mkdir(parents=True)
    bus_path.write_text(json.dumps({"event_type": "accept"}) + "\n")
    with pytest.raises(ValueError, match="missing keys"):
        trace.TraceBus.read(bus_path)


def test_rollup_counts(bus_path, fixed_clock):
    bus = trace.TraceBus(bus_path, clock=fixed_clock)
    bus.emit("L0", "builder", "gate")
    bus.emit("L1", "spec_author", "proposal")
    bus.emit("L1", "orchestrator", "reject")
    bus.emit("L1", "spec_author", "proposal")
    bus.emit("L1", "orchestrator", "accept")
    r = trace.rollup(trace.TraceBus.read(bus_path))
    assert r["events"] == 5
    assert r["by_loop"]["L0"] == {"gate": 1}
    assert r["by_loop"]["L1"] == {"proposal": 2, "reject": 1, "accept": 1}
    assert r["accepts"] == 1 and r["rejects"] == 1
    assert r["consecutive_rejects"] == 0
    assert r["last_event"]["event_type"] == "accept"


def test_is_alive_requires_fresh_heartbeat(bus_path, fixed_clock):
    bus = trace.TraceBus(bus_path, clock=fixed_clock)
    now = fixed_clock()
    assert not trace.is_alive([], now, max_age_s=300)
    bus.emit("SYS", "system", "heartbeat")
    events = trace.TraceBus.read(bus_path)
    assert trace.is_alive(events, now + 60, max_age_s=300)
    assert not trace.is_alive(events, now + 301, max_age_s=300)


def test_stall_detector(bus_path, fixed_clock):
    bus = trace.TraceBus(bus_path, clock=fixed_clock)
    emit = lambda: (bus.emit("L1", "orchestrator", "reject"),
                    bus.emit("L1", "spec_author", "proposal"))
    for _ in range(2):
        emit()
    events = trace.TraceBus.read(bus_path)
    assert trace.detect_stall(events, max_consecutive_rejects=3) is None
    bus.emit("L1", "orchestrator", "reject")
    events = trace.TraceBus.read(bus_path)
    stall = trace.detect_stall(events, max_consecutive_rejects=3)
    assert stall is not None
    assert stall["stalled"] is True
    assert stall["consecutive_rejects"] == 3
    assert stall["since_accept"] is None
    # an accept resets the counter
    bus.emit("L1", "orchestrator", "accept")
    bus.emit("L1", "orchestrator", "reject")
    events = trace.TraceBus.read(bus_path)
    assert trace.detect_stall(events, max_consecutive_rejects=3) is None
    stall = trace.detect_stall(events, max_consecutive_rejects=1)
    assert stall["since_accept"]["event_type"] == "accept"
