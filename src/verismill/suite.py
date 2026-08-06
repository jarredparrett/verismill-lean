"""Public aggregation of independently measured artifact Experiments."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import shutil
import time
from typing import Any, Callable

from . import trace
from .agents import PanelExecutionPolicy
from .experiment import Experiment
from .schema import ModelConfig
from .store import ObjectStore, canonical_json, digest_bytes


SUITE_SCHEMA_VERSION = "1.0"
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,79}$")
_PHASES = frozenset({"assembling", "attested"})


def _utc(clock: Callable[[], float]) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(clock()))


class ArtifactSuite:
    """A selected collection of exact, independently replayable Experiments.

    The suite owns only membership and collection qualification. Each child
    Experiment remains authoritative for its candidate, rubric, receipts,
    measurement, and Artifact Attestation.
    """

    def __init__(self, root: str | Path, *, clock: Callable[[], float] = time.time):
        self.root = Path(root)
        self.clock = clock
        self.state_path = self.root / "suite.json"
        if not self.state_path.exists():
            raise FileNotFoundError(f"not a verismill artifact suite: {self.root}")
        self.store = ObjectStore(self.root / "objects")
        self.bus = trace.TraceBus(self.root / "bus.jsonl", clock=clock)
        self.state = json.loads(self.state_path.read_text())
        self._validate_state()

    @classmethod
    def create(
        cls,
        root: str | Path,
        *,
        request: str,
        suite_id: str,
        parent: dict | None = None,
        clock: Callable[[], float] = time.time,
    ) -> "ArtifactSuite":
        root = Path(root)
        if root.exists() and (not root.is_dir() or any(root.iterdir())):
            raise FileExistsError(f"suite directory is not empty: {root}")
        if not _ID.fullmatch(suite_id):
            raise ValueError("suite_id must be 2-80 lowercase slug characters")
        if not request.strip():
            raise ValueError("suite request must not be empty")
        root.mkdir(parents=True, exist_ok=True)
        state = {
            "schema_version": SUITE_SCHEMA_VERSION,
            "id": suite_id,
            "request": request.strip(),
            "phase": "assembling",
            "created_at": _utc(clock),
            "updated_at": _utc(clock),
            "members": {},
            "refs": {},
            "parent": parent,
            "carried_forward": {},
            "impacts": {},
        }
        (root / "suite.json").write_bytes(canonical_json(state))
        suite = cls(root, clock=clock)
        suite.bus.emit(
            "SYS",
            "orchestrator",
            "suite",
            verdicts={"id": suite_id, "phase": "assembling"},
        )
        return suite

    @classmethod
    def open(
        cls, root: str | Path, *, clock: Callable[[], float] = time.time
    ) -> "ArtifactSuite":
        return cls(root, clock=clock)

    @property
    def phase(self) -> str:
        return self.state["phase"]

    def _validate_state(self) -> None:
        required = {"schema_version", "id", "request", "phase", "members", "refs"}
        missing = required - set(self.state)
        if missing:
            raise ValueError(f"suite state missing keys: {sorted(missing)}")
        if self.state["schema_version"] != SUITE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported artifact suite schema: {self.state['schema_version']}"
            )
        if self.state["phase"] not in _PHASES:
            raise ValueError(f"unsupported artifact suite phase: {self.state['phase']}")
        if not isinstance(self.state["members"], dict):
            raise ValueError("suite members must be a mapping")

    def _save(self) -> None:
        self.state["updated_at"] = _utc(self.clock)
        temporary = self.state_path.with_suffix(".json.tmp")
        temporary.write_bytes(canonical_json(self.state))
        temporary.replace(self.state_path)

    def _require_assembling(self) -> None:
        if self.phase != "assembling":
            raise ValueError("an attested artifact suite is immutable")

    @staticmethod
    def _validate_member_id(member_id: str) -> None:
        if not _ID.fullmatch(member_id):
            raise ValueError("member_id must be 2-80 lowercase slug characters")

    def _new_member(self, member_id: str, experiment: Experiment) -> None:
        self._validate_member_id(member_id)
        if member_id in self.state["members"]:
            raise ValueError(f"suite member already exists: {member_id}")
        relative = Path("experiments") / member_id
        self.state["members"][member_id] = {
            "path": relative.as_posix(),
            "experiment_id": experiment.state["id"],
            "candidate": None,
            "attestation": None,
        }
        self.bus.emit(
            "SYS",
            "orchestrator",
            "suite_member",
            inputs={"experiment_state": digest_bytes(experiment.state_path.read_bytes())},
            verdicts={"member_id": member_id, "status": "created"},
        )
        self._save()

    def create_experiment(
        self,
        member_id: str,
        *,
        request: str,
        experiment_id: str | None = None,
    ) -> Experiment:
        """Create one independent child Experiment in this suite workspace."""
        self._require_assembling()
        self._validate_member_id(member_id)
        if member_id in self.state["members"]:
            raise ValueError(f"suite member already exists: {member_id}")
        target = self.root / "experiments" / member_id
        experiment = Experiment.create(
            target,
            request=request,
            experiment_id=experiment_id or member_id,
            clock=self.clock,
        )
        self._new_member(member_id, experiment)
        return experiment

    @staticmethod
    def _copy_experiment(source: Experiment, target: Path) -> None:
        if target.exists():
            raise FileExistsError(f"suite experiment path already exists: {target}")
        target.mkdir(parents=True)
        (target / "experiment.json").write_bytes(source.state_path.read_bytes())
        (target / "bus.jsonl").write_bytes(source.bus.path.read_bytes())
        target_objects = target / "objects"
        target_objects.mkdir()
        for path in sorted(source.store.root.iterdir(), key=lambda item: item.name):
            if path.is_file() and not path.is_symlink() and re.fullmatch(
                r"[0-9a-f]{64}", path.name
            ):
                shutil.copyfile(path, target_objects / path.name)

    def link_experiment(
        self, member_id: str, experiment: Experiment, *, candidate: str | None = None
    ) -> str:
        """Snapshot and select an existing verified Experiment as one member."""
        self._require_assembling()
        self._validate_member_id(member_id)
        verification = experiment.verify()
        if not verification["ok"]:
            raise ValueError(
                f"cannot link unverified experiment: {verification['failures']}"
            )
        if member_id in self.state["members"]:
            raise ValueError(f"suite member already exists: {member_id}")
        target = self.root / "experiments" / member_id
        self._copy_experiment(experiment, target)
        copied = Experiment.open(target, clock=self.clock)
        self._new_member(member_id, copied)
        return self.select_member(member_id, candidate=candidate)

    def experiment(self, member_id: str) -> Experiment:
        try:
            member = self.state["members"][member_id]
        except KeyError as exc:
            raise KeyError(f"unknown suite member: {member_id}") from exc
        relative = Path(member["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"suite member path is not portable: {member['path']}")
        return Experiment.open(self.root / relative, clock=self.clock)

    def _member_material(
        self, member_id: str, experiment: Experiment, candidate: str | None
    ) -> dict:
        result = experiment.artifact_result(candidate)
        if not result["attestation"]["verification"]["ok"]:
            raise ValueError(f"suite member experiment is not verified: {member_id}")
        return {
            "schema_version": SUITE_SCHEMA_VERSION,
            "member_id": member_id,
            "experiment_id": experiment.state["id"],
            "experiment_revision": experiment.state["revision"],
            "experiment_state_hash": digest_bytes(experiment.state_path.read_bytes()),
            "experiment_bus_hash": digest_bytes(experiment.bus.path.read_bytes()),
            "candidate": result["attestation"]["candidate"],
            "artifact_attestation": result["attestation"],
        }

    def select_member(self, member_id: str, *, candidate: str | None = None) -> str:
        """Freeze one member to an exact Candidate and Artifact Attestation."""
        self._require_assembling()
        member = self.state["members"].get(member_id)
        if member is None:
            raise KeyError(f"unknown suite member: {member_id}")
        experiment = self.experiment(member_id)
        material = self._member_material(member_id, experiment, candidate)
        ref = self.store.put_json(material)
        if member["attestation"] is not None:
            if member["attestation"] == ref:
                return ref
            raise ValueError(f"suite member is already selected: {member_id}")
        member["candidate"] = material["candidate"]
        member["attestation"] = ref
        self.bus.emit(
            "SYS",
            "orchestrator",
            "suite_member",
            inputs={
                "experiment_state": material["experiment_state_hash"],
                "experiment_bus": material["experiment_bus_hash"],
                "artifact": material["artifact_attestation"]["artifact_hash"],
            },
            outputs={"member_attestation": ref},
            verdicts={
                "member_id": member_id,
                "status": material["artifact_attestation"]["measurement"]["status"],
            },
        )
        self._save()
        return ref

    def measure_member(
        self,
        member_id: str,
        *,
        class_name: str,
        persona: str,
        models: list[ModelConfig],
        backends: list[Any],
        policy: PanelExecutionPolicy | None = None,
    ) -> str:
        """Run and freeze one member's public absolute measurement workflow."""
        self._require_assembling()
        member = self.state["members"].get(member_id)
        if member is None:
            raise KeyError(f"unknown suite member: {member_id}")
        if member["attestation"] is not None:
            raise ValueError(f"suite member is already selected: {member_id}")
        experiment = self.experiment(member_id)
        evaluation = experiment.run_absolute_blind_measurement(
            class_name=class_name,
            persona=persona,
            models=models,
            backends=backends,
            policy=policy,
        )
        self.select_member(member_id)
        return evaluation

    def revise(
        self,
        destination: str | Path,
        *,
        suite_id: str,
        impacts: dict[str, str],
        request: str | None = None,
    ) -> "ArtifactSuite":
        """Create a child suite with explicit content-hash impact handling.

        Unchanged members preserve their exact Experiment snapshot, Candidate,
        Artifact Attestation, and Member Attestation.  Every impacted member is
        reset through ``Experiment.rerun(..., from_phase="development")`` so
        it must produce a child Candidate and fresh blind measurement before
        the new suite can earn accepted qualification.
        """
        if self.phase != "attested":
            raise ValueError("suite revision requires an attested parent")
        verification = self.verify()
        if not verification["ok"]:
            raise ValueError(f"cannot revise invalid suite: {verification['failures']}")
        if not isinstance(impacts, dict) or any(
            member_id not in self.state["members"] or not isinstance(reason, str)
            or not reason.strip()
            for member_id, reason in impacts.items()
        ):
            raise ValueError("impacts must map known member ids to nonempty reasons")
        parent_attestation = self.state["refs"]["attestation"]
        child = ArtifactSuite.create(
            destination,
            request=request or self.state["request"],
            suite_id=suite_id,
            parent={
                "suite_id": self.state["id"],
                "attestation": parent_attestation,
            },
            clock=self.clock,
        )
        self.store.copy_graph(parent_attestation, child.store)
        child.state["refs"]["parent_attestation"] = parent_attestation
        for member_id, member in sorted(self.state["members"].items()):
            parent_experiment = self.experiment(member_id)
            parent_member_attestation = member["attestation"]
            if member_id in impacts:
                rerun = parent_experiment.rerun(
                    child.root / "experiments" / member_id,
                    from_phase="development",
                )
                child._new_member(member_id, rerun)
                child.state["impacts"][member_id] = impacts[member_id].strip()
                child.bus.emit(
                    "SYS", "orchestrator", "suite_member",
                    inputs={"member_attestation": parent_member_attestation},
                    verdicts={
                        "member_id": member_id,
                        "status": "remeasure_required",
                        "reason": impacts[member_id].strip(),
                    },
                )
                child._save()
                continue
            target = child.root / "experiments" / member_id
            self._copy_experiment(parent_experiment, target)
            copied = Experiment.open(target, clock=self.clock)
            child._new_member(member_id, copied)
            carried_ref = child.select_member(
                member_id, candidate=member["candidate"])
            if carried_ref != parent_member_attestation:
                raise ValueError(
                    f"unchanged member did not preserve its attestation: {member_id}"
                )
            child.state["carried_forward"][member_id] = carried_ref
            child.bus.emit(
                "SYS", "orchestrator", "suite_member",
                inputs={"member_attestation": parent_member_attestation},
                outputs={"member_attestation": carried_ref},
                verdicts={"member_id": member_id, "status": "carried_forward"},
            )
            child._save()
        return child

    def artifact_results(self) -> dict[str, dict]:
        """Materialize every selected artifact through the child public facade."""
        verification = self.verify()
        if not verification["ok"]:
            raise ValueError(f"artifact suite is not verified: {verification['failures']}")
        results = {}
        for member_id, member in sorted(self.state["members"].items()):
            if member["candidate"] is None:
                raise ValueError(f"suite member is not selected: {member_id}")
            results[member_id] = self.experiment(member_id).artifact_result(
                member["candidate"]
            )
        return results

    def _qualification(self) -> dict:
        statuses = Counter()
        for member in self.state["members"].values():
            if member["attestation"] is None:
                statuses["unselected"] += 1
                continue
            material = self.store.read_json(member["attestation"])
            statuses[
                material["artifact_attestation"]["measurement"]["status"]
            ] += 1
        member_count = len(self.state["members"])
        if member_count and statuses["accepted"] == member_count:
            status = "accepted"
        elif statuses["not_accepted"]:
            status = "not_accepted"
        elif statuses["required"] or statuses["unselected"]:
            status = "measurement_required"
        else:
            status = "development_only"
        return {
            "evidence_class": "artifact_realism",
            "status": status,
            "member_count": member_count,
            "status_counts": dict(sorted(statuses.items())),
            "release_ready": status == "accepted",
        }

    def _attestation_material(self) -> dict:
        members = []
        for member_id, member in sorted(self.state["members"].items()):
            if member["attestation"] is None:
                raise ValueError(f"suite member is not selected: {member_id}")
            material = self.store.read_json(member["attestation"])
            members.append(
                {
                    "member_id": member_id,
                    "member_attestation": member["attestation"],
                    "experiment_id": material["experiment_id"],
                    "experiment_revision": material["experiment_revision"],
                    "candidate": material["candidate"],
                    "artifact_hash": material["artifact_attestation"]["artifact_hash"],
                    "manifest_hash": material["artifact_attestation"]["manifest_hash"],
                    "measurement_status": material["artifact_attestation"]["measurement"]["status"],
                }
            )
        if not members:
            raise ValueError("artifact suite requires at least one selected member")
        return {
            "schema_version": SUITE_SCHEMA_VERSION,
            "suite_id": self.state["id"],
            "request": self.state["request"],
            "parent": self.state.get("parent"),
            "members": members,
            "qualification": self._qualification(),
        }

    def attest(self) -> dict:
        """Seal the selected collection and return its content-addressed claim."""
        self._require_assembling()
        verification = self.verify()
        if not verification["ok"]:
            raise ValueError(f"cannot attest invalid suite: {verification['failures']}")
        material = self._attestation_material()
        ref = self.store.put_json(material)
        self.state["refs"]["attestation"] = ref
        self.state["phase"] = "attested"
        self.bus.emit(
            "SYS",
            "auditor",
            "suite_attestation",
            inputs={
                item["member_id"]: item["member_attestation"]
                for item in material["members"]
            },
            outputs={"attestation": ref},
            verdicts=material["qualification"],
        )
        self._save()
        return {"attestation_hash": ref, **material}

    def attestation(self) -> dict | None:
        ref = self.state["refs"].get("attestation")
        return {"attestation_hash": ref, **self.store.read_json(ref)} if ref else None

    def replay(self) -> dict:
        """Replay suite membership plus every authoritative member bus."""
        return {
            "suite": trace.TraceBus.read(self.bus.path),
            "members": {
                member_id: self.experiment(member_id).replay()
                for member_id in sorted(self.state["members"])
            },
        }

    def verify(self) -> dict:
        failures = []
        events = []
        if not trace.TraceBus.verify(self.bus.path):
            failures.append("suite bus hash chain is invalid")
        else:
            try:
                events = trace.TraceBus.read(self.bus.path)
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                failures.append(f"suite bus event schema is invalid: {exc}")
        selected_events = {
            event["output_refs"].get("member_attestation")
            for event in events
            if event["event_type"] == "suite_member"
        }
        parent = self.state.get("parent")
        parent_material = None
        if parent is not None:
            parent_ref = self.state.get("refs", {}).get("parent_attestation")
            if parent.get("attestation") != parent_ref \
                    or parent_ref is None or not self.store.verify(parent_ref):
                failures.append("parent suite attestation is missing or corrupt")
            else:
                parent_material = self.store.read_json(parent_ref)
                if parent_material.get("suite_id") != parent.get("suite_id"):
                    failures.append("parent suite identity differs from its attestation")
        for member_id, member in sorted(self.state["members"].items()):
            try:
                experiment = self.experiment(member_id)
                verification = experiment.verify()
                if not verification["ok"]:
                    failures.append(
                        f"member {member_id} experiment is invalid: {verification['failures']}"
                    )
                if member["experiment_id"] != experiment.state["id"]:
                    failures.append(f"member {member_id} experiment identity changed")
                if member["attestation"] is not None:
                    if not self.store.verify(member["attestation"]):
                        failures.append(f"member {member_id} attestation is corrupt")
                        continue
                    material = self.store.read_json(member["attestation"])
                    expected = self._member_material(
                        member_id, experiment, member["candidate"]
                    )
                    if material != expected:
                        failures.append(f"member {member_id} lineage changed")
                    if member["attestation"] not in selected_events:
                        failures.append(f"member {member_id} selection has no suite event")
                    carried = self.state.get("carried_forward", {}).get(member_id)
                    if carried is not None and carried != member["attestation"]:
                        failures.append(
                            f"member {member_id} carry-forward lineage changed"
                        )
                    if carried is not None and parent_material is not None:
                        parent_members = {
                            item["member_id"]: item
                            for item in parent_material.get("members", [])
                        }
                        parent_member = parent_members.get(member_id)
                        if parent_member is None or parent_member.get(
                                "member_attestation") != carried:
                            failures.append(
                                f"member {member_id} was not carried from its parent"
                            )
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                failures.append(f"member {member_id} cannot be verified: {exc}")
        final_ref = self.state["refs"].get("attestation")
        if self.phase == "attested":
            if final_ref is None or not self.store.verify(final_ref):
                failures.append("suite attestation is missing or corrupt")
            else:
                try:
                    stored = self.store.read_json(final_ref)
                    if stored != self._attestation_material():
                        failures.append("suite attestation does not match its members")
                    attested_events = {
                        event["output_refs"].get("attestation")
                        for event in events
                        if event["event_type"] == "suite_attestation"
                    }
                    if final_ref not in attested_events:
                        failures.append("suite attestation has no bus event")
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                    failures.append(f"suite attestation cannot be replayed: {exc}")
        elif final_ref is not None:
            failures.append("assembling suite unexpectedly names an attestation")
        for member_id in self.state.get("impacts", {}):
            member = self.state["members"].get(member_id)
            if member is None:
                failures.append(f"impact names unknown member {member_id}")
            elif member_id in self.state.get("carried_forward", {}):
                failures.append(f"impacted member {member_id} was carried forward")
        return {
            "ok": not failures,
            "failures": failures,
            "members_verified": len(self.state["members"]) if not failures else 0,
            "events_verified": len(events),
        }

    def report(self) -> str:
        qualification = self._qualification()
        lines = [
            f"# Artifact Suite: {self.state['id']}",
            "",
            f"**Objective:** {self.state['request']}",
            "",
            f"**State:** `{self.phase}`",
            "",
            "## Artifact-realism qualification",
            "",
            f"Status: `{qualification['status']}`",
            "",
        ]
        for member_id, member in sorted(self.state["members"].items()):
            status = "unselected"
            if member["attestation"]:
                material = self.store.read_json(member["attestation"])
                status = material["artifact_attestation"]["measurement"]["status"]
            lines.append(f"- `{member_id}` — {status}")
        lines += [
            "",
            "Member rubric scores remain namespaced to their Experiments and are not averaged.",
        ]
        return "\n".join(lines) + "\n"
