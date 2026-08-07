"""Capability contract for the contemporary wedding invitation suite."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import io
import random
import re
import subprocess
import sys

import pypdfium2 as pdfium
import pytest

from mattermill import wedding_suite


META = {
    "producer": "Adobe PDF Library 17.0",
    "creator": "Adobe InDesign 2024",
    "created": "2026-07-05 10:30:00",
    "modified": None,
}


def _model(*, pins=None, canon=None, seed=3):
    return wedding_suite.sample_suite(
        random.Random(seed), pins=pins,
        canon=canon if canon is not None else wedding_suite.DEFAULT_CANON)


def _pdf(model=None, defect=None):
    return wedding_suite.render_suite(model or _model(), metadata=META,
                                      defect=defect)


def _pages(data: bytes) -> list[str]:
    doc = pdfium.PdfDocument(io.BytesIO(data))
    return [" ".join((page.get_textpage().get_text_range() or "").split())
            for page in doc]


def test_anatomy_and_trim_sizes():
    """wedding-suite.anatomy: three ordered cards carry sourced trim sizes."""
    doc = pdfium.PdfDocument(io.BytesIO(_pdf()))
    assert len(doc) == 3
    sizes = [tuple(round(v, 1) for v in page.get_size()) for page in doc]
    assert sizes == [(360.0, 504.0), (360.0, 252.0), (360.0, 252.0)]
    text = _pages(_pdf())
    assert "TOGETHER WITH THEIR FAMILIES" in text[0]
    assert "THE DETAILS" in text[1]
    assert "KINDLY REPLY" in text[2]


def test_venue_canon_is_single_source():
    """wedding-suite.venue-canon: venue identity and address come from canon."""
    canon = dict(wedding_suite.DEFAULT_CANON,
                 venue_name="Harbor Elm House", venue_address="9 Quay Road",
                 venue_city="New London", venue_state="Connecticut",
                 venue_postal="06320", venue_capacity=140)
    pages = _pages(_pdf(_model(canon=canon,
                              pins={"invited_count": 140})))
    assert "Harbor Elm House" in pages[0] and "Harbor Elm House" in pages[1]
    assert "9 Quay Road · New London, Connecticut 06320" in pages[1]
    assert "Simsbury" not in " ".join(pages)


def test_calendar_weekday_is_derived():
    """wedding-suite.calendar-coherence: weekday derives from the ISO date."""
    model = _model()
    date = dt.date.fromisoformat(model["wedding_date"])
    assert model["weekday"] == date.strftime("%A") == "Saturday"
    page = _pages(_pdf(model))[0]
    assert "SATURDAY · OCTOBER THIRD" in page
    assert "TWO THOUSAND TWENTY-SIX" in page


def test_capacity_gates_invites_and_allocation():
    """wedding-suite.capacity-coherence: invited and household counts share one gate."""
    assert _model()["invited_count"] == _model()["venue_capacity"] == 200
    with pytest.raises(ValueError, match="between 1 and 200"):
        _model(pins={"invited_count": 201})
    with pytest.raises(ValueError, match="within the invited count"):
        _model(pins={"invited_count": 2, "party_allocation": 3})


def test_unknown_event_facts_remain_placeholders():
    """wedding-suite.unknowns-honest: missing send-critical facts stay explicit."""
    text = " ".join(_pages(_pdf()))
    for marker in ("[FIRST FULL NAME]", "[SECOND FULL NAME]",
                   "[INSERT CEREMONY TIME]", "[ADD RECEPTION DETAILS]",
                   "[INSERT RSVP DEADLINE]",
                   "[INSERT RSVP METHOD]", "[INSERT DRESS CODE]",
                   "[ADD LODGING OR TRAVEL DETAILS]", "[ADD WEDDING WEBSITE]"):
        assert marker in text


def test_rsvp_controls_large_party_headcount():
    """wedding-suite.rsvp-control: response card captures identity, decision, and count."""
    rsvp = _pages(_pdf())[2]
    for marker in ("KINDLY REPLY", "JOYFULLY ACCEPTS", "REGRETFULLY DECLINES",
                   "NUMBER ATTENDING", "OF ____", "RESPOND VIA"):
        assert marker in rsvp
    personalized = _pages(_pdf(_model(pins={"party_allocation": 4})))[2]
    assert "OF 4" in personalized


def test_logistics_are_legible_at_eight_points_or_more():
    """wedding-suite.legibility: every PDF text operator uses at least 8 points."""
    sizes = [float(value) for value in
             re.findall(rb"(?:^|\s)(?:/[A-Za-z0-9]+\s+)?([0-9.]+)\s+Tf", _pdf())]
    assert sizes, "uncompressed content should expose font sizes"
    assert min(sizes) >= 8


def test_guard_list_forbids_unsupplied_claims():
    """wedding-suite.guard-list: the proof does not settle optional event policy."""
    text = " ".join(_pages(_pdf())).lower()
    for forbidden in ("registry", "shuttle departs", "children are not invited",
                      "room block code", "choice of entrée"):
        assert forbidden not in text
    assert "[insert dress code]" in text
    assert "[add lodging or travel details]" in text
    assert "[add reception details]" in text
    assert "dinner & dancing" not in text


def test_determinism_holds_across_processes():
    """wedding-suite.determinism: same seed and canon are byte-identical across processes."""
    first = _pdf(_model(seed=17))
    second = _pdf(_model(seed=17))
    assert first == second
    code = (
        "import hashlib,random; from mattermill import wedding_suite as w; "
        "m=w.sample_suite(random.Random(17),canon=w.DEFAULT_CANON); "
        "meta={'producer':'Adobe PDF Library 17.0','creator':'Adobe InDesign 2024',"
        "'created':'2026-07-05 10:30:00','modified':None}; "
        "print(hashlib.sha256(w.render_suite(m,metadata=meta)).hexdigest())"
    )
    digest = subprocess.check_output([sys.executable, "-c", code], text=True).strip()
    assert digest == hashlib.sha256(first).hexdigest()
    assert _pdf(_model(seed=18)) != first


def test_forensic_metadata_is_fixed_and_event_prior():
    """wedding-suite.forensic-metadata: flattened proof dates match and precede event."""
    data = _pdf()
    created = re.search(rb"/CreationDate \(([^)]*)\)", data).group(1)
    modified = re.search(rb"/ModDate \(([^)]*)\)", data).group(1)
    assert created == modified == b"D:20260705103000"
    assert dt.date(2026, 7, 5) < dt.date.fromisoformat(_model()["wedding_date"])
    pair = re.search(rb"/ID \[<([0-9a-f]+)><([0-9a-f]+)>\]", data)
    assert pair and pair.group(1) == pair.group(2)
    from mattermill import registry
    _data, manifest = registry.emit("wedding_invitation_suite", seed=3)
    assert manifest["metadata"]["producer"].startswith("mattermill PDF Engine")
    assert manifest["metadata"]["creator"].startswith("mattermill Wedding Suite")


def test_each_defect_changes_only_its_display_target():
    """wedding-suite.defect-isolation: hooks alter one displayed relationship only."""
    model = _model()
    original = copy.deepcopy(model)
    clean = _pages(_pdf(model))
    weekday = _pages(_pdf(model, {"weekday": "Friday"}))
    venue = _pages(_pdf(model, {"details_venue": "Wrong Venue"}))
    allocation = _pages(_pdf(model, {"rsvp_allocation": 201}))
    assert weekday[1:] == clean[1:] and "FRIDAY" in weekday[0]
    assert venue[0] == clean[0] and venue[2] == clean[2] and "Wrong Venue" in venue[1]
    assert allocation[:2] == clean[:2] and "OF 201" in allocation[2]
    assert model == original
