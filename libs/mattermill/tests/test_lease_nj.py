"""lease_nj capability tests — each maps to a lease.* requirement.

Two contracts are under test. The clause anatomy is the Mode B contract from
the DCA Truth in Renting guide (p.6), transcribed in lease_nj.DOC_MARKERS. The
jurisdiction contract stacks New Jersey (Rent Security Deposit Act; the
disclosure battery) and Hoboken (Municipal Code Ch. 155 — the 5%/CPI cap, the
§ 155-4 disclosure statement), captured in the experiment's sourced-reference
contract.
"""

from __future__ import annotations

import datetime as _dt
import io
import random

import pypdfium2 as pdfium
import pytest

from mattermill import lease_nj as L

META = {"producer": "Applied Epic Forms", "creator": "Adobe PDF Library 15.0",
        "created": "2025-08-14 10:12:03", "modified": None}


def _pages(pdf: bytes) -> list[str]:
    doc = pdfium.PdfDocument(io.BytesIO(pdf))
    return [" ".join((p.get_textpage().get_text_range() or "").split())
            for p in doc]


def _content(pdf: bytes) -> str:
    return " ".join(_pages(pdf))


@pytest.fixture()
def model():
    # a renewal in a pre-1978 building — exercises the § 155-5 cap AND lead
    return L.sample_lease(random.Random(0), pins={
        "lease_type": "renewal", "prior_rent": 3000, "cpi_pct": 3.2,
        "building_year": 1962})


@pytest.fixture()
def pdf(model):
    return L.render_lease(model, metadata=META)


def test_jurisdiction_gate():
    """lease.nj-hoboken-jurisdiction-gate: the state and the municipality are
    gates, not labels. New Jersey's landlord-tenant world and Hoboken's
    rent-control world are the only ones sourced; another state or town raises
    rather than borrowing them."""
    with pytest.raises(ValueError, match="no landlord-tenant world sourced"):
        L.sample_lease(random.Random(1),
                       canon=dict(L.DEFAULT_CANON, state="CALIFORNIA"))
    with pytest.raises(ValueError, match="no municipal rent-control world"):
        L.sample_lease(random.Random(1),
                       canon=dict(L.DEFAULT_CANON, municipality="Newark"))
    ok = L.sample_lease(random.Random(1))
    assert ok["municipality"] == "Hoboken"
    # "NJ" abbreviation is accepted, other municipalities are not
    L.sample_lease(random.Random(1), canon=dict(L.DEFAULT_CANON, state="NJ"))


def test_deposit_within_statutory_cap(pdf):
    """lease.deposit-within-statutory-cap: the deposit follows from the rent
    and never exceeds one and one-half months (N.J.S.A. 46:8-19). It is
    computed, not sampled beside the rent."""
    for seed in range(40):
        m = L.sample_lease(random.Random(seed))
        assert m["deposit_months"] <= L.NJ["deposit_cap_months"]
        assert m["security_deposit"] == round(
            m["monthly_rent"] * m["deposit_months"], 2)
    # the emitter cannot render an unlawful figure even if asked
    with pytest.raises(ValueError, match="exceeds the New Jersey cap"):
        L.deposit_amount(3000, 2.0)
    assert "one and one-half" in _content(pdf)


def test_deposit_investment_by_unit_count():
    """lease.deposit-investment-by-unit-count: a building of ten or more units
    invests the deposit in a money-market fund/account (46:8-19 subsec. a); a
    smaller one uses an interest-bearing account (subsec. b). Either way the
    30-day notice names the institution, account type, rate and amount."""
    big = L.sample_lease(random.Random(2))          # default 128 units
    assert big["large_building"]
    tb = _content(L.render_lease(big, metadata=META))
    assert "money market" in tb
    assert "46:8-19(a)" in tb
    assert "Within thirty (30) days" in tb
    # the notice CONTENT the statute requires is described...
    assert "46:8-19(c)" in tb
    assert "name and address of the banking institution" in tb
    # ...but no fabricated bank name / account number is embedded in the lease
    # body (round-1 external_verifiability tell; invariant 7)
    assert "Savings Bank" not in tb
    assert "acct. ****" not in tb

    small = L.sample_lease(random.Random(2), canon=dict(L.DEFAULT_CANON, units=6))
    assert not small["large_building"]
    ts = _content(L.render_lease(small, metadata=META))
    assert "interest-bearing account" in ts
    assert "46:8-19(b)" in ts
    assert "money market" not in ts


