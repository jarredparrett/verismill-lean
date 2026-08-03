"""Diligence-packet capability tests — each maps to a diligence.* requirement
in foundry/spec/foundry.yaml. The world under test is
diligence.DEFAULT_CANON — a 1993 pre-opening diligence packet for a private
biological reserve. Canon is caller-supplied data, so these tests assert
against the canon rather than against any particular set of names."""

from __future__ import annotations

import datetime as _dt
import random
import re

import pytest

from mattermill import diligence, lens

META = {"producer": "Canon DR-C240 / Adobe Paper Capture",
        "creator": "Canon DR-C240",
        "created": "2019-03-14 09:22:11"}


@pytest.fixture(scope="module")
def model():
    return diligence.sample_packet(random.Random(93))


@pytest.fixture(scope="module")
def rendered(model):
    return diligence.render_packet(model, metadata=META)


_LITERAL = re.compile(r"\(((?:\\.|[^()\\])*)\)")
# Page furniture: bates stamps plus every party-appropriate legend (longest
# first, so the longer markings are stripped before their substrings).
_LEGENDS = sorted({diligence.DEFAULT_LEGEND, *diligence.PAGE_LEGENDS.values()},
                  key=len, reverse=True)
BATES = diligence.DEFAULT_CANON["bates_prefix"]
BATES_RE = re.escape(BATES)

_FURNITURE = re.compile("|".join([BATES_RE]
                                 + [re.escape(l) for l in _LEGENDS]))


@pytest.fixture(scope="module")
def stream(rendered):
    """The decompressed content stream — where the PDF operators live."""
    return lens._flate_streams(rendered).decode("latin-1", "replace")


def _read_stream(stream: str) -> str:
    """The packet as a reader sees it — reconstructed from the OCR layer,
    which is the only surface a judge or an adversary actually reads. Each
    drawn line is its own text-show operator, so reading order is recovered
    by joining the string literals in stream order."""
    def unescape(s):
        # octal escapes first (e.g. \227 — the WinAnsi em-dash), then the
        # simple ones; "(" is not an octal digit so the order is safe
        s = re.sub(r"\\([0-7]{3})",
                   lambda m: bytes([int(m.group(1), 8)]).decode("cp1252"), s)
        return s.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")

    parts = [unescape(m.group(1)) for m in _LITERAL.finditer(stream)]
    return re.sub(r"\s+", " ", " ".join(parts))


def _read(pdf: bytes) -> str:
    """Read a rendered packet end to end — for tests that render their own."""
    return _read_stream(lens._flate_streams(pdf).decode("latin-1", "replace"))


@pytest.fixture(scope="module")
def text(stream):
    return _read_stream(stream)


@pytest.fixture(scope="module")
def prose(text):
    """`text` with the per-page furniture (bates stamp, confidentiality
    legend) removed, so a sentence that spans a page break still reads as one
    sentence. Content assertions belong here; bates assertions belong on
    `text`."""
    return re.sub(r"\s+", " ", _FURNITURE.sub(" ", text))


def _lines(model, defect=None):
    return diligence.compose_packet(model, defect)


def _texts(lines):
    out = []
    for ln in lines:
        if ln.get("t"):
            out.append(ln["t"])
        if ln.get("hang"):
            out.append(ln["hang"][1])
        if ln.get("row"):
            out.extend(str(c) for c in ln["row"] if c and not isinstance(c, tuple))
    return out


# -- structure ---------------------------------------------------------------

def test_packet_index_matches_tabs(model, text):
    """diligence.packet-index-matches-tabs: the index lists exactly the tabs
    rendered, each against the bates number where that tab actually begins."""
    _, _, tab_pages = diligence._vector(_lines(model), model)
    assert sorted(tab_pages) == sorted(t[0] for t in diligence.TABS)
    for tab, title, source, _ in diligence.TABS:
        assert tab_pages[tab] in text, f"tab {tab} bates missing from index"
        assert f"TAB {tab}" in text, f"divider for tab {tab} missing"
    # the cited bates are ascending in tab order — an index that points
    # backwards is the tell that the index was written independently
    cited = [tab_pages[t[0]] for t in diligence.TABS]
    assert cited == sorted(cited)


