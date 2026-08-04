"""Public-corpus hygiene guard for prohibited default-world identifiers.

Two halves, because a name can enter an artifact two ways. The source scan
catches identifiers welded into a module's default canon. The emit scan
catches identifiers that only appear once a document is rendered — the case
a source grep cannot see.

The emit half replaces a guard that scanned two committed demo PDFs. Emitting
is strictly stronger: it covers every registered class rather than whichever
two demos happened to be checked in, and it cannot go stale against the code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Real companies, agencies, and trademarked indexes that appeared in the
# pre-launch corpus and were replaced with invented names (2026-07-31).
# Lowercase; matched case-insensitively as substrings.
FORBIDDEN = [
    "epiq",
    "kcc llc",
    "stretto",
    "gordon brothers",
    "hilco",
    "tiger asset",
    "random lengths",
    "dor.oregon.gov",
    "dor.wa.gov",
    "tax.idaho.gov",
    # Third-party fictional properties, extracted 2026-08-02. Canon is now
    # caller-supplied data (vintage.DEFAULT_CANON, diligence.DEFAULT_CANON);
    # welding someone else's world into an emitter made the module unusable
    # by anyone else and put their facts in our source tree. Anyone who wants
    # these worlds supplies them at the call site.
    "ingen",
    "isla nublar",
    "jurassic",
    "john hammond",
    "parker knoll",
    "hallie parker",
    "anne james",
    "queen elizabeth 2",
    # A real Hoboken apartment building that was previously shipped as the
    # lease emitter's default world.
    "the jordan",
    "1200 clinton",
    # Address fragments removed from the deed default canon.
    "18 larkspur lane",
    "green village road",
]

TEXT_DIRS = ["src", "libs"]
TEXT_SUFFIXES = {".py", ".yaml", ".yml", ".md", ".json", ".txt", ".toml"}


def _text_files():
    for d in TEXT_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if (p.is_file() and p.suffix.lower() in TEXT_SUFFIXES
                    and not {"__pycache__", "build", "dist"}.intersection(p.parts)
                    and not any(part.endswith(".egg-info") for part in p.parts)):
                yield p


def _offenders(body: str, label: str) -> list[str]:
    body = body.lower()
    return [f"{label}: {n}" for n in FORBIDDEN if n in body]


def test_no_forbidden_default_entities_in_source_tree():
    """default-world-hygiene: known third-party worlds and real properties do
    not re-enter shipped canon or generator source."""
    offenders = []
    for p in _text_files():
        offenders += _offenders(p.read_text(errors="ignore"),
                                str(p.relative_to(ROOT)))
    assert not offenders, "real-world identifiers present:\n" + "\n".join(offenders)


def test_no_forbidden_default_entities_in_emitted_artifacts():
    """default-world-hygiene, at the only place that finally settles it: the
    rendered bytes. Every registered class is emitted at a fixed seed and its
    text layer read back — for the scan-based classes that is the invisible
    OCR layer, which is exactly the surface an extraction tool would see."""
    pdfium = pytest.importorskip("pypdfium2")
    from mattermill import registry

    offenders, scanned = [], 0
    for entry in registry.list_classes():
        name = entry["name"]
        pdf, _manifest = registry.emit(name, seed=7)
        doc = pdfium.PdfDocument(pdf)
        body = "\n".join((pg.get_textpage().get_text_range() or "") for pg in doc)
        offenders += _offenders(body, name)
        scanned += 1

    assert scanned >= 6, f"expected the full registry, emitted {scanned}"
    assert not offenders, ("real-world identifiers in emitted artifacts:\n"
                           + "\n".join(offenders))
