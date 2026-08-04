"""Capability tests for the frozen 2019 Massachusetts estate-file contract."""

from __future__ import annotations

import io
import random

import pypdfium2 as pdfium
import pytest

from mattermill import estate_ma as E
from mattermill import registry


META = {
    "producer": "Adobe Acrobat Pro DC 19.021",
    "creator": "Microsoft Word 2016",
    "created": "2020-04-13 16:10:00",
    "modified": None,
}


def _pages(data: bytes) -> list[str]:
    doc = pdfium.PdfDocument(io.BytesIO(data))
    return [" ".join((page.get_textpage().get_text_range() or "").split())
            for page in doc]


def _composed_text(model: dict, defect: dict | None = None) -> str:
    parts: list[str] = []
    for line in E.compose_estate(model, defect):
        if "text" in line:
            parts.append(str(line["text"]))
        if "hang" in line:
            parts.extend(str(value) for value in line["hang"])
        if "row" in line:
            parts.extend(str(value) for value in line["row"])
        if "signature" in line:
            parts.extend(str(value) for value in line["signature"][:2])
    return " ".join(parts)


@pytest.fixture()
def model():
    return E.sample_estate(random.Random(85), pins={"bates_prefix": "VALE-EST-"})


@pytest.fixture()
def pdf(model):
    return E.render_estate(model, metadata=META)


def test_packet_completeness(model, pdf):
    """estate.packet-completeness: the ten requested components and tax memo appear."""
    text = " ".join(_pages(pdf))
    assert len(E.DOCUMENT_TITLES) == 11
    assert all(title in text for title in E.DOCUMENT_TITLES)
    assert all(str(number) in text for number in range(1, 12))


def test_canon_outcome(model):
    """estate.canon-outcome: the house, company, copyrights and residue reach one beneficiary."""
    text = _composed_text(model)
    for token in (model["beneficiary"], model["home_address"], model["company"],
                  "all author-owned catalog copyrights", "and the residue"):
        assert token in text
    assert "NON-NEGOTIABLE RETAINED OUTCOME" in text
    living_family = [person["name"] for person in model["family"]
                     if not person["relationship"].lower().startswith("predeceased")]
    assert all(name in text for name in living_family)
    assert model["family"][2]["name"] not in E._named_family(model)


def test_will_execution(model):
    """estate.will-execution: the will carries testator, two witnesses and self-proof."""
    text = _composed_text(model)
    assert "SELF-PROVING AFFIDAVIT" in text
    assert text.count(model["witness_1"]) >= 2
    assert text.count(model["witness_2"]) >= 2
    assert model["notary"] in text
    assert "presence and hearing" in text
    seals = [line["notary_seal"] for line in E.compose_estate(model)
             if "notary_seal" in line]
    assert len(seals) == 3
    assert all(name == model["notary"] for name, _ in seals)


def test_pour_over(model):
    """estate.pour-over: probate residue pours into the identified preexisting trust."""
    text = _composed_text(model)
    assert model["trust_name"] in text
    assert E._fmt(model["trust_original_date"]) in text
    assert "G. L. c. 190B, section 2-511" in text
    assert "all the residue of my probate estate" in text


def test_trust_amendment(model):
    """estate.trust-amendment: the restatement follows a stated signed-delivery method."""
    text = _composed_text(model)
    assert "signed writing delivered to the Trustee" in text
    assert "acknowledges delivery and acceptance" in text
    assert "Complete Restatement" in text
    assert "At death it becomes irrevocable" in text


def test_stock_and_copyright_funding(model):
    """estate.stock-and-copyright-funding: stock and author copyrights move by distinct assignments."""
    text = _composed_text(model)
    assert f"{model['company_shares']:,}" in text
    assert "entire issued and outstanding equity position" in text
    assert "ASSIGNMENT OF COPYRIGHTS" in text
    assert "17 U.S.C. section 204(a)" in text
    assert model["copyright_scope"] in text
    assert "ISSUER STOCK-LEDGER EXTRACT" in text
    assert "CANCELLED" in text and "OPEN" in text
    assert all(work["title"] in text for work in model["copyright_catalog"])