def test_bates_continuous_and_unique(model, rendered, text):
    """diligence.bates-continuous: every page carries a bates number; the
    sequence is unbroken from 1 and never repeats."""
    found = sorted(set(re.findall(BATES_RE + r"(\d{6})", text)))
    import pypdfium2 as pdfium
    n_pages = len(pdfium.PdfDocument(rendered))
    assert len(found) == n_pages, f"{len(found)} stamps for {n_pages} pages"
    assert [int(f) for f in found] == list(range(1, n_pages + 1))


def test_per_source_visual_identity(model):
    """diligence.per-source-visual-identity: instruments from different
    organisations do not share a typeface. A packet whose tabs are uniform
    reads as one author's work."""
    fonts_by_tab = {}
    for tab, _, _, fn in diligence.TABS:
        c = diligence._C()
        fn(c, model, diligence.compute_coverage(model))
        fonts_by_tab[tab] = {ln["font"][0] for ln in c.lines
                             if ln.get("font")}
    families = {tab: {f.split("-")[0] for f in fonts}
                for tab, fonts in fonts_by_tab.items()}
    # the law firm, the London surveyor and the operator's safety office must
    # not resolve to the same family
    assert families["1"] != families["2"], "counsel and surveyor share a face"
    assert families["2"] != families["4"], "surveyor and operator share a face"
    assert len({frozenset(f) for f in families.values()}) >= 3


# -- coherence by construction ----------------------------------------------

def test_specimen_roster_single_source(model, prose):
    """diligence.specimen-roster-single-source: the surveyor's schedule, the
    veterinary certificate and the licence exhibit are written by three
    parties and must agree, because all three render from one roster."""
    total = diligence.total_specimens(model)
    assert prose.count(f"{total}") >= 3
    for r in model["roster"]:
        # each species appears in all three schedules with the same count
        assert r["species"] in prose
    cov = diligence.compute_coverage(model)
    for tab in ("2", "3", "5"):
        fn = dict((t[0], t[3]) for t in diligence.TABS)[tab]
        c = diligence._C()
        fn(c, model, cov)
        rows = [ln["row"] for ln in c.lines if ln.get("row")]
        counts = {r[0]: r[1] for r in rows
                  if r and r[0] in {s["species"] for s in model["roster"]}}
        for spec in model["roster"]:
            assert counts[spec["species"]] == str(spec["count"]), (
                f"tab {tab} disagrees on {spec['species']}")


def test_containment_class_derived_not_sampled(model):
    """diligence.specimen-roster-single-source: class follows from mass AND
    behaviour. Velociraptor is apex on the pack limb alone — a rule that read
    mass only would under-rate the enclosure that fails."""
    for r in model["roster"]:
        assert r["class"] == diligence._containment_class(
            r["adult_mass_kg"], r["predator"], r["pack"])
    raptor = [r for r in model["roster"] if r["species"] == "Velociraptor"][0]
    rex = [r for r in model["roster"] if r["species"] == "Tyrannosaurus rex"][0]
    assert raptor["class"] == rex["class"] == "IV"
    assert raptor["adult_mass_kg"] < rex["adult_mass_kg"] / 10
    # strip the behavioural limb and it drops two classes
    assert diligence._containment_class(raptor["adult_mass_kg"], True,
                                        False) == "III"


def test_chronology_by_construction(model):
    """diligence.chronology-by-construction: every date derives by offset from
    one anchor, so the incident cannot postdate the survey that investigates
    it or the resolution that recites it."""
    order = ["incident_date", "survey_date", "memo_date", "board_date",
             "visit_date"]
    dates = [model[k] for k in order]
    assert dates == sorted(dates), dict(zip(order, dates))
    assert all(isinstance(d, _dt.date) for d in dates)
    # digitisation is in the PDF era and long after the represented events
    assert model["digitised"].year >= 2016
    assert model["digitised"] > model["visit_date"]


