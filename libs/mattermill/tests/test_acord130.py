"""acord130 capability tests — each maps to an acord130.* requirement in
foundry/spec/foundry.yaml.

Two contracts are under test. The layout contract is the real ACORD 130
(2017/05), transcribed in acord130.PAGE_MARKERS. The jurisdiction contract is
Minnesota's, sourced from MWCIA and recorded in
foundry/reference/templates/acord130/{provenance,contract}.json — the
classification rule, the premium build-up, and the guard list of pricing
programs that do not exist in this state.
"""

from __future__ import annotations

import io
import random

import pypdfium2 as pdfium
import pytest

from mattermill import acord130 as a

META = {"producer": "Acrobat Distiller 8.3.1 (Windows)",
        "creator": "AMS360 Form Library",
        "created": "2026-01-14 09:22:10", "modified": None}


def _pages(pdf: bytes) -> list[str]:
    doc = pdfium.PdfDocument(io.BytesIO(pdf))
    return [" ".join((p.get_textpage().get_text_range() or "").split())
            for p in doc]


def _content(pdf: bytes) -> str:
    return " ".join(_pages(pdf))


@pytest.fixture()
def model():
    return a.sample_130(random.Random(130))


@pytest.fixture()
def pdf(model):
    return a.render_130(model, metadata=META)


def test_2017_05_template_contract(pdf):
    """acord130.2017-05-template-contract: every marker transcribed from the
    real form appears, on the page it belongs to and in stream order. A form
    authored from memory drifts on exactly this — wrong section inventory,
    invented blocks, a footer from the wrong edition."""
    pages = _pages(pdf)
    assert len(pages) == 4
    for page_num, markers in a.PAGE_MARKERS.items():
        text = pages[page_num - 1]
        cursor = 0
        for marker in markers:
            idx = text.find(" ".join(marker.split()), cursor)
            assert idx >= 0, f"page {page_num} missing marker: {marker!r}"
            cursor = idx


def test_classification_is_derived():
    """acord130.classification-derived: Minnesota's gasoline-station code
    follows from what the station does. Full service is 8380 whatever the
    receipts split; self-service turns on the 90% gasoline test."""
    assert a.classify_station(full_service=True, gasoline_share=0.99,
                              food_service_share=0.02) == "8380"
    assert a.classify_station(full_service=True, gasoline_share=0.40,
                              food_service_share=0.30) == "8380"
    assert a.classify_station(full_service=False, gasoline_share=0.90,
                              food_service_share=0.05) == "8381"
    assert a.classify_station(full_service=False, gasoline_share=0.899,
                              food_service_share=0.05) == "8006"
    # Above the 50% food-service test the store is not an 8006 risk at all,
    # and the restaurant split was not sourced — so it raises rather than
    # guessing a classification.
    with pytest.raises(ValueError, match="food or beverages"):
        a.classify_station(full_service=False, gasoline_share=0.30,
                           food_service_share=0.55)


def test_sampled_model_matches_its_own_class():
    """acord130.classification-derived: the code on the worksheet is the one
    the station's own facts produce — never a free draw beside them."""
    for seed in range(25):
        m = a.sample_130(random.Random(seed))
        assert m["class_code"] == a.classify_station(
            full_service=m["full_service"],
            gasoline_share=m["gasoline_share"],
            food_service_share=m["food_service_share"])
        assert m["worksheet"][0]["class_code"] == m["class_code"]
        assert m["class_code"] in a.MN_RATING["rates"]


def test_worksheet_foots(model):
    """acord130.worksheet-foots: every row's manual premium is its own payroll
    over 100 times its own rate, and the page-2 TOTAL is their sum."""
    for row in model["worksheet"]:
        assert row["premium"] == round(row["payroll"] / 100 * row["rate"])
    prem = a.compute_premium(model)
    assert prem["manual_premium"] == sum(r["premium"] for r in model["worksheet"])
    assert prem["total_payroll"] == sum(r["payroll"] for r in model["worksheet"])


