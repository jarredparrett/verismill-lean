"""Vintage (period-scan) capability tests — each maps to a vintage.*
requirement in foundry/spec/foundry.yaml. Canon: The Parent Trap (1998) —
the Parker/James 1987 marital settlement agreement."""

from __future__ import annotations

import random
import re

import pytest

from mattermill import lens, vintage

META = {"producer": "Adobe Acrobat 9.5.2 Paper Capture Plug-in",
        "creator": "Xerox WorkCentre 5335",
        "created": "2012-06-14 09:31:00"}

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}


def _date(s: str) -> tuple:
    m = re.match(r"(\w+) (\d+), (\d+)", s)
    return (int(m.group(3)), _MONTHS[m.group(1)], int(m.group(2)))


def _content(pdf_bytes: bytes) -> str:
    raw = lens._flate_streams(pdf_bytes).decode("latin-1", "replace")
    return raw.replace("\\(", "(").replace("\\)", ")")


@pytest.fixture
def model():
    return vintage.sample_msa(random.Random(87))


@pytest.fixture
def rendered(model):
    return vintage.render_msa(model, metadata=META)


def test_canon_coherence(model):
    """vintage.canon-coherence: every canon fact reaches the model unsampled,
    and the chronology is strictly ordered — married (1985) < twins born <
    separated < executed (1987)."""
    for key, value in vintage.DEFAULT_CANON.items():
        assert model[key] == value, f"canon fact not carried: {key}"
    assert (_date(model["marriage_date"]) < _date(model["dob"])
            < _date(model["separation_date"]) < _date(model["execution_date"]))


def test_canon_is_caller_supplied():
    """vintage.canon-coherence: the world is DATA. A caller-supplied canon
    replaces every fixed fact, and an incomplete one fails loudly rather than
    rendering a blank where a name belongs."""
    mine = dict(vintage.DEFAULT_CANON,
                twin_a="ROSA ELENA MARQUEZ", twin_b_new="INES MARQUEZ",
                court_county="MERCED")
    m = vintage.sample_msa(random.Random(3), canon=mine)
    assert m["twin_a"] == "ROSA ELENA MARQUEZ"
    text = _content(vintage.render_msa(m, metadata=META))
    assert "ROSA ELENA MARQUEZ" in text
    assert "COUNTY OF MERCED" in text
    for old in vintage.DEFAULT_CANON["twin_a"], vintage.DEFAULT_CANON["court_county"]:
        assert old not in text, f"default canon leaked: {old}"

    with pytest.raises(ValueError, match="canon missing required keys"):
        vintage.sample_msa(random.Random(3), canon={"husband": "A. PERSON"})


def test_agreement_text(rendered):
    """vintage.pleading-paper-layout + the movie's split: both twins named
    with the same DOB, split custody, mutual no-contact, the surname
    provision that gives twin B the mother's maiden name."""
    content = _content(rendered)
    canon = vintage.DEFAULT_CANON
    for marker in ("SUPERIOR COURT OF THE STATE OF CALIFORNIA",
                   f"COUNTY OF {canon['court_county']}", "MARITAL SETTLEMENT",
                   canon["twin_a"], canon["twin_b"], canon["twin_b_new"],
                   "PERMANENT DIVISION OF CUSTODY",
                   "WAIVER OF PARENTAL ACCESS",
                   "PROTECTIVE NON-DISCLOSURE",
                   "CONFIDENTIALITY AND SEALING",
                   "ALLOCATION OF CHILD SUPPORT",
                   canon["ranch"].split(",")[0], canon["wife_trade"],
                   "ACKNOWLEDGMENT", "Notary Public"):
        assert marker in content, f"missing: {marker}"
    assert content.count(canon["dob"]) >= 2        # both twins, same DOB


def test_lawyered_record(rendered):
    """vintage.lawyered-record: the extremity is surrounded by a built
    record — professional recommendation, initialed access waiver, sealing,
    annual certification, minor's counsel, and the court's special findings
    with an Order Approving (round-5 external review)."""
    content = _content(rendered)
    for marker in ("Charles W. Ellison",          # recital H recommendation
                   "Wife's Initials",             # separately initialed waiver
                   "anniversary",                 # annual certification
                   "certified extract",           # sanitized-records mechanics
                   "Attorney Appointed for the Minor Children",
                   "EXHIBIT A", "EXHIBIT E",      # property + sealed evaluation
                   "irreparable",                 # enforcement clause
                   "SPECIAL FINDINGS CONCERNING THE MINOR CHILDREN",
                   "ORDER APPROVING MARITAL",
                   "JUDGE OF THE SUPERIOR COURT"):
        assert marker in content, f"missing: {marker}"


def test_period_citations(rendered):
    """vintage.period-citations: a 1987 agreement cites the Civil Code; the
    Family Code (1994) and the Hague Abduction Convention (US accession
    1988) are anachronisms."""
    content = _content(rendered)
    assert "Civil Code" in content
    assert "Family Code" not in content
    assert "Hague" not in content


def test_period_honest_scan(rendered):
    """vintage.period-honest-scan: pages are JPEG scans (PDF did not exist
    in 1987 — a vector original would be the tell), metadata is dated at
    DIGITIZATION in the PDF era, ModDate == CreationDate."""
    assert rendered.count(b"/DCTDecode") >= 4          # image-based pages
    cd = re.search(rb"/CreationDate \(D:(\d{4})", rendered).group(1)
    assert int(cd) >= 1993
    md = re.search(rb"/ModDate \((D:[0-9]+)\)", rendered).group(1)
    assert md == re.search(rb"/CreationDate \((D:[0-9]+)\)", rendered).group(1)


def test_ocr_text_layer(rendered):
    """vintage.ocr-text-layer: invisible (render mode 3) text overlays the
    scan, searchable like real Paper-Capture output."""
    content = _content(rendered)
    assert "3 Tr" in content
    assert "MARITAL SETTLEMENT" in content   # extractable despite image pages


def test_named_signatures():
    """vintage.named-signatures: signatures derive from the signer's actual
    name — deterministic per (seed, name), distinct across names and seeds."""
    from mattermill import assets
    a = assets.signature_png(61, name="Elizabeth James Parker")
    assert a == assets.signature_png(61, name="Elizabeth James Parker")
    assert a != assets.signature_png(61, name="Nicholas Parker")
    assert a != assets.signature_png(62, name="Elizabeth James Parker")
    assert a[:8] == b"\x89PNG\r\n\x1a\n"
    # legacy abstract scrawl unchanged for existing artifacts
    assert assets.signature_png(1) == assets.signature_png(1)


def test_seeded_everywhere(model):
    assert model == vintage.sample_msa(random.Random(87))
    assert vintage.render_msa(model, metadata=META) == \
        vintage.render_msa(model, metadata=META)


def test_defect_delta_hooks(model):
    """vintage.defect-delta-hooks: each hook breaks exactly one fact."""
    bad = vintage.render_msa(model, metadata=META,
                             defect={"dob_twin_b": "August 5, 1986"})
    content = _content(bad)
    assert "August 5, 1986" in content         # twins now have different DOBs
    assert model["dob"] in content             # twin A's stays honest

    bad2 = vintage.render_msa(model, metadata=META,
                              defect={"marriage_date": "November 6, 1987"})
    content2 = _content(bad2)
    assert "November 6, 1987" in content2      # marriage now postdates births
