"""Capability tests for the frozen 1997 Madison deed contract."""

from __future__ import annotations

import io
import random

import pypdfium2 as pdfium
import pytest

from mattermill import deed_nj as D, registry

META = {"producer": "Canon DR-C240 / Adobe Paper Capture",
        "creator": "Canon DR-C240", "created": "2012-06-18 11:02:03",
        "modified": None}


def _pages(data: bytes) -> list[str]:
    doc = pdfium.PdfDocument(io.BytesIO(data))
    return [" ".join((p.get_textpage().get_text_range() or "").split()) for p in doc]


@pytest.fixture()
def model():
    return D.sample_deed(random.Random(1997), pins={
        "consideration": 200_000, "grantor_married": True,
        "partial_exemption": "senior"})


@pytest.fixture()
def pdf(model):
    return D.render_deed(model, metadata=META)


def test_jurisdiction_gate():
    """deed.nj-madison-jurisdiction-gate: only the sourced recording world renders."""
    for change in ({"state": "NEW YORK"}, {"county": "Essex"},
                   {"municipality": "Chatham"}):
        with pytest.raises(ValueError, match="recording world"):
            D.sample_deed(random.Random(1), canon=dict(D.DEFAULT_CANON, **change))
    with pytest.raises(ValueError, match="1997"):
        D.sample_deed(random.Random(1), pins={"execution_date": "1998-01-02"})


def test_bargain_sale_anatomy(pdf):
    """deed.bargain-sale-anatomy: the sourced bargain-and-sale clauses are ordered."""
    text = _pages(pdf)[0]
    marks = D.PAGE_MARKERS[1]
    assert all(mark in text for mark in marks)
    assert [text.index(mark) for mark in marks] == sorted(text.index(mark) for mark in marks)


def test_covenant_grantor_acts(pdf):
    """deed.covenant-grantor-acts: the covenant is limited to the grantor's acts."""
    text = " ".join(_pages(pdf))
    assert "by acts of the Grantor" in text
    assert "general warranty" not in text.lower()


def test_property_canon(model, pdf):
    """deed.property-canon: every property occurrence reads from one complete canon."""
    text = " ".join(_pages(pdf))
    assert model["street"].split(" ", 1)[1] in model["legal_description"]
    for value in (model["municipality"], model["county"], model["street"],
                  model["block"], model["lot"], model["legal_description"],
                  model["prior_book"], model["prior_page"]):
        assert str(value) in text
    with pytest.raises(ValueError, match="canon missing"):
        D.sample_deed(random.Random(2), canon={"state": "NJ"})


def test_party_canon(model, pdf):
    """deed.party-canon: party names, capacity, addresses, signatures and ack agree."""
    text = " ".join(_pages(pdf))
    assert text.count(model["grantor"]) >= 5
    assert text.count(model["grantee"]) >= 1
    assert model["grantor_address"] in text and model["grantee_address"] in text
    capacity = "a married person" if model["grantor_married"] else "an unmarried person"
    assert capacity in text
    assert model["grantor_spouse"] in text
    assert "release matrimonial rights" in text


def test_consideration_coupling(model, pdf):
    """deed.consideration-coupling: deed, acknowledgment and RTF-1 share consideration."""
    token = f"${model['consideration']:,.2f}"
    assert " ".join(_pages(pdf)).count(token) >= 3


def test_rtf_1997():
    """deed.rtf-1997: the period rate and excess tier foot in $500 units."""
    assert D.rtf_1997(150_000) == 525.00
    assert D.rtf_1997(150_001) == 527.50
    assert D.rtf_1997(200_000) == 775.00
    assert D.rtf_1997(200_000, new_construction=True) == 475.00
    assert D.rtf_1997(200_000, partial_exemption="senior") == 475.00


def test_execution_acknowledgment(model, pdf):
    """deed.execution-acknowledgment: execution and individual acknowledgment are filled."""
    page = _pages(pdf)[1]
    assert model["grantor"] in page
    assert model["grantor_spouse"] in page
    assert model["execution_date"].strftime("%B %d, %Y") in page
    assert "I CERTIFY" in page and "Notary Public" in page
    # Two execution events by the same person are two physical marks, never
    # one pasted signature image.
    assert D.assets.signature_png(model["scan_seed"] + 101, name=model["grantor"]) != \
        D.assets.signature_png(model["scan_seed"] + 401, name=model["grantor"])


def test_acknowledgment_number_agreement():
    """deed.acknowledgment-number-agreement: signer count controls acknowledgment grammar."""
    single = D.sample_deed(random.Random(1997), pins={
        "grantor_married": False, "notary_name": "Elise North"})
    single_text = " ".join(_pages(D.render_deed(single, metadata=META)))
    assert "the Grantor is the person named" in single_text
    assert "they are the persons named" not in single_text

    joined = D.sample_deed(random.Random(1997), pins={
        "grantor_married": True, "notary_name": "Elise North"})
    joined_text = " ".join(_pages(D.render_deed(joined, metadata=META)))
    assert "they are the persons named" in joined_text


