"""The registry exposes static capabilities and reproducible emit recipes.

Experiment evidence and measured standing deliberately belong to verismill's
user-owned experiment store, not to this package catalog.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys

import pypdfium2 as pdfium
import pytest

from mattermill import registry


def _meta(pdf: bytes) -> dict:
    return {k: re.search(rb"/" + k.encode() + rb" \(([^)]*)\)", pdf)
            for k in ("Producer", "Creator")}


def test_catalog_reports_only_static_capabilities():
    """registry.catalog-contract: package metadata contains capabilities, not
    a copied experiment result that can drift away from its evidence."""
    classes = registry.list_classes()
    assert classes, "the catalog is empty"
    for c in classes:
        assert c["substrate"], f"{c['name']} does not say what it physically is"
        assert c["mattermill"], f"{c['name']} does not name its package version"
        assert "standing" not in c, (
            f"{c['name']} copied user experiment state into the package catalog")
        blob = json.dumps(c).lower()
        assert "realistic" not in blob, f"{c['name']} calls itself realistic"


def test_emit_is_deterministic():
    """seeded.everywhere: same class, pins and seed → byte-identical bytes and
    an identical sha, including the metadata the facade chose. The manifest is
    a reproduction recipe or it is decoration."""
    for name in sorted(registry.CLASSES):
        a, ma = registry.emit(name, seed=11)
        b, mb = registry.emit(name, seed=11)
        assert a == b, f"{name} is not deterministic"
        assert ma["sha256"] == mb["sha256"] == (
            "sha256:" + __import__("hashlib").sha256(a).hexdigest())
        assert ma["bytes"] == len(a)


def test_seed_actually_varies_the_artifact():
    """seeded.everywhere: determinism must not be constancy — a different seed
    must produce a different artifact, or the seed is decorative."""
    for name in sorted(registry.CLASSES):
        a, _ = registry.emit(name, seed=1)
        b, _ = registry.emit(name, seed=2)
        assert a != b, f"{name} ignores its seed"


def test_facade_owns_era_correct_metadata():
    """registry.era-correct-metadata: the facade sets capture metadata so no
    caller has to, and it is honest about the era. A scan-class artifact's
    CreationDate is its DIGITISATION, never the date the document claims — a
    1642 deed carrying a 1642 CreationDate advertises the forgery. Membranes
    and bound volumes are captured overhead, not fed through a sheetfed
    scanner: round 8 lost forensic authenticity on exactly that."""
    for name, cls in registry.CLASSES.items():
        pdf, man = registry.emit(name, seed=3)
        created = man["metadata"]["created"]
        year = int(created[:4])
        assert year >= 1993, f"{name}: PDF did not exist in {year}"
        lo, hi = cls.capture_window
        assert lo <= year <= hi, f"{name}: {year} outside {cls.capture_window}"
        assert man["metadata"]["modified"] is None
        # the represented era must never be the file's claimed creation
        if cls.era.isdigit():
            assert not created.startswith(cls.era), (
                f"{name}: CreationDate claims the document's own era")
        assert man["metadata"]["producer"] in [p for p, _ in cls.profiles]

    membrane, m = registry.emit("bill_of_sale", seed=3)
    assert any(k in m["metadata"]["producer"]
               for k in ("Zeutschel", "CopiBook", "Bookeye")), (
        "a membrane cannot be fed through a sheetfed scanner")


def test_manifest_is_a_reproduction_recipe():
    """registry.manifest-provenance: the manifest carries everything needed to
    reproduce the bytes — class, version, seed, pins — plus the ground truth
    of anything planted."""
    pdf, man = registry.emit("bill_of_sale", seed=1642,
                             pins={"vessel_name": "Unity", "share": 4})
    for key in ("class", "mattermill", "module", "seed", "pins", "metadata",
                "sha256", "bytes", "ground_truth"):
        assert key in man, f"manifest missing {key}"
    assert "standing" not in man, "standing must derive from its experiment"
    assert man["pins"] == {"vessel_name": "Unity", "share": 4}
    assert man["ground_truth"] == []

    again, _ = registry.emit(man["class"], seed=man["seed"],
                             pins=man["pins"], metadata=man["metadata"])
    assert again == pdf, "the manifest does not reproduce its own artifact"


def test_manifest_preserves_caller_canon():
    """registry.manifest-canon: a canon-driven artifact records the exact
    caller world required to reproduce it, never a placeholder description."""
    canon = dict(registry.lease_nj.DEFAULT_CANON,
                 building_name="Harbor Loom",
                 street="9 Fictional Quay",
                 landlord_entity="Fictional Quay Owner, LLC")
    _pdf, manifest = registry.emit("lease_nj", seed=9, canon=canon)
    assert manifest["canon"] == canon


def test_planted_defect_is_recorded_as_ground_truth():
    """registry.manifest-provenance: a planted fault rides in the manifest, so
    an artifact used as a scorable fixture carries its own answer key."""
    clean, _ = registry.emit("bill_of_sale", seed=5)
    bad, man = registry.emit("bill_of_sale", seed=5,
                             defect={"regnal_year": "fifteenth"})
    assert bad != clean
    assert man["ground_truth"] == [{"regnal_year": "fifteenth"}]
    text = " ".join(
        (pdfium.PdfDocument(io.BytesIO(bad))[0].get_textpage()
         .get_text_range() or "").split())
    assert "fifteenth yeere of the reigne" in text


def test_unknown_class_and_bad_pins_fail_loudly():
    """registry.catalog-contract: the catalog is the contract. An unknown
    class names the alternatives; pins a class does not accept are refused
    rather than silently dropped."""
    with pytest.raises(KeyError, match="unknown document class"):
        registry.emit("acord_999")
    with pytest.raises(TypeError, match="takes no pins"):
        registry.emit("underwriting_file", pins={"vessel_name": "Unity"})
    with pytest.raises(TypeError, match="takes no canon"):
        registry.emit("bill_of_sale", canon={"anything": 1})


def test_cli_serves_a_request(tmp_path):
    """registry.cli-surface: a caller who never writes Python can name a class,
    pin a fact, and get an artifact plus its manifest."""
    out = tmp_path / "bill.pdf"
    r = subprocess.run(
        [sys.executable, "-m", "mattermill.cli", "emit",
         "--class", "bill_of_sale", "--seed", "1642", "--out", str(out),
         "--pin", "vessel_name=Hopewell", "--pin", "share=8",
         "--pin", "salutation=false"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert out.exists() and out.stat().st_size > 10_000
    man = json.loads((tmp_path / "bill.pdf.manifest.json").read_text())
    assert man["pins"] == {"vessel_name": "Hopewell", "share": 8,
                           "salutation": False}, "pin types not coerced"
    assert man["artifact"] == "bill.pdf"
    assert "standing" not in man
    assert "standing" not in r.stdout.lower()

    lst = subprocess.run([sys.executable, "-m", "mattermill.cli", "classes",
                          "--json"], capture_output=True, text=True)
    assert lst.returncode == 0, lst.stderr
    catalog = json.loads(lst.stdout)
    assert {c["name"] for c in catalog} == set(registry.CLASSES)
    assert all("standing" not in c for c in catalog)