def test_open_recommendations_tracked(model, prose):
    """diligence.open-recommendations-tracked: counsel and the board describe
    as open exactly what the surveyor's register records as open — computed
    from the register, never restated."""
    open_a = diligence.open_recommendations(model, "A")
    assert open_a, "fixture should have open A-rated items to track"
    serial = diligence._serial([r["no"] for r in open_a])
    # the same computed serial appears in the memo AND in the resolution
    assert prose.count(serial) >= 2, f"{serial!r} not tracked across tabs"
    n_a = len([r for r in model["recommendations"] if r["priority"] == "A"])
    assert f"{len(open_a)} of {n_a}" in prose
    # closed items are not described as outstanding
    closed = [r["no"] for r in model["recommendations"]
              if r["status"] == "Closed"]
    for no in closed:
        assert str(no) not in serial.split(", ")


def test_coverage_schedule_foots(model):
    """diligence.coverage-schedule-foots: sub-limits are fractions of the
    each-occurrence limit and the tower stacks; the Section I premium follows
    from the CONVENTIONAL declared values (which are themselves the sum of
    the statement-of-values components) and the applied rate."""
    cov = diligence.compute_coverage(model)
    assert cov["aggregate_mm"] == pytest.approx(cov["each_occurrence_mm"] * 2)
    assert cov["class_iv_sublimit_mm"] < cov["animal_sublimit_mm"]
    assert cov["animal_sublimit_mm"] < cov["each_occurrence_mm"]
    assert cov["each_occurrence_mm"] <= cov["aggregate_mm"]
    assert cov["premium"] == pytest.approx(
        cov["conventional_mm"] * 1000 * model["rate_per_mille"])
    for _, value in cov["layers"]:
        assert value <= cov["aggregate_mm"]


# -- the realism thesis ------------------------------------------------------

def test_scope_limitations_present(model, prose):
    """diligence.scope-limitations-present: each professional certifies
    something narrower than a reader assumes. If the limitations vanish the
    packet stops being an explanation and becomes a fantasy."""
    # counsel declines containment; the vet declines the control systems
    assert "express no opinion upon the adequacy of any containment" in prose
    assert "am not competent to certify, the adequacy of the systems" in prose
    # the vet's certificate is bounded in time and by body mass
    assert "as presently housed and at the body masses recorded" in prose
    assert "should not be relied upon beyond ninety days" in prose
    # the apex specimens were never examined at close quarters
    assert "were not examined at close quarters" in prose
    # the surveyor sub-limits rather than declines
    assert "not instructed to advise whether the risk should be written" in prose
    # counsel's minors advice, and that it was overridden
    assert "unenforceable in the majority of United States jurisdictions" in prose
    assert "the Chairman intends otherwise" in prose


def test_authorization_scope_limited(model, prose):
    """diligence.authorization-scope-limited: the board authorises an
    inspection and expressly not an opening, and the release is scoped to a
    private-facility invitee rather than a member of the public."""
    assert ("NOTHING IN THESE RESOLUTIONS AUTHORISES THE OPENING OF THE "
            "FACILITY TO THE PUBLIC") in prose
    assert "reserved to this Board and shall be the subject of a further" in prose
    assert "is not a customer, patron or member of the public" in prose
    assert "It is not open to the public, no admission is sold" in prose
    # the dissent on the minors resolution is recorded, not smoothed away
    assert model["dissenting_director"] in prose
    assert "dissenting" in prose


# -- period honesty ----------------------------------------------------------

def test_period_honest_1993(model, prose):
    """diligence.period-honest-1993: the represented instruments exist in
    1993 and the ones that do not are absent."""
    assert "MIRENEM" in prose                       # the ministry of the day
    assert "7317" in prose                          # Ley de Vida Silvestre 1992
    # the CBD is signed but not yet in force, which is the whole point
    assert "Convention on Biological Diversity" in prose
    assert "It is not in force, and the Republic has not ratified" in prose


@pytest.mark.parametrize("anachronism", [
    "MINAE",                       # the ministry from 1995
    "SINAC",                       # created 1998
    "Ley Orgánica del Ambiente",   # 1995
    "Cartagena Protocol",          # 2000
    "Nagoya Protocol",             # 2010
    "e-mail", "website", "Internet",
])
def test_no_anachronisms(prose, anachronism):
    """diligence.period-honest-1993 (guard): instruments and terms that
    postdate the represented date must not appear. MINAE and SINAC are the
    sharp ones — they are what a from-memory draft reaches for."""
    assert anachronism not in prose


