"""forensic.metadata — invariant 6, at the primitive that decides it.

Round 2 found that a PDF whose CreationDate is the render date rather than
the date the document claims announces itself. legalpdf owns that, every
emitter routes through it, and lens is what reads the bytes back — so this is
the one round-2 test that outlives the pre-registry forge the rest of that
file exercised.
"""

from __future__ import annotations

from mattermill import legalpdf, lens

META = {"producer": "iSEDQuickPDF 4.41 (www.sedtech.com)",
        "creator": "Microsoft Word", "created": "2026-04-28 13:58:19",
        "modified": "2026-04-28 13:58:19"}

MODEL = {
    "caption": {"court": "District of Oregon", "debtor": "X, Inc.",
                "case_no": "26-1"},
    "title": "T", "sections": [{"heading": "H", "paras": ["body"]}],
}


def test_creation_date_matches_represented_date(tmp_path):
    """forge.pdf-metadata + lens.pdf: CreationDate must be the represented
    filing date, not the render date — and the lens must read back exactly
    what legalpdf wrote, since that round trip is what stops the emitter and
    the verifier from drifting."""
    p = tmp_path / "d.pdf"
    p.write_bytes(legalpdf.render_court_pdf(MODEL, header_stamp=None,
                                            bates_prefix=None, metadata=META))
    info = lens.pdf_info(p)
    assert info["created"] == "D:20260428135819"
    assert info["modified"] == "D:20260428135819"
