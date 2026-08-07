"""Artifact Suite composition over independent Experiment lineages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from verismill import AgentRun, ArtifactSuite, Experiment, ModelConfig


def sha256(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode()
    return "sha256:" + hashlib.sha256(value).hexdigest()


def receipt(role: str, name: str, parsed: dict | None = None) -> AgentRun:
    parsed = parsed or {"ok": True}
    return AgentRun(
        run_id=f"{role}-{name}",
        agent_id=f"agent-{role}-{name}",
        context_id=f"context-{role}-{name}",
        role=role,
        model=ModelConfig(provider="test", model=f"model-{name}"),
        prompt_hash=sha256(f"prompt-{role}-{name}"),
        input_hashes={"task": sha256(f"input-{role}-{name}")},
        raw_response=json.dumps(parsed),
        parsed_output=parsed,
    )


def prepare_experiment(root: Path, name: str) -> tuple[Experiment, str]:
    exp = Experiment.create(
        root, request=f"Forge {name}", experiment_id=name,
        clock=lambda: 1_700_000_000,
    )
    exp.freeze_preparation(
        research={
            "sources": [{
                "id": f"source-{name}", "kind": "facsimile",
                "provenance": {"publisher": "archive"},
            }],
            "coverage": {"capture": "sourced"},
        },
        rubric={
            "version": "archival.1",
            "dimensions": [{
                "id": "capture", "description": "Captured-object fidelity",
                "anchors": {"0": "flat", "100": "source-calibrated"},
            }],
            "acceptance": {"rules": [
                {"metric": "overall_min", "operator": ">=", "value": 80},
            ]},
        },
        requirements=[{
            "id": "archive.capture", "property": "source-calibrated capture",
            "failure": "page reads as a flat synthetic export",
        }],
    )
    builder = exp.record_agent_run(receipt("builder", name))
    artifact = f"%PDF-1.4\n{name}\n".encode()
    candidate = exp.record_candidate(
        artifact=artifact,
        manifest={
            "class": name, "mattermill": "test-1", "seed": 1,
            "sha256": sha256(artifact), "bytes": len(artifact),
        },
        builder_run=builder,
        explanation={
            "observation": "baseline lacked capture context",
            "requirement": "archive.capture",
            "change": "added source-calibrated capture",
        },
    )
    return exp, candidate


def seal_for_measurement(exp: Experiment, candidate: str, name: str, *,
                         agent_approval: bool = False) -> None:
    development = exp.record_agent_run(receipt("development_judge", name))
    exp.record_development_round(
        candidate=candidate,
        judge_runs=[development],
        findings=[],
        decision="select",
        score={"capture": 85},
    )
    if agent_approval:
        task = exp.agent_approval_task(
            model=ModelConfig(provider="test", model=f"approval-{name}"))
        parsed = {"decision": "approve", "rationale": "Ready for blind measurement."}
        reviewer = exp.record_agent_run(AgentRun(
            run_id=f"approval-{name}", agent_id=f"approval-agent-{name}",
            context_id=f"approval-context-{name}", role=task.role,
            model=task.model, prompt_hash=task.prompt_hash(),
            input_hashes=task.input_hashes(), raw_response=json.dumps(parsed),
            parsed_output=parsed,
        ))
        exp.record_agent_approval(candidate=candidate, reviewer_run=reviewer)
    else:
        exp.record_human_review(
            candidate=candidate,
            reviewer_id=f"reviewer-{name}",
            decision="approve",
            feedback=[],
        )


def measure_directly(exp: Experiment, candidate: str, name: str, score: int) -> None:
    seal_for_measurement(exp, candidate, name)
    judge_refs = []
    for index in (1, 2, 3):
        parsed = {
            "glance_impression": "source-calibrated archival capture",
            "authenticity": "genuine" if score >= 80 else "synthetic",
            "confidence": 0.85,
            "dimension_scores": {"capture": score},
            "tells": [],
        }
        judge_refs.append(
            exp.record_agent_run(receipt("blind_judge", f"{name}-{index}", parsed))
        )
    exp.record_absolute_blind_evaluation(judge_runs=judge_refs)


def test_suite_links_independent_experiments_and_attests_without_blending_scores(tmp_path):
    """suite.attestation: collection standing names every exact child lineage."""
    accepted, accepted_candidate = prepare_experiment(tmp_path / "accepted", "night_log")
    rejected, rejected_candidate = prepare_experiment(tmp_path / "rejected", "memo")
    measure_directly(accepted, accepted_candidate, "night_log", 91)
    measure_directly(rejected, rejected_candidate, "memo", 63)

    suite = ArtifactSuite.create(
        tmp_path / "suite", request="Winter Observatory artifacts",
        suite_id="winter_observatory", clock=lambda: 1_700_000_000,
    )
    suite.link_experiment("night_log", accepted)
    suite.link_experiment("memo", rejected)
    attestation = suite.attest()

    assert attestation["qualification"] == {
        "evidence_class": "artifact_realism",
        "status": "not_accepted",
        "member_count": 2,
        "status_counts": {"accepted": 1, "not_accepted": 1},
        "release_ready": False,
    }
    assert "overall" not in attestation["qualification"]
    assert {item["member_id"] for item in attestation["members"]} == {
        "night_log", "memo",
    }
    assert suite.verify()["ok"]
    assert set(suite.artifact_results()) == {"night_log", "memo"}
    replay = suite.replay()
    assert len(replay["suite"]) == 6
    assert all(replay["members"].values())
    assert "not averaged" in suite.report()


def test_suite_creates_and_measures_member_through_public_experiment_api(tmp_path):
    """suite.measurement: suite orchestration delegates to the child facade."""
    suite = ArtifactSuite.create(
        tmp_path / "suite", request="One measured archive",
        suite_id="measured_archive", clock=lambda: 1_700_000_000,
    )
    exp = suite.create_experiment("night_log", request="Forge a night log")
    exp.freeze_preparation(
        research={
            "sources": [{
                "id": "source-night", "kind": "facsimile",
                "provenance": {"publisher": "archive"},
            }],
            "coverage": {"capture": "sourced"},
        },
        rubric={
            "version": "archival.1",
            "dimensions": [{
                "id": "capture", "description": "Captured-object fidelity",
                "anchors": {"0": "flat", "100": "source-calibrated"},
            }],
            "acceptance": {"rules": [
                {"metric": "overall_min", "operator": ">=", "value": 80},
            ]},
        },
        requirements=[{
            "id": "archive.capture", "property": "source-calibrated capture",
            "failure": "page reads as a flat synthetic export",
        }],
    )
    builder = exp.record_agent_run(receipt("builder", "created"))
    artifact = b"%PDF-1.4\ncreated\n"
    candidate = exp.record_candidate(
        artifact=artifact,
        manifest={
            "class": "night_log", "mattermill": "test-1", "seed": 1,
            "sha256": sha256(artifact), "bytes": len(artifact),
        },
        builder_run=builder,
        explanation={
            "observation": "baseline lacked capture context",
            "requirement": "archive.capture",
            "change": "added source-calibrated capture",
        },
    )
    seal_for_measurement(exp, candidate, "created", agent_approval=True)
    models = [ModelConfig(provider="test", model=f"panel-{i}") for i in (1, 2, 3)]

    class Backend:
        def __init__(self, index: int):
            self.index = index

        def invoke(self, task):
            parsed = {
                "glance_impression": "credible archive capture",
                "authenticity": "genuine", "confidence": 0.9,
                "dimension_scores": {"capture": 92}, "tells": [],
            }
            return AgentRun(
                run_id=f"suite-panel-{self.index}",
                agent_id=f"suite-agent-{self.index}",
                context_id=f"suite-context-{self.index}",
                role=task.role,
                model=task.model,
                prompt_hash=task.prompt_hash(),
                input_hashes=task.input_hashes(),
                raw_response=json.dumps(parsed),
                parsed_output=parsed,
            )

    suite.measure_member(
        "night_log", class_name="night_log", persona="archive conservator",
        models=models, backends=[Backend(i) for i in (1, 2, 3)],
    )
    attestation = suite.attest()
    assert attestation["qualification"]["status"] == "accepted"
    assert attestation["qualification"]["release_ready"] is True
    result = suite.artifact_results()["night_log"]
    assert result["attestation"]["human_approval"] is None
    assert result["attestation"]["agent_approval"] is not None
    assert suite.verify()["ok"]


def test_suite_is_portable_and_detects_member_lineage_mutation(tmp_path):
    """suite.portability: relative child buses replay and exact mutation fails."""
    exp, candidate = prepare_experiment(tmp_path / "source", "ledger")
    measure_directly(exp, candidate, "ledger", 90)
    suite = ArtifactSuite.create(
        tmp_path / "suite", request="Portable suite", suite_id="portable_suite",
        clock=lambda: 1_700_000_000,
    )
    suite.link_experiment("ledger", exp)
    suite.attest()

    relocated_root = tmp_path / "relocated" / "portable-suite"
    shutil.copytree(suite.root, relocated_root)
    relocated = ArtifactSuite.open(relocated_root, clock=lambda: 1_700_000_000)
    assert relocated.verify()["ok"]
    assert relocated.attestation() == suite.attestation()
    assert not Path(relocated.state["members"]["ledger"]["path"]).is_absolute()

    member = relocated.experiment("ledger")
    candidate_record = member.store.read_json(
        relocated.state["members"]["ledger"]["candidate"]
    )
    member.store.path_for(candidate_record["artifact"]).write_bytes(b"tampered")
    verification = relocated.verify()
    assert not verification["ok"]
    assert any("ledger" in failure for failure in verification["failures"])


def test_suite_verifies_legacy_member_attestation_without_agent_approval_field(
        tmp_path):
    """suite.agent-approval-backcompat: pre-agent-approval Experiment and
    Member Attestation shapes remain stable when replayed by current code."""
    exp, candidate = prepare_experiment(tmp_path / "legacy", "legacy_log")
    state = json.loads(exp.state_path.read_text())
    state.pop("agent_approvals")
    exp.state_path.write_text(json.dumps(state))
    legacy = Experiment.open(exp.root, clock=lambda: 1_700_000_000)

    suite = ArtifactSuite.create(
        tmp_path / "legacy-suite", request="Legacy archive",
        suite_id="legacy_archive", clock=lambda: 1_700_000_000,
    )
    suite.link_experiment("legacy_log", legacy, candidate=candidate)
    member = suite.store.read_json(
        suite.state["members"]["legacy_log"]["attestation"]
    )
    assert "agent_approval" not in member["artifact_attestation"]
    assert suite.verify()["ok"]


def test_attested_suite_and_selected_members_are_immutable(tmp_path):
    """suite.immutability: collection identity cannot drift after attestation."""
    exp, candidate = prepare_experiment(tmp_path / "source", "register")
    suite = ArtifactSuite.create(
        tmp_path / "suite", request="Immutable suite", suite_id="immutable_suite",
        clock=lambda: 1_700_000_000,
    )
    suite.link_experiment("register", exp, candidate=candidate)
    suite.attest()
    with pytest.raises(ValueError, match="immutable"):
        suite.create_experiment("other", request="Another artifact")
    with pytest.raises(ValueError, match="immutable"):
        suite.select_member("register")


def test_suite_rejects_nonportable_member_ids_before_writing(tmp_path):
    """suite.member-path: a caller cannot escape the portable suite root."""
    suite = ArtifactSuite.create(
        tmp_path / "suite", request="Safe suite", suite_id="safe_suite",
        clock=lambda: 1_700_000_000,
    )
    with pytest.raises(ValueError, match="member_id"):
        suite.create_experiment("../escape", request="Escape")
    assert not (tmp_path / "escape").exists()


def test_suite_revision_carries_exact_unchanged_lineage_and_invalidates_impacts(tmp_path):
    """suite.carry-forward: unchanged content reuses exact attestations while
    an impact resets only the named Experiment before candidate generation."""
    stable, stable_candidate = prepare_experiment(tmp_path / "stable", "night_log")
    changed, changed_candidate = prepare_experiment(tmp_path / "changed", "telegram")
    measure_directly(stable, stable_candidate, "night_log", 91)
    measure_directly(changed, changed_candidate, "telegram", 92)
    parent = ArtifactSuite.create(
        tmp_path / "parent", request="Observatory packet", suite_id="packet_v1",
        clock=lambda: 1_700_000_000,
    )
    parent.link_experiment("night_log", stable)
    parent.link_experiment("telegram", changed)
    parent_attestation = parent.attest()
    stable_member_ref = parent.state["members"]["night_log"]["attestation"]
    changed_member_ref = parent.state["members"]["telegram"]["attestation"]

    child = parent.revise(
        tmp_path / "child", suite_id="packet_v2",
        impacts={"telegram": "canonical disappearance time changed"},
    )

    assert child.state["parent"] == {
        "suite_id": "packet_v1",
        "attestation": parent_attestation["attestation_hash"],
    }
    assert child.state["members"]["night_log"]["attestation"] == stable_member_ref
    assert child.state["carried_forward"] == {"night_log": stable_member_ref}
    stable_child = child.experiment("night_log")
    assert stable_child.state_path.read_bytes() == parent.experiment(
        "night_log").state_path.read_bytes()
    assert stable_child.bus.path.read_bytes() == parent.experiment(
        "night_log").bus.path.read_bytes()

    impacted = child.experiment("telegram")
    assert child.state["members"]["telegram"]["attestation"] is None
    assert changed_member_ref not in child.state["carried_forward"].values()
    assert impacted.phase.value == "rubric_frozen"
    assert impacted.state["candidates"] == []
    assert impacted.state["evaluations"] == []
    assert impacted.state["standing"] is None
    assert child._qualification()["status"] == "measurement_required"
    assert child.verify()["ok"], child.verify()

    relocated_root = tmp_path / "relocated-child"
    shutil.copytree(child.root, relocated_root)
    relocated = ArtifactSuite.open(relocated_root, clock=lambda: 1_700_000_000)
    assert relocated.verify()["ok"]
