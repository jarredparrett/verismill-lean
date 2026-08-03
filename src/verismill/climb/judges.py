"""Judge trial machinery: blind pairwise assembly + verdict scoring.

The module assembles trials (deterministically, from the orchestrator's
seed vault), builds the judge brief, and scores returned verdicts. It never
judges — the judge is a blind agent invoked outside this module, seeing
only the trial_trees/ directory and the cover story.

Blindness protocol: each trial copies sampled files into
trial_trees/<trial_id>/{left,right}/. Which side is synthetic is decided by
the trial seed and recorded in the (builder- and judge-hidden) answer key
the orchestrator keeps. The brief contains no provenance.
"""

from __future__ import annotations

import json
import random
import re
import shutil
from pathlib import Path

COVER_STORY = (
    "You are reviewing two samples, left/ and right/. Exactly one is genuine; "
    "the other was synthesized. Investigate both — read them closely, compare "
    "conventions, check internal coherence — then decide which is synthetic. "
    "Cite quoted evidence (exact spans) for every tell you rely on.")
"""The default brief. Deliberately says nothing about what the samples ARE:
naming the domain tells a judge what to be suspicious of. A round that needs
a domain-matched reader passes its own `cover_story=` instead — that framing
is the round's instrument, not this module's."""

VERDICT_SCHEMA = {
    "pick": "left | right  (which tree is SYNTHETIC)",
    "confidence": "0..1",
    "tells": [{"path": "file the tell appears in",
               "quote": "exact quoted span",
               "rationale": "why this indicates synthesis"}],
}


def sample_tree(src: Path, dest: Path, *, rng: random.Random,
                n_files: int, exts: tuple[str, ...] | None = None,
                exclude: tuple[str, ...] = ("pull_manifest.json",)) -> list[str]:
    """Copy a random sample of files from src into dest (flat). Returns the
    sampled relative names. Deterministic under rng."""
    files = [p for p in sorted(src.rglob("*")) if p.is_file()
             and p.name not in exclude]
    if exts:
        files = [p for p in files if p.suffix.lower() in exts]
    chosen = rng.sample(files, min(n_files, len(files)))
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for p in chosen:
        name = p.name if p.suffix else p.name + ".eml"  # maildir → .eml
        target = dest / name
        i = 1
        while target.exists():
            target = dest / f"{Path(name).stem}_{i}{Path(name).suffix}"
            i += 1
        shutil.copy2(p, target)
        out.append(str(p.relative_to(src)))
    return sorted(out)


def assemble_trial(trial_root: Path, *, real_src: Path, synth_src: Path | None,
                   real_src_b: Path | None, trial_seed: int,
                   n_files: int = 10, key_dir: Path | None = None,
                   cover_story: str = COVER_STORY) -> dict:
    """Build one blind pairwise trial. synth_src None ⇒ real-vs-real control
    (real_src_b provides the second real sample). Returns the answer key.

    The answer key is written OUTSIDE the trial tree (key_dir, orchestrator-
    only): the trial tree contains just left/, right/, brief.md — nothing a
    judge can peek at."""
    rng = random.Random(trial_seed)
    trial_id = f"trial_{trial_seed:06d}"
    tdir = trial_root / trial_id
    if tdir.exists():
        shutil.rmtree(tdir)

    left_is_synth = bool(rng.getrandbits(1))
    a = sample_tree(real_src, tdir / "_a", rng=rng, n_files=n_files)
    if synth_src is not None:
        b = sample_tree(synth_src, tdir / "_b", rng=rng, n_files=n_files)
    else:
        b = sample_tree(real_src_b, tdir / "_b", rng=rng, n_files=n_files)

    (tdir / "left").mkdir(exist_ok=True)
    (tdir / "right").mkdir(exist_ok=True)
    first, second = ("_b", "_a") if left_is_synth and synth_src is not None else ("_a", "_b")
    # in control trials left_is_synth still assigns the (meaningless) label
    if synth_src is None:
        first, second = ("_b", "_a") if left_is_synth else ("_a", "_b")
    for src_dir, dst in ((tdir / first, tdir / "left"), (tdir / second, tdir / "right")):
        for p in src_dir.iterdir():
            shutil.move(str(p), dst / p.name)
        src_dir.rmdir()

    key = {
        "trial_id": trial_id,
        "trial_seed": trial_seed,
        "mode": "synth_vs_real" if synth_src is not None else "real_vs_real",
        "synthetic_side": ("left" if left_is_synth else "right"),
        "sampled_a": a, "sampled_b": b,
        "answer": ("left" if left_is_synth else "right") if synth_src is not None else None,
    }
    key_dest = key_dir or trial_root.parent
    key_dest.mkdir(parents=True, exist_ok=True)
    (key_dest / f"{trial_id}.json").write_text(json.dumps(key, indent=2, sort_keys=True) + "\n")
    (tdir / "brief.md").write_text(
        f"{cover_story}\n\nVerdict format (JSON only):\n"
        f"{json.dumps(VERDICT_SCHEMA, indent=2)}\n")
    return key


def parse_verdict(text: str) -> dict:
    """Extract and validate a verdict JSON from judge output."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in judge output")
    verdict = json.loads(m.group(0))
    if verdict.get("pick") not in ("left", "right"):
        raise ValueError(f"verdict.pick must be left|right, got {verdict.get('pick')!r}")
    verdict.setdefault("confidence", None)
    verdict.setdefault("tells", [])
    for tell in verdict["tells"]:
        for k in ("path", "quote", "rationale"):
            if k not in tell:
                raise ValueError(f"tell missing {k!r}")
    return verdict


def score_batch(keys: list[dict], verdicts: dict[str, dict]) -> dict:
    """Accuracy per mode. Controls (real_vs_real) should sit at chance;
    synth_vs_real should be near 1.0 while the climb has work to do."""
    by_mode: dict[str, list[bool]] = {"synth_vs_real": [], "real_vs_real": []}
    for key in keys:
        verdict = verdicts.get(key["trial_id"])
        if verdict is None:
            continue
        correct = verdict["pick"] == key["synthetic_side"]
        by_mode[key["mode"]].append(correct)
    return {
        "synth_vs_real_accuracy": (sum(by_mode["synth_vs_real"]) / len(by_mode["synth_vs_real"])
                                   if by_mode["synth_vs_real"] else None),
        "real_vs_real_pick_rate": (sum(by_mode["real_vs_real"]) / len(by_mode["real_vs_real"])
                                   if by_mode["real_vs_real"] else None),
        "trials_scored": sum(len(v) for v in by_mode.values()),
    }