def test_period_honest_scan(model, rendered):
    """diligence.period-honest-scan: a production set is paper first and
    images later. Pages are JPEG, metadata dates the digitisation in the PDF
    era, and ModDate equals CreationDate for a flattened export."""
    meta = lens.pdf_meta(rendered) if hasattr(lens, "pdf_meta") else None
    assert b"/DCTDecode" in rendered, "pages must be scanned images"
    created = re.search(rb"/CreationDate\s*\(D:(\d{8})", rendered).group(1)
    modified = re.search(rb"/ModDate\s*\(D:(\d{8})", rendered).group(1)
    assert created == modified, "flattened export: ModDate == CreationDate"
    assert created.startswith(b"2019")
    # the 1993 originals never claim a 1993 CreationDate
    assert not created.startswith(b"1993")


def test_ocr_text_layer_is_invisible_and_searchable(stream, text):
    """diligence.period-honest-scan: the Paper-Capture text layer is present
    (searchable) and rendered invisibly (mode 3), as a real one is."""
    assert "3 Tr" in stream, "text layer must be render mode 3 (invisible)"
    assert diligence.DEFAULT_CANON["island"] in text
    assert diligence.DEFAULT_CANON["park"] in text


# -- determinism -------------------------------------------------------------

def test_sample_deterministic():
    """seeded.everywhere: same seed in, same model out."""
    a = diligence.sample_packet(random.Random(7))
    b = diligence.sample_packet(random.Random(7))
    assert a == b
    assert diligence.sample_packet(random.Random(8)) != a


def test_render_byte_identical(model):
    """seeded.everywhere: same model in, byte-identical bytes out."""
    a = diligence.render_packet(model, metadata=META)
    b = diligence.render_packet(model, metadata=META)
    assert a == b


# -- defect hooks ------------------------------------------------------------

def test_defect_specimen_count_breaks_only_the_certificate(model):
    """diligence.defect-delta-hooks: one displayed count moves; the surveyor's
    schedule and the licence exhibit stay honest, so the three-way agreement
    becomes a findable, provable contradiction."""
    clean = _texts(_lines(model))
    target = model["roster"][1]["species"]
    bad = _texts(_lines(model, {"specimen_count": (target, 99)}))
    assert clean != bad
    assert sum("99" == t for t in bad) >= 1
    # the totals recompute honestly around the altered row
    m2 = diligence._apply_defect(model, {"specimen_count": (target, 99)})
    assert diligence.total_specimens(m2) != diligence.total_specimens(model)


def test_defect_recommendation_status_splits_register_from_narrative(model):
    """diligence.defect-delta-hooks: flipping one register status leaves the
    memo and the board reciting an item the register now shows closed — a
    cross-instrument contradiction with a quotable span on both sides."""
    open_a = diligence.open_recommendations(model, "A")
    no = open_a[0]["no"]
    m2 = diligence._apply_defect(model, {"recommendation_status": (no, "Closed")})
    assert no not in [r["no"] for r in diligence.open_recommendations(m2, "A")]
    assert len(diligence.open_recommendations(m2, "A")) == len(open_a) - 1


def test_defect_incident_date_inverts_chronology(model):
    """diligence.defect-delta-hooks: the board recites an incident dated after
    the meeting that recites it — the chronology break an expert checks."""
    later = model["board_date"] + _dt.timedelta(days=10)
    m2 = diligence._apply_defect(model, {"incident_date": later})
    assert m2["incident_date"] > m2["board_date"]
    assert model["incident_date"] < model["board_date"]      # clean is honest


def test_defect_sublimit_breaks_the_tower(model):
    """diligence.defect-delta-hooks: one sub-limit exceeds the layer above it
    while every other figure stays computed and correct."""
    m2 = diligence._apply_defect(model, {"class_iv_sublimit_pct": 1.4})
    cov = diligence.compute_coverage(m2)
    assert cov["class_iv_sublimit_mm"] > cov["each_occurrence_mm"]
    assert cov["aggregate_mm"] == pytest.approx(cov["each_occurrence_mm"] * 2)


