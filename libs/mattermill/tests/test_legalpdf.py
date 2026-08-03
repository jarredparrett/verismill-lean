"""Tests for mattermill's reportlab-backed legal PDF renderer."""

from __future__ import annotations

from pathlib import Path

import pytest

from mattermill import legalpdf, lens

MODEL = {
    "caption": {"court": "District of Oregon",
                "debtor": "Meridian Forest Products, Inc.",
                "case_no": "26-10458", "chapter": "11",
                "related": "Docket Nos. 187, 234",
                "hearing": "May 6, 2026 at 10:00 a.m. (Pacific)"},
    "title": "LIMITED OBJECTION OF THE OFFICIAL COMMITTEE OF UNSECURED CREDITORS",
    "intro": "The Committee respectfully states as follows:",
    "sections": [
        {"heading": "PRELIMINARY STATEMENT", "paras": ["First para."]},
        {"heading": "OBJECTION", "paras": [
            "The equipment is worth no more than $11.6 million as of March 31, 2026, "
            "reflecting current auction comparables for used mill equipment.",
            "The warehouse appraisal remains incomplete."]},
    ],
    "prayer": "WHEREFORE, the Committee requests relief.",
    "dated": "April 28, 2026",
    "signature": ["STANTON VERE LLP", "/s/ Margaret E. Stanton"],
    "certificate": {"date": "April 28, 2026", "method": "via CM/ECF",
                    "name": "Margaret E. Stanton"},
}

META = {"producer": "Acrobat Distiller 8.3.1 (Windows)",
        "creator": "Microsoft Word", "created": "2026-04-28 16:41:03",
        "title": "Limited Objection"}


@pytest.fixture
def rendered(tmp_path):
    p = tmp_path / "objection.pdf"
    p.write_bytes(legalpdf.render_court_pdf(
        MODEL, header_stamp="Case 26-10458 Doc 245 Filed 04/28/26  Page {page} of 2",
        bates_prefix="COMMITTEE_", metadata=META))
    return p


def test_deterministic(tmp_path):
    a = legalpdf.render_court_pdf(MODEL, header_stamp=None, bates_prefix=None, metadata=META)
    b = legalpdf.render_court_pdf(MODEL, header_stamp=None, bates_prefix=None, metadata=META)
    assert a == b, "render_court_pdf must be byte-identical across runs"


def test_lens_reads_metadata_and_bates(rendered):
    info = lens.pdf_info(rendered)
    assert info["producer"] == "Acrobat Distiller 8.3.1 (Windows)"
    assert info["creator"] == "Microsoft Word"
    assert info["pages"] >= 1
    assert any(b.startswith("COMMITTEE_") for b in info["bates_stamps"])


def test_keyed_span_preserved(rendered):
    """The D1 keyed span must survive rendering (lens decompresses streams)."""
    raw = rendered.read_bytes()
    content = lens._flate_streams(raw).decode("latin-1", "replace")
    assert "no more than $11.6 million" in content.replace("  ", " ") or \
           "no more than $11.6" in content  # reportlab may kern-split words


def test_structure_markers(rendered):
    content = lens._flate_streams(rendered.read_bytes()).decode("latin-1", "replace")
    for marker in ("UNITED STATES BANKRUPTCY COURT", "PRELIMINARY STATEMENT",
                   "WHEREFORE", "CERTIFICATE OF SERVICE"):
        assert marker in content


def test_caption_no_court_duplication(tmp_path):
    """'District of Oregon' input must not double the court line."""
    p = tmp_path / "c.pdf"
    p.write_bytes(legalpdf.render_court_pdf(MODEL, header_stamp=None,
                                            bates_prefix=None, metadata=META))
    content = lens._flate_streams(p.read_bytes()).decode("latin-1", "replace")
    assert content.count("UNITED STATES BANKRUPTCY COURT") == 1