def test_premium_box_order(model):
    """acord130.premium-box-order: standard premium excludes the expense
    constant, the SCF surcharge and Terrorism by rule, and those three are
    added after the discount. Terrorism is computed on total payroll and takes
    no modification of any kind."""
    r = a.MN_RATING
    prem = a.compute_premium(model)
    assert prem["standard_premium"] == (
        prem["manual_premium"] + prem["experience_mod_charge"]
        + prem["schedule_rating_charge"] + prem["increased_limits"])
    assert prem["terrorism"] == round(
        prem["total_payroll"] / 100 * r["terrorism_per_100_payroll"])
    assert prem["scf_surcharge"] == round(
        prem["standard_premium"] * r["scf_assessment_pct"] / 100)
    assert prem["total_estimated_annual"] == max(
        prem["standard_premium"] - prem["premium_discount"]
        + prem["expense_constant"] + prem["terrorism"] + prem["scf_surcharge"],
        prem["minimum_premium"])
    # the sourced Type A table: 0.0% through the first bracket, then 0.1% a step
    assert a.premium_discount_pct(5_000) == 0.0
    assert a.premium_discount_pct(5_026) == 0.0
    assert a.premium_discount_pct(5_027) == 0.1
    assert a.premium_discount_pct(9_405) == 4.4
    with pytest.raises(ValueError, match="above the transcribed range"):
        a.premium_discount_pct(50_000)


def test_page1_total_agrees_with_page2(model, pdf):
    """acord130.worksheet-foots: the page-2 worksheet foots into the PREMIUM
    box, which foots into the page-1 TOTAL ESTIMATED ANNUAL PREMIUM - ALL
    STATES. A total that appears twice and disagrees is the first thing an
    underwriter checks."""
    prem = a.compute_premium(model)
    total = f"{prem['total_estimated_annual']:,.0f}"
    pages = _pages(pdf)
    assert total in pages[0], "page 1 all-states total missing"
    assert total in pages[1], "page 2 state total missing"


def test_minnesota_guard_list(model, pdf):
    """acord130.minnesota-guard-list: the rows Minnesota's User's Guide
    publishes as unavailable here carry no charge. ARAP and the Assigned Risk
    Surcharge Program do not exist in this state; Catastrophe is a non-ratable
    element and non-ratable elements do not apply in Minnesota; CCPAP is
    Minnesota's MCPAP and is a contracting program.

    The labels are preprinted on the form, so their presence is correct — what
    must be absent is a CHARGE beside them. An empty cell and a zero are not
    the same claim: a zero is a computed charge, an empty cell is a program
    that does not exist here."""
    prem = a.compute_premium(model)
    rows = dict((lab, amt) for lab, _f, amt
                in (a.premium_rows(model, prem)[0] + a.premium_rows(model, prem)[1]))
    for label in a.UNAVAILABLE_ROWS:
        assert label in rows, f"row not on the form at all: {label}"
        assert rows[label] is None, \
            f"{label} carries a charge in a state that has no such program"
    # and the labels really are preprinted, since the guard is about what sits
    # beside them, not about hiding the row
    page2 = _pages(pdf)[1]
    for label in ("ARAP", "ASSIGNED RISK SURCHARGE", "CATASTROPHE", "CCPAP"):
        assert label in page2, f"preprinted row missing: {label}"


def test_minnesota_is_not_an_ncci_state(model, pdf):
    """acord130.minnesota-guard-list: MWCIA, not NCCI, is Minnesota's rating
    organisation, so the risk's file number goes in OTHER RATING BUREAU ID and
    the NCCI RISK ID box stays empty."""
    assert a.MN_RATING["is_ncci_state"] is False
    assert model["ncci_risk_id"] == ""
    assert model["other_bureau_id"].startswith("MN ")
    page1 = _pages(pdf)[0]
    assert "NCCI RISK ID NUMBER" in page1          # the box is preprinted
    assert "OTHER RATING BUREAU ID OR STATE" in page1
    assert model["other_bureau_id"] in page1