def test_inventory_titling(model):
    """estate.inventory-titling: one derived title map separates trust and probate values."""
    values = E.compute_assets(model)
    assert values["gross_total"] == values["trust_total"] + values["probate_total"]
    assert values["trust_cash"] + model["probate_cash"] == model["liquid_assets"]
    text = _composed_text(model)
    for amount in (values["trust_total"], values["probate_total"],
                   values["gross_total"]):
        assert E._money(amount) in text
    assert "Company assets and liabilities are subsumed in the stock appraisal" in text
    bad = _composed_text(model, {"inventory_total": 1})
    assert "$1" in bad and E._money(values["trust_total"]) in bad


def test_memorandum_role(model):
    """estate.memorandum-role: the disinheritance memorandum is evidentiary, not dispositive."""
    text = _composed_text(model)
    assert "THIS MEMORANDUM IS NOT A WILL, CODICIL, TRUST AMENDMENT" in text
    assert "creates no transfer" in text
    assert "signed Will, Trust Restatement, and assignments alone control" in text


def test_capacity_record(model):
    """estate.capacity-record: the physician records observations without giving a legal conclusion."""
    text = _composed_text(model)
    assert "limited clinical assessment" in text
    assert "not giving a legal opinion" in text
    assert "These observations describe one encounter" in text
    for token in ("person", "place", "date", "property", "family"):
        assert token in text.lower()


def test_independent_execution(model):
    """estate.independent-execution: the beneficiary neither instructs nor attends execution."""
    text = _composed_text(model)
    assert "beneficiary was not present" in text
    assert "did not participate" in text
    signatures = [line["signature"][0] for line in E.compose_estate(model)
                  if "signature" in line]
    assert model["beneficiary"] not in signatures


def test_probate_petition(model):
    """estate.probate-petition: the petition states venue, parties, relief and honest filing status."""
    text = _composed_text(model)
    assert "Docket No. TO BE ASSIGNED BY COURT" in text
    assert f"{model['county']} Division" in text
    for form in ("MPC 160", "MPC 162", "MPC 163", "MPC 280", "MPC 801"):
        assert form in text
    assert all(person["name"] in text for person in model["family"]
               if person["heir_at_law"])
    assert "Sole beneficial recipient through pour-over trust" in text


def test_objection_merits(model):
    """estate.objection-merits: family objections plead plausible grounds without claiming proof."""
    text = _composed_text(model)
    for token in ("Testamentary capacity", "Undue influence and procurement",
                  "Execution and amendment", "Mistake, fraud, and ownership"):
        assert token in text
    assert "suspicion and opportunity alone do not prove coercion" in text


def test_slayer_rule(model):
    """estate.slayer-rule: forfeiture requires a felonious and intentional killing."""
    text = _composed_text(model)
    assert "feloniously and intentionally" in text
    assert "felonious and intentional" in text
    assert "negligence or a medication error alone" in text
    assert "another person switched labels" in text


def test_no_contest_honesty(model):
    """estate.no-contest-honesty: the analysis does not overstate a will penalty clause."""
    text = _composed_text(model)
    assert "does not eliminate standing" in text
    assert "does not" in text and "decide treatment of a separate trust clause" in text
    assert "has no gift to forfeit" in text
    assert "not the principal defense" in text


def test_settlement_control(model):
    """estate.settlement-control: cash resolves claims while core inheritance stays intact."""
    values = E.compute_assets(model)
    text = _composed_text(model)
    assert E._money(values["settlement_offer"]) in text
    assert "receive cash only" in text
    for token in (model["home_address"], model["company"],
                  "catalog copyrights", "governance and licensing control"):
        assert token in text
    assert E._money(E.compute_tax_projection(model)["total_reserve"]) in text


