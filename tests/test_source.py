"""Template-sourcer capability tests — each maps to a sourcing.* requirement.

The extraction fixture is emitted, not committed: `registry.emit("acord126")`
gives a real 4-page form on demand, so the test cannot go stale against a
demo file someone forgot to regenerate, and no binary has to live in the repo
to make it pass. Offline either way.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from verismill import source

pytest.importorskip("pypdfium2")


@pytest.fixture(scope="module")
def demo(tmp_path_factory) -> Path:
    from mattermill import registry
    pdf, _ = registry.emit("acord126", seed=126)
    path = tmp_path_factory.mktemp("ref") / "acord126_gl_section.pdf"
    path.write_bytes(pdf)
    return path


def test_provenance_recorded(tmp_path, demo):
    """sourcing.provenance-recorded: registering a form writes sha256, size,
    origin, and retrieval date next to the source."""
    source.register_local(demo, "demo126", out_root=tmp_path)
    prov = json.loads((tmp_path / "demo126/provenance.json").read_text())
    assert prov["sha256"] and prov["bytes"] == demo.stat().st_size
    assert prov["local_path"].endswith("acord126_gl_section.pdf")
    assert prov["retrieved_utc"].endswith("Z")


def test_rejects_non_pdf(tmp_path):
    """sourcing.pdf-verified: an HTML landing page saved under a .pdf name is
    the standard silent failure of this step — the name is right and the form
    is absent. It must raise at registration, not surface as empty extraction
    three steps later."""
    bogus = tmp_path / "bogus.pdf"
    bogus.write_bytes(b"<html>not a form</html>")
    with pytest.raises(ValueError, match="not a PDF"):
        source.register_local(bogus, "bogus", out_root=tmp_path)


def test_contract_extraction(tmp_path, demo):
    """sourcing.contract-extraction: per-page text lines, page count, size."""
    source.register_local(demo, "demo126", out_root=tmp_path)
    contract_path = source.write_contract("demo126", out_root=tmp_path)
    contract = json.loads(contract_path.read_text())
    assert contract["pages"] == 4
    assert len(contract["page_lines"]) == 4
    assert contract["provenance"]["sha256"]
    joined = ["\n".join(p) for p in contract["page_lines"]]
    assert "SCHEDULE OF HAZARDS" in joined[0]
    assert "CONTRACTORS" in joined[1]
    assert "GENERAL INFORMATION" in joined[2]
    assert "REMARKS" in joined[3]


def test_marker_proposal(tmp_path, demo):
    """sourcing.marker-proposal: form-number and pagination marks always
    proposed; section headers surfaced per page."""
    source.register_local(demo, "demo126", out_root=tmp_path)
    contract = json.loads(source.write_contract("demo126", out_root=tmp_path).read_text())
    pm = contract["proposed_markers"]
    assert "ACORD 126 (2009/08)" in pm["1"]
    assert "Page 2 of 4" in pm["2"]
    assert "Page 4 of 4" in pm["4"]
    assert any("SCHEDULE OF HAZARDS" in m for m in pm["1"])
    assert all(len(v) <= 24 for v in pm.values())
