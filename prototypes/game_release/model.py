"""Pure functions for the throwaway Game Release prototype."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import PurePosixPath
from typing import Any


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def release_identity(release: dict[str, Any]) -> str:
    payload = copy.deepcopy(release)
    payload.pop("release_id", None)
    return "sha256:" + _sha256(_canonical_bytes(payload))


def _index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in items}


def _nested_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_nested_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_nested_keys(item) for item in value))
    return set()


def _phase_index(release: dict[str, Any]) -> dict[str, int]:
    return {phase["id"]: index for index, phase in enumerate(release["game"]["phases"])}


def _material_is_available(
    release: dict[str, Any], material_id: str, seat_id: str, phase: str
) -> bool:
    phases = _phase_index(release)
    rule = next(rule for rule in release["access_rules"] if rule["material"] == material_id)
    for grant in rule["grants"]:
        audience = grant["audience"]
        authorized = audience == "all" or seat_id in audience
        if authorized and phases[grant["from_phase"]] <= phases[phase]:
            return True
    return False


def validate_release(
    release: dict[str, Any], material_bytes: dict[str, bytes]
) -> list[str]:
    """Verify identity, references, material bytes, and projection boundaries."""

    findings: list[str] = []
    if release.get("release_id") != release_identity(release):
        findings.append("release_id does not match canonical release content")

    facts = _index(release["trusted"]["facts"])
    hypotheses = _index(release["trusted"]["hypotheses"])
    proof_paths = _index(release["trusted"]["proof_paths"])
    seats = _index(release["seats"])
    materials = _index(release["materials"])
    phases = _phase_index(release)

    for item in release["materials"]:
        content = material_bytes.get(item["path"])
        if content is None:
            findings.append(f"missing material bytes: {item['path']}")
        elif _sha256(content) != item["sha256"]:
            findings.append(f"material hash mismatch: {item['id']}")
        for fact_id in item["represents"]:
            if fact_id not in facts:
                findings.append(f"{item['id']} represents unknown fact {fact_id}")
        for hypothesis_id in item["supports"] + item["contradicts"]:
            if hypothesis_id not in hypotheses:
                findings.append(
                    f"{item['id']} references unknown hypothesis {hypothesis_id}"
                )

    access_materials: set[str] = set()
    for rule in release["access_rules"]:
        material_id = rule["material"]
        if material_id in access_materials:
            findings.append(f"duplicate access rule for {material_id}")
        access_materials.add(material_id)
        if material_id not in materials:
            findings.append(f"access rule references unknown material {material_id}")
        for grant in rule["grants"]:
            if grant["from_phase"] not in phases:
                findings.append(
                    f"{material_id} grant uses unknown phase {grant['from_phase']}"
                )
            audience = grant["audience"]
            if audience != "all":
                for seat_id in audience:
                    if seat_id not in seats:
                        findings.append(
                            f"{material_id} grant references unknown seat {seat_id}"
                        )
    for material_id in materials.keys() - access_materials:
        findings.append(f"material has no access rule: {material_id}")

    for seat in release["seats"]:
        for fact_id in seat["knowledge"] + seat["secrets"]:
            if fact_id not in facts:
                findings.append(f"{seat['id']} references unknown fact {fact_id}")
        for belief in seat["beliefs"]:
            if belief["hypothesis"] not in hypotheses:
                findings.append(
                    f"{seat['id']} references unknown hypothesis "
                    f"{belief['hypothesis']}"
                )
        for objective in seat["objectives"]:
            if objective["active_from"] not in phases:
                findings.append(
                    f"{objective['id']} uses unknown phase {objective['active_from']}"
                )

    for path in release["trusted"]["proof_paths"]:
        for material_id in path["requires"]:
            if material_id not in materials:
                findings.append(f"{path['id']} requires unknown material {material_id}")
        if path["concludes"] not in hypotheses:
            findings.append(
                f"{path['id']} concludes unknown hypothesis {path['concludes']}"
            )

    resolution = release["trusted"]["resolution"]
    if resolution["opens_at"] not in phases:
        findings.append("resolution opens in an unknown phase")
    if resolution["correct_hypothesis"] not in hypotheses:
        findings.append("resolution names an unknown correct hypothesis")
    for path_id in resolution["accepts_proof_paths"]:
        if path_id not in proof_paths:
            findings.append(f"resolution accepts unknown proof path {path_id}")

    if not findings:
        for seat_id in seats:
            for phase in phases:
                state = initial_session(release, "validation-session")
                state["phase"] = phase
                snapshot = project_seat(release, state, seat_id)
                forbidden = {"trusted", "verdict", "proof_paths", "correct_hypothesis"}
                if forbidden & _nested_keys(snapshot):
                    findings.append(f"trusted data leaked into {seat_id} snapshot")
        try:
            build_physical_export(release, material_bytes)
        except ValueError as error:
            findings.append(str(error))

    return findings


def initial_session(release: dict[str, Any], session_id: str) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "release_id": release["release_id"],
        "sequence": 0,
        "last_event_hash": None,
        "phase": release["game"]["phases"][0]["id"],
        "private_notes": {seat["id"]: [] for seat in release["seats"]},
        "accusations": [],
        "public_events": [],
    }


def make_event(
    release: dict[str, Any],
    state: dict[str, Any],
    actor_type: str,
    actor_id: str,
    action: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    body = {
        "schema": "kernel.session-event/v0",
        "session_id": state["session_id"],
        "release_id": release["release_id"],
        "sequence": state["sequence"] + 1,
        "previous_event_hash": state["last_event_hash"],
        "actor": {"type": actor_type, "id": actor_id},
        "action": action,
        "payload": payload,
    }
    body["event_id"] = "event." + _sha256(_canonical_bytes(body))[:16]
    body["event_hash"] = "sha256:" + _sha256(_canonical_bytes(body))
    return body


def apply_event(
    release: dict[str, Any], state: dict[str, Any], event: dict[str, Any]
) -> dict[str, Any]:
    expected_hash = "sha256:" + _sha256(
        _canonical_bytes({key: value for key, value in event.items() if key != "event_hash"})
    )
    if event["event_hash"] != expected_hash:
        raise ValueError("event hash is invalid")
    if event["release_id"] != release["release_id"]:
        raise ValueError("event belongs to another release")
    if event["session_id"] != state["session_id"]:
        raise ValueError("event belongs to another session")
    if event["sequence"] != state["sequence"] + 1:
        raise ValueError("event sequence is not contiguous")
    if event["previous_event_hash"] != state["last_event_hash"]:
        raise ValueError("event chain is broken")

    next_state = copy.deepcopy(state)
    actor = event["actor"]
    action = event["action"]
    payload = event["payload"]
    phases = [phase["id"] for phase in release["game"]["phases"]]
    seats = _index(release["seats"])

    if action == "phase_advanced":
        if actor["type"] != "host":
            raise ValueError("only the host may advance the phase")
        current = phases.index(state["phase"])
        if current + 1 >= len(phases) or payload["to_phase"] != phases[current + 1]:
            raise ValueError("phase transition is not the next declared phase")
        next_state["phase"] = payload["to_phase"]
        next_state["public_events"].append(
            {"action": action, "phase": payload["to_phase"]}
        )
    elif action == "private_note_recorded":
        if actor["type"] != "seat" or actor["id"] not in seats:
            raise ValueError("a private note requires a known seat actor")
        next_state["private_notes"][actor["id"]].append(payload["text"])
    elif action == "accusation_submitted":
        if actor["type"] != "seat" or actor["id"] not in seats:
            raise ValueError("an accusation requires a known seat actor")
        phase = next(
            phase for phase in release["game"]["phases"] if phase["id"] == state["phase"]
        )
        if "submit_accusation" not in phase["player_actions"]:
            raise ValueError("accusations are not allowed in the current phase")
        if payload["hypothesis"] not in _index(release["trusted"]["hypotheses"]):
            raise ValueError("accusation names an unknown hypothesis")
        available = {
            material["id"]
            for material in release["materials"]
            if _material_is_available(
                release, material["id"], actor["id"], state["phase"]
            )
        }
        cited = set(payload["materials"])
        if not cited <= available:
            raise ValueError("accusation cites material unavailable to the seat")
        next_state["accusations"].append(
            {
                "seat_id": actor["id"],
                "hypothesis": payload["hypothesis"],
                "materials": payload["materials"],
            }
        )
        next_state["public_events"].append(
            {"action": action, "seat_id": actor["id"]}
        )
    else:
        raise ValueError(f"unknown event action: {action}")

    next_state["sequence"] = event["sequence"]
    next_state["last_event_hash"] = event["event_hash"]
    return next_state


def replay(
    release: dict[str, Any], session_id: str, events: list[dict[str, Any]]
) -> dict[str, Any]:
    state = initial_session(release, session_id)
    for event in events:
        state = apply_event(release, state, event)
    return state


def project_seat(
    release: dict[str, Any], state: dict[str, Any], seat_id: str
) -> dict[str, Any]:
    seats = _index(release["seats"])
    if seat_id not in seats:
        raise ValueError(f"unknown seat: {seat_id}")
    seat = seats[seat_id]
    facts = _index(release["trusted"]["facts"])
    hypotheses = _index(release["trusted"]["hypotheses"])
    phases = _phase_index(release)

    available_materials = []
    for material in release["materials"]:
        if _material_is_available(release, material["id"], seat_id, state["phase"]):
            available_materials.append(
                {
                    "id": material["id"],
                    "title": material["title"],
                    "media_type": material["media_type"],
                    "sha256": material["sha256"],
                }
            )

    active_objectives = [
        {"id": objective["id"], "text": objective["text"]}
        for objective in seat["objectives"]
        if phases[objective["active_from"]] <= phases[state["phase"]]
    ]
    phase = next(
        phase for phase in release["game"]["phases"] if phase["id"] == state["phase"]
    )

    resolution = None
    if phases[release["trusted"]["resolution"]["opens_at"]] <= phases[state["phase"]]:
        resolution = {"prompt": release["trusted"]["resolution"]["prompt"]}

    return {
        "schema": "kernel.seat-snapshot/v0",
        "session_id": state["session_id"],
        "release_id": release["release_id"],
        "sequence": state["sequence"],
        "seat": {"id": seat["id"], "character": seat["character"]},
        "phase": state["phase"],
        "knowledge": [facts[fact_id]["statement"] for fact_id in seat["knowledge"]],
        "secrets": [facts[fact_id]["statement"] for fact_id in seat["secrets"]],
        "beliefs": [
            {
                "statement": hypotheses[belief["hypothesis"]]["statement"],
                "confidence": belief["confidence"],
            }
            for belief in seat["beliefs"]
        ],
        "objectives": active_objectives,
        "available_materials": available_materials,
        "visible_public_events": state["public_events"],
        "allowed_actions": phase["player_actions"],
        "private_notes": state["private_notes"][seat_id],
        "resolution": resolution,
    }


def read_material_for_seat(
    release: dict[str, Any],
    material_bytes: dict[str, bytes],
    state: dict[str, Any],
    seat_id: str,
    material_id: str,
) -> bytes:
    if not _material_is_available(release, material_id, seat_id, state["phase"]):
        raise ValueError(f"{material_id} is not authorized for {seat_id}")
    material = _index(release["materials"])[material_id]
    return material_bytes[material["path"]]


def build_physical_export(
    release: dict[str, Any], material_bytes: dict[str, bytes]
) -> dict[str, bytes]:
    """Derive a complete physical file tree from release data only."""

    output: dict[str, bytes] = {}
    config = release["physical_export"]
    phases = _phase_index(release)
    materials = _index(release["materials"])

    truth_lines = [release["game"]["title"], "", "CANONICAL TRUTH"]
    truth_lines.extend(f"- {fact['statement']}" for fact in release["trusted"]["facts"])
    truth_lines.extend(["", "ACCEPTED PROOF PATHS"])
    for path in release["trusted"]["proof_paths"]:
        truth_lines.append(f"- {path['id']}: {', '.join(path['requires'])}")
    output[f"{config['host_directory']}/truth-ledger.txt"] = (
        "\n".join(truth_lines) + "\n"
    ).encode()

    run_lines = [release["game"]["title"], "", "RUN SHEET"]
    run_lines.extend(
        f"{index + 1}. {phase['id']}" for index, phase in enumerate(release["game"]["phases"])
    )
    run_lines.extend(["", "HINTS"])
    run_lines.extend(
        f"- {hint['available_from']}: {hint['text']}" for hint in release["host"]["hints"]
    )
    output[f"{config['host_directory']}/run-sheet.txt"] = (
        "\n".join(run_lines) + "\n"
    ).encode()

    opening_state = initial_session(release, "physical-export")
    for seat in release["seats"]:
        snapshot = project_seat(release, opening_state, seat["id"])
        dossier = [snapshot["seat"]["character"]["name"], "", "WHAT YOU KNOW"]
        dossier.extend(f"- {item}" for item in snapshot["knowledge"])
        dossier.extend(["", "YOUR OBJECTIVES"])
        dossier.extend(f"- {item['text']}" for item in snapshot["objectives"])
        path = (
            f"{config['seat_directory']}/{seat['id'].removeprefix('seat.')}/"
            "opening-dossier.txt"
        )
        output[path] = ("\n".join(dossier) + "\n").encode()

    represented_grants = 0
    for rule in release["access_rules"]:
        material = materials[rule["material"]]
        filename = PurePosixPath(material["path"]).name
        for grant in rule["grants"]:
            phase_number = phases[grant["from_phase"]] + 1
            phase_dir = f"{phase_number:02d}-{grant['from_phase']}"
            audience = grant["audience"]
            if audience == "all":
                path = f"{config['phase_directory']}/{phase_dir}/PUBLIC/{filename}"
                output[path] = material_bytes[material["path"]]
                represented_grants += 1
            else:
                for seat_id in audience:
                    seat_dir = seat_id.removeprefix("seat.")
                    if grant["from_phase"] == release["game"]["phases"][0]["id"]:
                        path = (
                            f"{config['seat_directory']}/{seat_dir}/"
                            f"starting-materials/{filename}"
                        )
                    else:
                        path = (
                            f"{config['phase_directory']}/{phase_dir}/"
                            f"{seat_dir}/{filename}"
                        )
                    output[path] = material_bytes[material["path"]]
                    represented_grants += 1

    expected_grants = sum(
        1 if grant["audience"] == "all" else len(grant["audience"])
        for rule in release["access_rules"]
        for grant in rule["grants"]
    )
    if represented_grants != expected_grants:
        raise ValueError("physical export omitted an access grant")

    assembly = [
        release["game"]["title"],
        "",
        f"Release: {release['release_id']}",
        "Print HOST for the facilitator.",
        "Give each CHARACTER directory only to its named player.",
        "Seal each ROUNDS directory and open it at the named phase.",
    ]
    output[f"{config['print_directory']}/assembly.txt"] = (
        "\n".join(assembly) + "\n"
    ).encode()

    manifest = {
        "release_id": release["release_id"],
        "files": [
            {"path": path, "sha256": _sha256(content)}
            for path, content in sorted(output.items())
        ],
    }
    output[f"{config['print_directory']}/manifest.json"] = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode()
    return output
