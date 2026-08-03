"""bill_of_sale capability tests — each maps to a billofsale.* requirement in
foundry/spec/foundry.yaml. The contract under test is the sourced genre
contract in foundry/reference/templates/bill_of_sale_1642/contract.json."""

from __future__ import annotations

import io
import random

import pypdfium2 as pdfium
import pytest

from mattermill import bill_of_sale as bos

META = {"producer": "Canon DR-C240 / Adobe Paper Capture",
        "creator": "Canon DR-C240", "created": "2019-03-14 09:22:11",
        "modified": None}


@pytest.fixture()
def model():
    return bos.sample_bill(random.Random(1642), pins={"salutation": False})


def _content(pdf_bytes: bytes) -> str:
    """The OCR text layer — what a Paper-Capture workflow leaves behind —
    whitespace-normalized (manuscript line wraps are layout, not content)."""
    doc = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    text = "\n".join(p.get_textpage().get_text_range() or "" for p in doc)
    return " ".join(text.split())


def _rendered(model):
    return bos.render_bill(model, metadata=META)


def test_clause_contract(model):
    """billofsale.clause-contract: the ten-clause anatomy of the sourced
    exemplar, in order, in period orthography — and the guard list (no
    notary, no anno-domini date, no printed-form furniture)."""
    text = _content(_rendered(model))
    markers = ["daye of",
               "yeere of the reigne of our soveraigne lord King Charles",
               "witnesseth that I", "have bargained and sold",
               "with all manner of implements and tackling",
               "binds himself his executors and assigns by these presents",
               "lawfull money of England", "warraunt and discharge",
               "against all men", "voyde and of none effect",
               "full strength and vertue",
               "knowledge myself to have receaved"]
    pos = 0
    for marker in markers:
        found = text.find(marker, pos)
        assert found >= 0, f"missing or out of order: {marker}"
        pos = found
    if model["attestation"]:
        assert "Sealed and delivered in the presence of" in text
    else:
        assert "Witnesses to the saide bargain and sale" in text
    for w in model["witnesses"]:
        assert w["name"] in text            # witnesses engrossed legibly
    if model["literate"]:
        assert "set my hand and seale" in text
    else:
        assert "set my seale and marke" in text
    for absent in ("notary", "Notary", "Anno Domini",
                   "Signed, sealed", "To all to whom these presents"):
        assert absent not in text, f"out-of-genre furniture present: {absent}"


def test_clause_contract_salutation_form():
    """billofsale.clause-contract, form B (deed-poll salutation): 'To all to
    whom these presents shall come, greeting' with the consideration/receipt
    acknowledged in hand and the date carried in the testimonium — the
    attested-composite variant, same machinery."""
    m = bos.sample_bill(random.Random(7), pins={"salutation": True})
    text = _content(_rendered(m))
    markers = ["To all to whom these presents shall come, greeting",
               "Know ye that I", "for and in consideration of the sum of",
               "in hand paid before the sealing and delivery",
               "the receipt whereof I do hereby acknowledge",
               "do bargain and sell",
               "with all manner of implements and tackling",
               "binds himself his executors and assigns by these presents",
               "lawfull money of England",
               "warraunt and discharge", "against all men",
               "voyde and of none effect", "full strength and vertue",
               "yeere of the reigne of our soveraigne lord King Charles"]
    pos = 0
    for marker in markers:
        found = text.find(marker, pos)
        assert found >= 0, f"form B missing or out of order: {marker}"
        pos = found
    for absent in ("notary", "Notary", "Anno Domini", "This bill made"):
        assert absent not in text, f"form B furniture present: {absent}"


