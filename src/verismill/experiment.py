"""The public, persistent facade for a verismill experiment.

An :class:`Experiment` is the stable object around the agentic lifecycle:

    request -> research + frozen rubric -> development climb
            -> fresh blind judgment -> repeat

Agent providers remain adapters.  This module owns state, evidence, role
separation, transitions, replay, rerun preparation, and human explanation.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from . import trace
from .agents import (AgentTask, PanelExecutionError, PanelExecutionPolicy,
                     scoped_view)
from .schema import (SCHEMA_VERSION, AgentRun, ModelConfig, Phase,
                     normalize_rubric, transition_allowed, validate_research,
                     validate_requirements, validate_rubric)
from .store import ObjectStore, canonical_json, digest_bytes, refs_in


_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,79}$")


def _slug(request: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", request.lower()).strip("_")[:64]
    return slug if len(slug) >= 2 else "experiment"


def _utc(clock: Callable[[], float]) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(clock()))


class Experiment:
    """A resumable and auditable experiment bundle.

    The small ``experiment.json`` file is mutable current state.  Every
    substantive value it names is immutable and content-addressed beneath
    ``objects/``; ``bus.jsonl`` records the transition history.
    """

    def __init__(self, root: str | Path, *, clock: Callable[[], float] = time.time):
        self.root = Path(root)
        self.clock = clock
        self.state_path = self.root / "experiment.json"
        if not self.state_path.exists():
            raise FileNotFoundError(f"not a verismill experiment: {self.root}")
        self.store = ObjectStore(self.root / "objects")
        self.bus = trace.TraceBus(self.root / "bus.jsonl", clock=clock)
        self.state = json.loads(self.state_path.read_text())
        self._validate_state()

    @classmethod
    def create(cls, root: str | Path, *, request: str,
               experiment_id: str | None = None, revision: int = 1,
               parent: dict | None = None,
               clock: Callable[[], float] = time.time) -> "Experiment":
        root = Path(root)
        if root.exists() and (not root.is_dir() or any(root.iterdir())):
            raise FileExistsError(f"experiment directory is not empty: {root}")
        root.mkdir(parents=True, exist_ok=True)
        experiment_id = experiment_id or _slug(request)
        if not _ID.fullmatch(experiment_id):
            raise ValueError("experiment_id must be 2-80 lowercase slug characters")
        if not request.strip():
            raise ValueError("request must not be empty")
        state = {
            "schema_version": SCHEMA_VERSION,
            "id": experiment_id,
            "revision": int(revision),
            "request": request.strip(),
            "phase": Phase.REQUESTED.value,
            "created_at": _utc(clock),
            "updated_at": _utc(clock),
            "parent": parent,
            "refs": {},
            "agent_runs": [],
            "inherited_agent_runs": [],
            "references": [],
            "candidates": [],
            "development_rounds": [],
            "evaluations": [],
            "panel_executions": [],
            "human_reviews": [],
            "reports": [],
            "standing": None,
        }
        (root / "experiment.json").write_bytes(canonical_json(state))
        exp = cls(root, clock=clock)
        exp.bus.emit("SYS", "orchestrator", "experiment",
                     verdicts={"id": experiment_id, "revision": revision,
                               "phase": Phase.REQUESTED.value})
        return exp

    @classmethod
    def open(cls, root: str | Path, *,
             clock: Callable[[], float] = time.time) -> "Experiment":
        """Resume an existing experiment from its persisted state."""
        return cls(root, clock=clock)

    @property
    def phase(self) -> Phase:
        return Phase(self.state["phase"])

    def _validate_state(self) -> None:
        required = {"schema_version", "id", "revision", "request", "phase", "refs",
                    "agent_runs", "candidates", "development_rounds", "evaluations"}
        missing = required - set(self.state)
        if missing:
            raise ValueError(f"experiment state missing keys: {sorted(missing)}")
        if self.state["schema_version"] != SCHEMA_VERSION:
            raise ValueError(f"unsupported experiment schema: {self.state['schema_version']}")
        Phase(self.state["phase"])

    def _save(self) -> None:
        self.state["updated_at"] = _utc(self.clock)
        temporary = self.state_path.with_suffix(".json.tmp")
        temporary.write_bytes(canonical_json(self.state))
        temporary.replace(self.state_path)

    def _transition(self, target: Phase, *, reason: str) -> None:
        current = self.phase
        if not transition_allowed(current, target):
            raise ValueError(f"invalid experiment transition: {current.value} -> {target.value}")
        self.state["phase"] = target.value
        self.bus.emit("SYS", "orchestrator", "transition",
                     inputs={"state_before": digest_bytes(canonical_json({
                         "phase": current.value, "revision": self.state["revision"]}))},
                     verdicts={"from": current.value, "to": target.value,
                               "reason": reason})
        self._save()

    # -- preparation -----------------------------------------------------

    def begin_preparation(self) -> None:
        self._transition(Phase.PREPARING, reason="research and rubric preparation began")

    def source_local_reference(self, path: str | Path, *, name: str) -> str:
        """Run the existing source-contract machinery inside the experiment.

        Acquisition remains authoring-time only.  Its files are immediately
        captured as immutable objects so a later replay does not depend on the
        mutable staging directory.
        """
        if self.phase == Phase.REQUESTED:
            self.begin_preparation()
        # A blind round can reveal a sourcing debt (wrong edition, missing
        # registry rule, unsourced physical feature).  Harvesting that finding
        # is part of the climb, so reference acquisition must remain available
        # after measurement as well as during initial preparation.  The bytes
        # are still authoring-time-only and are captured immutably below.
        if self.phase not in {Phase.PREPARING, Phase.JUDGED, Phase.CLIMBING}:
            raise ValueError("references can only be added during preparation or a repair climb")
        from . import source

        if any(self.store.read_json(ref).get("name") == name
               for ref in self.state["references"]):
            raise ValueError(f"reference name is already registered: {name}")
        staging = self.root / "work" / "references"
        source_path = source.register_local(path, name, staging)
        contract_path = source.write_contract(name, staging)
        provenance_path = source_path.parent / "provenance.json"
        bundle = {
            "name": name,
            "source": self.store.put_bytes(source_path.read_bytes()),
            "provenance": self.store.put_json(json.loads(provenance_path.read_text())),
            "contract": self.store.put_json(json.loads(contract_path.read_text())),
        }
        ref = self.store.put_json(bundle)
        self.state["references"].append(ref)
        self.bus.emit("L2", "researcher", "research",
                     inputs={"operator_source": digest_bytes(Path(path).expanduser().read_bytes())},
                     outputs={"reference": ref, **bundle},
                     verdicts={"name": name, "mode": "local"})
        self._save()
        return ref

    def freeze_preparation(self, *, research: dict, rubric: dict,
                           requirements: list[dict]) -> None:
        """Freeze the evidence and scoring instrument before measurement."""
        if self.phase == Phase.REQUESTED:
            self.begin_preparation()
        if self.phase != Phase.PREPARING:
            raise ValueError(f"cannot freeze preparation while {self.phase.value}")
        rubric = normalize_rubric(rubric)
        validate_research(research)
        validate_rubric(rubric)
        validate_requirements(requirements)
        self.state["refs"].update({
            "research": self.store.put_json(research),
            "rubric": self.store.put_json(rubric),
            "requirements": self.store.put_json(requirements),
        })
        self.bus.emit("L2", "spec_author", "rubric",
                     inputs={"research": self.state["refs"]["research"]},
                     outputs={"rubric": self.state["refs"]["rubric"],
                              "requirements": self.state["refs"]["requirements"]},
                     verdicts={"frozen": True, "rubric_version": rubric["version"]})
        self._save()
        self._transition(Phase.RUBRIC_FROZEN,
                         reason="research, requirements, and rubric frozen")

    # -- agent receipts and candidates ----------------------------------

    def record_agent_run(self, run: AgentRun) -> str:
        receipt = run.to_dict()
        ref = digest_bytes(canonical_json(receipt))
        for existing_ref in [*self.state.get("inherited_agent_runs", []),
                             *self.state["agent_runs"]]:
            existing = self._run(existing_ref)
            if existing.run_id == run.run_id and existing_ref != ref:
                raise ValueError(f"agent run_id is already registered: {run.run_id}")
        ref = self.store.put_json(receipt)
        if ref not in self.state["agent_runs"]:
            self.state["agent_runs"].append(ref)
            self.bus.emit("L3", run.role, "agent_run",
                          inputs=dict(run.input_hashes),
                          outputs={"agent_run": ref},
                          verdicts={"run_id": run.run_id,
                                    "agent_id": run.agent_id,
                                    "context_id": run.context_id,
                                    "provider": run.model.provider,
                                    "model": run.model.model,
                                    "resolved_model": run.model.resolved_model,
                                    "prompt_hash": run.prompt_hash})
            self._save()
        return ref

    def invoke_agent(self, backend, task) -> str:
        """Invoke any ``AgentBackend`` and persist its provider-neutral receipt."""
        run = backend.invoke(task)
        self._validate_agent_run(run, task)
        return self.record_agent_run(run)

    @staticmethod
    def _validate_agent_run(run: AgentRun, task: AgentTask) -> None:
        if run.role != task.role:
            raise ValueError(f"backend returned role {run.role!r} for task {task.role!r}")
        if run.model != task.model:
            raise ValueError("backend receipt model does not match the assigned task model")
        if run.prompt_hash != task.prompt_hash():
            raise ValueError("backend receipt prompt hash does not match the assigned task")
        if run.input_hashes != task.input_hashes():
            raise ValueError("backend receipt input hashes do not match the assigned task")

    @staticmethod
    def _usage_total(usage: dict[str, Any]) -> int:
        total = usage.get("total_tokens")
        if isinstance(total, int) and not isinstance(total, bool) and total >= 0:
            return total
        values = []
        for key in ("input_tokens", "output_tokens"):
            value = usage.get(key, 0)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                values.append(value)
        return sum(values)

    def _record_panel_execution(self, record: dict) -> str:
        ref = self.store.put_json(record)
        self.state.setdefault("panel_executions", []).append(ref)
        self.bus.emit(
            "L1", "orchestrator", "panel_execution",
            inputs={"candidate": record["candidate"], "rubric": record["rubric"]},
            outputs={"panel_execution": ref},
            verdicts={
                "status": record["status"],
                "calls": record["calls"],
                "successful_arms": len(record["judge_runs"]),
                "total_tokens": record["usage"]["total_tokens"],
            },
        )
        self._save()
        return ref

    def _run(self, ref: str, expected_roles: set[str] | None = None) -> AgentRun:
        run = AgentRun.from_dict(self.store.read_json(ref))
        if expected_roles is not None and run.role not in expected_roles:
            raise ValueError(f"agent run {run.run_id} has role {run.role}, expected "
                             f"one of {sorted(expected_roles)}")
        return run

    def record_candidate(self, *, artifact: bytes, manifest: dict,
                         builder_run: str, explanation: dict) -> str:
        """Record a candidate and the evidence -> change causal explanation."""
        return self._record_candidate(
            artifact=artifact, manifest=manifest, builder_run=builder_run,
            explanation=explanation, emitter=None)

    def _record_candidate(self, *, artifact: bytes, manifest: dict,
                          builder_run: str, explanation: dict,
                          emitter: dict | None) -> str:
        if self.phase not in {Phase.RUBRIC_FROZEN, Phase.CLIMBING, Phase.JUDGED}:
            raise ValueError(f"cannot record a candidate while {self.phase.value}")
        if builder_run not in self.state["agent_runs"]:
            raise ValueError("candidate builder receipt is not registered in this attempt")
        self._run(builder_run, {"builder", "fixer"})
        required = {"observation", "requirement", "change"}
        if required - set(explanation):
            raise ValueError(f"candidate explanation missing: {sorted(required - set(explanation))}")
        requirement_ids = {
            item["id"] for item in self.store.read_json(self.state["refs"]["requirements"])
        }
        if explanation["requirement"] not in requirement_ids:
            raise ValueError("candidate explanation names no frozen requirement")
        artifact_ref = digest_bytes(artifact)
        if manifest.get("sha256") != artifact_ref:
            raise ValueError("candidate manifest sha256 does not match artifact bytes")
        if manifest.get("bytes") != len(artifact):
            raise ValueError("candidate manifest byte count does not match artifact bytes")
        artifact_ref = self.store.put_bytes(artifact)
        manifest_ref = self.store.put_json(manifest)
        candidate = {
            "number": len(self.state["candidates"]) + 1,
            "artifact": artifact_ref,
            "manifest": manifest_ref,
            "builder_run": builder_run,
            "rubric": self.state["refs"]["rubric"],
            "requirements": self.state["refs"]["requirements"],
            "explanation": explanation,
            "emitter": emitter,
        }
        ref = self.store.put_json(candidate)
        self.state["candidates"].append(ref)
        self.state["refs"]["current_candidate"] = ref
        self.bus.emit("L0", "builder", "candidate",
                     inputs={"rubric": candidate["rubric"],
                             "requirements": candidate["requirements"],
                             "builder_run": builder_run},
                     outputs={"candidate": ref, "artifact": artifact_ref,
                              "manifest": manifest_ref},
                     verdicts={"number": candidate["number"],
                               "change": explanation["change"]})
        self._save()
        if self.phase == Phase.RUBRIC_FROZEN:
            self._transition(Phase.CLIMBING, reason="first candidate recorded")
        elif self.phase == Phase.JUDGED:
            self._transition(Phase.CLIMBING, reason="new candidate after failed judgment")
        return ref

    def emit_candidate(self, class_name: str, *, builder_run: str,
                       explanation: dict, seed: int = 0, pins: dict | None = None,
                       canon: dict | None = None, defect: dict | None = None,
                       metadata: dict | None = None) -> str:
        """Render through mattermill and persist its artifact and manifest."""
        try:
            from mattermill import registry
        except ImportError as exc:  # pragma: no cover - packaging environment
            raise RuntimeError("emit_candidate requires the mattermill distribution") from exc
        artifact, manifest = registry.emit(class_name, pins=pins, seed=seed,
                                           canon=canon, defect=defect,
                                           metadata=metadata)
        if manifest.get("class") != class_name:
            raise ValueError("mattermill manifest class does not match the request")
        if not isinstance(manifest.get("mattermill"), str) or not manifest["mattermill"]:
            raise ValueError("mattermill manifest does not name its package version")
        emitter = {"class": class_name, "mattermill": manifest["mattermill"]}
        return self._record_candidate(
            artifact=artifact, manifest=manifest, builder_run=builder_run,
            explanation=explanation, emitter=emitter)

    def artifact_result(self, candidate: str | None = None) -> dict:
        """Materialize one recorded candidate through the public facade.

        Downstream products need the exact artifact bytes and enough trusted
        provenance to copy them into their own content-addressed stores.  They
        must not reach through :class:`Experiment` into its private object
        graph to do so.  This method returns the artifact and manifest plus an
        attestation that binds both to the experiment, frozen instrument,
        emitter, measurement status, and verification result.
        """
        candidate = candidate or self.state["refs"].get("current_candidate")
        if candidate is None:
            raise ValueError("artifact result requires a recorded candidate")
        if candidate not in self.state["candidates"]:
            raise ValueError("artifact result candidate is not part of this experiment")

        record = self.store.read_json(candidate)
        artifact = self.store.read_bytes(record["artifact"])
        manifest = self.store.read_json(record["manifest"])
        evaluations = []
        for ref in self.state["evaluations"]:
            evaluation = self.store.read_json(ref)
            if evaluation.get("candidate") == candidate:
                evaluations.append(ref)
        standing = self.state.get("standing")
        if standing and standing.get("candidate") == candidate:
            measurement_status = "accepted"
            candidate_standing = standing
        elif evaluations:
            measurement_status = "not_accepted"
            candidate_standing = None
        elif candidate == self.state["refs"].get("current_candidate") and \
                self.phase == Phase.AWAITING_BLIND_JUDGMENT:
            measurement_status = "required"
            candidate_standing = None
        else:
            measurement_status = "development_only"
            candidate_standing = None

        return {
            "schema_version": "1.0",
            "artifact": artifact,
            "manifest": manifest,
            "attestation": {
                "schema_version": "1.0",
                "experiment_id": self.state["id"],
                "experiment_revision": self.state["revision"],
                "candidate": candidate,
                "artifact_hash": record["artifact"],
                "manifest_hash": record["manifest"],
                "emitter": record.get("emitter"),
                "rubric_hash": record["rubric"],
                "requirements_hash": record["requirements"],
                "human_approval": self._human_approval(candidate),
                "measurement": {
                    "status": measurement_status,
                    "evaluation": evaluations[-1] if evaluations else None,
                    "standing": candidate_standing,
                },
                "verification": self.verify(),
            },
        }

    def record_development_round(self, *, candidate: str,
                                 judge_runs: list[str], findings: list[dict],
                                 decision: str, score: dict) -> str:
        if self.phase != Phase.CLIMBING:
            raise ValueError("development rounds only run while climbing")
        if candidate not in self.state["candidates"]:
            raise ValueError("development candidate is not part of this experiment")
        if decision not in {"select", "reject", "continue"}:
            raise ValueError("development decision must be select, reject, or continue")
        if not judge_runs:
            raise ValueError("development round requires at least one judge receipt")
        for run_ref in judge_runs:
            if run_ref not in self.state["agent_runs"]:
                raise ValueError("development judge receipt is not registered")
            self._run(run_ref, {"development_judge"})
        requirement_ids = {
            item["id"] for item in self.store.read_json(self.state["refs"]["requirements"])
        }
        for i, finding in enumerate(findings):
            needed = {"observation", "evidence", "requirement"}
            if needed - set(finding):
                raise ValueError(f"finding {i} missing: {sorted(needed - set(finding))}")
            if finding["requirement"] not in requirement_ids:
                raise ValueError(f"finding {i} names no frozen requirement")
        record = {
            "number": len(self.state["development_rounds"]) + 1,
            "candidate": candidate,
            "rubric": self.state["refs"]["rubric"],
            "judge_runs": judge_runs,
            "findings": findings,
            "decision": decision,
            "score": score,
            "blind_measurement_required": decision == "select",
        }
        ref = self.store.put_json(record)
        self.state["development_rounds"].append(ref)
        if decision == "select":
            self.state["refs"]["current_candidate"] = candidate
        self.bus.emit("L1", "development_judge", "development",
                     inputs={"candidate": candidate, "rubric": record["rubric"]},
                     outputs={"round": ref},
                     verdicts={"decision": decision, "score": score,
                               "findings": len(findings)})
        self._save()
        if decision == "select":
            self._transition(
                Phase.AWAITING_BLIND_JUDGMENT,
                reason="development selection automatically sealed for blind measurement")
        return ref

    def record_human_review(
        self,
        *,
        candidate: str,
        reviewer_id: str,
        decision: str,
        feedback: list[dict],
    ) -> str:
        """Persist first-order human direction or approval for one Candidate."""
        if self.phase not in {Phase.CLIMBING, Phase.AWAITING_BLIND_JUDGMENT}:
            raise ValueError("human review requires a development candidate")
        if candidate not in self.state["candidates"]:
            raise ValueError("human review candidate is not part of this experiment")
        if candidate != self.state["refs"].get("current_candidate"):
            raise ValueError("human review must address the current candidate")
        if not str(reviewer_id).strip():
            raise ValueError("human reviewer_id is required")
        if decision not in {"approve", "request_changes"}:
            raise ValueError("human decision must be approve or request_changes")
        if not isinstance(feedback, list):
            raise ValueError("human feedback must be a list")
        requirement_ids = {
            item["id"] for item in self.store.read_json(self.state["refs"]["requirements"])
        }
        for index, item in enumerate(feedback):
            needed = {"observation", "evidence", "requirement", "direction"}
            if not isinstance(item, dict) or needed - set(item):
                missing = needed - set(item) if isinstance(item, dict) else needed
                raise ValueError(f"human feedback {index} missing: {sorted(missing)}")
            if item["requirement"] not in requirement_ids:
                raise ValueError(f"human feedback {index} names no frozen requirement")
        record = {
            "schema_version": "1.0",
            "candidate": candidate,
            "rubric": self.state["refs"]["rubric"],
            "reviewer_id": reviewer_id.strip(),
            "decision": decision,
            "feedback": feedback,
        }
        ref = self.store.put_json(record)
        self.state.setdefault("human_reviews", []).append(ref)
        self.bus.emit(
            "L1", "user", "human_review",
            inputs={"candidate": candidate, "rubric": record["rubric"]},
            outputs={"human_review": ref},
            verdicts={
                "decision": decision,
                "reviewer_id": reviewer_id.strip(),
                "feedback_count": len(feedback),
            },
        )
        self._save()
        if decision == "request_changes" and self.phase == Phase.AWAITING_BLIND_JUDGMENT:
            self._transition(
                Phase.CLIMBING,
                reason="human review requested candidate changes before blind measurement",
            )
        return ref

    def _human_approval(self, candidate: str) -> str | None:
        for ref in reversed(self.state.get("human_reviews", [])):
            review = self.store.read_json(ref)
            if review.get("candidate") == candidate:
                return ref if review.get("decision") == "approve" else None
        return None

    def record_tell(self, *, tell_class: str, path: str, rationale: str,
                    trial_id: str, round_no: int, quote: str | None = None,
                    page: int | None = None,
                    bbox_norm: list[float] | None = None) -> dict:
        """Record quoted or visual evidence through the existing Atlas API."""
        from .climb.atlas import Atlas

        atlas = Atlas(self.root / "atlas.json")
        if quote is not None:
            tell = atlas.record(tell_class=tell_class, quote=quote, path=path,
                                rationale=rationale, trial_id=trial_id,
                                round_no=round_no)
        elif page is not None and bbox_norm is not None:
            tell = atlas.record_region(tell_class=tell_class, path=path, page=page,
                                       bbox_norm=bbox_norm, rationale=rationale,
                                       trial_id=trial_id, round_no=round_no)
        else:
            raise ValueError("a tell requires either quote or page+bbox_norm evidence")
        atlas.save()
        atlas_ref = self.store.put_bytes(atlas.path.read_bytes())
        self.state["refs"]["atlas"] = atlas_ref
        self.bus.emit("L1", "judge", "tell",
                     inputs={"trial": digest_bytes(trial_id.encode())},
                     outputs={"atlas": atlas_ref},
                     verdicts={"tell_class": tell_class, "path": path,
                               "state": tell["state"], "locus": tell["locus"]})
        self._save()
        return tell

    def assert_repair(self, *, tell_class: str, round_no: int,
                      quote: str | None = None, path: str | None = None,
                      page: int | None = None) -> dict:
        """Persist a harvest repair assertion without claiming resolution.

        Only a later blind round by non-fixers may move the tell to resolved.
        """
        if self.phase != Phase.CLIMBING:
            raise ValueError("repairs can only be asserted during a climb")
        from .climb.atlas import Atlas

        atlas = Atlas(self.root / "atlas.json")
        prior_atlas_ref = self.state["refs"].get("atlas")
        tell = atlas.assert_repair(tell_class=tell_class, quote=quote,
                                   path=path, page=page, round_no=round_no)
        atlas.save()
        atlas_ref = self.store.put_bytes(atlas.path.read_bytes())
        self.state["refs"]["atlas"] = atlas_ref
        locus = {"quote": quote} if quote is not None else {"path": path, "page": page}
        self.bus.emit("L1", "fixer", "repair_asserted",
                      inputs={"atlas_before": prior_atlas_ref or atlas_ref},
                      outputs={"atlas": atlas_ref},
                      verdicts={"tell_class": tell_class, "round": round_no,
                                "repair_status": "repair_asserted", **locus})
        self._save()
        return tell

    def resolve_repair(self, *, evaluation: str, tell_class: str,
                       quote: str | None = None, path: str | None = None,
                       page: int | None = None) -> dict:
        """Resolve an asserted repair only against the latest blind panel.

        The panel must not have re-raised the same quoted span or image page.
        This closes the loop without allowing a fixer or development review to
        certify its own work.
        """
        if self.phase not in {Phase.JUDGED, Phase.ACCEPTED}:
            raise ValueError("repair resolution requires a completed blind evaluation")
        if page is not None and path is None:
            raise ValueError("image-region repair resolution requires path and page")
        if not self.state["evaluations"] or evaluation != self.state["evaluations"][-1]:
            raise ValueError("repair resolution requires the latest recorded evaluation")
        record = self.store.read_json(evaluation)
        if record["candidate"] != self.state["refs"].get("current_candidate"):
            raise ValueError("evaluation does not measure the current candidate")
        target_quote = re.sub(r"\s+", " ", quote or "").strip().lower()
        for verdict in record["verdicts"]:
            for raised in verdict.get("tells", []):
                if raised.get("path") != path and path is not None:
                    continue
                locus = raised.get("quote_or_region", raised.get("quote"))
                if quote is not None and isinstance(locus, str) and \
                        re.sub(r"\s+", " ", locus).strip().lower() == target_quote:
                    raise ValueError("latest blind evaluation re-raised this repair")
                if page is not None and isinstance(locus, dict) and \
                        locus.get("page") == page:
                    raise ValueError("latest blind evaluation re-raised this repair")
        from .climb.atlas import Atlas

        atlas = Atlas(self.root / "atlas.json")
        prior_atlas_ref = self.state["refs"].get("atlas")
        tell = atlas.resolve(tell_class=tell_class, quote=quote,
                             path=path, page=page, round_no=record["number"])
        atlas.save()
        atlas_ref = self.store.put_bytes(atlas.path.read_bytes())
        self.state["refs"]["atlas"] = atlas_ref
        self.bus.emit(
            "L1", "blind_judge", "repair_resolved",
            inputs={"evaluation": evaluation,
                    "atlas_before": prior_atlas_ref or atlas_ref},
            outputs={"atlas": atlas_ref},
            verdicts={"tell_class": tell_class, "round": record["number"],
                      "repair_status": "resolved"})
        self._save()
        return tell

    # -- blind evaluation ------------------------------------------------

    def submit_for_blind_judgment(self, candidate: str | None = None) -> None:
        """Seal a candidate without a development selection.

        Normal forge and climb workflows use ``decision='select'``, which seals
        automatically. This explicit boundary remains for imported candidates
        and evaluation-only reruns.
        """
        if self.phase != Phase.CLIMBING:
            raise ValueError("only a climbing experiment can be submitted")
        candidate = candidate or self.state["refs"].get("current_candidate")
        if candidate not in self.state["candidates"]:
            raise ValueError("a recorded candidate is required")
        self.state["refs"]["current_candidate"] = candidate
        self._save()
        self._transition(Phase.AWAITING_BLIND_JUDGMENT,
                         reason="candidate submitted for blind judgment")

    def absolute_judge_tasks(self, *, class_name: str, persona: str,
                             models: list[ModelConfig]) -> list[AgentTask]:
        """Build isolated absolute-review tasks for a heterogeneous panel."""
        if self.phase != Phase.AWAITING_BLIND_JUDGMENT:
            raise ValueError("blind judge tasks require a sealed candidate")
        if not models:
            raise ValueError("at least one blind judge model is required")
        from .climb import judges

        if len(models) < judges.MIN_BLIND_PANEL_SIZE:
            raise ValueError(
                f"absolute blind measurement requires at least "
                f"{judges.MIN_BLIND_PANEL_SIZE} fresh judges")

        candidate = self.store.read_json(self.state["refs"]["current_candidate"])
        artifact = self.store.read_bytes(candidate["artifact"])
        rubric = self.store.read_json(self.state["refs"]["rubric"])
        scorer = rubric["scorer"]
        if scorer == "absolute-v0.2":
            lenses = judges.assign_lenses(len(models))
            schema = {
                "authenticity": "genuine | synthetic",
                "confidence": "0..1",
                "disqualifiers": {
                    key: "pass | fail" for key in judges.DISQUALIFIERS
                },
                "dimension_scores": {
                    key: "0..100" for key in judges.DIMENSIONS
                },
                "tells": [{
                    "path": "artifact filename", "quote_or_region": "evidence",
                    "rationale": "why it indicates synthesis",
                }],
            }
            briefs = [judges.build_absolute_brief(
                class_name=class_name, persona=persona, lens=lens
            ) for lens in lenses]
        elif scorer == "absolute-v0.3":
            lenses = judges.assign_rubric_lenses(rubric, len(models))
            schema = {
                "authenticity": "genuine | synthetic",
                "confidence": "0..1",
                "dimension_scores": {
                    key: "0..100" for key in judges.rubric_dimension_ids(rubric)
                },
                "tells": [{
                    "path": "artifact filename", "quote_or_region": "evidence",
                    "rationale": "why it indicates synthesis",
                }],
            }
            briefs = [judges.build_rubric_absolute_brief(
                rubric=rubric, persona=persona, primary_dimensions=lens
            ) for lens in lenses]
        else:
            raise ValueError(f"rubric scorer {scorer!r} is not an absolute scorer")
        return [
            AgentTask(role="blind_judge",
                      instructions=brief,
                      inputs={"document.pdf": artifact}, response_schema=schema,
                      model=model)
            for model, brief in zip(models, briefs, strict=True)
        ]

    def run_absolute_blind_measurement(
            self, *, class_name: str, persona: str,
            models: list[ModelConfig], backends: list[Any],
            policy: PanelExecutionPolicy | None = None) -> str:
        """Invoke and persist one complete absolute blind panel.

        Development selection has already sealed the candidate. This method is
        the provider-neutral integrated continuation: build isolated tasks,
        invoke every model arm, persist the receipts, score the required lens
        set, and transition to ``accepted`` or ``judged``.
        """
        if len(backends) != len(models):
            raise ValueError("one backend is required for every blind judge model")
        candidate = self.state["refs"].get("current_candidate")
        if candidate is None or self._human_approval(candidate) is None:
            raise ValueError(
                "public blind measurement requires human approval of the exact candidate"
            )
        tasks = self.absolute_judge_tasks(
            class_name=class_name, persona=persona, models=models)
        policy = policy or PanelExecutionPolicy()
        arm_count = len(tasks)
        call_limit = policy.max_calls or (arm_count * policy.max_attempts)
        if call_limit < arm_count:
            raise ValueError("max_calls must allow every blind panel arm one attempt")
        workers = min(policy.max_workers or arm_count, arm_count)
        pending = list(range(arm_count))
        successful: dict[int, str] = {}
        attempts: list[dict] = []
        calls = 0
        token_total = 0

        for attempt_number in range(1, policy.max_attempts + 1):
            wave = pending[:max(0, call_limit - calls)]
            if not wave:
                break
            outcomes: dict[int, tuple[AgentRun | None, Exception | None]] = {}
            with ThreadPoolExecutor(max_workers=min(workers, len(wave))) as executor:
                futures = {
                    index: executor.submit(backends[index].invoke, tasks[index])
                    for index in wave
                }
                for index in wave:
                    try:
                        run = futures[index].result()
                        self._validate_agent_run(run, tasks[index])
                        outcomes[index] = (run, None)
                    except Exception as exc:  # provider and receipt failures are retryable
                        outcomes[index] = (None, exc)
            pending = []
            for index in wave:
                calls += 1
                run, error = outcomes[index]
                if run is None:
                    attempts.append({
                        "arm": index,
                        "attempt": attempt_number,
                        "status": "failed",
                        "error_type": type(error).__name__,
                    })
                    pending.append(index)
                    continue
                run_ref = self.record_agent_run(run)
                successful[index] = run_ref
                used = self._usage_total(run.usage)
                token_total += used
                attempts.append({
                    "arm": index,
                    "attempt": attempt_number,
                    "status": "succeeded",
                    "agent_run": run_ref,
                    "total_tokens": used,
                })
            if policy.max_total_tokens is not None and token_total > policy.max_total_tokens:
                break
            if not pending:
                break

        if policy.max_total_tokens is not None and token_total > policy.max_total_tokens:
            status = "budget_exhausted"
        elif len(successful) == arm_count:
            status = "complete"
        else:
            status = "failed"
        judge_runs = [successful[index] for index in range(arm_count) if index in successful]
        record = {
            "schema_version": "1.0",
            "kind": "absolute_blind_panel",
            "candidate": self.state["refs"]["current_candidate"],
            "rubric": self.state["refs"]["rubric"],
            "policy": policy.to_dict(),
            "arms": [
                {
                    "index": index,
                    "model": task.model.to_dict(),
                    "prompt_hash": task.prompt_hash(),
                    "input_hashes": task.input_hashes(),
                }
                for index, task in enumerate(tasks)
            ],
            "attempts": attempts,
            "calls": calls,
            "usage": {"total_tokens": token_total},
            "judge_runs": judge_runs,
            "status": status,
        }
        execution_ref = self._record_panel_execution(record)
        if status != "complete":
            raise PanelExecutionError(
                f"blind panel stopped with status {status}",
                execution_ref=execution_ref,
            )
        return self.record_absolute_blind_evaluation(
            judge_runs=judge_runs, panel_execution=execution_ref)

    def _contaminated_identities(self) -> tuple[set[str], set[str]]:
        agents, contexts = set(), set()
        for ref in [*self.state.get("inherited_agent_runs", []),
                    *self.state["agent_runs"]]:
            run = self._run(ref)
            if run.role in {"builder", "fixer", "development_judge"}:
                agents.add(run.agent_id)
                contexts.add(run.context_id)
        prior_blind_refs = {
            run_ref
            for evaluation_ref in self.state["evaluations"]
            for run_ref in self.store.read_json(evaluation_ref)["judge_runs"]
        }
        for ref in prior_blind_refs:
            run = self._run(ref, {"blind_judge"})
            agents.add(run.agent_id)
            contexts.add(run.context_id)
        return agents, contexts

    def _acceptance_decision(self, scores: dict,
                             rubric_ref: str | None = None) -> tuple[bool, list[dict]]:
        rubric = self.store.read_json(rubric_ref or self.state["refs"]["rubric"])
        operators = {
            ">=": lambda a, b: a >= b, ">": lambda a, b: a > b,
            "<=": lambda a, b: a <= b, "<": lambda a, b: a < b,
            "==": lambda a, b: a == b,
        }
        results = []
        for rule in rubric["acceptance"]["rules"]:
            metric = rule["metric"]
            if metric not in scores:
                raise ValueError(f"acceptance metric {metric!r} is absent from scores")
            actual = scores[metric]
            try:
                passed = operators[rule["operator"]](actual, rule["value"])
            except TypeError as exc:
                raise ValueError(f"acceptance metric {metric!r} cannot be compared "
                                 f"with {rule['value']!r}") from exc
            results.append({**rule, "actual": actual, "passed": passed})
        for requirement in rubric["acceptance"].get("dimension_requirements", []):
            dimension = requirement["dimension"]
            try:
                actual = scores["dimension_means"][dimension]
            except KeyError as exc:
                raise ValueError(
                    f"acceptance dimension {dimension!r} is absent from scores"
                ) from exc
            try:
                passed = operators[requirement["operator"]](
                    actual, requirement["value"]
                )
            except TypeError as exc:
                raise ValueError(
                    f"acceptance dimension {dimension!r} cannot be compared "
                    f"with {requirement['value']!r}"
                ) from exc
            results.append({
                "metric": f"dimension_means.{dimension}",
                "operator": requirement["operator"],
                "value": requirement["value"],
                "actual": actual,
                "passed": passed,
            })
        return all(item["passed"] for item in results), results

    def _record_blind_evaluation(self, *, judge_runs: list[str], verdicts: list[dict],
                                 scores: dict, scorer: str,
                                 scorer_inputs: dict) -> str:
        """Persist a blind result already derived by a trusted scorer.

        This is deliberately private: callers register judge receipts, then use
        an explicit absolute or pairwise evaluation method.  Accepting arbitrary
        verdict and score JSON here would let an experiment manufacture its own
        standing without evidence from the recorded receipts.
        """
        if self.phase != Phase.AWAITING_BLIND_JUDGMENT:
            raise ValueError("experiment is not awaiting blind judgment")
        if not judge_runs or len(judge_runs) != len(verdicts):
            raise ValueError("one blind judge run is required for every verdict")
        panel_execution = scorer_inputs.get("panel_execution")
        if panel_execution is not None:
            if panel_execution not in self.state.get("panel_executions", []):
                raise ValueError("evaluation panel execution is not registered")
            execution = self.store.read_json(panel_execution)
            if execution.get("status") != "complete" \
                    or execution.get("judge_runs") != judge_runs:
                raise ValueError("evaluation requires its complete panel execution")
            prior_runs = {
                run_ref
                for ref in self.state.get("panel_executions", [])
                if ref != panel_execution
                for run_ref in self.store.read_json(ref).get("judge_runs", [])
            }
            if prior_runs.intersection(judge_runs):
                raise ValueError("a fresh panel cannot reuse an earlier execution receipt")
        contaminated_agents, contaminated_contexts = self._contaminated_identities()
        seen_agents: set[str] = set()
        seen_contexts: set[str] = set()
        for run_ref in judge_runs:
            if run_ref not in self.state["agent_runs"]:
                raise ValueError("blind judge receipt is not registered in this attempt")
            run = self._run(run_ref, {"blind_judge"})
            if run.agent_id in contaminated_agents or run.context_id in contaminated_contexts:
                raise ValueError(f"blind judge {run.agent_id}/{run.context_id} is not fresh "
                                 "for this blind evaluation")
            if run.context_id in seen_contexts:
                raise ValueError("blind judges must use independent contexts")
            if run.agent_id in seen_agents:
                raise ValueError("blind judges must use independent agent identities")
            seen_agents.add(run.agent_id)
            seen_contexts.add(run.context_id)
        rubric_ref = self.state["refs"]["rubric"]
        rubric = self.store.read_json(rubric_ref)
        if rubric["scorer"] != scorer:
            raise ValueError(
                f"rubric requires {rubric['scorer']}, not {scorer}")
        accepted, acceptance_results = self._acceptance_decision(scores)
        record = {
            "number": len(self.state["evaluations"]) + 1,
            "candidate": self.state["refs"]["current_candidate"],
            "rubric": rubric_ref,
            "judge_runs": judge_runs,
            "verdicts": verdicts,
            "scores": scores,
            "scorer": scorer,
            "scorer_inputs": scorer_inputs,
            "acceptance_results": acceptance_results,
            "accepted": accepted,
        }
        ref = self.store.put_json(record)
        self.state["evaluations"].append(ref)
        self.bus.emit("L1", "blind_judge", "evaluation",
                     inputs={"candidate": record["candidate"],
                             "rubric": record["rubric"]},
                     outputs={"evaluation": ref},
                     verdicts={"accepted": accepted, "scores": scores,
                               "scorer": scorer,
                               "acceptance_results": acceptance_results,
                               "k": len(judge_runs)})
        if accepted:
            self.state["standing"] = {
                "evaluation": ref,
                "candidate": record["candidate"],
                "rubric": record["rubric"],
                "scores": scores,
                "k": len(judge_runs),
            }
        self._save()
        self._transition(Phase.ACCEPTED if accepted else Phase.JUDGED,
                         reason="blind evaluation accepted" if accepted
                         else "blind evaluation did not meet acceptance rule")
        return ref

    def record_absolute_blind_evaluation(self, *, judge_runs: list[str],
                                         assigned_lenses: list[Any] | None = None,
                                         panel_execution: str | None = None) -> str:
        """Parse and score existing absolute-review judge receipts."""
        from .climb import judges

        if len(judge_runs) < judges.MIN_BLIND_PANEL_SIZE:
            raise ValueError(
                f"absolute blind measurement requires at least "
                f"{judges.MIN_BLIND_PANEL_SIZE} fresh judges")
        if assigned_lenses is not None and len(assigned_lenses) != len(judge_runs):
            raise ValueError("one lens is required for every blind judge run")
        rubric = self.store.read_json(self.state["refs"]["rubric"])
        scorer = rubric["scorer"]
        verdict_map = {}
        ordered = []
        for ref in judge_runs:
            run = self._run(ref, {"blind_judge"})
            if scorer == "absolute-v0.2":
                verdict = judges.parse_absolute_verdict(
                    json.dumps(run.parsed_output)
                )
            elif scorer == "absolute-v0.3":
                verdict = judges.parse_rubric_absolute_verdict(
                    json.dumps(run.parsed_output),
                    judges.rubric_dimension_ids(rubric),
                )
            else:
                raise ValueError(
                    f"rubric scorer {scorer!r} is not an absolute scorer"
                )
            verdict_map[run.run_id] = verdict
            ordered.append(verdict)
        if scorer == "absolute-v0.2":
            assigned_lenses = assigned_lenses or judges.assign_lenses(len(judge_runs))
            if not judges.coverage_ok(assigned_lenses):
                raise ValueError("absolute blind measurement must cover every judge lens")
            scores = judges.score_absolute_batch(verdict_map, assigned_lenses)
        else:
            assigned_lenses = assigned_lenses or judges.assign_rubric_lenses(
                rubric, len(judge_runs)
            )
            if not judges.rubric_coverage_ok(rubric, assigned_lenses):
                raise ValueError(
                    "absolute blind measurement must cover every rubric dimension"
                )
            scores = judges.score_rubric_absolute_batch(
                verdict_map, judges.rubric_dimension_ids(rubric), assigned_lenses
            )
        scorer_inputs = {"assigned_lenses": assigned_lenses}
        if panel_execution is not None:
            scorer_inputs["panel_execution"] = panel_execution
        return self._record_blind_evaluation(
            judge_runs=judge_runs, verdicts=ordered, scores=scores,
            scorer=scorer,
            scorer_inputs=scorer_inputs)

    def record_pairwise_blind_evaluation(self, *, keys: list[dict],
                                         judge_runs: list[str]) -> str:
        """Parse and score existing pairwise judge receipts against hidden keys."""
        from .climb import judges

        if len(judge_runs) < judges.MIN_BLIND_PANEL_SIZE:
            raise ValueError(
                f"pairwise blind measurement requires at least "
                f"{judges.MIN_BLIND_PANEL_SIZE} fresh judges")
        if not keys or len(keys) != len(judge_runs):
            raise ValueError("one hidden trial key is required for every judge run")
        verdict_map = {}
        ordered = []
        for ref in judge_runs:
            run = self._run(ref, {"blind_judge"})
            verdict = judges.parse_verdict(json.dumps(run.parsed_output))
            verdict_map[run.run_id] = verdict
            ordered.append(verdict)
        # Trial ids, rather than run ids, are the scorer join key.  Preserve
        # explicit trial_id when provided and otherwise map in order.
        joined = {}
        for key, ref, verdict in zip(keys, judge_runs, ordered, strict=True):
            run = self._run(ref)
            joined[key["trial_id"]] = verdict_map[run.run_id]
        scores = judges.score_batch(keys, joined)
        return self._record_blind_evaluation(
            judge_runs=judge_runs, verdicts=ordered, scores=scores,
            scorer="pairwise-v1", scorer_inputs={"keys": keys})

    def continue_climb(self) -> None:
        self._transition(Phase.CLIMBING, reason="failed judgment begins next climb cycle")

    def revise(self, *, reason: str) -> None:
        """Start a new experimental revision when the instrument changes."""
        if self.phase not in {Phase.JUDGED, Phase.ACCEPTED}:
            raise ValueError("a rubric revision starts after a completed evaluation")
        archive = self.store.put_json({
            "revision": self.state["revision"], "refs": self.state["refs"],
            "standing": self.state["standing"], "reason": reason,
        })
        self.state.setdefault("prior_revisions", []).append(archive)
        self.state["revision"] += 1
        self.state["refs"] = {}
        self.state["standing"] = None
        self._save()
        self._transition(Phase.PREPARING, reason=reason)

    # -- views, reports, verification -----------------------------------

    def next_actions(self) -> list[str]:
        return {
            Phase.REQUESTED: ["begin preparation"],
            Phase.PREPARING: ["complete research", "define requirements",
                              "freeze rubric"],
            Phase.RUBRIC_FROZEN: ["record a baseline candidate"],
            Phase.CLIMBING: ["run development until a candidate is selected"],
            Phase.AWAITING_BLIND_JUDGMENT: ["complete the required fresh blind panel"],
            Phase.JUDGED: ["continue climbing", "revise the rubric as a new revision"],
            Phase.ACCEPTED: ["publish standing", "revise only as a new revision"],
        }[self.phase]

    def view(self, role: str = "user") -> dict:
        refs = self.state["refs"]
        research = self.store.read_json(refs["research"]) if "research" in refs else None
        value = {
            "id": self.state["id"], "revision": self.state["revision"],
            "request": self.state["request"], "phase": self.phase.value,
            "research": research,
            "references": list(self.state.get("references", [])),
            "research_summary": ({"source_count": len(research["sources"]),
                                  "sources": research["sources"],
                                  "coverage": research["coverage"]}
                                 if research else None),
            "rubric": self.store.read_json(refs["rubric"]) if "rubric" in refs else None,
            "requirements": (self.store.read_json(refs["requirements"])
                             if "requirements" in refs else None),
            "current_candidate": (self.store.read_json(refs["current_candidate"])
                                  if "current_candidate" in refs else None),
            "candidates": [self.store.read_json(ref) for ref in self.state["candidates"]],
            "development": [self.store.read_json(ref)
                            for ref in self.state["development_rounds"]],
            "development_standing": self._development_standing(),
            "evaluations": [self.store.read_json(ref) for ref in self.state["evaluations"]],
            "human_reviews": [
                self.store.read_json(ref) for ref in self.state.get("human_reviews", [])
            ],
            "atlas_summary": self._atlas_summary(),
            "standing": self.state["standing"],
            "measurement": self._measurement_status(),
            "next_actions": self.next_actions(),
        }
        if role == "blind_judge":
            candidate = value["current_candidate"]
            value["current_candidate"] = ({"artifact": candidate["artifact"]}
                                          if candidate else None)
            value["trial_packet"] = {
                "artifact": candidate["artifact"] if candidate else None,
                "rubric": refs.get("rubric"),
            }
        if role == "auditor":
            value.update({"state": self.state, "events": self.replay()})
        return scoped_view(value, role)

    def _development_standing(self) -> dict | None:
        """Expose climb progress without manufacturing release standing."""
        candidate = self.state["refs"].get("current_candidate")
        if candidate is None:
            return None
        matching = []
        for ref in self.state["development_rounds"]:
            record = self.store.read_json(ref)
            if record.get("candidate") == candidate:
                matching.append((ref, record))
        if not matching:
            return None
        ref, record = matching[-1]
        return {
            "status": "progress_only",
            "release_claim": False,
            "round": ref,
            "candidate": candidate,
            "decision": record["decision"],
            "score": record["score"],
        }

    def _measurement_status(self) -> dict:
        """Describe whether the current candidate has completed blind measurement."""
        candidate = self.state["refs"].get("current_candidate")
        evaluations = []
        if candidate:
            for ref in self.state["evaluations"]:
                evaluation = self.store.read_json(ref)
                if evaluation.get("candidate") == candidate:
                    evaluations.append((ref, evaluation))
        standing = self.state.get("standing")
        if standing and standing.get("candidate") == candidate:
            status = "accepted"
        elif evaluations:
            status = "not_accepted"
        elif self.phase == Phase.AWAITING_BLIND_JUDGMENT:
            status = "required"
        elif candidate:
            status = "development_only"
        else:
            status = "no_candidate"
        return {
            "status": status,
            "blind_required": candidate is not None and status != "accepted",
            "candidate": candidate,
            "evaluation": evaluations[-1][0] if evaluations else None,
        }

    def _atlas_summary(self) -> dict | None:
        if "atlas" not in self.state["refs"]:
            return None
        snapshot = self.store.read_json(self.state["refs"]["atlas"])
        counts: dict[str, int] = {}
        for tell in snapshot.get("tells", []):
            counts[tell["state"]] = counts.get(tell["state"], 0) + 1
        return {"tells": len(snapshot.get("tells", [])), "by_state": counts}

    def replay(self) -> list[dict]:
        """Replay recorded events without invoking any model."""
        return trace.TraceBus.read(self.bus.path)

    def verify(self) -> dict:
        failures: list[str] = []
        bus_ok = trace.TraceBus.verify(self.bus.path)
        events: list[dict] = []
        if not bus_ok:
            failures.append("bus hash chain is invalid")
        else:
            try:
                events = self.replay()
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                bus_ok = False
                failures.append(f"bus event schema is invalid: {exc}")
        event_count = len(events)
        pending = list(dict.fromkeys(refs_in(self.state)))
        checked: set[str] = set()
        while pending:
            ref = pending.pop()
            if ref in checked:
                continue
            if not self.store.verify(ref):
                failures.append(f"missing or corrupt object: {ref}")
                continue
            checked.add(ref)
            try:
                pending.extend(refs_in(self.store.read_json(ref)))
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
        event_agent_runs = {
            event["output_refs"].get("agent_run") for event in events
            if event["event_type"] == "agent_run"
        }
        for run_ref in self.state.get("agent_runs", []):
            try:
                self._run(run_ref)
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                failures.append(f"invalid agent receipt {run_ref}: {exc}")
            if run_ref not in event_agent_runs:
                failures.append(f"agent receipt has no bus event: {run_ref}")
        for candidate_ref in self.state.get("candidates", []):
            try:
                candidate = self.store.read_json(candidate_ref)
                artifact = self.store.read_bytes(candidate["artifact"])
                manifest = self.store.read_json(candidate["manifest"])
                if manifest.get("sha256") != candidate["artifact"]:
                    failures.append(f"candidate manifest digest mismatch: {candidate_ref}")
                if manifest.get("bytes") != len(artifact):
                    failures.append(f"candidate manifest byte mismatch: {candidate_ref}")
                emitter = candidate.get("emitter")
                if emitter is not None and emitter != {
                        "class": manifest.get("class"),
                        "mattermill": manifest.get("mattermill")}:
                    failures.append(
                        f"candidate emitter provenance mismatch: {candidate_ref}")
                known_runs = [*self.state.get("inherited_agent_runs", []),
                              *self.state.get("agent_runs", [])]
                if candidate.get("builder_run") not in known_runs:
                    failures.append(f"candidate builder receipt is not registered: {candidate_ref}")
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                failures.append(f"invalid candidate {candidate_ref}: {exc}")
        event_evaluations = {
            event["output_refs"].get("evaluation") for event in events
            if event["event_type"] == "evaluation"
        }
        for evaluation_ref in self.state.get("evaluations", []):
            try:
                self._verify_evaluation(evaluation_ref)
            except (OSError, ValueError, KeyError, TypeError,
                    json.JSONDecodeError) as exc:
                failures.append(f"invalid evaluation {evaluation_ref}: {exc}")
            if evaluation_ref not in event_evaluations:
                failures.append(f"evaluation has no bus event: {evaluation_ref}")
        event_panel_executions = {
            event["output_refs"].get("panel_execution") for event in events
            if event["event_type"] == "panel_execution"
        }
        for execution_ref in self.state.get("panel_executions", []):
            try:
                self._verify_panel_execution(execution_ref)
            except (OSError, ValueError, KeyError, TypeError,
                    json.JSONDecodeError) as exc:
                failures.append(f"invalid panel execution {execution_ref}: {exc}")
            if execution_ref not in event_panel_executions:
                failures.append(
                    f"panel execution has no bus event: {execution_ref}"
                )
        for run_ref in self.state.get("inherited_agent_runs", []):
            try:
                self._run(run_ref)
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                failures.append(f"invalid inherited agent receipt {run_ref}: {exc}")
        event_human_reviews = {
            event["output_refs"].get("human_review") for event in events
            if event["event_type"] == "human_review"
        }
        for review_ref in self.state.get("human_reviews", []):
            try:
                review = self.store.read_json(review_ref)
                if review.get("candidate") not in self.state.get("candidates", []):
                    raise ValueError("review names no recorded candidate")
                candidate = self.store.read_json(review["candidate"])
                if review.get("rubric") != candidate.get("rubric"):
                    raise ValueError("review rubric differs from candidate")
                if review.get("decision") not in {"approve", "request_changes"}:
                    raise ValueError("review decision is invalid")
                if not str(review.get("reviewer_id", "")).strip():
                    raise ValueError("reviewer_id is missing")
                feedback = review.get("feedback")
                if not isinstance(feedback, list):
                    raise ValueError("review feedback is invalid")
                requirement_ids = {
                    item["id"] for item in self.store.read_json(
                        candidate["requirements"]
                    )
                }
                for item in feedback:
                    required = {"observation", "evidence", "requirement", "direction"}
                    if not isinstance(item, dict) or required - set(item):
                        raise ValueError("review feedback is incomplete")
                    if item["requirement"] not in requirement_ids:
                        raise ValueError("review feedback names no frozen requirement")
            except (OSError, ValueError, KeyError, TypeError,
                    json.JSONDecodeError) as exc:
                failures.append(f"invalid human review {review_ref}: {exc}")
            if review_ref not in event_human_reviews:
                failures.append(f"human review has no bus event: {review_ref}")
        if self.state.get("standing"):
            evaluation_ref = self.state["standing"].get("evaluation")
            if evaluation_ref not in self.state["evaluations"]:
                failures.append("standing does not name a recorded evaluation")
            elif not self.store.read_json(evaluation_ref).get("accepted"):
                failures.append("standing was not derived from an accepted evaluation")
            else:
                evaluation = self.store.read_json(evaluation_ref)
                expected = {
                    "evaluation": evaluation_ref,
                    "candidate": evaluation["candidate"],
                    "rubric": evaluation["rubric"],
                    "scores": evaluation["scores"],
                    "k": len(evaluation["judge_runs"]),
                }
                if self.state["standing"] != expected:
                    failures.append("standing does not match its accepted evaluation")
        return {"ok": not failures, "failures": failures,
                "objects_verified": len(checked),
                "events_verified": event_count if bus_ok else 0}

    def _verify_evaluation(self, evaluation_ref: str) -> None:
        """Replay a persisted scorer from immutable judge receipts."""
        from .climb import judges

        evaluation = self.store.read_json(evaluation_ref)
        judge_runs = evaluation["judge_runs"]
        execution_ref = evaluation.get("scorer_inputs", {}).get("panel_execution")
        if execution_ref is not None:
            self._verify_panel_execution(execution_ref)
            execution = self.store.read_json(execution_ref)
            if execution["status"] != "complete":
                raise ValueError("evaluation names an incomplete panel execution")
            if execution["judge_runs"] != judge_runs:
                raise ValueError("evaluation judge runs differ from its panel execution")
            if execution["candidate"] != evaluation["candidate"] \
                    or execution["rubric"] != evaluation["rubric"]:
                raise ValueError("evaluation lineage differs from its panel execution")
        verdicts = []
        if evaluation["scorer"] == "absolute-v0.2":
            verdict_map = {}
            for ref in judge_runs:
                run = self._run(ref, {"blind_judge"})
                verdict = judges.parse_absolute_verdict(json.dumps(run.parsed_output))
                verdict_map[run.run_id] = verdict
                verdicts.append(verdict)
            lenses = evaluation["scorer_inputs"]["assigned_lenses"]
            if len(lenses) != len(judge_runs):
                raise ValueError("absolute scorer lens count does not match judge count")
            scores = judges.score_absolute_batch(verdict_map, lenses)
        elif evaluation["scorer"] == "absolute-v0.3":
            rubric = self.store.read_json(evaluation["rubric"])
            dimension_ids = judges.rubric_dimension_ids(rubric)
            verdict_map = {}
            for ref in judge_runs:
                run = self._run(ref, {"blind_judge"})
                verdict = judges.parse_rubric_absolute_verdict(
                    json.dumps(run.parsed_output), dimension_ids
                )
                verdict_map[run.run_id] = verdict
                verdicts.append(verdict)
            lenses = evaluation["scorer_inputs"]["assigned_lenses"]
            if len(lenses) != len(judge_runs):
                raise ValueError("absolute scorer lens count does not match judge count")
            if not judges.rubric_coverage_ok(rubric, lenses):
                raise ValueError(
                    "absolute scorer lenses do not cover the frozen rubric"
                )
            scores = judges.score_rubric_absolute_batch(
                verdict_map, dimension_ids, lenses
            )
        elif evaluation["scorer"] == "pairwise-v1":
            keys = evaluation["scorer_inputs"]["keys"]
            if len(keys) != len(judge_runs):
                raise ValueError("pairwise key count does not match judge count")
            joined = {}
            for key, ref in zip(keys, judge_runs, strict=True):
                run = self._run(ref, {"blind_judge"})
                verdict = judges.parse_verdict(json.dumps(run.parsed_output))
                verdicts.append(verdict)
                joined[key["trial_id"]] = verdict
            scores = judges.score_batch(keys, joined)
        else:
            raise ValueError(f"unknown scorer {evaluation.get('scorer')!r}")
        if evaluation["verdicts"] != verdicts:
            raise ValueError("stored verdicts differ from parsed judge receipts")
        if evaluation["scores"] != scores:
            raise ValueError("stored scores differ from replayed scorer output")
        accepted, results = self._acceptance_decision(scores, evaluation["rubric"])
        if evaluation["accepted"] != accepted or evaluation["acceptance_results"] != results:
            raise ValueError("stored acceptance differs from frozen rubric replay")

    def _verify_panel_execution(self, execution_ref: str) -> None:
        record = self.store.read_json(execution_ref)
        required = {
            "schema_version", "kind", "candidate", "rubric", "policy", "arms",
            "attempts", "calls", "usage", "judge_runs", "status",
        }
        missing = required - set(record)
        if missing:
            raise ValueError(f"panel execution missing keys: {sorted(missing)}")
        if record["schema_version"] != "1.0" \
                or record["kind"] != "absolute_blind_panel":
            raise ValueError("unsupported panel execution contract")
        if record["candidate"] not in self.state.get("candidates", []):
            raise ValueError("panel execution names no recorded candidate")
        if record["rubric"] != self.store.read_json(record["candidate"])["rubric"]:
            raise ValueError("panel execution rubric differs from its candidate")
        policy = PanelExecutionPolicy(**record["policy"])
        arms = record["arms"]
        if not isinstance(arms, list) or not arms:
            raise ValueError("panel execution requires arms")
        if [arm.get("index") for arm in arms] != list(range(len(arms))):
            raise ValueError("panel execution arms are not in assigned order")
        attempts = record["attempts"]
        if record["calls"] != len(attempts):
            raise ValueError("panel execution call count differs from attempts")
        if policy.max_calls is not None and record["calls"] > policy.max_calls:
            raise ValueError("panel execution exceeded max_calls")
        successes: dict[int, str] = {}
        token_total = 0
        previous = (0, -1)
        for attempt in attempts:
            key = (attempt["attempt"], attempt["arm"])
            if key <= previous:
                raise ValueError("panel attempts are not in deterministic order")
            previous = key
            if attempt["attempt"] > policy.max_attempts:
                raise ValueError("panel execution exceeded max_attempts")
            if attempt["arm"] not in range(len(arms)):
                raise ValueError("panel attempt names an unknown arm")
            if attempt["status"] == "succeeded":
                if attempt["arm"] in successes:
                    raise ValueError("panel execution retried a successful arm")
                run_ref = attempt["agent_run"]
                run = self._run(run_ref, {"blind_judge"})
                arm = arms[attempt["arm"]]
                if run.model.to_dict() != arm["model"] \
                        or run.prompt_hash != arm["prompt_hash"] \
                        or run.input_hashes != arm["input_hashes"]:
                    raise ValueError("panel receipt differs from its assigned arm")
                used = self._usage_total(run.usage)
                if attempt["total_tokens"] != used:
                    raise ValueError("panel attempt usage differs from receipt")
                token_total += used
                successes[attempt["arm"]] = run_ref
            elif attempt["status"] != "failed" or not attempt.get("error_type"):
                raise ValueError("panel attempt has an unsupported outcome")
        expected_runs = [successes[index] for index in range(len(arms))
                         if index in successes]
        if record["judge_runs"] != expected_runs:
            raise ValueError("panel judge runs are not the final successful arms")
        if record["usage"] != {"total_tokens": token_total}:
            raise ValueError("panel execution usage cannot be replayed")
        budget_exhausted = policy.max_total_tokens is not None \
            and token_total > policy.max_total_tokens
        expected_status = (
            "budget_exhausted" if budget_exhausted
            else "complete" if len(successes) == len(arms)
            else "failed"
        )
        if record["status"] != expected_status:
            raise ValueError("panel execution status cannot be replayed")

    def report(self) -> str:
        view = self.view("user")
        lines = [f"# Experiment: {view['id']} (revision {view['revision']})", "",
                 f"**Objective:** {view['request']}", "",
                 f"**State:** `{view['phase']}`", ""]
        research = view.get("research_summary")
        if research:
            lines += ["## Research", "",
                      f"{research['source_count']} source(s) recorded.", ""]
            for source in research["sources"]:
                provenance = json.dumps(source["provenance"], sort_keys=True)
                lines.append(
                    f"- **{source['id']}** ({source['kind']}): `{provenance}`")
            lines.append("")
            for dimension, coverage in research["coverage"].items():
                lines.append(f"- {dimension}: {coverage}")
            lines.append("")
        rubric = view.get("rubric")
        if rubric:
            lines += [f"## Rubric {rubric['version']} (frozen)", ""]
            lines.append(f"Scorer: `{rubric['scorer']}`")
            lines.append("")
            for dimension in rubric["dimensions"]:
                lines.append(f"- **{dimension['id']}** — {dimension['description']}")
            lines += ["", "Acceptance rules:"]
            for rule in rubric["acceptance"]["rules"]:
                lines.append(
                    f"- `{rule['metric']} {rule['operator']} {rule['value']}`")
            lines.append("")
        if view["candidates"]:
            lines += ["## Candidates", ""]
            for item in view["candidates"]:
                explanation = item["explanation"]
                manifest = self.store.read_json(item["manifest"])
                lines.append(f"### Candidate {item['number']}")
                lines.append("")
                lines.append(f"- **Artifact:** `{item['artifact']}`")
                if manifest.get("class"):
                    lines.append(f"- **Emitter:** `{manifest['class']}` "
                                 f"mattermill `{manifest.get('mattermill', 'unknown')}`, "
                                 f"seed `{manifest.get('seed')}`")
                lines.append(f"- **Observation:** {explanation['observation']}")
                lines.append(f"- **Requirement:** {explanation['requirement']}")
                lines.append(f"- **Change:** {explanation['change']}")
                if explanation.get("evidence"):
                    lines.append(f"- **Evidence:** {explanation['evidence']}")
                lines.append("")
        if view["development"]:
            lines += ["## Development climb", ""]
            for item in view["development"]:
                lines.append(f"### Round {item['number']} — {item['decision']}")
                lines.append("")
                lines.append(f"Score: `{json.dumps(item['score'], sort_keys=True)}`")
                lines.append("")
                for finding in item["findings"]:
                    lines.append(f"- **Observation:** {finding['observation']}")
                    lines.append(f"  **Evidence:** {finding['evidence']}")
                    lines.append(f"  **Requirement:** {finding['requirement']}")
                lines.append("")
        if view.get("human_reviews"):
            lines += ["## Human oversight", ""]
            for item in view["human_reviews"]:
                lines.append(
                    f"- **{item['decision']}** by `{item['reviewer_id']}` for "
                    f"Candidate `{item['candidate']}`"
                )
                for feedback in item["feedback"]:
                    lines.append(
                        f"  - {feedback['observation']} → {feedback['direction']} "
                        f"(`{feedback['requirement']}`)"
                    )
            lines.append("")
        if view["evaluations"]:
            lines += ["## Blind evaluations", ""]
            for item in view["evaluations"]:
                outcome = "accepted" if item["accepted"] else "not accepted"
                panel = []
                for run_ref in item["judge_runs"]:
                    run = self._run(run_ref)
                    panel.append(run.model.resolved_model or run.model.model)
                lines.append(f"- Evaluation {item['number']}: **{outcome}**, "
                             f"scorer `{item['scorer']}`, k={len(item['judge_runs'])}, "
                             f"panel `{json.dumps(panel)}`, scores "
                             f"`{json.dumps(item['scores'], sort_keys=True)}`")
            lines.append("")
        if view.get("atlas_summary"):
            lines += ["## Evidence atlas", "",
                      f"{view['atlas_summary']['tells']} tell(s) recorded: "
                      f"`{json.dumps(view['atlas_summary']['by_state'], sort_keys=True)}`.", ""]
        lines += ["## Conclusion", ""]
        if view["standing"]:
            lines.append("The candidate earned standing in the recorded blind evaluation.")
        elif view["measurement"]["status"] == "required":
            lines.append("The selected candidate is sealed, but its required blind panel "
                         "is incomplete. It is not an accepted result.")
        else:
            lines.append("No accepted standing has been earned yet.")
        lines += ["", "Next: " + "; ".join(view["next_actions"]), "",
                  "## Verification", "",
                  "Every score and explanation above is backed by content-addressed "
                  "records in this experiment bundle and the hash-chained event bus.", ""]
        return "\n".join(lines)

    def write_report(self, path: str | Path | None = None) -> Path:
        path = Path(path) if path else self.root / "report.md"
        path.write_text(self.report())
        report_ref = self.store.put_bytes(path.read_bytes())
        self.state["reports"].append(report_ref)
        self._save()
        self.bus.emit("SYS", "auditor", "report",
                     outputs={"report": report_ref})
        return path

    # -- rerun ------------------------------------------------------------

    def rerun(self, destination: str | Path, *, from_phase: str = "development") -> "Experiment":
        """Create a new attempt with frozen inputs copied by content hash.

        ``development`` retains research/rubric/requirements.
        ``evaluation`` additionally retains the selected candidate and starts
        awaiting a fresh judge panel.  Original model responses remain in this
        bundle for replay and are never presented as a deterministic rerun.
        """
        if from_phase not in {"development", "evaluation"}:
            raise ValueError("from_phase must be development or evaluation")
        if self.phase in {Phase.REQUESTED, Phase.PREPARING}:
            raise ValueError("preparation must be frozen before it can be rerun")
        child = Experiment.create(destination, request=self.state["request"],
                                  experiment_id=self.state["id"],
                                  revision=self.state["revision"],
                                  parent={"path": str(self.root),
                                          "state": "pending",
                                          "from_phase": from_phase},
                                  clock=self.clock)
        # The parent snapshot is an object, not a bare checksum: verification
        # can therefore prove both its bytes and the claimed lineage.
        child.state["parent"]["state"] = child.store.put_bytes(
            self.state_path.read_bytes())
        # The immutable parent snapshot is itself a graph root.  Preserve all
        # objects it names so lineage verification survives relocation even
        # though only the selected frozen inputs are promoted into child state.
        for ref in dict.fromkeys(refs_in(self.state)):
            if self.store.verify(ref):
                self.store.copy_graph(ref, child.store)
        for name in ("research", "rubric", "requirements"):
            if name in self.state["refs"]:
                ref = self.state["refs"][name]
                self.store.copy_graph(ref, child.store)
                child.state["refs"][name] = ref
        for ref in self.state.get("references", []):
            self.store.copy_graph(ref, child.store)
            child.state["references"].append(ref)
        child.state["phase"] = Phase.RUBRIC_FROZEN.value
        if from_phase == "evaluation":
            candidate = self.state["refs"].get("current_candidate")
            if not candidate:
                raise ValueError("evaluation rerun needs a selected candidate")
            self.store.copy_graph(candidate, child.store)
            child.state["candidates"] = [candidate]
            child.state["refs"]["current_candidate"] = candidate
            builder_run = child.store.read_json(candidate)["builder_run"]
            child.state["inherited_agent_runs"] = [builder_run]
            child.state["phase"] = Phase.AWAITING_BLIND_JUDGMENT.value
        child._save()
        child.bus.emit("SYS", "orchestrator", "rerun",
                       inputs={"parent_state": child.state["parent"]["state"]},
                       verdicts={"from_phase": from_phase,
                                 "phase": child.state["phase"]})
        return child
