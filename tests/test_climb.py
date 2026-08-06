"""Tests for the climb machinery (forge/climb/)."""

from __future__ import annotations

import json

import pytest

from verismill.climb import atlas, judges


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


# -- judges.protocol v0.2.0 (absolute review, min+veto) ----------------------


def _abs_verdict(**over):
    """A well-formed absolute verdict; override any field."""
    v = {
        "authenticity": "synthetic", "confidence": 0.8,
        "disqualifiers": {"executed_consistently": "pass",
                          "signature_is_a_hand": "pass",
                          "no_impossible_identifier": "pass"},
        "dimension_scores": {d: 80 for d in judges.DIMENSIONS},
        "tells": [],
    }
    v.update(over)
    return v


def test_aggregate_is_min_not_mean():
    """FM1: a strong dimension cannot buy back a weak one. Overall is the MIN
    over dimensions, not their average."""
    dims = dict.fromkeys(judges.DIMENSIONS, 93)
    dims["forensic_authenticity"] = 40
    agg = judges.aggregate_absolute(_abs_verdict(dimension_scores=dims))
    assert agg["overall_score"] == 40           # not the ~85 mean
    assert agg["coherence_profile"] > 40         # mean retained, informational


def test_disqualifier_vetoes_the_score():
    """FM1: a failed disqualifier caps the score regardless of the dimensions —
    the gate an unsigned lease scoring 60 was missing."""
    dims = dict.fromkeys(judges.DIMENSIONS, 90)
    v = _abs_verdict(dimension_scores=dims,
                     disqualifiers={"executed_consistently": "fail",
                                    "signature_is_a_hand": "fail",
                                    "no_impossible_identifier": "pass"})
    agg = judges.aggregate_absolute(v)
    assert agg["overall_score"] == 25            # lowest failed cap wins
    assert set(agg["failed_disqualifiers"]) == {"executed_consistently",
                                                "signature_is_a_hand"}


def test_parse_absolute_verdict_requires_full_answers():
    """FM1/FM3: every disqualifier answered, every dimension scored."""
    good = judges.parse_absolute_verdict(json.dumps(_abs_verdict()))
    assert good["authenticity"] == "synthetic"
    # missing a disqualifier answer
    bad = _abs_verdict()
    del bad["disqualifiers"]["signature_is_a_hand"]
    with pytest.raises(ValueError, match="signature_is_a_hand"):
        judges.parse_absolute_verdict(json.dumps(bad))
    # a dimension out of range
    bad2 = _abs_verdict()
    bad2["dimension_scores"]["forensic_authenticity"] = 150
    with pytest.raises(ValueError, match="0..100"):
        judges.parse_absolute_verdict(json.dumps(bad2))


def test_parse_absolute_verdict_accepts_region_tell():
    """FM4: an image-domain tell carries page+bbox instead of a text quote."""
    v = _abs_verdict(tells=[{"path": "lease.pdf",
                             "quote_or_region": {"page": 4,
                                                 "bbox_norm": [0.1, 0.2, 0.4, 0.3]},
                             "rationale": "signature does not spell the name"}])
    parsed = judges.parse_absolute_verdict(json.dumps(v))
    assert parsed["tells"][0]["quote_or_region"]["page"] == 4


def test_lens_assignment_covers_forensic():
    """FM5: k=3 covers all lenses; any missing lens is incomplete measurement."""
    assert judges.coverage_ok(judges.assign_lenses(3))
    assert set(judges.assign_lenses(3)) == set(judges.LENSES)
    assert not judges.coverage_ok(["arithmetic_and_dates", "procedural_and_citations"])
    assert not judges.coverage_ok(["forensic_and_visual"] * 3)


def test_absolute_brief_is_two_pass_and_omits_overall():
    """FM3: the glance pass and the disqualifiers come before the deep read;
    the judge never supplies an overall (the scorer owns it)."""
    brief = judges.build_absolute_brief(class_name="lease_nj",
                                        persona="NJ landlord-tenant attorney",
                                        lens="forensic_and_visual")
    assert brief.index("PASS 1 — GLANCE") < brief.index("PASS 2 — DEEP READ")
    for did in judges.DISQUALIFIERS:
        assert did in brief
    assert "no overall score" in brief


def test_score_absolute_batch_reports_distribution():
    """The batch reports the harshest and mean per-judge overall and the
    disqualifier fail counts — never one laundered number."""
    verdicts = {
        "J1": _abs_verdict(dimension_scores=dict.fromkeys(judges.DIMENSIONS, 88)),
        "J2": _abs_verdict(disqualifiers={"executed_consistently": "fail",
                                          "signature_is_a_hand": "pass",
                                          "no_impossible_identifier": "pass"}),
        "J3": _abs_verdict(),
    }
    out = judges.score_absolute_batch(verdicts, judges.assign_lenses(3))
    assert out["overall_min"] == 25              # J2's veto
    assert out["overall_min"] <= out["overall_mean"]
    assert out["disqualifier_fail_counts"]["executed_consistently"] == 1
    assert out["discrimination_accuracy"] == 1.0
    assert out["coverage_ok"] is True


# -- judges.protocol v0.3.0 (rubric-driven absolute review) -----------------