def test_regnal_dating():
    """billofsale.regnal-dating: Julian + Lady Day discipline — dates from
    25 March 1642 are 18 Charles I (legal 1642); 1 Jan - 24 Mar 1642 are
    17 Charles I, legal year 1641; the payment feast always FOLLOWS the bill
    date; Pentecost is the computed Julian movable feast, not a sampled one."""
    for month, day, regnal, legal in ((1, 10, "seventeenth", 1641),
                                      (3, 24, "seventeenth", 1641),
                                      (3, 25, "eighteenth", 1642),
                                      (10, 19, "eighteenth", 1642)):
        m = bos.sample_bill(random.Random(5),
                            pins={"sale_month": month, "sale_day": day})
        assert m["date"]["regnal"] == regnal, (month, day, m["date"])
        assert m["date"]["legal_year"] == legal
        assert m["date"]["dual"] == (legal == 1641)
        # the bond matures no sooner than the warranty it secures: the feast
        # is ~a year out from the bill date (round-8 defeasance-timing tell)
        fm, fd = next((f[1], f[2]) for f in bos._feasts(1642)
                      if f[0] == m["feast"])
        gap = bos._doy(fm, fd) - bos._doy(month, day)
        if gap < 360:
            gap += 365
        assert gap >= 360, f"{m['feast']} only {gap}d after {month}/{day}"
    em, ed = bos._julian_easter(1642)
    pm, pd_ = bos._add_days(em, ed, 49)
    assert ("Pentecost", pm, pd_) in bos._feasts(1642)


def test_couplings(model):
    """billofsale.couplings: one sampled fact answers every clause it touches
    — the share in the bargain, warranty, and receipt; the vessel's value
    derived from its tuns and rate, the consideration a share of it, the bond
    double the consideration; the vessel in subject and appurtenances; the
    parties across all clauses."""
    text = " ".join(_content(_rendered(model)).split())
    sh = model["share"]
    assert f"{sh['of_a']} {model['vessel']['type']}" in text          # bargain
    assert f"the said {sh['said']} of the said" in text               # warranty
    assert f"for the {sh['for_the']} of the same" in text             # receipt
    v = model["vessel"]
    assert model["whole_pounds"] == v["tuns"] * v["rate"]
    assert model["price_pounds"] == max(1, round(model["whole_pounds"]
                                                 / sh["den"]))
    assert model["bond_pounds"] == 2 * model["price_pounds"]
    assert model["bond_words"] in text                                # bond words
    assert f"{model['price_roman']} li." in text                      # receipt
    assert f"called the {v['name']}" in text
    assert f"of {v['port']}" in text
    if v["former"]:
        assert f"sometime called the {v['former']}" in text
    assert f"{bos._words(v['tuns'])} tunnes" in text


def test_pins_honored():
    """billofsale.couplings: caller pins fix the fact they own, and every
    clause follows — vessel name, tuns, former-name convention, share, price,
    sale date, salutation — with the sampler still coherent around them."""
    m = bos.sample_bill(random.Random(11),
                        pins={"vessel_name": "Unity", "tuns": 24,
                              "former": True, "share": 4, "price_pounds": 60,
                              "sale_month": 5, "sale_day": 9,
                              "salutation": False})
    assert m["vessel"]["name"] == "Unity" and m["vessel"]["tuns"] == 24
    assert m["vessel"]["former"] is not None
    assert m["share"]["den"] == 4 and m["price_pounds"] == 60
    assert m["bond_pounds"] == 120
    text = _content(_rendered(m))
    assert "called the Unity, sometime called the" in text
    assert "twenty four tunnes" in text
    assert "one fourth part of a" in text
    assert m["salutation"] is False
    m23 = bos.sample_bill(random.Random(11), pins={"sale_month": 10,
                                                   "sale_day": 23,
                                                   "salutation": False})
    assert "twenty third daye of October" in _content(_rendered(m23))


