"""Tests for the climb machinery (forge/climb/)."""

from __future__ import annotations

import json

import pytest

from verismill import trace
from verismill.climb import atlas, judges, orchestrator


# -- atlas lifecycle -----------------------------------------------------------


def test_corroboration_requires_distinct_trials(tmp_path):
    a = atlas.Atlas(tmp_path / "atlas.json", corroboration_k=3)
    rec = lambda trial: a.record(tell_class="formats.pdf", quote="Acrobat 9.0",
                                 path="x.pdf", rationale="r", trial_id=trial, round_no=1)
    t = rec("t1")
    assert t["state"] == "reported"
    rec("t1")  # same trial — NOT new evidence
    assert t["state"] == "reported"
    rec("t2")
    assert t["state"] == "reported"
    rec("t3")
    assert t["state"] == "corroborated"
    assert a.promote_candidates() == [t]


def test_promotion_flow(tmp_path):
    a = atlas.Atlas(tmp_path / "atlas.json", corroboration_k=2)
    for i in (1, 2):
        a.record(tell_class="c", quote="q", path="p", rationale="r",
                 trial_id=f"t{i}", round_no=1)
    a.mark_clause_candidate("c", "q")
    assert a.tells[0]["state"] == "clause_candidate"
    a.mark_promoted("c", "q", clause_id="formats.file-type-mix")
    assert a.tells[0]["state"] == "promoted"
    assert a.active() == []


def test_stale_then_regression_probe_then_archive(tmp_path):
    a = atlas.Atlas(tmp_path / "atlas.json", corroboration_k=1, stale_after_rounds=5)
    a.record(tell_class="c", quote="q", path="p", rationale="r",
             trial_id="t1", round_no=1)
    assert a.tells[0]["state"] == "corroborated"
    assert a.tick(4) == []                    # 4-1 < 5, still fresh
    changed = a.tick(6)                        # 6-1 >= 5, stale
    assert changed == [a.tells[0]]
    assert a.tells[0]["state"] == "stale"
    with pytest.raises(Exception):
        a.archive("c", "q")                    # must probe before archiving
    a.mark_regression_probe("c", "q")
    a.archive("c", "q")
    assert a.tells[0]["state"] == "archived"


def test_atlas_roundtrip(tmp_path):
    a = atlas.Atlas(tmp_path / "atlas.json", corroboration_k=2)
    a.record(tell_class="c", quote="q", path="p", rationale="r",
             trial_id="t1", round_no=1)
    a.save()
    b = atlas.Atlas(tmp_path / "atlas.json", corroboration_k=2)
    assert b.tells == a.tells


# -- judge trials -----------------------------------------------------------------


@pytest.fixture
def trees(tmp_path):
    real = tmp_path / "real"
    synth = tmp_path / "synth"
    real.mkdir()
    synth.mkdir()
    for i in range(15):
        (real / f"doc_{i:02d}.eml").write_text(f"Message-ID: <{i}@x>\nDate: Mon\nFrom: a\nSubject: s\n\nbody {i}\n")
        (synth / f"file_{i:02d}.md").write_text(f"generated doc {i}")
    return real, synth


def test_assemble_trial_blind_layout(tmp_path, trees):
    real, synth = trees
    key = judges.assemble_trial(tmp_path / "trials", real_src=real, synth_src=synth,
                                real_src_b=None, trial_seed=11, n_files=6)
    tdir = tmp_path / "trials" / key["trial_id"]
    assert (tdir / "left").is_dir() and (tdir / "right").is_dir()
    assert len(list((tdir / "left").iterdir())) == 6
    assert len(list((tdir / "right").iterdir())) == 6
    assert (tdir / "brief.md").exists()
    # answer key records the truth, brief must not leak it
    assert key["answer"] in ("left", "right")
    brief = (tdir / "brief.md").read_text()
    assert key["answer"] not in brief.lower().replace("left", "").replace("right", "")


