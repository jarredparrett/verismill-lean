#!/usr/bin/env python3
"""PROTOTYPE: replay one release and inspect trusted, seat, and print views."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from model import (
    build_physical_export,
    make_event,
    project_seat,
    replay,
    validate_release,
)


HERE = Path(__file__).resolve().parent
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def load_bundle() -> tuple[dict[str, Any], dict[str, bytes]]:
    release = json.loads((HERE / "release.json").read_text(encoding="utf-8"))
    materials = {
        material["path"]: (HERE / material["path"]).read_bytes()
        for material in release["materials"]
    }
    return release, materials


def append_action(
    release: dict[str, Any], ui: dict[str, Any], action: str
) -> None:
    state = replay(release, ui["session_id"], ui["events"])
    seat_id = release["seats"][ui["seat_index"]]["id"]
    phases = [phase["id"] for phase in release["game"]["phases"]]

    if action == "advance":
        current = phases.index(state["phase"])
        if current + 1 >= len(phases):
            raise ValueError("already at the final phase")
        event = make_event(
            release,
            state,
            "host",
            "host.primary",
            "phase_advanced",
            {"to_phase": phases[current + 1]},
        )
    elif action == "note":
        event = make_event(
            release,
            state,
            "seat",
            seat_id,
            "private_note_recorded",
            {"text": "Compare the access log with the physical traces."},
        )
    elif action == "accuse":
        snapshot = project_seat(release, state, seat_id)
        event = make_event(
            release,
            state,
            "seat",
            seat_id,
            "accusation_submitted",
            {
                "hypothesis": "hypothesis.evelyn",
                "materials": [item["id"] for item in snapshot["available_materials"]],
            },
        )
    else:
        raise ValueError(action)
    replay(release, ui["session_id"], [*ui["events"], event])
    ui["events"].append(event)


def render(
    release: dict[str, Any], materials: dict[str, bytes], ui: dict[str, Any]
) -> None:
    print("\033[2J\033[H", end="")
    state = replay(release, ui["session_id"], ui["events"])
    print(f"{BOLD}PROTOTYPE — Game Release boundary{RESET}")
    print(
        f"{DIM}{release['game']['title']} · {release['release_id'][:28]}… · "
        f"{len(ui['events'])} events{RESET}\n"
    )

    if ui["view"] == "trusted":
        print(f"{BOLD}Trusted release view{RESET}")
        value = {
            "source": release["source"],
            "trusted": release["trusted"],
            "access_rules": release["access_rules"],
        }
    elif ui["view"] == "physical":
        print(f"{BOLD}Derived physical export{RESET}")
        exported = build_physical_export(release, materials)
        value = {
            "file_count": len(exported),
            "paths": sorted(exported),
        }
    elif ui["view"] == "events":
        print(f"{BOLD}Append-only events and replayed state{RESET}")
        value = {"events": ui["events"], "replayed_state": state}
    else:
        seat_id = release["seats"][ui["seat_index"]]["id"]
        print(f"{BOLD}Authorized seat projection{RESET}")
        value = project_seat(release, state, seat_id)

    print(json.dumps(value, indent=2, ensure_ascii=False))
    print(
        f"\n{BOLD}[s]{RESET} next seat  {BOLD}[p]{RESET} advance phase  "
        f"{BOLD}[n]{RESET} private note  {BOLD}[a]{RESET} accuse  "
        f"{BOLD}[e]{RESET} events/replay  {BOLD}[t]{RESET} trusted view  "
        f"{BOLD}[x]{RESET} physical export  {BOLD}[v]{RESET} validate  "
        f"{BOLD}[q]{RESET} quit"
    )
    if ui["message"]:
        print(f"\n{DIM}{ui['message']}{RESET}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    release, materials = load_bundle()
    findings = validate_release(release, materials)

    if args.check:
        if findings:
            print("INVALID")
            print("\n".join(f"- {finding}" for finding in findings))
            raise SystemExit(1)
        first = replay(release, "check-session", [])
        second = replay(release, "check-session", [])
        if first != second:
            raise SystemExit("NONDETERMINISTIC REPLAY")
        exported = build_physical_export(release, materials)
        print(
            "VALID: release identity and materials verified; seat projections "
            f"are bounded; replay is deterministic; physical export has {len(exported)} files"
        )
        return

    ui = {
        "session_id": "prototype-session",
        "seat_index": 0,
        "events": [],
        "view": "seat",
        "message": "",
    }
    while True:
        render(release, materials, ui)
        command = input("> ").strip().lower()
        if command == "q":
            break
        ui["message"] = ""
        try:
            if command == "s":
                ui["seat_index"] = (ui["seat_index"] + 1) % len(release["seats"])
                ui["view"] = "seat"
            elif command == "p":
                append_action(release, ui, "advance")
                ui["view"] = "seat"
            elif command == "n":
                append_action(release, ui, "note")
                ui["view"] = "seat"
            elif command == "a":
                append_action(release, ui, "accuse")
                ui["view"] = "events"
            elif command == "e":
                ui["view"] = "events"
            elif command == "t":
                ui["view"] = "trusted"
            elif command == "x":
                ui["view"] = "physical"
            elif command == "v":
                ui["message"] = (
                    "VALID: release boundary holds"
                    if not findings
                    else "INVALID: " + " | ".join(findings)
                )
            else:
                ui["message"] = f"Unknown key: {command!r}"
        except ValueError as error:
            ui["message"] = f"REJECTED: {error}"


if __name__ == "__main__":
    main()
