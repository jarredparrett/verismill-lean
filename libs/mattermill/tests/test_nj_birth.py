"""nj_birth capability tests — each maps to an njbirth.* requirement in
foundry/spec/foundry.yaml. The contract under test is the SOURCED statutory
contract in foundry/reference/templates/nj_birth_1878_1900/contract.json,
which quotes section 2 of New Jersey's registry act verbatim."""

from __future__ import annotations

import datetime as _dt
import io
import random

import pypdfium2 as pdfium
import pytest

from mattermill import nj_birth as nb

META = {"producer": "Zeutschel OS 12002 / Adobe Paper Capture",
        "creator": "Zeutschel OS 12002", "created": "2018-04-02 11:07:44",
        "modified": None}


def _content(pdf: bytes) -> str:
    doc = pdfium.PdfDocument(io.BytesIO(pdf))
    return " ".join(" ".join(
        (p.get_textpage().get_text_range() or "") for p in doc).split())


@pytest.fixture()
def model():
    return nb.sample_birth(random.Random(1888))


def test_statutory_field_inventory(model):
    """njbirth.statutory-fields: every particular section 2 requires appears,
    in the statute's own terms. The field list is not a design choice — it is
    what the blank was printed to satisfy."""
    text = _content(nb.render_birth(model, metadata=META))
    for label in ("Name of child, if named", "Sex", "Color",
                  "Day and year of birth", "Precise place of residence",
                  "Name of father", "Name of mother", "Maiden name of mother",
                  "Birthplace of father", "Birthplace of mother",
                  "Residence of parents", "Occupation of father",
                  "Occupation of mother", "Name of attending physician"):
        assert label in text, f"statutory particular missing: {label}"


def test_guard_no_modern_furniture(model):
    """njbirth.statutory-fields: guard. These belong to 20th-century vital
    records and would date the artifact instantly."""
    text = _content(nb.render_birth(model, metadata=META))
    for absent in ("Certificate of Live Birth", "State File", "Registrar",
                   "Social Security", "Hospital", "Footprint"):
        assert absent not in text, f"out-of-era furniture present: {absent}"


def test_officer_follows_municipality():
    """njbirth.officer-coupling: the receiving officer is the township ASSESSOR
    or the CITY CLERK, and which one follows from the municipality's form. It
    is a fact about the world, not a label to sample."""
    twp = nb.sample_birth(random.Random(3), canon=dict(
        nb.DEFAULT_CANON, municipality_kind="township"))
    city = nb.sample_birth(random.Random(3), canon=dict(
        nb.DEFAULT_CANON, municipality_kind="city"))
    assert twp["officer_title"] == "Assessor"
    assert city["officer_title"] == "City Clerk"
    assert "Assessor" in _content(nb.render_birth(twp, metadata=META))
    city_text = _content(nb.render_birth(city, metadata=META))
    assert "City Clerk" in city_text and "the Assessor" not in city_text


def test_attendant_coupling():
    """njbirth.attendant-coupling: 'in case there be no physician or midwife
    present, it shall be the duty of the parent'. So a birth with no attendant
    cannot also name an attending physician — the same underlying fact answers
    both fields."""
    for seed in range(12):
        m = nb.sample_birth(random.Random(seed))
        text = _content(nb.render_birth(m, metadata=META))
        if m["attendant_kind"] == "none":
            assert m["attendant"] is None
            assert "None in attendance" in text
            assert not m["special_return"] or "special return" in text.lower()
        else:
            assert m["attendant"] and m["attendant"] in text
            assert "None in attendance" not in text


def test_special_return_is_the_assessors(model):
    """njbirth.attendant-coupling: a special return is the assessor filling the
    blank himself where the attendant failed to return. It is marked as such,
    it is reported by the officer, and it never carries an attendant."""
    m = nb.sample_birth(random.Random(9),
                        pins={"attendant": "none", "special_return": True})
    text = _content(nb.render_birth(m, metadata=META))
    assert m["special_return"] and m["attendant"] is None
    assert "SPECIAL RETURN" in text
    assert m["officer_title"] in m["reporter"]
    assert "None in attendance" in text


def test_chronology_is_statutory():
    """njbirth.thirty-day-return: the return falls within the statute's thirty
    days of the birth, and the officer forwards on the 15th of the following
    month. Both are computed from the birth date, never sampled beside it."""
    for seed in range(15):
        m = nb.sample_birth(random.Random(seed))
        lag = (m["return_date"] - m["date_of_birth"]).days
        assert 0 < lag <= 30, f"return {lag}d after birth exceeds the statute"
        t = m["transmittal_date"]
        assert t.day == 15, "assessors and clerks forward on the 15th"
        assert t > m["return_date"], "forwarded before it was returned"
        assert (t - m["return_date"]).days <= 46


