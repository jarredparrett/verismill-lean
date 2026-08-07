"""Tests for the experiment event bus."""

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
    event = bus.emit("L1", "blind_judge", "evaluation",
                     spec_version="v7",
                     inputs={"spec": "sha256:abc"},
                     verdicts={"accuracy": 0.52})
    events = trace.TraceBus.read(bus_path)
    assert len(events) == 1
    e = events[0]
    assert e == event
    assert e["loop_id"] == "L1"
    assert e["role"] == "blind_judge"
    assert e["event_type"] == "evaluation"
    assert e["spec_version"] == "v7"
    assert e["input_hashes"] == {"spec": "sha256:abc"}
    assert e["verdicts"] == {"accuracy": 0.52}
    assert e["event_id"].startswith("sha256:")
    assert e["prev_hash"] == trace.GENESIS


def test_chain_verifies_and_detects_tampering(bus_path, fixed_clock):
    bus = trace.TraceBus(bus_path, clock=fixed_clock)
    for i in range(3):
        bus.emit("L0", "builder", "candidate", verdicts={"round": i})
    assert trace.TraceBus.verify(bus_path)
    lines = bus_path.read_text().splitlines()
    event = json.loads(lines[1])
    event["verdicts"]["round"] = 99  # tamper with history
    lines[1] = json.dumps(event, sort_keys=True)
    bus_path.write_text("\n".join(lines) + "\n")
    assert not trace.TraceBus.verify(bus_path)


def test_reopen_continues_chain(bus_path, fixed_clock):
    trace.TraceBus(bus_path, clock=fixed_clock).emit("L0", "builder", "candidate")
    bus2 = trace.TraceBus(bus_path, clock=fixed_clock)
    bus2.emit("L1", "development_judge", "development")
    events = trace.TraceBus.read(bus_path)
    assert events[1]["prev_hash"] == events[0]["event_hash"]
    assert trace.TraceBus.verify(bus_path)


def test_stale_writer_is_rejected_before_it_can_fork_the_chain(
        bus_path, fixed_clock):
    """trace.single-writer: a handle with an old tail cannot append a fork."""
    first = trace.TraceBus(bus_path, clock=fixed_clock)
    stale = trace.TraceBus(bus_path, clock=fixed_clock)
    first.emit("L0", "builder", "candidate")
    with pytest.raises(RuntimeError, match="stale TraceBus handle"):
        stale.emit("SYS", "auditor", "report")
    assert len(trace.TraceBus.read(bus_path)) == 1
    assert trace.TraceBus.verify(bus_path)


def test_deterministic_under_fixed_clock(tmp_path, fixed_clock):
    def make(path):
        bus = trace.TraceBus(path, clock=fixed_clock)
        bus.emit("L2", "spec_author", "rubric", spec_version="v1")
        bus.emit("SYS", "orchestrator", "transition")
        return path.read_bytes()

    assert make(tmp_path / "a.jsonl") == make(tmp_path / "b.jsonl")


def test_validation_rejects_unknown_vocabulary(bus_path, fixed_clock):
    bus = trace.TraceBus(bus_path, clock=fixed_clock)
    with pytest.raises(ValueError, match="loop_id"):
        bus.emit("L9", "builder", "candidate")
    with pytest.raises(ValueError, match="role"):
        bus.emit("L0", "sneaky", "candidate")
    with pytest.raises(ValueError, match="event_type"):
        bus.emit("L0", "builder", "yolo")


def test_read_rejects_malformed(bus_path):
    bus_path.parent.mkdir(parents=True)
    bus_path.write_text(json.dumps({"event_type": "accept"}) + "\n")
    with pytest.raises(ValueError, match="missing keys"):
        trace.TraceBus.read(bus_path)