def test_hoboken_increase_cap():
    """lease.hoboken-increase-cap: a renewal increase is the LESSER of 5% or
    the CPI differential (§ 155-5), and the new rent is the prior rent lifted
    by that capped percentage, rounded to the nearest dollar (§ 155-4)."""
    # CPI below the cap governs
    assert L.capped_increase_pct(3.4) == 3.4
    # CPI above the 5% cap is held to 5%
    assert L.capped_increase_pct(9.0) == 5.0
    assert L.renewed_rent(3000, 9.0) == 3150        # 5% cap, not 9%
    assert L.renewed_rent(2630, 3.8) == 2730        # rounded to the dollar
    for seed in range(40):
        m = L.sample_lease(random.Random(seed), pins={"lease_type": "renewal"})
        assert m["increase_pct"] <= L.HOBOKEN["increase_cap_pct"]
        assert m["increase_pct"] == round(min(5.0, m["cpi_pct"]), 2)
        assert m["monthly_rent"] == round(
            m["prior_rent"] * (1 + m["increase_pct"] / 100))


def test_hoboken_disclosure_statement(pdf, model):
    """lease.hoboken-disclosure-statement: the § 155-4 statement carries the
    right to a legal rent calculation, the two-year bar, the registration on
    file, and the Truth-in-Renting acknowledgement — and its base-rent recital
    is coupled to whether the building existed at the Oct 1, 1985 base date."""
    text = _content(pdf)
    assert "HOBOKEN RENT CONTROL DISCLOSURE STATEMENT" in text
    assert "legal rent calculation" in text
    assert "two (2) years" in text
    assert "on file with the" in text
    assert "Rent Leveling and Stabilization Office" in text
    assert "Truth-in-Renting Act" in text
    # 1962 building existed at the base date -> the Oct 1, 1985 recital
    assert "as of October 1, 1985" in text
    # a post-1985 building recites the first rent charged after the base date
    newer = L.sample_lease(random.Random(0), pins={"building_year": 2004})
    tn = _content(L.render_lease(newer, metadata=META))
    assert "first legal rent charged for this dwelling unit after October 1, 1985" in tn


def test_required_disclosures_present(pdf):
    """lease.required-disclosures-present: the disclosure battery the Truth in
    Renting guide (p.6) enumerates is attached — flood, Truth in Renting,
    window guards, bed bugs, domestic violence — with their statutory hooks."""
    text = _content(pdf)
    required = [
        ("FLOOD RISK NOTICE", "46:8-50"),
        ("National Flood Insurance Program", None),
        ("TRUTH IN RENTING ACKNOWLEDGMENT", "46:8-44"),
        ("WINDOW GUARD NOTICE", "5:10-27.1"),
        ("BED BUG NOTICE", "5:10-10.2"),
        ("DOMESTIC VIOLENCE LEASE TERMINATION", "46:8-9.6"),
        ("A charge of $25.00 shall apply to any dishonored check", "2A:32A-1"),
    ]
    for label, cite in required:
        assert label in text, f"missing disclosure: {label}"
        if cite:
            assert cite in text, f"missing citation {cite} for {label}"
    # the DCA address Hoboken § 155-4 quotes
    assert "P.O. Box 805" in text