def test_pinned_notary_identity():
    """deed.pinned-notary-identity: the caller controls one non-party notary identity."""
    model = D.sample_deed(random.Random(1997), pins={"notary_name": "Elise North"})
    assert model["notary"] == "Elise North"
    assert "Elise North, Notary Public" in " ".join(
        _pages(D.render_deed(model, metadata=META))
    )
    with pytest.raises(ValueError, match="non-empty"):
        D.sample_deed(random.Random(1997), pins={"notary_name": " "})


def test_public_display_facts_cover_accessible_deed_fields():
    """deed.public-display-facts: the manifest exposes the accessible field contract."""
    _, manifest = registry.emit(
        "deed_nj_1997",
        seed=1997,
        pins={
            "execution_date": "1997-10-17",
            "consideration": 425_000,
            "grantor_married": False,
            "notary_name": "Elise North",
        },
    )
    facts = manifest["display_facts"]
    assert facts["execution_date"] == "1997-10-17"
    assert facts["consideration"] == 425_000
    assert facts["notary_name"] == "Elise North"
    assert facts["prior_book"] == D.DEFAULT_CANON["prior_book"]
    assert facts["prior_page"] == D.DEFAULT_CANON["prior_page"]


def test_prepared_return_recording(model, pdf):
    """deed.prepared-return-recording: one recording fact drives all recording furniture."""
    text = " ".join(_pages(pdf))
    assert model["prepared_by"] in text and model["return_to"] in text
    assert text.count(model["instrument"]) >= 4
    assert text.count(f"Book {model['book']}") >= 4
    assert model["recorded_date"].strftime("%b %d %Y") in text
    assert model["recorded_date"].weekday() < 5
    assert model["recorded_date"] not in D._CLERK_HOLIDAYS_1997


def test_rtf1_period_form(model, pdf):
    """deed.rtf1-period-form: the period affidavit carries the deed's facts."""
    page = _pages(pdf)[3]
    for token in ("RTF-1 (Rev. 1/85)", model["grantor"], model["street"],
                  f"${model['consideration']:,.2f}", f"${model['rtf']:,.2f}"):
        assert token in page
    for token in ("being duly sworn", "PARTIAL EXEMPTION",
                  "Subscribed and sworn", "My Commission Expires"):
        assert token in page
    assert f"Partial Exemption Credit ${model['rtf_exemption_credit']:,.2f}" in page
    ordinary = D.sample_deed(random.Random(8), pins={
        "consideration": 200_000, "partial_exemption": "none",
        "new_construction": False})
    ordinary_pdf = D.render_deed(ordinary, metadata=META)
    assert len(_pages(ordinary_pdf)) == 3
    assert "RTF-1" not in " ".join(_pages(ordinary_pdf))


def test_period_guard_list(pdf):
    """deed.period-guard-list: post-1997 recording forms and e-sign furniture are absent."""
    text = " ".join(_pages(pdf)).lower()
    for forbidden in ("git/rep", "cover sheet", "docusign", "e-recording", "qr code"):
        assert forbidden not in text


def test_scan_class(pdf):
    """deed.scan-class: output is an OCR'd raster scan with honest later metadata."""
    reader = pdfium.PdfDocument(io.BytesIO(pdf))
    assert len(reader) == 4
    for page in reader:
        assert any(type(obj).__name__ == "PdfImage" for obj in page.get_objects())
    assert "BARGAIN AND SALE" in " ".join(_pages(pdf))
    assert b"ReportLab" not in pdf and b"PaperCapt" not in pdf
    metadata = reader.get_metadata_dict()
    assert "2012" in metadata["CreationDate"]
    assert metadata["CreationDate"] == metadata["ModDate"]


def test_defect_delta_hooks(model):
    """deed.defect-delta-hooks: a planted fault changes one displayed fact only."""
    base, _ = D._render_vector(model, None)
    bad_deed, _ = D._render_vector(model, {"consideration_deed": 199_500})
    bad_fee, _ = D._render_vector(model, {"rtf_fee": 1.00})
    bp, dp, fp = _pages(base), _pages(bad_deed), _pages(bad_fee)
    assert [i for i in range(4) if bp[i] != dp[i]] == [0]
    assert [i for i in range(4) if bp[i] != fp[i]] == [3]


def test_seeded_everywhere():
    """seeded.everywhere: identical seed, pins and metadata produce identical bytes."""
    m1 = D.sample_deed(random.Random(77), pins={"consideration": 300_000})
    m2 = D.sample_deed(random.Random(77), pins={"consideration": 300_000})
    assert m1 == m2
    assert D.render_deed(m1, metadata=META) == D.render_deed(m2, metadata=META)