def test_tax_liquidity_control(model):
    """estate.settlement-control: taxes, liquidity and a preservation plan share one asset model."""
    assets = E.compute_assets(model)
    projection = E.compute_tax_projection(model)
    assert projection["taxable_estate"] == (
        assets["gross_total"] - assets["administration_reserve"])
    assert projection["total_reserve"] > projection["liquid_assets"]
    assert projection["liquidity_shortfall"] == (
        projection["total_reserve"] - projection["liquid_assets"])
    assert projection["section_6166_candidate"]
    text = _composed_text(model)
    for token in ("Form 706", "Form M-706", "I.R.C. section 6166",
                  "PROJECTED LIQUIDITY SHORTFALL", "not designated for sale"):
        assert token in text


def test_professional_role_separation(model):
    """estate.independent-execution: drafting, fiduciary and advocacy roles stay separate."""
    assert len({model["attorney"], model["independent_fiduciary"],
                model["estate_counsel"], model["beneficiary_counsel"]}) == 4
    text = _composed_text(model)
    assert f"nominate {model['independent_fiduciary']}" in text
    assert f"At the Settlor's death, {model['independent_fiduciary']}" in text
    assert f"Responsible attorney: {model['attorney']}" in text


def test_cross_document_coherence():
    """estate.cross-document-coherence: caller canon drives every repeated fact without leakage."""
    canon = dict(E.DEFAULT_CANON,
                 decedent="Lucian Cross",
                 beneficiary="Rosa Bell",
                 attorney="Amos Finch",
                 independent_fiduciary="Marian Holt",
                 estate_counsel="Eleanor Pike",
                 beneficiary_counsel="Thomas Carver",
                 company="Cross Quill Publishing, Inc.",
                 company_short="Cross Quill",
                 home_address="91 Alder Lane",
                 trust_name="The Lucian Cross Revocable Trust",
                 copyright_scope="all Lucian Cross literary copyrights",
                 copyright_catalog=[{"title": "The Cross File", "year": 2007}])
    model = E.sample_estate(random.Random(4), canon=canon)
    text = _composed_text(model)
    for value in (canon["decedent"], canon["beneficiary"], canon["attorney"],
                  canon["company"], canon["home_address"], canon["trust_name"],
                  canon["copyright_scope"]):
        assert value in text
    for leaked in (E.DEFAULT_CANON["decedent"], E.DEFAULT_CANON["beneficiary"],
                   E.DEFAULT_CANON["company"]):
        assert leaked not in text


def test_identifier_honesty(model):
    """estate.identifier-honesty: unverified identifiers are omitted without synthetic leakage."""
    text = _composed_text(model)
    assert "TO BE ASSIGNED" in text
    assert "no court-issued citation or docket number existed" in text
    assert "unverified Copyright Office registration number" in text
    assert "synthetic" not in text.lower()


def test_seeded_everywhere():
    """estate.determinism: identical seed, canon, pins and metadata produce identical bytes."""
    first, first_manifest = registry.emit(
        "estate_packet_ma", seed=85, pins={"bates_prefix": "TEST-"},
        canon=E.DEFAULT_CANON, metadata=META)
    second, second_manifest = registry.emit(
        "estate_packet_ma", seed=85, pins={"bates_prefix": "TEST-"},
        canon=E.DEFAULT_CANON, metadata=META)
    assert first == second
    assert first_manifest["sha256"] == second_manifest["sha256"]


def test_forensic_packet(model, pdf):
    """estate.forensic-packet: searchable pages carry coherent signatures, metadata and Bates furniture."""
    pages = _pages(pdf)
    assert len(pages) >= 12
    assert all(page.strip() for page in pages)
    assert all(f"VALE-EST-{number:06d}" in page
               for number, page in enumerate(pages, 1))
    assert all(f"Page {number}" in page for number, page in enumerate(pages, 1))
    metadata = pdfium.PdfDocument(io.BytesIO(pdf)).get_metadata_dict()
    assert "2020" in metadata["CreationDate"]
    assert metadata["CreationDate"] == metadata["ModDate"]
    assert any(type(obj).__name__ == "PdfImage"
               for page in pdfium.PdfDocument(io.BytesIO(pdf))
               for obj in page.get_objects())
    assert all(E.pdfmetrics.stringWidth(E._fit_footer(title), "Helvetica", 6.5)
               <= 185 for title in E.DOCUMENT_TITLES)