def test_round1_harvest_fixes(model, pdf):
    """lease.round1-harvest: the tells three blind judges raised in round 1,
    fixed at the level each lives. (a) execution state — a signed lease is
    initialed on every page and each disclosure is acknowledged, not left
    blank; (b) no fabricated bank/registration identifiers embedded in the
    body; (c) the operative clauses a counsel-drafted management lease carries;
    (d) the federal lead mandate; (e) the § 2A:18-61.67 bold reciprocal-fee
    notice."""
    text = _content(pdf)
    # (a) executed, not a blank specimen
    ini = L._initials(model["tenants"])
    assert ini and f"Tenant initials: {ini}" in text
    assert "Acknowledged by Tenant:" in text
    assert "Acknowledged: ____" not in text            # no blank ack lines
    # (b) no invented identifiers in the lease body
    assert "Savings Bank" not in text
    assert "Reg. No." not in text
    # (c) the operative bulk of a real lease
    for clause in ("LANDLORD'S RIGHT OF ENTRY", "FIRE, CASUALTY AND CONDEMNATION",
                   "DEFAULT AND REMEDIES", "HOLDOVER", "QUIET ENJOYMENT",
                   "NOTICES", "SUBORDINATION AND ESTOPPEL",
                   "ENTIRE AGREEMENT"):
        assert clause in text, f"missing operative clause: {clause}"
    # (d) lead is federally mandated; the NJ-only cite was a procedural tell
    lead = _content(L.render_lease(
        L.sample_lease(random.Random(5), pins={"building_year": 1955}),
        metadata=META))
    assert "42 U.S.C. 4852d" in lead
    assert "40 C.F.R. Part 745" in lead
    # (e) the reciprocal-fee bold notice the statute requires
    assert "2A:18-61.67" in text
    assert "Tenant shall recover attorney's fees" in text


def test_esign_ids_are_rfc4122_v4():
    """lease.round3-uuid: envelope/signature IDs are conformant v4 UUIDs (a
    round-3 forensic judge caught random hex dressed as GUIDs). Version nibble
    is 4; variant nibble is 8/9/a/b."""
    import re
    m = L.sample_lease(random.Random(5))
    ids = [m["esign"]["envelope_id"]] + [s["id"] for s in m["esign"]["signers"]]
    v4 = re.compile(r"^[0-9A-F]{8}-[0-9A-F]{4}-4[0-9A-F]{3}-[89AB][0-9A-F]{3}-"
                    r"[0-9A-F]{12}$")
    for u in ids:
        assert v4.match(u), f"not a v4 UUID: {u}"


def test_round2_esign_execution_model(model, pdf):
    """lease.round2-esign: the round-2 disqualifiers (executed_consistently,
    signature_is_a_hand) closed by construction — ONE execution convention.
    Every party adopts a typeset e-signature that spells the signer's name;
    every initial slot is filled (no blank '____' lines); a certificate of
    completion seals the envelope under NJ UETA."""
    text = _content(pdf)
    # one convention: adopted e-signatures, no wet-ink raster (no JPEG image)
    assert b"/DCTDecode" not in pdf
    assert "Signed electronically by:" in text
    # the adopted signature is the signer's actual name (not a scrawl)
    for signer in model["esign"]["signers"]:
        assert signer["name"] in text
    # NO blank required-initial lines anywhere (the lead-paint slots are filled)
    assert "______" not in text
    li = L._person_initials(model["leasing_agent"])
    ti = L._person_initials(model["tenants"][0])
    assert f"[{li}]" in text and f"[{ti}]" in text
    # a certificate of completion, sealed under NJ UETA, naming every signer
    assert "CERTIFICATE OF COMPLETION" in text
    assert model["esign"]["envelope_id"] in text
    assert "Uniform Electronic Transactions Act" in text
    assert "12A:12-1" in text
    # the platform is fictional — no real e-sign brand impersonated
    assert "DocuSign" not in text and "Adobe Sign" not in text