def test_experience_rating_eligibility(pdf):
    """acord130.experience-rating-eligibility: a Minnesota risk under the
    $15,000 threshold has no modification promulgated for it, so the field is
    unity and the loss-history MOD column is blank — with the reason stated in
    REMARKS rather than left as an unexplained gap."""
    threshold = a.MN_RATING["experience_rating_eligibility_premium"]
    for seed in range(30):
        m = a.sample_130(random.Random(seed))
        manual = sum(r["premium"] for r in m["worksheet"])
        assert m["experience_rating_eligible"] == (manual >= threshold)
        if not m["experience_rating_eligible"]:
            assert m["experience_mod"] is None
            assert all(r["mod"] == "" for r in m["loss_history"])
        else:
            assert m["experience_mod"] is not None
            assert all(r["mod"] for r in m["loss_history"])
    assert "no experience modification promulgated by MWCIA" in _content(pdf)


def test_officer_payroll_limits(model, pdf):
    """acord130.officer-payroll-limits: an included officer's remuneration sits
    between Minnesota's weekly minimum and maximum, and — per the form's own
    instruction — is PART OF the station's rating payroll rather than a
    separate figure that happens to sit nearby."""
    r = a.MN_RATING
    for seed in range(20):
        m = a.sample_130(random.Random(seed))
        assert r["officer_weekly_min"] <= m["owner_weekly"] <= r["officer_weekly_max"]
        assert m["owner_annual"] == m["owner_weekly"] * 52
        station = m["worksheet"][0]
        assert station["payroll"] > m["owner_annual"], \
            "officer remuneration is not contained in the station payroll"
        assert m["owner_class_code"] == m["class_code"]
    assert f"{model['owner_annual']:,.0f}" in _pages(pdf)[0]


def test_yes_answers_explained(model, pdf):
    """acord130.yes-answers-explained: the form instructs EXPLAIN ALL "YES"
    RESPONSES, so every Y carries an explanation and every explanation reaches
    the page-2 REMARKS block."""
    text = _content(pdf)
    ys = [i for i, v in model["answers"].items() if v == "Y"]
    assert ys, "a gasoline station cannot answer every question N"
    for i in ys:
        assert i in model["explanations"], f"question {i} answered Y unexplained"
        assert f"GENERAL INFORMATION ITEM {i}:" in text
    for i, v in model["answers"].items():
        if v == "N":
            assert f"GENERAL INFORMATION ITEM {i}:" not in text


def test_fuel_tanks_answer_is_coupled(pdf):
    """acord130.yes-answers-explained: question 2 names fuel tanks in its own
    text. A gasoline station stores motor fuel, so there is no honest N here —
    the answer follows from what the risk is."""
    for seed in range(15):
        m = a.sample_130(random.Random(seed))
        assert m["answers"][2] == "Y"
        assert "storage tank" in m["explanations"][2]
    assert "underground motor fuel storage tanks" in _content(pdf)


def test_state_gate():
    """acord130.state-gate: the state is a gate, not a label. A rating world is
    a jurisdiction's own arithmetic and none of it transfers, so a state whose
    world was never sourced raises rather than borrowing Minnesota's."""
    with pytest.raises(ValueError, match="no rating world sourced"):
        a.sample_130(random.Random(1), pins={"state": "WI"})
    with pytest.raises(ValueError, match="no rating world sourced"):
        a.sample_130(random.Random(1), pins={"state": "CA"})
    ok = a.sample_130(random.Random(1), pins={"state": "MN"})
    assert ok["state"] == "MN"


