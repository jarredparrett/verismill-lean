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


# ===========================================================================
# Absolute review — judges.protocol v0.2.0 (.foundry/spec.yaml judges.protocol)
#
# Formalised after lease_nj round 1, where a human found in one glance what a
# k=3 blind round + a self-graded harvest under-resolved. Each construct below
# closes a numbered failure mode (FM1..FM5); the scorer, not the judge, owns
# aggregation, so the min+veto rule cannot be averaged away by a judge.
# ===========================================================================

DIMENSIONS = ("drafting_realism", "procedural_correctness",
              "cross_field_consistency", "financial_operational",
              "external_verifiability", "visual_formatting",
              "forensic_authenticity")

# FM1 — binary fatals a human treats as disqualifying; a NO caps the score.
DISQUALIFIERS = {
    "executed_consistently": {
        "cap": 25,
        "question": ("If the document recites that it is executed/signed, is it "
                     "consistently executed — every signature, initial, and "
                     "acknowledgment slot filled in ONE convention (all wet-ink "
                     "OR all e-sign), with NO blank required-initial lines (e.g. "
                     "a lead-paint LESSOR/LESSEE initial slot left as '____')?")},
    "signature_is_a_hand": {
        "cap": 30,
        "question": ("Do the signatures render as a plausible human hand for the "
                     "NAMED signer — not a name-agnostic scrawl, and not one "
                     "visual hand shared by adverse parties?")},
    "no_impossible_identifier": {
        "cap": 35,
        "question": ("Is every identifier that invites a lookup (registry code, "
                     "form edition, account number, bank name) either correct "
                     "or ABSENT — never invented? Do not flag a citation as "
                     "fabricated unless you are confident it is.")},
}

# FM5 — k judges must COVER the tell space, not corroborate one reading.
LENSES = ("arithmetic_and_dates", "procedural_and_citations",
          "forensic_and_visual")
LENS_FOCUS = {
    "arithmetic_and_dates":
        "Weight recomputing every derived figure (deposit vs rent, totals, "
        "percentages) and checking every date and term.",
    "procedural_and_citations":
        "Weight whether required disclosures are present and correctly cited, "
        "and whether any identifier would survive a real lookup.",
    "forensic_and_visual":
        "Weight signatures, initials, seals, fill/execution state, layout and "
        "whitespace — whether this reads as a genuinely EXECUTED document.",
}


def assign_lenses(k: int) -> list[str]:
    """One lens per judge, cycling so every lens is covered once k >= 3."""
    return [LENSES[i % len(LENSES)] for i in range(k)]


def coverage_ok(assigned: list[str]) -> bool:
    """A round with no forensic lens is not a forensic measurement (FM5)."""
    return "forensic_and_visual" in assigned


def build_absolute_brief(*, class_name: str, persona: str, lens: str) -> str:
    """The v0.2.0 absolute-review brief for one blind judge: a GLANCE pass
    before any text (FM3), the three disqualifiers answered up front (FM1), a
    primary lens (FM5), the seven dimensions, and a verdict schema that OMITS
    an overall score — the judge scores dimensions and answers disqualifiers;
    `aggregate_absolute` computes the headline, so min+veto cannot be averaged
    away by a generous judge."""
    dq = "\n".join(f'  - {i}: {d["question"]}' for i, d in DISQUALIFIERS.items())
    schema = {
        "glance_impression": "one-line gut read from PASS 1, before reading text",
        "authenticity": "genuine | synthetic",
        "confidence": "0..1",
        "disqualifiers": {i: "pass | fail" for i in DISQUALIFIERS},
        "dimension_scores": {d: "0..100" for d in DIMENSIONS},
        "tells": [{"path": "file the tell is in",
                   "quote_or_region": "exact text span, OR {page:int, bbox_norm:[x0,y0,x1,y1]} for a visual tell",
                   "rationale": "why it indicates synthesis"}],
    }
    return (
        f"You are a {persona}. A colleague forwarded you ONE document and asked "
        f"whether it is a GENUINE executed instrument or a SYNTHESIZED specimen. "
        f"Score it as an expert who notices what a layperson would not.\n\n"
        f"PASS 1 — GLANCE (do this FIRST, before reading any text). View every "
        f"page as a rendered image at full scale. From the look alone, form your "
        f"impression of whether this is a genuinely executed document, and "
        f"answer each disqualifier now:\n{dq}\n\n"
        f"PASS 2 — DEEP READ. Now read the text. {LENS_FOCUS[lens]} Then score "
        f"each of these 0..100 (100 = indistinguishable from genuine): "
        f"{', '.join(DIMENSIONS)}.\n\n"
        f"Return ONLY this JSON (no overall score — that is computed for you):\n"
        f"{json.dumps(schema, indent=2)}")