def test_lead_disclosure_coupled_to_age():
    """lease.lead-disclosure-coupled-to-age: the lead-based paint disclosure is
    present for pre-1978 housing and ABSENT for newer housing — never invented
    either way (federal 1978 cutoff)."""
    for year, expect in [(1929, True), (1977, True), (1978, False), (2011, False)]:
        m = L.sample_lease(random.Random(5), pins={"building_year": year})
        assert m["pre_1978"] is expect
        text = _content(L.render_lease(m, metadata=META))
        assert ("LEAD-BASED PAINT DISCLOSURE" in text) is expect
        if expect:
            assert str(year) in text


def test_term_coherent(model):
    """lease.term-coherent: the term ends the day before its anniversary and
    the total rent is the monthly rent times twelve — computed, never a free
    draw."""
    for seed in range(30):
        m = L.sample_lease(random.Random(seed))
        assert m["term_end"] == L.term_end(m["term_start"], 12)
        assert (m["term_end"] - m["term_start"]).days in (364, 365)
        assert m["annual_rent"] == m["monthly_rent"] * 12
    # a leap-day start is handled
    assert L.term_end(_dt.date(2028, 2, 29), 12) == _dt.date(2029, 2, 27)


def test_high_entropy_parties():
    """lease.high-entropy-parties: tenant names, the signing agent, and the
    deposit account tail are drawn from large combinatorial spaces, so a run of
    generated leases reuses essentially no low-entropy token — the reuse that
    would itself become a tell."""
    tenants, agents = set(), set()
    N = 120
    for seed in range(N):
        m = L.sample_lease(random.Random(seed))
        tenants.add(tuple(m["tenants"]))
        agents.add(m["leasing_agent"])
    assert len(tenants) / N >= 0.95, f"tenant reuse too high: {len(tenants)}/{N}"
    assert len(agents) / N >= 0.90, f"agent reuse too high: {len(agents)}/{N}"


def test_clause_anatomy(pdf, model):
    """lease.clause-anatomy: every clause the Truth in Renting guide's
    recommended-provisions list requires appears, in document order (the Mode B
    contract). A lease authored from memory drifts on exactly this — a missing
    subletting clause, no renter's-insurance requirement, no keys provision."""
    text = _content(pdf)
    cursor = 0
    for marker in L.DOC_MARKERS:
        if marker == "LEAD-BASED PAINT" and not model["pre_1978"]:
            continue
        idx = text.find(" ".join(marker.split()), cursor)
        assert idx >= 0, f"missing clause marker in order: {marker!r}"
        cursor = idx


def test_guard_list(pdf, model):
    """lease.guard-list: what the sources proved must be ABSENT. No deposit
    over the 1.5-month cap; no renewal increase over min(5%, CPI); no waiver of
    the tenant's right to a legal rent calculation; no pet deposit on an
    assistance animal; no invented NJ-Realtors form edition mark; a flood
    notice that does not answer 'No' in flood-exposed Hoboken."""
    text = _content(pdf)
    # deposit never exceeds the cap, across the sample space
    for seed in range(60):
        m = L.sample_lease(random.Random(seed))
        assert m["security_deposit"] <= m["monthly_rent"] * 1.5 + 0.001
        if m["lease_type"] == "renewal":
            assert m["monthly_rent"] <= m["prior_rent"] * 1.05 + 1
    # the tenant's legal-rent-calculation right is affirmed, never waived
    assert "right to request a legal rent calculation" in text.lower()
    assert "waive" not in text.lower() or "waives any right to a legal rent" not in text.lower()
    # assistance animals are carved out of any pet charge
    assert "no pet fee or pet deposit shall be charged" in text
    # no NJ-Realtors form edition furniture we did not source
    assert "NJ REALTORS" not in text.upper()
    assert "Form 125" not in text
    # flood notice answers on Hoboken's known exposure, not "No"
    assert model["flood_in_hazard_area"] == "Yes"


