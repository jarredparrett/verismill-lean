"""The public experiment lifecycle: persistence, blindness, and reruns."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from verismill import (AgentRun, AgentTask, Experiment, ModelConfig, Phase,
                       class_catalog, derive_local_standings, experiments_root,
                       user_data_root)


def research():
    return {
        "sources": [{"id": "form-1", "kind": "blank_form",
                     "provenance": {"publisher": "issuer", "sha256": "sha256:x"}}],
        "coverage": {"layout": "sourced", "forensic": "open"},
    }


def rubric():
    from verismill.climb.judges import DIMENSIONS

    return {
        "version": "1.0",
        "scorer": "absolute-v0.2",
        "dimensions": [
            {
                "id": dimension,
                "description": f"Legacy absolute review: {dimension}",
                "anchors": {"0": "unacceptable", "100": "source-faithful"},
            }
            for dimension in DIMENSIONS
        ],
        "acceptance": {"rules": [
            {"metric": "overall_min", "operator": ">=", "value": 80},
        ]},
    }


def requirements():
    return [{"id": "form.layout", "property": "section order matches the source",
             "failure": "a required section is missing or out of order"}]


def sha256(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode()
    return "sha256:" + hashlib.sha256(value).hexdigest()


def absolute_output(score: int = 61, authenticity: str = "synthetic") -> dict:
    from verismill.climb.judges import DIMENSIONS, DISQUALIFIERS

    return {
        "glance_impression": "internally coherent but visibly synthesized",
        "authenticity": authenticity,
        "confidence": 0.8,
        "disqualifiers": {key: "pass" for key in DISQUALIFIERS},
        "dimension_scores": {key: score for key in DIMENSIONS},
        "tells": [],
    }


def run(role: str, n: int, *, agent: str | None = None,
        context: str | None = None, model: str = "model-a",
        score: int = 61, authenticity: str = "synthetic") -> AgentRun:
    parsed = absolute_output(score, authenticity) if role == "blind_judge" else {"ok": True}
    return AgentRun(
        run_id=f"run-{role}-{n}", agent_id=agent or f"agent-{role}-{n}",
        context_id=context or f"context-{role}-{n}", role=role,
        model=ModelConfig(provider="test", model=model,
                          resolved_model=f"{model}-2026-01-01", tools=("pdf",)),
        prompt_hash=sha256(f"prompt-{role}-{n}"),
        input_hashes={"task": sha256(f"input-{role}-{n}")},
        raw_response=json.dumps(parsed), parsed_output=parsed,
        usage={"input_tokens": 10, "output_tokens": 4})


def prepared(tmp_path, rubric_value=None) -> Experiment:
    exp = Experiment.create(tmp_path / "experiment", request="Forge a standard form",
                            experiment_id="standard_form", clock=lambda: 1_700_000_000)
    exp.freeze_preparation(research=research(), rubric=rubric_value or rubric(),
                           requirements=requirements())
    return exp


def candidate(exp: Experiment, n: int = 1, *, model: str = "model-a",
              class_name: str = "test_class",
              mattermill: str = "test-version") -> tuple[str, str]:
    builder = exp.record_agent_run(run("builder", n, model=model))
    artifact = b"%PDF-1.4\nsynthetic\n"
    ref = exp.record_candidate(
        artifact=artifact,
        manifest={"class": class_name, "mattermill": mattermill, "seed": n,
                  "sha256": sha256(artifact), "bytes": len(artifact)},
        builder_run=builder,
        explanation={"observation": "the baseline omitted the footer",
                     "requirement": "form.layout", "change": "added the sourced footer",
                     "evidence": "source form-1 page 1"})
    return ref, builder


def emitted_candidate(exp: Experiment, monkeypatch, *,
                      class_name: str, mattermill: str) -> str:
    """Record a lightweight candidate through the trusted emitter boundary."""
    from mattermill import registry

    artifact = f"%PDF-1.4\n{class_name}-{mattermill}\n".encode()
    manifest = {"class": class_name, "mattermill": mattermill, "seed": 1,
                "sha256": sha256(artifact), "bytes": len(artifact)}
    monkeypatch.setattr(registry, "emit", lambda *args, **kwargs:
                        (artifact, manifest))
    builder = exp.record_agent_run(run("builder", 1))
    return exp.emit_candidate(
        class_name, seed=1, builder_run=builder,
        explanation={"observation": "the baseline omitted the footer",
                     "requirement": "form.layout",
                     "change": "added the sourced footer",
                     "evidence": "source form-1 page 1"})


def test_schema_and_state_machine_are_explicit(tmp_path):
    exp = Experiment.create(tmp_path / "e", request="Forge a lease",
                            experiment_id="lease_exp", clock=lambda: 1_700_000_000)
    assert exp.phase == Phase.REQUESTED
    assert Experiment.open(exp.root, clock=lambda: 1_700_000_000).phase == Phase.REQUESTED
    with pytest.raises(ValueError, match="only a climbing"):
        exp.submit_for_blind_judgment()
    with pytest.raises(ValueError, match="dimensions"):
        exp.freeze_preparation(research=research(),
                               rubric={"version": "1", "scorer": "absolute-v0.2",
                                       "dimensions": [], "acceptance": {}},
                               requirements=requirements())
    assert exp.phase == Phase.PREPARING
    incompatible = rubric()
    incompatible["acceptance"]["rules"][0]["metric"] = "layout"
    with pytest.raises(ValueError, match="not produced"):
        exp.freeze_preparation(research=research(), rubric=incompatible,
                               requirements=requirements())


def test_new_domain_rubric_defaults_to_v03_and_legacy_mismatch_is_rejected(tmp_path):
    """experiment.rubric-default: new rubrics cannot silently use legal v0.2."""
    domain_rubric = {
        "version": "archival.1",
        "dimensions": [{
            "id": "capture",
            "description": "The page behaves like a captured physical record.",
            "anchors": {"0": "flat synthetic page", "100": "source-calibrated"},
        }],
        "acceptance": {"rules": [
            {"metric": "overall_min", "operator": ">=", "value": 80},
        ]},
    }
    exp = Experiment.create(
        tmp_path / "default", request="Forge an archival log",
        experiment_id="archival_default", clock=lambda: 1_700_000_000,
    )
    exp.freeze_preparation(
        research=research(), rubric=domain_rubric, requirements=requirements(),
    )
    assert "scorer" not in domain_rubric
    assert exp.store.read_json(exp.state["refs"]["rubric"])["scorer"] == "absolute-v0.3"

    legacy = {**domain_rubric, "scorer": "absolute-v0.2"}
    rejected = Experiment.create(
        tmp_path / "legacy", request="Forge an archival log",
        experiment_id="archival_legacy", clock=lambda: 1_700_000_000,
    )
    with pytest.raises(ValueError, match="fixed legacy instrument"):
        rejected.freeze_preparation(
            research=research(), rubric=legacy, requirements=requirements(),
        )


def test_historical_mismatched_v02_experiment_still_replays(monkeypatch, tmp_path):
    """experiment.rubric-history: the new freeze guard does not rewrite history."""
    import verismill.experiment as experiment_module

    historical_rubric = {
        "version": "historical.1",
        "scorer": "absolute-v0.2",
        "dimensions": [{
            "id": "capture",
            "description": "A domain dimension v0.2 historically ignored.",
            "anchors": {"0": "flat", "100": "source-calibrated"},
        }],
        "acceptance": {"rules": [
            {"metric": "overall_min", "operator": ">=", "value": 80},
        ]},
    }
    monkeypatch.setattr(experiment_module, "validate_rubric", lambda value: None)
    exp = prepared(tmp_path, historical_rubric)
    cand, _ = candidate(exp)
    dev = exp.record_agent_run(run("development_judge", 1))
    exp.record_development_round(
        candidate=cand, judge_runs=[dev], decision="select",
        score={"capture": 80}, findings=[],
    )
    blind = [exp.record_agent_run(run("blind_judge", i)) for i in (1, 2, 3)]
    exp.record_absolute_blind_evaluation(judge_runs=blind)
    root = exp.root
    monkeypatch.undo()

    reopened = Experiment.open(root, clock=lambda: 1_700_000_000)
    assert reopened.verify()["ok"]
    assert reopened.replay() == exp.replay()


def test_full_rejected_cycle_is_resumable_and_replayable(tmp_path):
    exp = prepared(tmp_path)
    cand, _ = candidate(exp)
    dev = exp.record_agent_run(run("development_judge", 1))
    exp.record_development_round(
        candidate=cand, judge_runs=[dev], decision="select", score={"layout": 72},
        findings=[{"observation": "footer weight is uniform",
                   "evidence": "page 1 footer region", "requirement": "form.layout"}])
    assert exp.phase == Phase.AWAITING_BLIND_JUDGMENT
    assert exp.view("user")["measurement"]["status"] == "required"
    assert "required blind panel is incomplete" in exp.report()
    blind = [exp.record_agent_run(run("blind_judge", i)) for i in (1, 2, 3)]
    evaluation = exp.record_absolute_blind_evaluation(judge_runs=blind)
    assert exp.phase == Phase.JUDGED
    assert exp.state["standing"] is None
    assert exp.store.read_json(evaluation)["candidate"] == cand
    resumed = Experiment.open(exp.root, clock=lambda: 1_700_000_000)
    assert resumed.phase == Phase.JUDGED
    assert len(resumed.replay()) >= 6
    assert resumed.verify()["ok"]
    resumed.continue_climb()
    assert resumed.phase == Phase.CLIMBING
    second, _ = candidate(resumed, 2)
    resumed.submit_for_blind_judgment(second)
    with pytest.raises(ValueError, match="not fresh"):
        resumed.record_absolute_blind_evaluation(judge_runs=blind)


def test_artifact_result_is_a_public_materialization_boundary(tmp_path, monkeypatch):
    """experiment.artifact-result: downstreams receive bytes and attestation
    without reading the private object store."""
    exp = prepared(tmp_path)
    candidate_ref = emitted_candidate(
        exp, monkeypatch, class_name="test_class", mattermill="test-version")

    result = exp.artifact_result(candidate_ref)

    assert result["schema_version"] == "1.0"
    assert result["artifact"] == b"%PDF-1.4\ntest_class-test-version\n"
    assert result["manifest"]["sha256"] == result["attestation"]["artifact_hash"]
    assert result["attestation"] == {
        "schema_version": "1.0",
        "experiment_id": "standard_form",
        "experiment_revision": 1,
        "candidate": candidate_ref,
        "artifact_hash": result["manifest"]["sha256"],
        "manifest_hash": exp.view("user")["current_candidate"]["manifest"],
        "emitter": {"class": "test_class", "mattermill": "test-version"},
        "rubric_hash": exp.state["refs"]["rubric"],
        "requirements_hash": exp.state["refs"]["requirements"],
        "measurement": {
            "status": "development_only", "evaluation": None, "standing": None,
        },
        "verification": exp.verify(),
    }
    assert result["attestation"]["verification"]["ok"]
    assert Experiment.open(exp.root).artifact_result()["artifact"] == result["artifact"]


def test_artifact_result_rejects_missing_or_foreign_candidate(tmp_path):
    """experiment.artifact-result-membership: only recorded candidates export."""
    exp = prepared(tmp_path)
    with pytest.raises(ValueError, match="recorded candidate"):
        exp.artifact_result()
    with pytest.raises(ValueError, match="not part of this experiment"):
        exp.artifact_result(sha256("foreign"))


def test_harvest_repair_is_persisted_but_not_resolved(tmp_path):
    exp = prepared(tmp_path)
    candidate(exp)
    tell = exp.record_tell(tell_class="forensic.signature", path="document.pdf",
                           rationale="same signature image appears twice",
                           trial_id="blind-1", round_no=1,
                           quote="identical signature")
    assert tell["repair_status"] is None
    repaired = exp.assert_repair(tell_class="forensic.signature",
                                 quote="identical signature", round_no=1)
    assert repaired["repair_status"] == "repair_asserted"
    reopened = Experiment.open(exp.root)
    assert reopened.store.read_json(reopened.state["refs"]["atlas"])["tells"][0]["repair_status"] == "repair_asserted"
    assert reopened.verify()["ok"]


def test_only_a_fresh_blind_evaluation_resolves_a_repair(tmp_path):
    """experiments.repair-resolution: a harvest assertion becomes resolved
    only when the latest blind panel on the current candidate omits the tell."""
    exp = prepared(tmp_path)
    cand, _ = candidate(exp)
    exp.record_tell(tell_class="forensic.signature", path="document.pdf",
                    rationale="same signature image appears twice",
                    trial_id="harvest-1", round_no=1,
                    quote="identical signature")
    exp.assert_repair(tell_class="forensic.signature",
                      quote="identical signature", round_no=1)
    exp.submit_for_blind_judgment(cand)
    blind = [exp.record_agent_run(run("blind_judge", i)) for i in (1, 2, 3)]
    evaluation = exp.record_absolute_blind_evaluation(judge_runs=blind)
    resolved = exp.resolve_repair(
        evaluation=evaluation, tell_class="forensic.signature",
        path="document.pdf", quote="identical signature")
    assert resolved["repair_status"] == "resolved"
    assert exp.verify()["ok"]


def test_blindness_rejects_builder_or_development_context(tmp_path):
    exp = prepared(tmp_path)
    cand, _ = candidate(exp)
    exp.submit_for_blind_judgment(cand)
    contaminated = exp.record_agent_run(run("blind_judge", 3,
                                            agent="agent-builder-1",
                                            context="fresh-context"))
    fresh = [exp.record_agent_run(run("blind_judge", i)) for i in (4, 5)]
    with pytest.raises(ValueError, match="not fresh"):
        exp.record_absolute_blind_evaluation(
            judge_runs=[contaminated, *fresh])


def test_role_views_hide_provenance_and_development_history(tmp_path):
    exp = prepared(tmp_path)
    candidate(exp)
    builder_view = exp.view("builder")
    assert "requirements" in builder_view
    assert "research" not in builder_view
    assert "evaluations" not in builder_view
    blind_view = exp.view("blind_judge")
    assert "trial_packet" in blind_view
    assert "request" not in blind_view and "id" not in blind_view
    assert "research" not in blind_view
    assert "development" not in blind_view
    assert set(blind_view["current_candidate"]) == {"artifact"}
    auditor = exp.view("auditor")
    assert "state" in auditor and "events" in auditor


def test_models_are_recorded_as_candidate_arms_not_hidden_state(tmp_path):
    exp = prepared(tmp_path)
    a, a_run = candidate(exp, 1, model="builder-a")
    b, b_run = candidate(exp, 2, model="builder-b")
    assert a != b
    assert exp.store.read_json(a_run)["model"]["resolved_model"] == \
        "builder-a-2026-01-01"
    assert exp.store.read_json(b_run)["model"]["resolved_model"] == \
        "builder-b-2026-01-01"


def test_accepted_standing_is_derived_and_report_is_causal(tmp_path):
    exp = prepared(tmp_path)
    cand, _ = candidate(exp)
    exp.submit_for_blind_judgment(cand)
    blind = [exp.record_agent_run(run("blind_judge", i, score=91,
                                      authenticity="genuine"))
             for i in (1, 2, 3)]
    evaluation = exp.record_absolute_blind_evaluation(judge_runs=blind)
    assert exp.phase == Phase.ACCEPTED
    assert exp.state["standing"]["evaluation"] == evaluation
    report = exp.report()
    assert "Research" in report and "Rubric 1.0 (frozen)" in report
    assert "Blind evaluations" in report and "accepted" in report
    assert "content-addressed" in report
    assert exp.verify()["ok"]


def test_user_data_root_is_configurable_and_outside_the_clone(tmp_path, monkeypatch):
    """catalog.user-space: the default experiment collection belongs to the
    operator and may be relocated without changing repository content."""
    configured = tmp_path / "operator-data"
    monkeypatch.setenv("VERISMILL_HOME", str(configured))
    assert user_data_root() == configured
    assert experiments_root() == configured / "experiments"


def test_local_standing_is_derived_from_verified_user_experiments(
        tmp_path, monkeypatch):
    """catalog.evidence-derived: class standing is discovered from verified
    accepted bundles and is never copied into mattermill metadata."""
    from mattermill import __version__ as mattermill_version

    owned = tmp_path / "owned-experiments"
    exp = prepared(owned)
    cand = emitted_candidate(exp, monkeypatch, class_name="lease_nj",
                             mattermill=mattermill_version)
    exp.submit_for_blind_judgment(cand)
    blind = [exp.record_agent_run(run("blind_judge", i, score=91,
                                      authenticity="genuine"))
             for i in (1, 2, 3)]
    exp.record_absolute_blind_evaluation(judge_runs=blind)

    standings, errors = derive_local_standings(owned)
    assert errors == []
    assert standings["lease_nj"][0]["experiment_id"] == "standard_form"
    assert standings["lease_nj"][0]["scores"] == exp.state["standing"]["scores"]

    catalog = class_catalog(owned)
    lease = next(item for item in catalog["classes"]
                 if item["name"] == "lease_nj")
    assert lease["local_standing"]["path"] == str(exp.root)
    assert lease["latest_historical_standing"] is None
    assert "standing" not in {key for key in lease
                              if key not in {"local_standing",
                                             "latest_historical_standing"}}


def test_catalog_does_not_promote_invalid_or_old_version_evidence(
        tmp_path, monkeypatch):
    """catalog.version-bound: corrupt evidence is reported and an accepted
    result for an old emitter version is historical, not current standing."""
    historical_root = tmp_path / "historical"
    exp = prepared(historical_root)
    cand = emitted_candidate(exp, monkeypatch, class_name="lease_nj",
                             mattermill="0.0.1")
    exp.submit_for_blind_judgment(cand)
    blind = [exp.record_agent_run(run("blind_judge", i, score=91,
                                      authenticity="genuine"))
             for i in (1, 2, 3)]
    exp.record_absolute_blind_evaluation(judge_runs=blind)
    lease = next(item for item in class_catalog(historical_root)["classes"]
                 if item["name"] == "lease_nj")
    assert lease["local_standing"] is None
    assert lease["latest_historical_standing"]["mattermill"] == "0.0.1"

    exp.store.path_for(exp.state["refs"]["rubric"]).write_text("tampered")
    catalog = class_catalog(historical_root)
    assert catalog["errors"]
    lease = next(item for item in catalog["classes"]
                 if item["name"] == "lease_nj")
    assert lease["local_standing"] is None
    assert lease["latest_historical_standing"] is None


def test_generic_candidate_cannot_claim_registered_class_standing(tmp_path):
    """catalog.emitter-provenance: a caller-authored manifest may describe its
    bytes, but cannot impersonate the mattermill facade in the class catalog."""
    owned = tmp_path / "generic"
    exp = prepared(owned)
    cand, _ = candidate(exp, class_name="lease_nj", mattermill="0.14.5")
    exp.submit_for_blind_judgment(cand)
    blind = [exp.record_agent_run(run("blind_judge", i, score=91,
                                      authenticity="genuine"))
             for i in (1, 2, 3)]
    exp.record_absolute_blind_evaluation(judge_runs=blind)
    standings, errors = derive_local_standings(owned)
    assert errors == []
    assert standings == {}


def test_verification_replays_scores_from_judge_receipts(tmp_path):
    """experiments.score-replay: immutable score JSON is not sufficient proof;
    verification must reproduce it from judge outputs and the named scorer."""
    exp = prepared(tmp_path)
    cand, _ = candidate(exp)
    exp.submit_for_blind_judgment(cand)
    blind = [exp.record_agent_run(run("blind_judge", i)) for i in (1, 2, 3)]
    evaluation = exp.record_absolute_blind_evaluation(judge_runs=blind)
    forged = exp.store.read_json(evaluation)
    forged["scores"]["overall_min"] = 100
    forged_ref = exp.store.put_json(forged)
    with pytest.raises(ValueError, match="replayed scorer"):
        exp._verify_evaluation(forged_ref)


def test_evaluation_rerun_copies_frozen_object_graph_and_uses_fresh_judges(tmp_path):
    exp = prepared(tmp_path)
    cand, _ = candidate(exp)
    exp.submit_for_blind_judgment(cand)
    child = exp.rerun(tmp_path / "rerun", from_phase="evaluation")
    assert child.phase == Phase.AWAITING_BLIND_JUDGMENT
    assert child.state["refs"]["rubric"] == exp.state["refs"]["rubric"]
    assert child.state["refs"]["current_candidate"] == cand
    assert child.verify()["ok"]
    assert child.state["agent_runs"] == []
    assert len(child.state["inherited_agent_runs"]) == 1


def test_verify_detects_object_tampering(tmp_path):
    exp = prepared(tmp_path)
    rubric_ref = exp.state["refs"]["rubric"]
    exp.store.path_for(rubric_ref).write_text("tampered")
    result = exp.verify()
    assert not result["ok"]
    assert any("corrupt object" in failure for failure in result["failures"])


def test_source_and_mattermill_are_available_behind_facade(tmp_path, monkeypatch):
    from verismill import source
    from mattermill import registry

    raw = tmp_path / "blank.pdf"
    raw.write_bytes(b"%PDF-reference")

    def fake_register(path, name, out):
        dest = out / name
        dest.mkdir(parents=True)
        (dest / "source.pdf").write_bytes(Path(path).read_bytes())
        (dest / "provenance.json").write_text(json.dumps({"name": name}))
        return dest / "source.pdf"

    def fake_contract(name, out):
        path = out / name / "contract.json"
        path.write_text(json.dumps({"pages": 1, "proposed_markers": {"1": ["FORM"]}}))
        return path

    monkeypatch.setattr(source, "register_local", fake_register)
    monkeypatch.setattr(source, "write_contract", fake_contract)
    exp = Experiment.create(tmp_path / "integrated", request="Forge a form",
                            experiment_id="integrated_form")
    reference = exp.source_local_reference(raw, name="form")
    assert exp.store.read_json(reference)["name"] == "form"
    exp.freeze_preparation(research=research(), rubric=rubric(),
                           requirements=requirements())
    builder = exp.record_agent_run(run("builder", 1))
    emitted = b"%PDF-emitted"
    monkeypatch.setattr(
        registry, "emit",
        lambda *a, **k: (emitted, {"class": a[0], "mattermill": "test-version",
                                   "seed": k["seed"],
                                   "sha256": sha256(emitted),
                                   "bytes": len(emitted)}))
    cand = exp.emit_candidate("test_class", seed=7, builder_run=builder,
                              explanation={"observation": "baseline",
                                           "requirement": "form.layout",
                                           "change": "rendered source contract"})
    assert exp.store.read_json(exp.store.read_json(cand)["manifest"])["seed"] == 7
    # A judge can expose a sourcing debt only after a candidate exists.  The
    # repair loop must be able to ingest that newly required reference and
    # preserve it on the same experiment ledger.
    repair_reference = exp.source_local_reference(raw, name="repair-form")
    assert exp.store.read_json(repair_reference)["name"] == "repair-form"
    assert exp.phase == Phase.CLIMBING


def test_pairwise_judge_harness_is_available_behind_facade(tmp_path):
    pairwise_rubric = rubric()
    pairwise_rubric["scorer"] = "pairwise-v1"
    pairwise_rubric["acceptance"] = {"rules": [
        {"metric": "synth_vs_real_accuracy", "operator": "<=", "value": 0.5},
    ]}
    exp = prepared(tmp_path, pairwise_rubric)
    cand, _ = candidate(exp)
    exp.submit_for_blind_judgment(cand)
    judge_refs = []
    keys = []
    for i in (1, 2, 3):
        base = run("blind_judge", i)
        judge = AgentRun(run_id=base.run_id, agent_id=base.agent_id,
                         context_id=base.context_id, role=base.role, model=base.model,
                         prompt_hash=base.prompt_hash, input_hashes=base.input_hashes,
                         raw_response='{"pick":"left"}',
                         parsed_output={"pick": "left", "confidence": 0.8,
                                        "tells": []})
        judge_refs.append(exp.record_agent_run(judge))
        keys.append({"trial_id": f"t{i}", "mode": "synth_vs_real",
                     "synthetic_side": "left"})
    evaluation = exp.record_pairwise_blind_evaluation(
        keys=keys, judge_runs=judge_refs)
    assert exp.store.read_json(evaluation)["scores"]["synth_vs_real_accuracy"] == 1.0


def test_atlas_is_available_behind_facade_without_leaking_to_builder(tmp_path):
    exp = prepared(tmp_path)
    tell = exp.record_tell(tell_class="forensic.signature", path="lease.pdf",
                           quote="/s/ Example", rationale="typeset signature",
                           trial_id="trial-1", round_no=1)
    assert tell["state"] == "reported"
    assert exp.view("user")["atlas_summary"] == {
        "tells": 1, "by_state": {"reported": 1}}
    assert "atlas_summary" not in exp.view("builder")
    assert exp.verify()["ok"]


def test_heterogeneous_blind_panel_tasks_use_only_sealed_artifact(tmp_path):
    exp = prepared(tmp_path)
    cand, _ = candidate(exp)
    exp.submit_for_blind_judgment(cand)
    models = [ModelConfig(provider="provider", model=f"judge-{i}") for i in range(3)]
    with pytest.raises(ValueError, match="at least 3"):
        exp.absolute_judge_tasks(class_name="secret-internal-name",
                                 persona="domain expert", models=models[:2])
    tasks = exp.absolute_judge_tasks(class_name="secret-internal-name",
                                     persona="domain expert", models=models)
    assert [task.model for task in tasks] == models
    assert all(task.role == "blind_judge" for task in tasks)
    assert all(set(task.inputs) == {"document.pdf"} for task in tasks)
    assert len({task.instructions for task in tasks}) == 3
    assert any("recomputing every derived figure" in task.instructions for task in tasks)
    assert any("required disclosures" in task.instructions for task in tasks)
    assert any("signatures, initials, seals" in task.instructions for task in tasks)
    assert all("baseline omitted" not in task.instructions for task in tasks)


def test_rubric_driven_absolute_panel_replays_exact_frozen_dimensions(tmp_path):
    """absolute-v0.3 prompts, parses, scores, and replays the declared rubric."""
    rubric_v3 = {
        "version": "archival.1",
        "scorer": "absolute-v0.3",
        "dimensions": [
            {"id": "capture", "description": "Captured-object fidelity",
             "anchors": {"0": "flat", "100": "source-calibrated"}},
            {"id": "working_hand", "description": "Working-hand fidelity",
             "anchors": {"0": "font", "100": "credible hand"}},
            {"id": "institutional_use", "description": "Ordinary record behavior",
             "anchors": {"0": "prop", "100": "ordinary record"}},
            {"id": "reproducibility", "description": "Stable evidence",
             "anchors": {"0": "unstable", "100": "reproducible"}},
        ],
        "acceptance": {"rules": [
            {"metric": "overall_min", "operator": ">=", "value": 80},
            {"metric": "coverage_ok", "operator": "==", "value": True},
        ]},
    }
    exp = prepared(tmp_path, rubric_v3)
    cand, _ = candidate(exp)
    development = exp.record_agent_run(run("development_judge", 1))
    exp.record_development_round(
        candidate=cand, judge_runs=[development], decision="select",
        score={"capture": 90},
        findings=[{"observation": "ready for the frozen archival panel",
                   "evidence": "full-scale rendered inspection",
                   "requirement": "form.layout"}],
    )
    models = [ModelConfig(provider="test", model=f"rubric-{i}")
              for i in (1, 2, 3)]
    tasks = exp.absolute_judge_tasks(
        class_name="archival_record", persona="records conservator", models=models
    )
    expected_dimensions = {
        dimension["id"] for dimension in rubric_v3["dimensions"]
    }
    assert all(
        set(task.response_schema["dimension_scores"]) == expected_dimensions
        for task in tasks
    )
    assert all("disqualifiers" not in task.response_schema for task in tasks)
    assert all("lead-paint" not in task.instructions for task in tasks)

    judge_refs = []
    for index, task in enumerate(tasks, 1):
        parsed = {
            "glance_impression": "credible working archive capture",
            "authenticity": "genuine", "confidence": 0.82,
            "dimension_scores": {
                dimension: 91 for dimension in expected_dimensions
            },
            "tells": [],
        }
        judge_refs.append(exp.record_agent_run(AgentRun(
            run_id=f"rubric-blind-{index}", agent_id=f"rubric-agent-{index}",
            context_id=f"rubric-context-{index}", role="blind_judge",
            model=task.model, prompt_hash=task.prompt_hash(),
            input_hashes=task.input_hashes(), raw_response=json.dumps(parsed),
            parsed_output=parsed,
        )))
    evaluation_ref = exp.record_absolute_blind_evaluation(
        judge_runs=judge_refs
    )
    evaluation = exp.store.read_json(evaluation_ref)
    assert evaluation["scorer"] == "absolute-v0.3"
    assert evaluation["scores"]["overall_min"] == 91
    assert evaluation["scores"]["coverage_ok"] is True
    assert exp.phase == Phase.ACCEPTED
    assert exp.verify()["ok"]


def test_absolute_measurement_requires_three_judges_and_all_lenses(tmp_path):
    """experiments.integrated-blind-measurement: a selected candidate cannot
    complete measurement with a partial panel or partial lens assignment."""
    exp = prepared(tmp_path)
    cand, _ = candidate(exp)
    dev = exp.record_agent_run(run("development_judge", 1))
    exp.record_development_round(
        candidate=cand, judge_runs=[dev], decision="select", score={"layout": 80},
        findings=[{"observation": "candidate is ready for blind measurement",
                   "evidence": "rendered page inspection",
                   "requirement": "form.layout"}])
    blind = [exp.record_agent_run(run("blind_judge", i)) for i in (1, 2, 3)]
    with pytest.raises(ValueError, match="at least 3"):
        exp.record_absolute_blind_evaluation(judge_runs=blind[:2])
    with pytest.raises(ValueError, match="every judge lens"):
        exp.record_absolute_blind_evaluation(
            judge_runs=blind,
            assigned_lenses=["arithmetic_and_dates"] * 3)
    exp.record_absolute_blind_evaluation(judge_runs=blind)
    assert exp.phase == Phase.JUDGED


def test_provider_backends_run_as_one_integrated_blind_measurement(tmp_path):
    """experiments.integrated-panel-runner: provider adapters can execute,
    persist, score, and transition the complete panel in one operation."""
    exp = prepared(tmp_path)
    cand, _ = candidate(exp)
    dev = exp.record_agent_run(run("development_judge", 1))
    exp.record_development_round(
        candidate=cand, judge_runs=[dev], decision="select", score={"layout": 90},
        findings=[{"observation": "candidate is ready for blind measurement",
                   "evidence": "rendered page inspection",
                   "requirement": "form.layout"}])
    models = [ModelConfig(provider="test", model=f"panel-{i}") for i in (1, 2, 3)]

    class Backend:
        def __init__(self, number):
            self.number = number

        def invoke(self, task):
            parsed = absolute_output(91, "genuine")
            return AgentRun(
                run_id=f"integrated-panel-{self.number}",
                agent_id=f"integrated-agent-{self.number}",
                context_id=f"integrated-context-{self.number}",
                role=task.role, model=task.model,
                prompt_hash=task.prompt_hash(),
                input_hashes=task.input_hashes(),
                raw_response=json.dumps(parsed), parsed_output=parsed)

    backends = [Backend(i) for i in (1, 2, 3)]
    with pytest.raises(ValueError, match="one backend"):
        exp.run_absolute_blind_measurement(
            class_name="test_class", persona="domain expert",
            models=models, backends=backends[:2])
    evaluation = exp.run_absolute_blind_measurement(
        class_name="test_class", persona="domain expert",
        models=models, backends=backends)
    assert exp.store.read_json(evaluation)["scores"]["k"] == 3
    assert exp.phase == Phase.ACCEPTED
    assert exp.view("user")["measurement"]["status"] == "accepted"


def test_receipt_digests_are_not_mistaken_for_object_references(tmp_path):
    """experiments.receipt-digests: valid prompt and input digests prove inputs;
    they are not object-store graph edges unless a typed ref field names them."""
    exp = prepared(tmp_path)
    receipt = exp.record_agent_run(run("builder", 1))
    assert exp.store.verify(receipt)
    assert exp.verify()["ok"]
    events = exp.replay()
    assert any(event["event_type"] == "agent_run" and
               event["output_refs"]["agent_run"] == receipt for event in events)


def test_receipts_require_real_sha256_input_evidence():
    """experiments.receipt-evidence: builder and judge receipts cannot persist
    placeholder prompt digests or omit the hashes of the inputs they saw."""
    with pytest.raises(ValueError, match="prompt_hash"):
        AgentRun(run_id="bad", agent_id="agent", context_id="context",
                 role="builder", model=ModelConfig(provider="test", model="m"),
                 prompt_hash="sha256:placeholder", input_hashes={"task": sha256("x")},
                 raw_response="response", parsed_output={})
    with pytest.raises(ValueError, match="must hash the exact inputs"):
        AgentRun(run_id="bad", agent_id="agent", context_id="context",
                 role="blind_judge", model=ModelConfig(provider="test", model="m"),
                 prompt_hash=sha256("prompt"), input_hashes={},
                 raw_response="response", parsed_output={})


def test_candidate_manifest_must_describe_persisted_artifact(tmp_path):
    """experiments.candidate-integrity: a candidate manifest cannot claim a
    different digest or byte length than the immutable artifact it accompanies."""
    exp = prepared(tmp_path)
    builder = exp.record_agent_run(run("builder", 1))
    with pytest.raises(ValueError, match="manifest sha256"):
        exp.record_candidate(
            artifact=b"artifact", manifest={"sha256": sha256("other"), "bytes": 8},
            builder_run=builder,
            explanation={"observation": "baseline", "requirement": "form.layout",
                         "change": "rendered source contract"})
    with pytest.raises(ValueError, match="no frozen requirement"):
        exp.record_candidate(
            artifact=b"artifact",
            manifest={"sha256": sha256("artifact"), "bytes": 8},
            builder_run=builder,
            explanation={"observation": "baseline", "requirement": "invented.rule",
                         "change": "rendered source contract"})


def test_backend_receipt_must_match_assigned_task(tmp_path):
    """experiments.backend-contract: an adapter cannot attribute a response to
    a different prompt or input set than the task the experiment assigned."""
    exp = Experiment.create(tmp_path / "backend", request="Research a form")
    model = ModelConfig(provider="test", model="model-a")
    task = AgentTask(role="researcher", instructions="Read the source.",
                     inputs={"source.pdf": b"%PDF-source"},
                     response_schema={"sources": "array"}, model=model)

    class Backend:
        def __init__(self, prompt_hash):
            self.prompt_hash = prompt_hash

        def invoke(self, assigned):
            return AgentRun(
                run_id="provider-run", agent_id="research-agent",
                context_id="research-context", role=assigned.role, model=model,
                prompt_hash=self.prompt_hash,
                input_hashes=assigned.input_hashes(), raw_response='{"sources": []}',
                parsed_output={"sources": []})

    ref = exp.invoke_agent(Backend(task.prompt_hash()), task)
    assert exp.store.verify(ref)
    with pytest.raises(ValueError, match="prompt hash"):
        exp.invoke_agent(Backend(sha256("different prompt")), task)


def test_cli_initializes_prepares_and_verifies_an_experiment(tmp_path):
    """experiments.cli-lifecycle: a public caller can create and freeze the
    validated experiment instrument without importing internal modules."""
    root = tmp_path / "cli-experiment"
    values = {
        "research.json": research(),
        "rubric.json": rubric(),
        "requirements.json": requirements(),
    }
    for name, value in values.items():
        (tmp_path / name).write_text(json.dumps(value))
    init = subprocess.run(
        [sys.executable, "-m", "verismill", "init", str(root),
         "--id", "cli_experiment", "--request", "Forge a standard form"],
        capture_output=True, text=True)
    assert init.returncode == 0, init.stderr
    prepared_run = subprocess.run(
        [sys.executable, "-m", "verismill", "prepare", str(root),
         "--research", str(tmp_path / "research.json"),
         "--rubric", str(tmp_path / "rubric.json"),
         "--requirements", str(tmp_path / "requirements.json")],
        capture_output=True, text=True)
    assert prepared_run.returncode == 0, prepared_run.stderr
    verified = subprocess.run(
        [sys.executable, "-m", "verismill", "verify", str(root)],
        capture_output=True, text=True)
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["ok"] is True


def test_cli_defaults_new_experiments_to_user_space(tmp_path):
    """catalog.cli-default: omitting ROOT creates a named experiment beneath
    VERISMILL_HOME, while explicit paths remain supported."""
    data = tmp_path / "user-data"
    env = dict(os.environ, VERISMILL_HOME=str(data))
    init = subprocess.run(
        [sys.executable, "-m", "verismill", "init", "--id", "owned_exp",
         "--request", "Forge a standard form"],
        capture_output=True, text=True, env=env)
    assert init.returncode == 0, init.stderr
    root = data / "experiments" / "owned_exp"
    assert (root / "experiment.json").exists()

    home = subprocess.run([sys.executable, "-m", "verismill", "home"],
                          capture_output=True, text=True, env=env)
    assert home.returncode == 0, home.stderr
    assert Path(home.stdout.strip()) == data

    listed = subprocess.run(
        [sys.executable, "-m", "verismill", "classes", "--json"],
        capture_output=True, text=True, env=env)
    assert listed.returncode == 0, listed.stderr
    value = json.loads(listed.stdout)
    assert Path(value["experiment_root"]) == data / "experiments"
    assert value["classes"]