def parse_absolute_verdict(text: str) -> dict:
    """Extract and validate a v0.2.0 absolute verdict. Enforces that every
    disqualifier is answered (FM1) and every dimension scored, and that each
    tell carries a locus — a text quote OR a page+bbox (FM4)."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in judge output")
    v = json.loads(m.group(0))
    if v.get("authenticity") not in ("genuine", "synthetic"):
        raise ValueError(f"authenticity must be genuine|synthetic, "
                         f"got {v.get('authenticity')!r}")
    dq = v.get("disqualifiers") or {}
    for did in DISQUALIFIERS:
        if dq.get(did) not in ("pass", "fail"):
            raise ValueError(f"disqualifier {did!r} must be answered pass|fail")
    ds = v.get("dimension_scores") or {}
    for dim in DIMENSIONS:
        s = ds.get(dim)
        if not isinstance(s, (int, float)) or not 0 <= s <= 100:
            raise ValueError(f"dimension {dim!r} must be a 0..100 score")
    v.setdefault("confidence", None)
    for tell in v.setdefault("tells", []):
        if "path" not in tell or "rationale" not in tell:
            raise ValueError("tell missing path/rationale")
        loc = tell.get("quote_or_region", tell.get("quote"))
        has_region = isinstance(loc, dict) and "page" in loc and "bbox_norm" in loc
        if not (isinstance(loc, str) or has_region):
            raise ValueError("tell needs a locus: a text quote OR {page, bbox_norm}")
    return v


def aggregate_absolute(verdict: dict) -> dict:
    """The scorer. FM1: overall = MIN over dimensions, then capped by the
    lowest cap of any FAILED disqualifier. The arithmetic mean is retained only
    as an informational coherence_profile — a 93 arithmetic can never buy back
    a 40 forensic or an unsigned-lease veto."""
    dims = verdict["dimension_scores"]
    base = min(dims.values())
    failed = [did for did, ans in verdict["disqualifiers"].items() if ans == "fail"]
    cap = min((DISQUALIFIERS[d]["cap"] for d in failed), default=100)
    return {
        "overall_score": min(base, cap),
        "coherence_profile": round(sum(dims.values()) / len(dims)),
        "min_dimension": base,
        "disqualifier_cap": cap if failed else None,
        "failed_disqualifiers": failed,
    }


def score_absolute_batch(verdicts: dict[str, dict],
                         assigned_lenses: list[str] | None = None) -> dict:
    """Aggregate a k-judge absolute round. Reports the DISTRIBUTION of per-judge
    overalls (each already min+veto), never a single laundered number: the min
    is the harshest credible read, the mean is context, and the disqualifier
    fail counts show whether a veto was 1-of-k or unanimous."""
    aggs = {j: aggregate_absolute(v) for j, v in verdicts.items()}
    overalls = [a["overall_score"] for a in aggs.values()]
    dim_means = {d: round(sum(v["dimension_scores"][d] for v in verdicts.values())
                          / len(verdicts)) for d in DIMENSIONS}
    synth = sum(1 for v in verdicts.values() if v["authenticity"] == "synthetic")
    out = {
        "k": len(verdicts),
        "overall_min": min(overalls),
        "overall_mean": round(sum(overalls) / len(overalls)),
        "overall_by_judge": {j: a["overall_score"] for j, a in aggs.items()},
        "dimension_means": dim_means,
        "coherence_profile": round(sum(dim_means.values()) / len(dim_means)),
        "disqualifier_fail_counts": {
            i: sum(1 for v in verdicts.values() if v["disqualifiers"][i] == "fail")
            for i in DISQUALIFIERS},
        "synthetic_calls": synth,
        "discrimination_accuracy": round(synth / len(verdicts), 2),
    }
    if assigned_lenses is not None:
        out["coverage_ok"] = coverage_ok(assigned_lenses)
    return out


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