# -- the underwriting file (round 6) -----------------------------------------

def test_programme_towers_separated(model, prose):
    """diligence.programme-towers-separated: the programme is placed in
    sections, each with its own rating base — property-style rating no
    longer sits on a liability schedule."""
    cov = diligence.compute_coverage(model)
    assert len(cov["sections"]) == 6
    romans = [r for r, _, _ in cov["sections"]]
    assert romans == ["I", "II", "III", "IV", "V", "VI"]
    for roman, name, _ in cov["sections"]:
        assert f"Section {roman}" in prose, f"section {roman} not on slip"
    # BI is standing-charges only: speculative revenue is refused, in words
    assert "standing charges and increased cost of working only" in prose
    assert "Prospective gate receipts" in prose


def test_statement_of_values_foots(model, prose):
    """diligence.statement-of-values-foots: the declared total is the sum of
    the conventional components and the specimen schedule — components are
    sampled, the total is derived, and each line carries its basis."""
    cov = diligence.compute_coverage(model)
    assert cov["conventional_mm"] == pytest.approx(
        round(sum(v for _, v, _ in model["sov_conventional"]), 1))
    assert cov["specimen_mm"] == pytest.approx(
        round(sum(r["count"] * r["agreed_value_mm"]
                  for r in model["roster"]), 1))
    assert cov["declared_mm"] == pytest.approx(
        round(cov["conventional_mm"] + cov["specimen_mm"], 1))
    assert f"USD {cov['declared_mm']:,.1f} m" in prose
    for item, value, basis in model["sov_conventional"]:
        assert f"USD {value:,.1f} m" in prose
    # the value-basis question an underwriter actually asks is answered
    assert "Agreed value" in prose
    assert "neither production cost nor" in prose
    # and the library is expressly NOT insured (coheres with the licence)
    assert "genetic library" in prose


def test_placing_slip_subscription(model, prose):
    """diligence.placing-slip-subscription: written lines oversubscribe;
    signed lines are computed and foot to exactly 100%; following markets
    are not passive clones of the lead — at least one line condition."""
    cov = diligence.compute_coverage(model)
    assert cov["written_total"] > 100.0
    assert sum(cov["signed"]) == pytest.approx(100.0)
    # each follower signs no more than it wrote
    for s, signed in zip(model["subscription"], cov["signed"]):
        assert signed <= s["written"] + 1e-9
    assert model["subscription"][0]["lead"]
    conditions = [s["condition"] for s in model["subscription"]
                  if s["condition"]]
    assert conditions, "every follower is a passive clone"
    for cond in conditions:
        assert cond.split()[0] in prose
    assert f"{cov['written_total']:.2f}%" in prose
    assert "100.00%" in prose


def test_subjectivities_derived(model, prose):
    """diligence.subjectivities-derived: the lead's register cannot disagree
    with the instruments it reads from — the minors item is unsatisfied
    because resolution 6 permits them; the certification item tracks the
    open A-rated recommendations; the census item tracks recommendation 6."""
    reg = diligence.subjectivity_register(model)
    by_no = {s["no"]: s for s in reg}
    assert by_no[2]["status"] == "NOT SATISFIED"          # resolution 6
    open_a = diligence.open_recommendations(model, "A")
    assert (by_no[3]["status"] == "NOT SATISFIED") == bool(open_a)
    rec6_open = any(r["no"] == 6 and r["status"] == "Open"
                    for r in model["recommendations"])
    assert (by_no[6]["status"] == "NOT SATISFIED") == rec6_open
    # the register appears in the packet, and the minors item's evidence
    # cites the board's own resolution (cells wrap, so assert on the model
    # side and on tokens that cannot split)
    assert "SUBJECT TO" in prose
    assert "NOT SATISFIED" in prose
    for name, _age in model["minors"]:
        assert name.title() in by_no[2]["evidence"]