def test_canon_is_caller_supplied():
    """The world is DATA. Every party, place and policy number follows from a
    caller-supplied canon; the shipped default is invented."""
    mine = dict(a.CANON, insured="Hollow Creek Fuel Stop, Inc.",
                city="Bemidji", county="Beltrami", brand="Hollow Creek Stop")
    m = a.sample_130(random.Random(3), canon=mine)
    text = _content(a.render_130(m, metadata=META))
    assert "Hollow Creek Fuel Stop, Inc." in text
    assert "Bemidji, Beltrami County" in text
    assert a.CANON["insured"] not in text
    with pytest.raises(ValueError, match="canon missing required keys"):
        a.sample_130(random.Random(3), canon={"agency": "X"})


def test_unknown_pins_are_refused():
    with pytest.raises(ValueError, match="unknown pins"):
        a.sample_130(random.Random(1), pins={"clas_code": "8006"})


def test_defect_delta_hooks(model):
    """acord130.defect-delta-hooks: each hook alters exactly one displayed
    value while everything computed around it stays honest — which is what
    makes the artifact scorable rather than merely wrong."""
    clean = _content(a.render_130(model, metadata=META))
    prem = a.compute_premium(model)

    # (1) a worksheet row that stops footing against its own payroll x rate.
    # The planted value stays in the range a real mis-keyed premium would take
    # — an absurd figure is spotted by arithmetic-free reading and makes a
    # weak fixture.
    wrong = model["worksheet"][0]["premium"] + 1_400
    bad = _content(a.render_130(model, metadata=META,
                                defect={"worksheet_premium": (0, wrong)}))
    assert f"{wrong:,.0f}" in bad
    assert f"{model['worksheet'][0]['payroll']:,.0f}" in bad     # payroll intact
    assert f"{model['worksheet'][0]['rate']:.3f}" in bad         # rate intact

    # (2) a total that mis-adds while every component still shows correctly
    bad2 = _content(a.render_130(model, metadata=META,
                                 defect={"premium_total": 1_234_567}))
    assert "1,234,567" in bad2
    assert f"{prem['standard_premium']:,.0f}" in bad2
    assert f"{prem['expense_constant']:,.0f}" in bad2

    # (3) a modification on a risk Minnesota does not experience-rate
    assert model["experience_rating_eligible"] is False
    bad3 = _content(a.render_130(model, metadata=META,
                                 defect={"experience_mod": 0.79}))
    assert "0.79" in bad3
    assert "0.79" not in clean

    # (4) a charge under a program the state does not have
    bad4 = _content(a.render_130(model, metadata=META, defect={"arap": 412}))
    page2 = _pages(a.render_130(model, metadata=META, defect={"arap": 412}))[1]
    assert "412" in page2
    assert "412" not in _pages(a.render_130(model, metadata=META))[1]
    assert "ARAP" in bad4


def test_metadata_is_born_digital(pdf):
    """An ACORD 130 (2017/05) is printed by an agency management system, so it
    is a vector file, not a scan — no JPEG page images, and a creation date in
    the era the document claims."""
    import re
    assert b"/DCTDecode" not in pdf
    created = re.search(rb"/CreationDate \(D:(\d{4})", pdf).group(1)
    assert int(created) >= 2017, "the 2017/05 edition cannot predate its own release"


def test_seeded_everywhere(model):
    """seeded.everywhere: same seed in, same model and same bytes out."""
    assert model == a.sample_130(random.Random(130))
    assert a.render_130(model, metadata=META) == a.render_130(model, metadata=META)
    other = a.sample_130(random.Random(131))
    assert a.render_130(other, metadata=META) != a.render_130(model, metadata=META)


def test_every_class_branch_renders():
    """All three gasoline-station codes must render, not just the common one.
    A branch that has never been drawn is a branch that has never been seen."""
    seen = {}
    for seed in range(60):
        m = a.sample_130(random.Random(seed))
        seen.setdefault(m["class_code"], m)
    assert set(seen) == {"8006", "8380", "8381"}, f"only produced {sorted(seen)}"
    for code, m in seen.items():
        text = _content(a.render_130(m, metadata=META))
        assert code in text
        assert a.GASOLINE_STATION_CLASSES[code] in text
