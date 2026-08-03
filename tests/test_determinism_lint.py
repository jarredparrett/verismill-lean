"""Static determinism lint — invariant 1, enforced rather than remembered.

Every one of these is a bug class this repo actually shipped. Builtin `hash()`
is the worst of them: it is salted per interpreter process, so it passes
same-process byte-identity tests and still breaks reproducibility across runs.
Round 6 found it twice in shipped code. A capability test cannot catch it,
because the test and the code run in one process — only reading the source can.

The rule is not "never be random". It is that randomness must arrive as the
caller's `rng`, so an artifact stays a function of its seed and a measurement
replays to the exact bytes that produced it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Modules that compose or render an artifact. Everything reachable from
# registry.emit() has to be a pure function of (pins, canon, seed).
EMITTER_DIRS = [ROOT / "libs" / "mattermill" / "src" / "mattermill"]

# The CLI is exempt by design: it is the one place a wall clock is correct,
# because an operator asking for a document now gets a manifest stamped now.
EXEMPT = {"cli.py"}

BANNED_CALLS = {
    "hash": "builtin hash() is salted per process — it passes same-process "
            "tests and breaks reproducibility across runs (round 6, twice)",
    "uuid1": "uuid1 encodes the clock and the MAC address",
    "uuid4": "uuid4 draws from os.urandom, outside the caller's seed",
}
BANNED_ATTRS = {
    ("time", "time"): "wall clock",
    ("time", "time_ns"): "wall clock",
    ("datetime", "now"): "wall clock — represented dates come from the model",
    ("datetime", "today"): "wall clock",
    ("os", "urandom"): "entropy outside the caller's seed",
    ("random", "random"): "module-level random uses the global RNG; thread "
                          "the caller's rng instead",
    ("random", "choice"): "module-level random uses the global RNG",
    ("random", "randint"): "module-level random uses the global RNG",
    ("random", "seed"): "seeding the global RNG makes determinism a global "
                        "side effect rather than a property of the call",
    # both import styles: `uuid.uuid4()` is an attribute call, `from uuid
    # import uuid4` then `uuid4()` is a bare name — BANNED_CALLS covers the
    # second, and only checking one of them is how a lint stays green while
    # the bug ships
    ("uuid", "uuid1"): "uuid1 encodes the clock and the MAC address",
    ("uuid", "uuid4"): "uuid4 draws from os.urandom, outside the caller's seed",
    ("secrets", "token_hex"): "entropy outside the caller's seed",
    ("secrets", "token_bytes"): "entropy outside the caller's seed",
}


def _emitter_files():
    for d in EMITTER_DIRS:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.py")):
            if p.name not in EXEMPT and "__pycache__" not in p.parts:
                yield p


def _offenders(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    out: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id in BANNED_CALLS:
            out.append(f"{path.name}:{node.lineno} {fn.id}() — "
                       f"{BANNED_CALLS[fn.id]}")
        elif isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
            key = (fn.value.id, fn.attr)
            if key in BANNED_ATTRS:
                out.append(f"{path.name}:{node.lineno} "
                           f"{fn.value.id}.{fn.attr}() — {BANNED_ATTRS[key]}")
    return out


def test_there_are_files_to_lint():
    """An empty file list would make the lint below vacuously green."""
    files = list(_emitter_files())
    assert len(files) >= 10, f"expected the emitter tree, found {len(files)}"


@pytest.mark.parametrize("path", list(_emitter_files()),
                         ids=lambda p: p.name)
def test_no_nondeterminism_in_emitter_source(path):
    """seeded.everywhere: no clocks, no process-salted hashing, no entropy
    outside the caller's rng, no use of the global RNG."""
    offenders = _offenders(path)
    assert not offenders, (
        "non-deterministic call in emitter source:\n  "
        + "\n  ".join(offenders)
        + "\n\nThread the caller's rng, or derive display values from a "
          "stable digest (see diligence._stable_hash).")