def test_special_acceptance_trail(model, prose):
    """diligence.special-acceptance-trail: request -> refusal -> priced,
    restricted exception. The market does not waive; it prices — and the
    exclusion names the minors against Class III and IV contact."""
    m = model
    cov = diligence.compute_coverage(m)
    assert "REQUEST FOR SPECIAL ACCEPTANCE" in prose
    assert "Underwriters do not waive the subjectivities" in prose
    assert f"ENDORSEMENT NO. {m['endt_no']}" in prose
    assert f"USD {cov['ap_inspection']:,.2f}" in prose
    for name, _age in m["minors"]:
        assert name.title() in prose
    assert "contact with, escape of, or attempted avoidance" in prose
    assert "are not waived and remain unsatisfied" in prose
    # chronology: request follows the board; endorsement precedes the visit
    assert m["board_date"] < m["request_date"] < m["visit_date"]
    assert m["request_date"] < m["endt_date"] < m["visit_date"]


def test_warranty_1993_discharge(model, prose):
    """diligence.warranty-1993-discharge: in 1993 a breach of warranty
    DISCHARGES underwriters from the date of breach (MIA 1906 s.33(3)
    regime). Suspension-until-cure is an Insurance Act 2015 anachronism and
    must not appear."""
    assert "discharged from liability" in prose
    assert "discharges Underwriters from liability" in prose
    assert "without prejudice to liability" in prose
    assert not re.search(r"suspend(?:ed|s)? (?:cover|from the date)", prose)
    assert "until compliance is certified" not in prose


def test_retention_full_dollars(model, prose):
    """diligence.retention-full-dollars: the retention renders in full
    dollars everywhere. A $250 retention against a $15m occurrence limit was
    the round-6 review's sharpest single catch."""
    cov = diligence.compute_coverage(model)
    usd = cov["retention_usd"]
    assert usd == model["retention_k"] * 1000
    assert (f"${usd:,}" in prose) and (f"USD {usd:,}" in prose)
    # the bare thousands figure never renders as a dollar amount
    assert f"${model['retention_k']:,} each and every loss" not in prose
    assert f"USD {model['retention_k']:,} " not in prose + " "


def test_pricing_decomposed_foots(model, prose):
    """diligence.pricing-decomposed-foots: each section premium follows from
    its own base; the annual premium is their sum; the inclusive total adds
    the inspection additional premium."""
    m = model
    cov = diligence.compute_coverage(m)
    assert cov["annual_premium"] == pytest.approx(
        sum(p for _, _, p in cov["sections"]))
    sov = dict((item, v) for item, v, _ in m["sov_conventional"])
    assert cov["sections"][1][2] == pytest.approx(
        round((sov["Control, communications and security systems"]
               + sov["Power generation and distribution"]) * 1000
              * m["mb_rate_per_mille"], 2), rel=1e-3)
    assert cov["sections"][4][2] == pytest.approx(
        cov["specimen_mm"] * 1000 * m["specimen_rate_per_mille"], rel=1e-3)
    for _, _, prem in cov["sections"]:
        assert f"USD {prem:,.2f}" in prose
    assert f"USD {cov['annual_premium']:,.2f}" in prose
    assert (f"USD {cov['annual_premium'] + cov['ap_inspection']:,.2f}"
            in prose)


def test_pml_scenarios(model, prose):
    """diligence.pml-scenarios: the survey quantifies property PML per
    scenario and records WHY the liability MFL cannot be estimated, instead
    of merely asserting that it cannot."""
    cov = diligence.compute_coverage(model)
    assert cov["pml_control_mm"] == pytest.approx(
        round(cov["conventional_mm"] * model["pml_control_pct"], 1))
    for key in ("pml_control_mm", "pml_fire_mm", "pml_storm_mm"):
        assert f"USD {cov[key]:,.1f} m" in prose
    assert "ESTIMATED MAXIMUM LOSS" in prose
    assert "not bounded by the insured premises" in prose


