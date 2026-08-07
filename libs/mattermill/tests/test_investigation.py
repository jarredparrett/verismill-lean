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


def test_access_export_uses_historical_report_fields_and_native_landscape():
    """investigation.access-event-export: event sequence, time, credential,
    cardholder, door, event message, direction, and exact filters are visible."""
    data, _ = _pdf("access_event_report")
    text = _text(data)
    for marker in (
        "Sequence", "Credential", "Cardholder", "Door / device",
        "Event message", "REPORT PARAMETERS", "controller-assigned",
    ):
        assert marker.lower() in text.lower()
    page = pdfium.PdfDocument(data)[0]
    assert page.get_width() > page.get_height()


def test_tenant_account_is_honest_about_not_being_the_executed_lease():
    """investigation.tenant-account: one coherent property-system record links
    tenant, premises, term, rent, deposit, transactions, and its own limits."""
    text = _text(_pdf("tenant_account_ledger")[0])
    for marker in (
        "TENANT ACCOUNT RECORD", "Tenant of record", "Term and recurring charge",
        "Account ledger", "$2,800.00", "$4,200.00", "not the executed lease",
    ):
        assert marker.lower() in text.lower()
    assert "RESIDENTIAL LEASE AGREEMENT" not in text


def test_voicemail_report_preserves_source_audio_over_derived_transcript():
    """investigation.voicemail-source-boundary: transcript offsets and audible
    events remain subordinate to the hashed retained source audio."""
    text = _text(_pdf("voicemail_evidence_report")[0])
    for marker in (
        "VOICEMAIL EVIDENCE REPORT", "Source record", "Time-aligned transcript",
        "retained audio is the source record", "not biometric identification",
    ):
        assert marker.lower() in text.lower()


def test_pump_card_has_native_card_geometry_and_safety_order():
    """investigation.pump-emergency-card: the native card identifies equipment,
    forbids occupancy, isolates energy, releases externally, and records use."""
    data, _ = _pdf("pump_emergency_card")
    text = _text(data)
    for marker in (
        "EMERGENCY RELEASE", "PUMP HOUSING P-2", "NO OCCUPANCY",
        "Isolate electrical disconnect", "RED EMERGENCY RELEASE RING",
        "tag P-2 out of service",
    ):
        assert marker.lower() in text.lower()
    page = pdfium.PdfDocument(data)[0]
    assert page.get_width() == pytest.approx(432)
    assert page.get_height() == pytest.approx(288)


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