def test_control_trial_has_no_answer(tmp_path, trees):
    real, _ = trees
    key = judges.assemble_trial(tmp_path / "trials", real_src=real, synth_src=None,
                                real_src_b=real, trial_seed=5, n_files=4)
    assert key["mode"] == "real_vs_real"
    assert key["answer"] is None


def test_parse_verdict(tmp_path):
    v = judges.parse_verdict('some prose {"pick": "left", "confidence": 0.8, "tells": [{"path": "a", "quote": "q", "rationale": "r"}]} tail')
    assert v["pick"] == "left"
    with pytest.raises(ValueError):
        judges.parse_verdict('{"pick": "neither"}')
    with pytest.raises(ValueError):
        judges.parse_verdict("no json here")


def test_score_batch(trees, tmp_path):
    real, synth = trees
    keys = [judges.assemble_trial(tmp_path / "t", real_src=real, synth_src=synth,
                                  real_src_b=None, trial_seed=s, n_files=4)
            for s in (1, 2, 3)]
    verdicts = {k["trial_id"]: {"pick": k["synthetic_side"]} for k in keys[:2]}
    verdicts[keys[2]["trial_id"]] = {"pick": "left" if keys[2]["synthetic_side"] == "right" else "right"}
    scores = judges.score_batch(keys, verdicts)
    assert scores["synth_vs_real_accuracy"] == pytest.approx(2 / 3)
    assert scores["trials_scored"] == 3


# -- orchestrator --------------------------------------------------------------------


def _orch(tmp_path):
    bus = trace.TraceBus(tmp_path / "bus" / "events.jsonl", clock=lambda: 1_700_000_000.0)
    return orchestrator.Orchestrator(tmp_path / "scores", bus), bus


def test_accept_only_on_improvement(tmp_path):
    orch, bus = _orch(tmp_path)
    keys = [{"trial_id": f"t{i}", "mode": "synth_vs_real", "synthetic_side": "left"}
            for i in range(4)]
    def verdicts(n_correct):
        v = {f"t{i}": {"pick": "left"} for i in range(n_correct)}
        v.update({f"t{i}": {"pick": "right"} for i in range(n_correct, 4)})
        return v
    r1 = orch.on_judge_batch(keys=keys, verdicts=verdicts(4), spec_version="v1")
    assert not r1["accepted"]                       # accuracy 1.0, no improvement over 1.0
    r2 = orch.on_judge_batch(keys=keys, verdicts=verdicts(3), spec_version="v2")
    assert r2["accepted"]                           # 0.75 < 1.0 - margin
    r3 = orch.on_judge_batch(keys=keys, verdicts=verdicts(3), spec_version="v3")
    assert not r3["accepted"]                       # no improvement over new best
    r4 = orch.on_judge_batch(keys=keys, verdicts=verdicts(2), spec_version="v4")
    assert r4["accepted"]                           # 0.5 < 0.75 - margin
    events = trace.TraceBus.read(bus.path)
    types = [e["event_type"] for e in events]
    assert types.count("accept") == 2 and types.count("reject") == 2
    assert orch.state["best_accuracy"] == 0.5
    assert trace.TraceBus.verify(bus.path)


def test_stall_detection_after_five_rejects(tmp_path):
    orch, bus = _orch(tmp_path)
    keys = [{"trial_id": "t", "mode": "synth_vs_real", "synthetic_side": "left"}]
    for _ in range(5):
        orch.on_judge_batch(keys=keys, verdicts={"t": {"pick": "left"}}, spec_version="v")
    events = trace.TraceBus.read(bus.path)
    assert any(e["event_type"] == "stall" for e in events)


def test_checkpoint_written_on_accept(tmp_path):
    orch, _ = _orch(tmp_path)
    keys = [{"trial_id": "t", "mode": "synth_vs_real", "synthetic_side": "left"}]
    orch.on_judge_batch(keys=keys, verdicts={"t": {"pick": "right"}}, spec_version="v9")
    cps = list((tmp_path / "scores" / "checkpoints").iterdir())
    assert len(cps) == 1
    assert (cps[0] / "spec_version.txt").read_text().strip() == "v9"
