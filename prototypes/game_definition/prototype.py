#!/usr/bin/env python3
"""PROTOTYPE: inspect a static game definition through author and seat views."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from model import author_snapshot, seat_snapshot, validate_game


HERE = Path(__file__).resolve().parent
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def load_game() -> dict[str, Any]:
    return yaml.safe_load((HERE / "game.yaml").read_text(encoding="utf-8"))


def render(game: dict[str, Any], state: dict[str, Any]) -> None:
    print("\033[2J\033[H", end="")
    print(f"{BOLD}PROTOTYPE — human-readable game definition{RESET}")
    print(f"{DIM}{game['title']} · {game['profile']}{RESET}\n")

    if state["author_view"]:
        print(f"{BOLD}Trusted author view{RESET}")
        snapshot = author_snapshot(game)
    else:
        character_id = game["characters"][state["character_index"]]["id"]
        phase = game["phases"][state["phase_index"]]
        print(f"{BOLD}Authorized seat view{RESET}")
        snapshot = seat_snapshot(game, character_id, phase)

    print(json.dumps(snapshot, indent=2, ensure_ascii=False))
    print(f"\n{BOLD}[s]{RESET} next seat  {BOLD}[n]{RESET} next phase  "
          f"{BOLD}[p]{RESET} previous phase  {BOLD}[a]{RESET} author/seat view  "
          f"{BOLD}[v]{RESET} validate  {BOLD}[q]{RESET} quit")
    if state["message"]:
        print(f"\n{DIM}{state['message']}{RESET}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    game = load_game()
    findings = validate_game(game)

    if args.check:
        if findings:
            print("INVALID")
            print("\n".join(f"- {finding}" for finding in findings))
            raise SystemExit(1)
        print("VALID: all references resolve and no runtime/render keys are embedded")
        return

    state = {
        "character_index": 0,
        "phase_index": 0,
        "author_view": False,
        "message": "",
    }
    while True:
        render(game, state)
        command = input("> ").strip().lower()
        if command == "q":
            break
        if command == "s":
            state["character_index"] = (
                state["character_index"] + 1
            ) % len(game["characters"])
        elif command == "n":
            state["phase_index"] = min(
                state["phase_index"] + 1, len(game["phases"]) - 1
            )
        elif command == "p":
            state["phase_index"] = max(state["phase_index"] - 1, 0)
        elif command == "a":
            state["author_view"] = not state["author_view"]
        elif command == "v":
            state["message"] = (
                "VALID: all references resolve"
                if not findings
                else "INVALID: " + " | ".join(findings)
            )
        else:
            state["message"] = f"Unknown key: {command!r}"


if __name__ == "__main__":
    main()