def test_party_appropriate_markings(model):
    """diligence.party-appropriate-markings: privilege belongs to counsel's
    memorandum alone. The survey carries an underwriting-purposes legend, the
    lead's file note is not to be disclosed to the assured, and no page
    outside tab 1 claims privilege."""
    lines = _lines(model)
    _, pages_runs, tab_pages = diligence._vector(lines, model)
    # rebuild page -> legend from the frame runs
    legends = {}
    for idx, runs in enumerate(pages_runs, start=1):
        for _x, y, text, _f in runs:
            if y == 56.0 and not text.startswith(BATES):
                legends[idx] = text
    start = {tab: int(b.split("-")[-1]) for tab, b in tab_pages.items()}
    order = sorted(start, key=lambda t: start[t])
    end = {tab: (start[order[i + 1]] - 1 if i + 1 < len(order)
                 else max(legends))
           for i, tab in enumerate(order)}
    for tab in order:
        for page in range(start[tab], end[tab] + 1):
            expected = diligence.PAGE_LEGENDS[tab]
            assert legends[page] == expected, (tab, page, legends[page])
    # privilege appears on tab 1's pages only
    for page, legend in legends.items():
        if "PRIVILEGED" in legend:
            assert start["1"] <= page <= end["1"]


def test_defect_signed_line_breaks_subscription(model):
    """diligence.defect-delta-hooks: one displayed signed line moves; the
    totals row stays the honest sum, so the slip no longer foots to 100%."""
    cov = diligence.compute_coverage(model)
    target = model["subscription"][2]["market"]
    honest = cov["signed"][2]
    bad = honest + 4.75
    texts = _texts(_lines(model, {"signed_line": (target, bad)}))
    assert f"{bad:.2f}%" in texts
    assert f"{sum(cov['signed']):.2f}%" in texts          # total stays honest
    clean = _texts(_lines(model))
    assert f"{bad:.2f}%" not in clean


def test_defect_subjectivity_status_contradicts_record(model):
    """diligence.defect-delta-hooks: the register shows the minors item
    satisfied while resolution 6 and the special-acceptance correspondence
    keep saying otherwise — a cross-instrument contradiction with quotable
    spans on both sides."""
    bad = " ".join(_texts(_lines(model,
                                 {"subjectivity_status": (2, "Satisfied")})))
    clean = " ".join(_texts(_lines(model)))
    reg = diligence.subjectivity_register(model)
    assert [s for s in reg if s["no"] == 2][0]["status"] == "NOT SATISFIED"
    # exactly one register cell moved: one fewer NOT SATISFIED than clean,
    # and the board's permission and the broker's request still render
    assert bad.count("NOT SATISFIED") == clean.count("NOT SATISFIED") - 1
    assert "REQUEST FOR SPECIAL ACCEPTANCE" in bad
    assert bad != clean


def test_clean_render_has_no_planted_faults(model):
    """A packet rendered without a defect must pass its own coherence checks —
    otherwise planted faults are indistinguishable from ambient noise."""
    cov = diligence.compute_coverage(model)
    assert cov["class_iv_sublimit_mm"] < cov["each_occurrence_mm"]
    assert model["incident_date"] < model["board_date"]
    assert diligence.total_specimens(model) == sum(
        r["count"] for r in model["roster"])


def test_canon_is_caller_supplied():
    """diligence.canon-coherence: the world is DATA. A caller-supplied canon
    replaces every fixed fact — including the production numbering and the tab
    sources, which are templates resolved against the model — and an
    incomplete canon fails loudly rather than rendering a blank where an
    operator's name belongs."""
    mine = dict(diligence.DEFAULT_CANON,
                company="ARDENT MARINE BIOLOGICS PLC",
                company_short="Ardent", subsidiary="Ardent Pacific Pty Ltd",
                island="Motu Rangi", bates_prefix="ARDENT-DIL-")
    m = diligence.sample_packet(random.Random(5), canon=mine)
    assert m["company_short"] == "Ardent"
    text = _read(diligence.render_packet(m, metadata=META))
    for expected in ("ARDENT MARINE BIOLOGICS PLC", "Motu Rangi",
                     "Ardent Pacific Pty Ltd", "ARDENT-DIL-"):
        assert expected in text, f"caller canon not honoured: {expected}"
    for leaked in (diligence.DEFAULT_CANON["company"],
                   diligence.DEFAULT_CANON["island"],
                   diligence.DEFAULT_CANON["bates_prefix"]):
        assert leaked not in text, f"default canon leaked: {leaked}"

    with pytest.raises(ValueError, match="canon missing required keys"):
        diligence.sample_packet(random.Random(5), canon={"company": "X CORP"})
