"""Merge static document capabilities with user-owned experiment standing."""

from __future__ import annotations

from pathlib import Path

from .experiment import Experiment
from .paths import experiments_root, user_data_root
from .schema import AgentRun


def derive_local_standings(
        root: str | Path | None = None) -> tuple[dict[str, list[dict]], list[dict]]:
    """Return verified accepted experiments grouped by emitter class.

    Invalid bundles are reported, never silently promoted or mutated. Direct
    byte candidates with no mattermill class remain valid experiments but do
    not become class standing.
    """
    root = Path(root) if root is not None else experiments_root()
    standings: dict[str, list[dict]] = {}
    errors: list[dict] = []
    if not root.is_dir():
        return standings, errors
    for state_path in sorted(root.rglob("experiment.json")):
        exp_root = state_path.parent
        try:
            exp = Experiment.open(exp_root)
            verification = exp.verify()
            if not verification["ok"]:
                errors.append({"path": str(exp_root),
                               "failures": verification["failures"]})
                continue
            standing = exp.state.get("standing")
            if not standing:
                continue
            candidate = exp.store.read_json(standing["candidate"])
            emitter = candidate.get("emitter")
            if not emitter:
                continue
            manifest = exp.store.read_json(candidate["manifest"])
            class_name = emitter["class"]
            evaluation = exp.store.read_json(standing["evaluation"])
            panel = []
            for run_ref in evaluation["judge_runs"]:
                run = AgentRun.from_dict(exp.store.read_json(run_ref))
                panel.append({
                    "provider": run.model.provider,
                    "model": run.model.model,
                    "resolved_model": run.model.resolved_model,
                })
            record = {
                "status": "accepted",
                "class": class_name,
                "experiment_id": exp.state["id"],
                "revision": exp.state["revision"],
                "updated_at": exp.state["updated_at"],
                "path": str(exp_root),
                "candidate": standing["candidate"],
                "artifact": candidate["artifact"],
                "evaluation": standing["evaluation"],
                "rubric": standing["rubric"],
                "scorer": evaluation["scorer"],
                "scores": standing["scores"],
                "k": standing["k"],
                "panel": panel,
                "mattermill": emitter["mattermill"],
            }
            standings.setdefault(class_name, []).append(record)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append({"path": str(exp_root), "failures": [str(exc)]})
    for records in standings.values():
        records.sort(key=lambda value: (value["updated_at"], value["path"]),
                     reverse=True)
    return standings, errors


def class_catalog(root: str | Path | None = None) -> dict:
    """Static mattermill capabilities plus optional local accepted standing."""
    try:
        from mattermill import registry
    except ImportError as exc:  # pragma: no cover - packaging environment
        raise RuntimeError("class catalog requires the mattermill distribution") from exc
    standings, errors = derive_local_standings(root)
    classes = []
    for capability in registry.list_classes():
        item = dict(capability)
        records = standings.get(item["name"], [])
        current = next((record for record in records
                        if record["mattermill"] == item["mattermill"]), None)
        item["local_standing"] = current
        item["latest_historical_standing"] = (
            records[0] if current is None and records else None)
        classes.append(item)
    return {
        "experiment_root": str(Path(root) if root is not None else experiments_root()),
        "classes": classes,
        "errors": errors,
    }
