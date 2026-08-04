"""Pure model functions for the throwaway game-definition prototype."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


TOP_LEVEL_KEYS = {
    "schema",
    "id",
    "title",
    "profile",
    "direction",
    "phases",
    "truth",
    "hypotheses",
    "characters",
    "evidence",
    "proof_paths",
    "reveals",
    "resolution",
}


def _index(items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in items}


def validate_game(game: dict[str, Any]) -> list[str]:
    """Return human-readable findings; an empty list means references resolve."""

    findings: list[str] = []
    missing = TOP_LEVEL_KEYS - game.keys()
    extra = game.keys() - TOP_LEVEL_KEYS
    if missing:
        findings.append(f"missing top-level keys: {', '.join(sorted(missing))}")
    if extra:
        findings.append(
            "definition embeds concerns outside the prototype: "
            + ", ".join(sorted(extra))
        )
    if missing:
        return findings

    facts = _index(game["truth"]["facts"])
    hypotheses = _index(game["hypotheses"])
    characters = _index(game["characters"])
    evidence = _index(game["evidence"])
    proof_paths = _index(game["proof_paths"])
    phases = game["phases"]

    collections = {
        "facts": (game["truth"]["facts"], facts),
        "hypotheses": (game["hypotheses"], hypotheses),
        "characters": (game["characters"], characters),
        "evidence": (game["evidence"], evidence),
        "proof paths": (game["proof_paths"], proof_paths),
    }
    for label, (items, indexed) in collections.items():
        if len(items) != len(indexed):
            findings.append(f"{label} contain a duplicate id")

    for character in game["characters"]:
        for fact_id in character["knows"] + character["hides"]:
            if fact_id not in facts:
                findings.append(f"{character['id']} references unknown fact {fact_id}")
        for belief in character["believes"]:
            if belief["hypothesis"] not in hypotheses:
                findings.append(
                    f"{character['id']} believes unknown hypothesis "
                    f"{belief['hypothesis']}"
                )

    for item in game["evidence"]:
        for fact_id in item["represents"]:
            if fact_id not in facts:
                findings.append(f"{item['id']} represents unknown fact {fact_id}")
        for hypothesis_id in item["supports"] + item["contradicts"]:
            if hypothesis_id not in hypotheses:
                findings.append(
                    f"{item['id']} references unknown hypothesis {hypothesis_id}"
                )

    revealed_evidence: dict[str, str] = {}
    for reveal in game["reveals"]:
        if reveal["at"] not in phases:
            findings.append(f"{reveal['id']} uses unknown phase {reveal['at']}")
        recipients = reveal["to"]
        if recipients != "all":
            for character_id in recipients:
                if character_id not in characters:
                    findings.append(
                        f"{reveal['id']} names unknown character {character_id}"
                    )
        for evidence_id in reveal["evidence"]:
            if evidence_id not in evidence:
                findings.append(
                    f"{reveal['id']} references unknown evidence {evidence_id}"
                )
            elif evidence_id in revealed_evidence:
                findings.append(
                    f"{evidence_id} is scheduled by both "
                    f"{revealed_evidence[evidence_id]} and {reveal['id']}"
                )
            else:
                revealed_evidence[evidence_id] = reveal["id"]

    for path in game["proof_paths"]:
        for evidence_id in path["requires"]:
            if evidence_id not in evidence:
                findings.append(
                    f"{path['id']} requires unknown evidence {evidence_id}"
                )
            elif evidence_id not in revealed_evidence:
                findings.append(
                    f"{path['id']} requires evidence that is never revealed: "
                    f"{evidence_id}"
                )
        if path["concludes"] not in hypotheses:
            findings.append(
                f"{path['id']} concludes unknown hypothesis {path['concludes']}"
            )

    resolution = game["resolution"]
    if resolution["opens_at"] not in phases:
        findings.append(
            f"resolution uses unknown phase {resolution['opens_at']}"
        )
    if resolution["correct_hypothesis"] not in hypotheses:
        findings.append(
            "resolution references unknown correct hypothesis "
            f"{resolution['correct_hypothesis']}"
        )
    for path_id in resolution["accepts_proof_paths"]:
        path = proof_paths.get(path_id)
        if path is None:
            findings.append(f"resolution accepts unknown proof path {path_id}")
        elif path["concludes"] != resolution["correct_hypothesis"]:
            findings.append(
                f"resolution accepts {path_id}, which concludes "
                f"{path['concludes']} instead of the correct hypothesis"
            )

    return findings


def seat_snapshot(
    game: dict[str, Any], character_id: str, phase: str
) -> dict[str, Any]:
    """Project only information available to one character at a phase."""

    character = _index(game["characters"])[character_id]
    facts = _index(game["truth"]["facts"])
    hypotheses = _index(game["hypotheses"])
    evidence = _index(game["evidence"])
    phase_number = game["phases"].index(phase)

    available_evidence: list[dict[str, str]] = []
    for reveal in game["reveals"]:
        recipients = reveal["to"]
        is_recipient = recipients == "all" or character_id in recipients
        if is_recipient and game["phases"].index(reveal["at"]) <= phase_number:
            for evidence_id in reveal["evidence"]:
                item = evidence[evidence_id]
                available_evidence.append(
                    {"id": item["id"], "title": item["title"], "finding": item["finding"]}
                )

    resolution = None
    if game["phases"].index(game["resolution"]["opens_at"]) <= phase_number:
        resolution = {"prompt": game["resolution"]["prompt"]}

    return {
        "seat": {"id": character["id"], "name": character["name"]},
        "phase": phase,
        "knowledge": [facts[fact_id]["statement"] for fact_id in character["knows"]],
        "secrets": [facts[fact_id]["statement"] for fact_id in character["hides"]],
        "beliefs": [
            {
                "statement": hypotheses[belief["hypothesis"]]["statement"],
                "confidence": belief["confidence"],
            }
            for belief in character["believes"]
        ],
        "objectives": character["objectives"],
        "available_evidence": available_evidence,
        "resolution": resolution,
    }


def author_snapshot(game: dict[str, Any]) -> dict[str, Any]:
    """Expose the trusted author view of truth, proof, and disclosure."""

    return {
        "direction": game["direction"],
        "truth": game["truth"],
        "hypotheses": game["hypotheses"],
        "proof_paths": game["proof_paths"],
        "reveals": game["reveals"],
        "resolution": game["resolution"],
    }