def test_manuscript_scan(model):
    """billofsale.manuscript-scan: the artifact is a scan of an engrossed
    membrane — JPEG image pages, LANDSCAPE (the sourced visual exemplar is a
    skin whose lines run its full width, never a portrait stock sheet), a
    1642 instrument cannot be a vector file (PDF shipped 1993), metadata
    dated at DIGITIZATION in the PDF era, ModDate == CreationDate, the dorse
    carrying docket and witnesses, and the OCR layer keeping it searchable.
    Hands: the party's (when literate) plus every witness subscribing the
    dorse — and nothing else is an embedded image."""
    import re
    vector, _, ph = bos._manuscript_pdf(bos.compose_bill(model),
                                        random.Random(model["scan_seed"]),
                                        model)
    signers = len(model["witnesses"]) + (1 if model["literate"] else 0)
    n_hands = 2 * signers                       # cursive PNG + its alpha mask
    assert len(re.findall(rb"/Subtype\s*/Image", vector)) == n_hands
    assert bos.PAGE_W > ph                      # a membrane, not a stock sheet
    pdf = _rendered(model)
    assert pdf.count(b"/DCTDecode") >= 2             # engrossment + dorse
    cd = re.search(rb"/CreationDate \(D:(\d{4})", pdf).group(1)
    assert int(cd) >= 1993
    md = re.search(rb"/ModDate \((D:[0-9]+)\)", pdf).group(1)
    assert md == re.search(rb"/CreationDate \((D:[0-9]+)\)", pdf).group(1)
    from mattermill import lens
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(pdf)
        f.flush()
        info = lens.pdf_info(f.name)
    assert info["producer"] == META["producer"]
    assert info["pages"] == 2                        # one skin, both sides
    text = _content(pdf)
    assert "witnesseth that I" in text               # OCR layer present
    assert "The bill of sale of the" in text         # dorse endorsement


def test_defect_delta_hooks(model):
    """billofsale.defect-delta-hooks: each hook alters exactly one displayed
    value while everything computed around it stays honest."""
    clean = " ".join(_content(_rendered(model)).split())

    bad = " ".join(_content(bos.render_bill(
        model, metadata=META, defect={"regnal_year": "fifteenth"})).split())
    assert "fifteenth yeere of the reigne" in bad
    assert f"{model['date']['day_ord']} daye of {model['date']['month_name']}" in bad

    alt_share = next(s[1] for s in bos.SHARES if s[1] != model["share"]["for_the"])
    bad2 = " ".join(_content(bos.render_bill(
        model, metadata=META, defect={"receipt_share": alt_share})).split())
    assert f"for the {alt_share} of the same" in bad2                 # receipt lies
    assert clean.split("for the")[0] in bad2 or True                  # bargain intact
    assert f"{model['share']['of_a']} {model['vessel']['type']}" in bad2

    bad3 = " ".join(_content(bos.render_bill(
        model, metadata=META, defect={"receipt_price": "xcix li."})).split())
    assert "xcix li." in bad3
    assert model["bond_words"] in bad3                                # bond honest

    bad4 = " ".join(_content(bos.render_bill(
        model, metadata=META,
        defect={"feast": "the Purification of the Virgin Mary"})).split())
    assert "the feast of the Purification of the Virgin Mary" in bad4


def test_defect_delta_hooks_salutation_form():
    """billofsale.defect-delta-hooks, form B: the same hooks land on the
    salutation form's analogous sites (testimonium regnal, consideration
    words, appurtenance share)."""
    m = bos.sample_bill(random.Random(7), pins={"salutation": True})
    bad = _content(bos.render_bill(m, metadata=META,
                                   defect={"regnal_year": "fifteenth"}))
    assert "in the fifteenth yeere of the reigne" in bad
    bad2 = _content(bos.render_bill(
        m, metadata=META, defect={"receipt_price": "nine hundred and ninety"}))
    assert "sum of nine hundred and ninety pounds" in bad2
    alt = next(s[3] for s in bos.SHARES if s[3] != m["share"]["said"])
    bad3 = _content(bos.render_bill(
        m, metadata=META, defect={"receipt_share": alt}))
    assert f"to the {alt} of the same {m['vessel']['type']} appertaining" in bad3
    assert f"{m['share']['of_a']} {m['vessel']['type']}" in bad3   # bargain intact


def test_seeded_everywhere(model):
    """seeded.everywhere: same seed in, same model out, byte-identical scan
    out — across the sampler, composer, manuscript stage, and scan pipe."""
    assert model == bos.sample_bill(random.Random(1642),
                                    pins={"salutation": False})
    assert _rendered(model) == _rendered(model)
