"""The atlas: the climb's shared memory of how we get caught.

Every tell a judge cites lands here with its quoted evidence and the trial
that produced it. Lifecycle (evidence-of-k, thresholds from the spec):

    reported → corroborated (≥k DISTINCT trials) → clause_candidate → promoted
             ↘ stale (no sighting in M rounds) → regression_probe → archived

Two design rules: corroboration counts distinct trials, not total mentions
(one loud trial is not evidence); and a tell that stops appearing triggers a
regression probe, not silent archiving — quiet might mean fixed or might
mean the judges went blind.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

STATES = ("reported", "corroborated", "clause_candidate", "promoted",
          "stale", "regression_probe", "archived")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


class Atlas:
    def __init__(self, path: str | Path, *, corroboration_k: int = 3,
                 stale_after_rounds: int = 5):
        self.path = Path(path)
        self.k = corroboration_k
        self.stale_after = stale_after_rounds
        self.tells: list[dict] = []
        if self.path.exists():
            data = json.loads(self.path.read_text())
            self.tells = data["tells"]

    # -- recording ----------------------------------------------------------

    def record(self, *, tell_class: str, quote: str, path: str,
               rationale: str, trial_id: str, round_no: int) -> dict:
        """Record one sighting. Dedupes on (class, normalized quote): a repeat
        sighting in a new trial adds evidence, not a new entry."""
        key = (tell_class, _norm(quote))
        for tell in self.tells:
            if (tell["tell_class"], _norm(tell["quote"])) == key:
                if trial_id not in tell["sightings"]:
                    tell["sightings"].append(trial_id)
                    tell["last_seen_round"] = round_no
                    self._maybe_corroborate(tell)
                return tell
        tell = {
            "tell_class": tell_class, "quote": quote, "path": path,
            "rationale": rationale, "state": "reported",
            "sightings": [trial_id],
            "first_seen_round": round_no, "last_seen_round": round_no,
        }
        self.tells.append(tell)
        self._maybe_corroborate(tell)
        return tell

    def _maybe_corroborate(self, tell: dict) -> None:
        if tell["state"] == "reported" and len(tell["sightings"]) >= self.k:
            tell["state"] = "corroborated"

    # -- lifecycle ----------------------------------------------------------

    def promote_candidates(self) -> list[dict]:
        """Corroborated tells awaiting a spec clause."""
        return [t for t in self.tells if t["state"] == "corroborated"]

    def mark_clause_candidate(self, tell_class: str, quote: str) -> None:
        tell = self._find(tell_class, quote)
        if tell["state"] != "corroborated":
            raise ValueError(f"cannot mark clause_candidate from state {tell['state']!r}")
        tell["state"] = "clause_candidate"

    def mark_promoted(self, tell_class: str, quote: str, clause_id: str) -> None:
        tell = self._find(tell_class, quote)
        if tell["state"] != "clause_candidate":
            raise ValueError(f"cannot promote from state {tell['state']!r}")
        tell["state"] = "promoted"
        tell["clause_id"] = clause_id

    def tick(self, round_no: int) -> list[dict]:
        """Advance the round clock. Active tells not sighted within
        stale_after_rounds move to stale; stale tells need a regression probe
        before they may archive. Returns tells that changed state."""
        changed = []
        for tell in self.tells:
            if tell["state"] in ("reported", "corroborated", "clause_candidate"):
                if round_no - tell["last_seen_round"] >= self.stale_after:
                    tell["state"] = "stale"
                    changed.append(tell)
        return changed

    def mark_regression_probe(self, tell_class: str, quote: str) -> None:
        tell = self._find(tell_class, quote)
        if tell["state"] != "stale":
            raise ValueError(f"cannot regression-probe from state {tell['state']!r}")
        tell["state"] = "regression_probe"

    def archive(self, tell_class: str, quote: str) -> None:
        tell = self._find(tell_class, quote)
        if tell["state"] != "regression_probe":
            raise ValueError(f"cannot archive from state {tell['state']!r} "
                             "(stale tells must pass a regression probe first)")
        tell["state"] = "archived"

    def _find(self, tell_class: str, quote: str) -> dict:
        for tell in self.tells:
            if tell["tell_class"] == tell_class and _norm(tell["quote"]) == _norm(quote):
                return tell
        raise KeyError(f"tell not found: {tell_class} / {quote[:40]}")

    # -- views ----------------------------------------------------------------

    def active(self) -> list[dict]:
        return [t for t in self.tells
                if t["state"] in ("reported", "corroborated", "clause_candidate")]

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for tell in self.tells:
            counts[tell["state"]] = counts.get(tell["state"], 0) + 1
        return {"tells": len(self.tells), "by_state": counts,
                "corroboration_k": self.k, "stale_after_rounds": self.stale_after}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(
            {"corroboration_k": self.k, "stale_after_rounds": self.stale_after,
             "tells": self.tells}, indent=2, sort_keys=True) + "\n")