def test_defect_delta_hooks(model):
    """lease.defect-delta-hooks: each hook alters exactly one displayed value
    while everything computed around it stays honest — which is what makes the
    artifact scorable rather than merely wrong. Each breaks a relationship an
    expert checks: the deposit cap, the term chronology, the § 155-5 cap, the
    flood answer against Hoboken's exposure."""
    clean = _content(L.render_lease(model, metadata=META))

    # (1) a deposit over the statutory cap; the rent and the months stay honest
    over = round(model["monthly_rent"] * 2.0, 2)
    bad = _content(L.render_lease(model, metadata=META,
                                  defect={"security_deposit": over}))
    assert f"${over:,.2f}" in bad
    assert f"${model['monthly_rent']:,.2f}" in bad          # rent intact

    # (2) a term end inconsistent with a 12-month term; the start stays honest
    wrong_end = (model["term_start"] + _dt.timedelta(days=200)).isoformat()
    bad2 = _content(L.render_lease(model, metadata=META,
                                   defect={"term_end": wrong_end}))
    assert L._date(_dt.date.fromisoformat(wrong_end)) in bad2
    assert L._date(model["term_start"]) in bad2             # start intact

    # (3) a recited increase over the § 155-5 cap; prior/new rent stay honest
    bad3 = _content(L.render_lease(model, metadata=META,
                                   defect={"increase_pct": 8.0}))
    assert "8.00%" in bad3
    assert "8.00%" not in clean
    assert f"${float(model['prior_rent']):,.2f}" in bad3    # prior rent intact

    # (4) a flood notice that answers "No" in flood-exposed Hoboken
    bad4 = _content(L.render_lease(model, metadata=META,
                                   defect={"flood_answer": "No"}))
    assert "Flood Hazard Area or Moderate Risk Flood Hazard Area? No." in bad4
    assert "Flood Hazard Area or Moderate Risk Flood Hazard Area? Yes." in clean


def test_metadata_born_digital(pdf):
    """lease.metadata-born-digital: a contemporary lease exported by a property
    manager's system is a vector file, not a scan — no JPEG page images — and
    its CreationDate is in the era the document claims, never before the flood
    law that governs it."""
    import re
    assert b"/DCTDecode" not in pdf
    created = re.search(rb"/CreationDate \(D:(\d{4})", pdf).group(1)
    assert int(created) >= 2024, "the flood-disclosure era cannot predate 2024"
    # producer is the management system's, not reportlab's default
    assert b"ReportLab" not in re.search(rb"/Producer\s*\((?:\\.|[^()\\])*\)",
                                         pdf).group(0)


def test_seeded_everywhere(model):
    """seeded.everywhere: same seed in, same model and same bytes out."""
    assert model == L.sample_lease(random.Random(0), pins={
        "lease_type": "renewal", "prior_rent": 3000, "cpi_pct": 3.2,
        "building_year": 1962})
    assert L.render_lease(model, metadata=META) == L.render_lease(model, metadata=META)
    other = L.sample_lease(random.Random(7))
    assert L.render_lease(other, metadata=META) != L.render_lease(model, metadata=META)


def test_canon_is_caller_supplied():
    """The world is DATA: the building and its landlord are caller-supplied
    canon, so a replacement canon relocates the whole lease coherently, and a
    missing key raises rather than rendering a blank where a name belongs."""
    mine = dict(L.DEFAULT_CANON, building_name="Harbor Point Tower",
                street="55 River Street", unit="1408",
                landlord_entity="55 River Owner, LLC")
    m = L.sample_lease(random.Random(3), canon=mine)
    text = _content(L.render_lease(m, metadata=META))
    assert "Harbor Point Tower" in text
    assert "55 River Street" in text
    assert L.DEFAULT_CANON["building_name"] not in text
    with pytest.raises(ValueError, match="canon missing required keys"):
        L.sample_lease(random.Random(3), canon={"building_name": "X"})


def test_unknown_pins_are_refused():
    with pytest.raises(ValueError, match="unknown pins"):
        L.sample_lease(random.Random(1), pins={"rent": 3000})