def _rubric_v3():
    return {
        "version": "archival.1",
        "scorer": "absolute-v0.3",
        "dimensions": [
            {"id": "capture", "description": "Looks like a captured object",
             "anchors": {"0": "flat", "100": "source-calibrated"}},
            {"id": "working_hand", "description": "Marks read as a working hand",
             "anchors": {"0": "font", "100": "credible hand"}},
            {"id": "institutional_use", "description": "Record owns its fields",
             "anchors": {"0": "prop", "100": "ordinary record"}},
            {"id": "reproducibility", "description": "Evidence is stable",
             "anchors": {"0": "unstable", "100": "reproducible"}},
        ],
        "acceptance": {"rules": [
            {"metric": "overall_min", "operator": ">=", "value": 80},
        ]},
    }


def test_rubric_absolute_brief_uses_only_frozen_dimensions():
    """v0.3 prompts the declared artifact rubric, not lease execution criteria."""
    rubric = _rubric_v3()
    groups = judges.assign_rubric_lenses(rubric, 3)
    brief = judges.build_rubric_absolute_brief(
        rubric=rubric, persona="archival records conservator",
        primary_dimensions=groups[0],
    )
    assert set(d for group in groups for d in group) == \
        set(judges.rubric_dimension_ids(rubric))
    for dimension in judges.rubric_dimension_ids(rubric):
        assert dimension in brief
    assert "lead-paint" not in brief
    assert "required disclosures" not in brief
    assert "signature_is_a_hand" not in brief


def test_rubric_absolute_parser_requires_exact_dimension_set():
    rubric = _rubric_v3()
    ids = judges.rubric_dimension_ids(rubric)
    verdict = {
        "authenticity": "genuine", "confidence": 0.8,
        "dimension_scores": {dimension: 88 for dimension in ids},
        "tells": [],
    }
    assert judges.parse_rubric_absolute_verdict(
        json.dumps(verdict), ids
    )["dimension_scores"] == verdict["dimension_scores"]
    verdict["dimension_scores"]["foreign_legal_dimension"] = 90
    with pytest.raises(ValueError, match="match frozen rubric"):
        judges.parse_rubric_absolute_verdict(json.dumps(verdict), ids)


def test_rubric_absolute_batch_uses_declared_min_and_coverage():
    rubric = _rubric_v3()
    ids = judges.rubric_dimension_ids(rubric)
    verdicts = {
        "J1": {"authenticity": "genuine",
               "dimension_scores": {dimension: 90 for dimension in ids}},
        "J2": {"authenticity": "synthetic",
               "dimension_scores": {**dict.fromkeys(ids, 86), "working_hand": 62}},
        "J3": {"authenticity": "genuine",
               "dimension_scores": {dimension: 82 for dimension in ids}},
    }
    lenses = judges.assign_rubric_lenses(rubric, 3)
    result = judges.score_rubric_absolute_batch(verdicts, ids, lenses)
    assert result["overall_min"] == 62
    assert result["dimension_means"]["working_hand"] < \
        result["dimension_means"]["capture"]
    assert result["coverage_ok"] is True


# -- atlas: region tells + fix-verification (FM4, FM2) -----------------------


def test_region_tell_dedupes_on_page(tmp_path):
    """FM4: an image tell has no quote; it keys on (class, path, page)."""
    a = atlas.Atlas(tmp_path / "atlas.json", corroboration_k=3)
    for j in ("J1", "J2", "J3"):
        a.record_region(tell_class="forensic.signature", path="lease.pdf",
                        page=4, bbox_norm=[0.1, 0.2, 0.4, 0.3],
                        rationale="scrawl doesn't spell the name",
                        trial_id=j, round_no=2)
    assert len(a.tells) == 1                      # one tell, three sightings
    assert a.tells[0]["state"] == "corroborated"
    assert a.tells[0]["locus"] == "region"


def test_harvest_asserts_repair_only_nonfixer_resolves(tmp_path):
    """FM2: a harvest may only assert a repair; resolving requires a later
    round. Resolving something never asserted is refused."""
    a = atlas.Atlas(tmp_path / "atlas.json", corroboration_k=1)
    a.record(tell_class="forensic.execution_state", quote="Initials: ____",
             path="lease.pdf", rationale="blank on a signed lease",
             trial_id="J1", round_no=1)
    a.assert_repair(tell_class="forensic.execution_state",
                    quote="Initials: ____", round_no=1)
    assert a.tells[0]["repair_status"] == "repair_asserted"
    assert len(a.repair_asserted()) == 1
    # a non-fixer round did not re-raise it -> resolve
    a.resolve(tell_class="forensic.execution_state",
              quote="Initials: ____", round_no=2)
    assert a.tells[0]["repair_status"] == "resolved"
    assert a.repair_asserted() == []
    # cannot resolve one that was never asserted
    a.record(tell_class="c2", quote="q2", path="p", rationale="r",
             trial_id="J1", round_no=2)
    with pytest.raises(ValueError, match="cannot resolve"):
        a.resolve(tell_class="c2", quote="q2", round_no=2)


def test_reraised_repair_reopens(tmp_path):
    """FM2: a repair_asserted tell that a later round RE-RAISES did not hold —
    it reopens rather than silently resolving."""
    a = atlas.Atlas(tmp_path / "atlas.json", corroboration_k=1)
    a.record(tell_class="forensic.signature", quote="same-hand scrawl",
             path="lease.pdf", rationale="one hand", trial_id="J1", round_no=1)
    a.assert_repair(tell_class="forensic.signature",
                    quote="same-hand scrawl", round_no=1)
    a.record(tell_class="forensic.signature", quote="same-hand scrawl",
             path="lease.pdf", rationale="one hand", trial_id="J2", round_no=2)
    assert a.tells[0]["repair_status"] == "reopened"