def test_era_is_enforced():
    """njbirth.era-gate: New Jersey birth records are REGISTER format until
    1878 and no civil birth record exists before May 1848. A caller asking for
    an 1850s 'birth certificate' is asking for a document that did not exist,
    and the sampler says so rather than rendering an anachronism."""
    with pytest.raises(ValueError, match="REGISTER format"):
        nb.sample_birth(random.Random(1), pins={"year": 1855})
    with pytest.raises(ValueError, match="certificate era"):
        nb.sample_birth(random.Random(1), pins={"year": 1901})
    ok = nb.sample_birth(random.Random(1), pins={"year": 1878})
    assert ok["date_of_birth"].year == 1878


def test_unnamed_infant_stays_blank():
    """njbirth.statutory-fields: 'its name, if it be named'. An unnamed infant
    is period-normal; the field is left blank rather than filled with an
    invention."""
    m = nb.sample_birth(random.Random(4), pins={"named": False})
    assert m["child_name"] is None
    rows = dict(nb.compose_birth(m))
    assert rows["Name of child, if named"] == "—"


def test_maiden_name_never_equals_married_name():
    """njbirth.statutory-fields: the statute asks for the mother's maiden name
    because it differs from the name she is returned under."""
    for seed in range(20):
        m = nb.sample_birth(random.Random(seed))
        assert m["mother_maiden_name"] not in m["mother_name"]


def test_period_honest_scan(model):
    """njbirth.period-honest-scan: an 1878-1900 document cannot be a vector
    file — PDF shipped in 1993 — so the artifact is a scan with metadata dated
    at DIGITISATION and an invisible OCR layer."""
    import re
    pdf = nb.render_birth(model, metadata=META)
    assert pdf.count(b"/DCTDecode") >= 1
    created = re.search(rb"/CreationDate \(D:(\d{4})", pdf).group(1)
    assert int(created) >= 1993
    assert re.search(rb"/ModDate \((D:[0-9]+)\)", pdf).group(1) == \
        re.search(rb"/CreationDate \((D:[0-9]+)\)", pdf).group(1)
    assert "Day and year of birth" in _content(pdf)


def test_defect_delta_hooks(model):
    """njbirth.defect-delta-hooks: each hook alters exactly one displayed value
    while everything computed around it stays honest."""
    clean = _content(nb.render_birth(model, metadata=META))

    bad = _content(nb.render_birth(model, metadata=META,
                                   defect={"child_sex": "Female"}))
    assert "Female" in bad
    assert model["mother_maiden_name"] in bad          # neighbours intact

    alt = _dt.date(model["date_of_birth"].year + 3, 1, 4)
    bad2 = _content(nb.render_birth(model, metadata=META,
                                    defect={"date_of_birth": alt}))
    assert "January 4," in bad2
    assert nb._fmt(model["return_date"]) in bad2       # return date unchanged,
    assert nb._fmt(model["transmittal_date"]) in bad2  # so the chronology lies

    bad3 = _content(nb.render_birth(
        model, metadata=META, defect={"mother_maiden_name": model["mother_name"].split()[-1]}))
    assert model["father_name"] in bad3


def test_canon_is_caller_supplied():
    """njbirth.officer-coupling: the world is DATA. A vital record must never
    carry a real person's identity, so the people come from the caller."""
    mine = dict(nb.DEFAULT_CANON, county="MERCER", municipality="HOPEWELL",
                officer_name="A. B. STOUT")
    m = nb.sample_birth(random.Random(2), canon=mine)
    text = _content(nb.render_birth(m, metadata=META))
    assert "Hopewell, Mercer County" in text
    assert nb.DEFAULT_CANON["municipality"].title() not in text
    with pytest.raises(ValueError, match="canon missing required keys"):
        nb.sample_birth(random.Random(2), canon={"state": "NEW JERSEY"})


def test_seeded_everywhere(model):
    """seeded.everywhere: same seed in, same model and same bytes out."""
    assert model == nb.sample_birth(random.Random(1888))
    assert nb.render_birth(model, metadata=META) == \
        nb.render_birth(model, metadata=META)
    other = nb.sample_birth(random.Random(1889))
    assert nb.render_birth(other, metadata=META) != \
        nb.render_birth(model, metadata=META)
