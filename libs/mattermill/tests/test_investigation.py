"""Capability tests for independently forgeable museum-investigation records."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pypdfium2 as pdfium
import pytest

from mattermill import registry


CLASSES = (
    "museum_research_note",
    "curatorial_chronology",
    "conservation_examination",
    "access_event_report",
    "tenant_account_ledger",
    "voicemail_evidence_report",
    "pump_emergency_card",
)


def _pdf(name: str, **kwargs):
    return registry.emit(name, seed=18420728, pins={}, canon={}, **kwargs)


def _text(data: bytes) -> str:
    doc = pdfium.PdfDocument(data)
    return " ".join(
        "\n".join(page.get_textpage().get_text_range() for page in doc).split()
    )


def test_research_note_has_source_register_method_boundary_and_review():
    """investigation.research-note-source-register: a conclusion remains tied
    to named sources, source criticism, limitations, and curatorial review."""
    data, manifest = _pdf("museum_research_note")
    text = _text(data)
    for marker in (
        "RESEARCH NOTE", "OBJECT REF.", "Question", "Sources reviewed",
            "Captured-source register", "Method", "Limitations", "FINAL",
    ):
        assert marker.lower() in text.lower()
    assert manifest["display_facts"]["accessibility"]["interpretation"] == []


def test_chronology_separates_event_class_source_and_reading_rule():
    """investigation.chronology-boundaries: historical, observed, system,
    and device entries name their source without upgrading it to identity."""
    text = _text(_pdf("curatorial_chronology")[0])
    for marker in (
        "WORKING EVENT CHRONOLOGY", "historical", "observed", "system", "device",
        "does not identify the person", "does not identify the speaker",
        "ANALYST NOTE",
    ):
        assert marker.lower() in text.lower()


def test_conservation_report_carries_osac_casework_anatomy_and_limits():
    """investigation.conservation-report: custody, requested scope, methods,
    observations, evaluation, limitations, and technical review stay distinct."""
    text = _text(_pdf("conservation_examination")[0])
    for marker in (
        "Items received and custody", "Requested examination", "Methods",
        "Observations", "Evaluation", "Reporting limitations",
        "Technical reviewer", "Class characteristics cannot identify",
    ):
        assert marker.lower() in text.lower()


def test_conservation_final_status_matches_metadata_and_release_chronology():
    """investigation.conservation-release-provenance: a final report's PDF
    title and normalized UTC creation time agree with its visible release."""
    data, _ = _pdf("conservation_examination")
    metadata = pdfium.PdfDocument(data).get_metadata_dict()
    assert metadata["Title"] == "Limited examination report"
    assert metadata["CreationDate"] == "D:20260211184600-05'00'"
    assert metadata["ModDate"] == metadata["CreationDate"]


def test_access_export_uses_historical_report_fields_and_native_landscape():
    """investigation.access-event-export: event sequence, time, credential,
    cardholder, door, event message, direction, and exact filters are visible."""
    data, _ = _pdf("access_event_report")
    text = _text(data)
    for marker in (
        "Sequence", "Credential", "Cardholder", "Door / device",
        "Event message", "Database", "Operator / workstation",
        "Controller event sequence",
    ):
        assert marker.lower() in text.lower()
    page = pdfium.PdfDocument(data)[0]
    assert page.get_width() > page.get_height()


def test_tenant_account_separates_rent_receivable_and_deposit_liability():
    """investigation.tenant-account: one coherent property-system record links
    resident, premises, term, charges and receipts while keeping the security
    deposit outside the rent receivable balance."""
    data, _ = _pdf("tenant_account_ledger")
    text = _text(data)
    for marker in (
        "Resident Ledger", "Resident", "Lease term", "Account activity",
        "$2,800.00", "$4,200.00", "Rent balance", "Deposit held",
    ):
        assert marker.lower() in text.lower()
    assert "RESIDENTIAL LEASE AGREEMENT" not in text
    page = pdfium.PdfDocument(data)[0]
    assert page.get_height() > page.get_width()


def test_voicemail_report_preserves_source_audio_over_derived_transcript():
    """investigation.voicemail-source-boundary: transcript offsets and audible
    events remain subordinate to the hashed retained source audio."""
    text = _text(_pdf("voicemail_evidence_report")[0])
    for marker in (
        "DV-04 — Limited Mobile File Collection", "Authority and collection boundary",
        "Operator event log", "File Verification / Listening Notes",
        "effective 2025-10-01", "HPHC-IR-04", "CT-20260211-2131-07",
        "VM-00018472_20260211T203814-0500.m4a",
        "IR-26-07/source/MER-26-019", "711fc12a",
        "no device extraction", "not a carrier-origin record",
        "not biometric speaker identification",
    ):
        assert marker.lower() in text.lower()


def test_pump_card_has_native_card_geometry_and_safety_order():
    """investigation.pump-emergency-card: the equipment-mounted sheet defines
    non-entry release, defers entry and guarded work to controlled procedures,
    and records inspection, restoration authority, and post-use disposition."""
    data, _ = _pdf("pump_emergency_card")
    text = _text(data)
    for marker in (
        "NON-ENTRY EMERGENCY RELEASE", "PERMIT-REQUIRED CONFINED SPACE",
        "ER-2 RED RING", "DO NOT ENTER", "Trained and authorized staff",
        "use CSP-03 and ECP-LOTO-02 in full", "AFTER ER-2 OPERATION",
        "IF ER-2 DOES NOT OPEN DR-2", "NEVER ENTER R-2 FOR RESCUE",
        "P-2 work order", "Hoboken Fire Department technical rescue",
        "permit number and attendant", "Facilities DMS > Safety Documents",
        "Director of Safety & Compliance", "MONTHLY FIELD CHECK",
        "P-2 / ASSET 0227", "YOU ARE HERE",
    ):
        assert marker.lower() in text.lower()
    page = pdfium.PdfDocument(data)[0]
    assert page.get_width() == pytest.approx(792)
    assert page.get_height() == pytest.approx(612)


def test_investigation_defect_is_one_explicit_display_delta():
    """investigation.explicit-defect: a planted fault alters one named scalar
    and unsupported or structured mutations fail."""
    data, manifest = _pdf(
        "museum_research_note",
        defect={"field": "record_id", "value": "RIM-26-999"},
    )
    assert "RIM-26-999" in _text(data)
    assert manifest["ground_truth"] == [
        {"field": "record_id", "value": "RIM-26-999"}
    ]
    with pytest.raises(ValueError, match="exactly field and value"):
        _pdf("museum_research_note", defect={"record_id": "RIM-26-999"})
    with pytest.raises(ValueError, match="displayed scalar"):
        _pdf(
            "museum_research_note",
            defect={"field": "sources", "value": []},
        )


def test_investigation_classes_are_cross_process_seeded_and_registered():
    """investigation.seeded-offline: all seven classes are registry-addressable
    and byte-identical across interpreter hash seeds without network access."""
    assert set(CLASSES) <= {item["name"] for item in registry.list_classes()}
    script = """
from mattermill import registry
for name in %r:
    data, manifest = registry.emit(name, seed=18420728, pins={}, canon={})
    print(name, manifest['sha256'], len(data))
""" % (CLASSES,)
    outputs = []
    for hash_seed in ("1", "987654"):
        outputs.append(subprocess.check_output(
            [sys.executable, "-c", script], cwd=Path.cwd(),
            env=dict(os.environ, PYTHONHASHSEED=hash_seed),
        ))
    assert outputs[0] == outputs[1]
