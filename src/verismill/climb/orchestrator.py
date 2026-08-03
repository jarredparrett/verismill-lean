"""The orchestrator: deterministic event loop for the climb.

Not an LLM. It owns the accept/reject rule, the seed vault, checkpoints, and
the trigger table that turns artifact arrivals into the next materialization
(event-driven, per the loop-engineering design). Agents propose; the
orchestrator applies; the bus remembers everything.

Acceptance rule (L1): a spec revision is accepted iff its judge batch shows
synth_vs_real accuracy STRICTLY below the checkpoint best by more than the
CI margin — monotone hill-climb toward chance (0.5), the score a perfect
world earns.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .. import trace

CI_MARGIN = 0.05


def _hash_canonical(obj) -> str:
    """Hash of the canonical-JSON form — what pins a batch's keys and verdicts
    to the bus event that scored them."""
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


class Orchestrator:
    def __init__(self, root: str | Path, bus: trace.TraceBus):
        self.root = Path(root)
        self.bus = bus
        self.state_path = self.root / "state.json"
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text())
        else:
            self.state = {"round": 0, "best_accuracy": 1.0, "spec_version": None,
                          "checkpoints": []}

    # -- triggers (the event table) ------------------------------------------

    def on_judge_batch(self, *, keys: list[dict], verdicts: dict[str, dict],
                       spec_version: str) -> dict:
        """Trigger: judge_batch_complete → score → accept/reject → checkpoint."""
        from . import judges as judge_mod

        scores = judge_mod.score_batch(keys, verdicts)
        self.state["round"] += 1
        round_no = self.state["round"]
        accuracy = scores["synth_vs_real_accuracy"]

        accepted = (accuracy is not None
                    and accuracy < self.state["best_accuracy"] - CI_MARGIN)
        event_type = "accept" if accepted else "reject"
        self.bus.emit("L1", "orchestrator", event_type, spec_version=spec_version,
                      inputs={"keys": _hash_canonical(keys),
                              "verdicts": _hash_canonical(verdicts)},
                      verdicts={"accuracy": accuracy, "round": round_no,
                                "best": self.state["best_accuracy"], **scores})
        if accepted:
            self.state["best_accuracy"] = accuracy
            self.state["spec_version"] = spec_version
            self._checkpoint(spec_version, round_no, scores)
            self.bus.emit("L1", "orchestrator", "status", spec_version=spec_version,
                          verdicts={"checkpointed": True, "round": round_no})

        stall = trace.detect_stall(
            trace.TraceBus.read(self.bus.path), max_consecutive_rejects=5)
        if stall:
            self.bus.emit("SYS", "system", "stall", verdicts=stall)
        self._save()
        return {"accepted": accepted, "scores": scores, "round": round_no,
                "stalled": stall is not None}

    def on_atlas_threshold(self, *, tell_class: str, sightings: int) -> None:
        """Trigger: atlas ≥k in one tell class → spec-author round needed."""
        self.bus.emit("L1", "orchestrator", "promotion",
                      verdicts={"tell_class": tell_class, "sightings": sightings,
                                "needs": "spec_author_round"})

    def heartbeat(self) -> None:
        self.bus.emit("SYS", "system", "heartbeat")

    # -- checkpoints ------------------------------------------------------------

    def _checkpoint(self, spec_version: str, round_no: int, scores: dict) -> None:
        cp = self.root / "checkpoints" / f"round_{round_no:04d}"
        cp.mkdir(parents=True, exist_ok=True)
        (cp / "scores.json").write_text(json.dumps(scores, indent=2, sort_keys=True) + "\n")
        (cp / "spec_version.txt").write_text(spec_version + "\n")
        self.state["checkpoints"].append(str(cp.relative_to(self.root)))

    def _save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2, sort_keys=True) + "\n")
