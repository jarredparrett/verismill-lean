"""ACORD 126 capability tests — each maps to an acord.* requirement in
foundry/spec/foundry.yaml. The layout tests assert the template contract
transcribed from the real ACORD 126 (2009/08) form."""

from __future__ import annotations

import random

import pytest

from mattermill import acord, lens

META = {"producer": "Acrobat Distiller 8.3.1 (Windows)",
        "creator": "AMS360 Form Library", "created": "2026-04-15 10:22:00"}


def _content(pdf_bytes: bytes) -> str:
    raw = lens._flate_streams(pdf_bytes).decode("latin-1", "replace")
    return raw.replace("\\(", "(").replace("\\)", ")")


@pytest.fixture
def model():
    return acord.sample_126(random.Random(26))


@pytest.fixture
def rendered(tmp_path, model):
    p = tmp_path / "acord126.pdf"
    p.write_bytes(acord.render_126(model, metadata=META))
    return p


def test_template_contract(rendered):
    """acord.126-2009-08-template-contract: 4 pages, every page's section
    inventory present, in stream (page) order, with the ACORD marks."""
    assert lens.pdf_info(rendered)["pages"] == 4
    content = _content(rendered.read_bytes())
    pos = 0
    for page in (1, 2, 3, 4):
        for marker in acord.PAGE_MARKERS[page]:
            found = content.find(marker)
            assert found >= 0, f"page {page} missing: {marker}"
        # pages appear in order: anchor on the page's closing footer mark
        anchor = {1: "Attach to ACORD 125", 2: "Page 2 of 4",
                  3: "Page 3 of 4", 4: "Page 4 of 4"}[page]
        idx = content.find(anchor)
        assert idx > pos, f"page {page} out of order"
        pos = idx


def test_not_a_125(rendered):
    """The v1 tells: loss history and signature blocks belong to ACORD 125
    and must NOT appear on a 126."""
    content = _content(rendered.read_bytes())
    for absent in ("LOSS HISTORY", "Applicant's Signature", "Producer's Signature",
                   "ACORD 126 (2016/05)"):
        assert absent not in content, f"ACORD 125 artifact present: {absent}"


def test_premium_foots(model):
    """acord.premium-foots: schedule premiums = exposure/1,000 x rate,
    separately for Prem/Ops and Products."""
    for r in model["schedule"]:
        assert r["prem_premops"] == round(r["exposure"] / 1000 * r["rate_premops"]), r
        if r["rate_products"]:
            assert r["prem_products"] == round(r["exposure"] / 1000 * r["rate_products"]), r
        else:
            assert r["prem_products"] == 0


def test_premiums_box_foots(model):
    """acord.premiums-box-foots: the page-1 PREMIUMS box sums the schedule
    plus the EBL premium."""
    t = acord.compute_totals(model)
    assert t["premises_operations"] == sum(r["prem_premops"] for r in model["schedule"])
    assert t["products"] == sum(r["prem_products"] for r in model["schedule"])
    assert t["total"] == t["premises_operations"] + t["products"] + t["other"]


def test_limit_hierarchy(model):
    """acord.limit-hierarchy: aggregates >= occurrence, always."""
    lim = model["limits"]
    assert lim["general_aggregate"] >= lim["each_occurrence"]
    assert lim["products_aggregate"] >= lim["each_occurrence"]


def test_yes_answers_explained(model):
    """acord.yes-answers-explained: every Y carries an explanation and
    surfaces in the REMARKS block."""
    remarks = "\n".join(acord.remarks_lines(model))
    for section, key in (("CONTRACTORS", "contractors"),
                         ("PRODUCTS/COMPLETED OPS", "products_section"),
                         ("GENERAL INFORMATION", "general_info")):
        block = model[key]
        for num, ans in block["answers"].items():
            if ans == "Y":
                assert num in block["explanations"], f"{key} Q{num} = Y unexplained"
                assert f"{section} ITEM {num}:" in remarks


def test_cross_field_consistency(model):
    """acord.cross-field-consistency: one underlying fact answers every
    question it touches, across pages (external review, round 4: page-2
    'leases equipment: Y' vs page-3 'machinery rented to others: N' was an
    instant underwriter flag)."""
    ct, gi = model["contractors"], model["general_info"]
    # equipment leasing: Contractors Q6 and General Info Q5 are the same fact
    assert (ct["answers"][6] == "Y") == (gi["answers"][5] == "Y")
    # the work description discloses road building -> earth-moving Q3 is Y
    assert "road building" in ct["work_desc"].lower()
    assert ct["answers"][3] == "Y"
    # employee counts reconcile: EBL total == FT + PT, covered <= total
    eb = model["employee_benefits"]
    assert eb["employees"] == ct["full_time"] + ct["part_time"]
    assert eb["covered"] <= eb["employees"]
    # EBL is claims-made coverage: a retro date is always present
    assert eb["retro_date"] and eb["retro_date"] != "N/A"


def test_forensic_pdf_structure(rendered):
    """acord.metadata-chronology: ModDate == CreationDate (no epoch
    placeholder, no modified-before-created), and the xref survives the
    byte-level metadata edits — every offset points at its object."""
    import re
    pdf = rendered.read_bytes()
    cd = re.search(rb"/CreationDate \((D:[0-9]+)\)", pdf).group(1)
    md = re.search(rb"/ModDate \((D:[0-9]+)\)", pdf).group(1)
    assert md == cd
    start = int(re.search(rb"startxref\s+(\d+)", pdf[-100:]).group(1))
    head = re.match(rb"xref\s+(\d+) (\d+)\s*\n", pdf[start:])
    first, count = int(head.group(1)), int(head.group(2))
    entries = start + head.end()
    for i in range(max(first, 1), first + count):
        off = int(pdf[entries + (i - first) * 20: entries + (i - first) * 20 + 10])
        assert re.match(rb"\d+ 0 obj", pdf[off:off + 16]), f"obj {i} stale offset"


def test_seeded_everywhere(model):
    same = acord.sample_126(random.Random(26))
    assert model == same
    a = acord.render_126(model, metadata=META)
    b = acord.render_126(same, metadata=META)
    assert a == b


def test_defect_delta_hooks(model):
    """acord.defect-delta-hooks: each hook breaks exactly its target."""
    totals = acord.compute_totals(model)

    bad = acord.render_126(model, metadata=META, defect={"premium_row": (0, 99_999)})
    content = _content(bad)
    assert "99,999" in content
    assert f"{model['schedule'][0]['prem_premops']:,}" not in content

    bad2 = acord.render_126(model, metadata=META,
                            defect={"premium_total": totals["total"] + 4_100})
    content2 = _content(bad2)
    assert f"{totals['total'] + 4_100:,}" in content2
    assert f"{totals['premises_operations']:,}" in content2  # components stay honest

    bad3 = acord.render_126(model, metadata=META,
                            defect={"each_occurrence": 4_000_000})
    content3 = _content(bad3)
    assert "4,000,000" in content3  # occurrence now exceeds the $2M aggregate


def test_metadata_dates_represented(rendered):
    info = lens.pdf_info(rendered)
    assert info["created"] == "D:20260415102200"
