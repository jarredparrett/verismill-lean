"""Capability tests for the frozen 1937 private-observatory packet contract."""

from __future__ import annotations

import io
import json
import random
import subprocess
import sys

import pypdfium2 as pdfium
import pytest
from PIL import Image, ImageChops, ImageStat
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as rl_canvas

from mattermill import assets
from mattermill import observatory as O
from mattermill import registry


META = {
    "producer": "Zeutschel OS 12002 / Adobe Paper Capture",
    "creator": "Zeutschel OS 12002",
    "created": "2020-01-17 10:42:00",
    "modified": None,
}


def _pages(data: bytes) -> list[str]:
    doc = pdfium.PdfDocument(io.BytesIO(data))
    return [" ".join((page.get_textpage().get_text_range() or "").split())
            for page in doc]


@pytest.fixture()
def model():
    return O.sample_packet(random.Random(19370117))


@pytest.fixture()
def vector_pages(model):
    _data, layers = O._compose_vector(model, None)
    return [" ".join(str(line) for line in page) for page in layers]


@pytest.fixture()
def pdf(model):
    return O.render_packet(model, metadata=META, scan_dpi=90)


def test_packet_anatomy(vector_pages):
    """observatory.packet-anatomy: all evidentiary layers are separate objects."""
    assert len(vector_pages) == len(O.PAGE_MARKERS) == 20
    assert all(marker in page for marker, page in zip(O.PAGE_MARKERS, vector_pages))
    required = ("observing", "plate", "chronograph", "correction", "radio",
                "maintenance", "circular", "endowment", "key", "carbon letter",
                "storm", "ground-floor plan")
    inventory = vector_pages[0].lower()
    assert all(token in inventory for token in required)


def test_period_log_form(model, vector_pages):
    """observatory.period-log-form: source-calibrated log fields carry the observation."""
    page = vector_pages[1].lower()
    times = O._time_facts(model)
    for token in ("PLATE", "OBJECT", "R.A. 1900", "Declination 1900", "Telescope",
                  "Starting Time L.S.T.", "Ending Time L.S.T.", "Hour Angle Mid", "Observer",
                  model["final_plate_id"], model["field_ra"], model["field_dec"],
                  times["corrected_start_lst"], times["corrected_stop_lst"],
                  times["hour_angle"]):
        assert token.lower() in page
    assert f"temperature {model['weather_temp_f']} f" in page


def test_linked_plate_custody(model, vector_pages):
    """observatory.linked-plate-custody: one plate id links five distinct objects."""
    linked = [1, 2, 3, 4, 5, 7]
    assert all(model["final_plate_id"] in vector_pages[index] for index in linked)
    assert len({O.PAGE_MARKERS[index] for index in linked}) == len(linked)
    assert "ISSUED R. BELL" in vector_pages[2]
    assert "RETURNED 10:02 P.M." in vector_pages[2]


def test_clock_correction_sign(model):
    """observatory.clock-correction-sign: the sign reversal creates a 113.6-second shift."""
    honest, _ = O._compose_vector(model, None)
    altered, _ = O._compose_vector(model, {"correction_sign": "reverse"})
    hp, ap = _pages(honest), _pages(altered)
    assert model["true_correction_seconds"] == -56.8
    assert model["culprit_correction_seconds"] == 56.8
    assert model["correction_shift_seconds"] == 113.6
    assert "-56.8 seconds" in hp[5] and "+56.8 seconds" in ap[5]
    assert [i for i, pair in enumerate(zip(hp, ap)) if pair[0] != pair[1]] == [5]


def test_regulator_continuity(vector_pages):
    """observatory.regulator-continuity: the standard runs while named circuits fail."""
    chronograph, storm = vector_pages[4], vector_pages[15]
    assert "mains contact out; beats continue" in chronograph
    assert "mechanical standard continued" in storm
    assert "lights, dome motor, remote displays lost" in storm
    assert "GENERATOR" in storm and "lights only" in storm


def test_ra_ha_lst(model, vector_pages):
    """observatory.ra-ha-lst: the completed reduction records one balanced calculation."""
    page = vector_pages[7]
    assert "Hour Angle Mid" in vector_pages[1]
    assert "Hour Angle End" not in vector_pages[1]
    times = O._time_facts(model)
    for value in (model["field_ra"], times["hour_angle"], times["expected_lst"],
                  times["raw_midpoint_lst"], "-56.8"):
        assert str(value) in page


def test_solid_pier(vector_pages):
    """observatory.solid-pier: concealment is in a service chase beside a solid pier."""
    page = vector_pages[14]
    assert "concrete pier" in page
    assert "isolation joint" in page and "no wall bearing" in page
    assert "chase C" in page and "P-3 locked access" in page
    assert "Body of Dr. Alistair Vale recovered from chase C" in page


def test_local_isolation(model, vector_pages):
    """observatory.local-isolation: the private spur fails while regional access remains."""
    page = vector_pages[15].lower()
    for token in ("private spur", str(model["snow_depth_in"]), "telephone",
                  "overhead pair lost beyond gatehouse", "PUBLIC ROAD",
                  "reported open to valley gate", "GENERATOR"):
        assert token.lower() in page


def test_canonical_identity(model, vector_pages):
    """observatory.canonical-identity: repeated identities and figures share one model."""
    text = " ".join(vector_pages).lower()
    for value in (model["observatory"], model["represented_night"],
                  model["founder"], model["trustee"], model["curator"],
                  model["final_plate_id"], model["comparison_plate_id"],
                  model["early_plate_id"], model["transfer_reference"]):
        assert str(value).lower() in text
    assert model["restricted_balance"] == (
        model["restricted_principal"] - model["diverted_amount"])
    for amount in (model["restricted_principal"], model["diverted_amount"],
                   model["restricted_balance"]):
        assert O._fmt_money(amount) in vector_pages[10]


def test_red_herring_resolution(vector_pages):
    """observatory.red-herring-resolution: five bounded alterations remain non-murderous."""
    text = " ".join(vector_pages).lower()
    for token in ("3 Repeat plate 0417 3 Repeat plate 0417", "Archive charge R.B.",
                  "probable minor planet struck through", "JAN 16 struck through and JAN 12 entered",
                  "estimated magnitude 8.1 struck through and 5.8 entered"):
        assert token.lower() in text
    assert "Clock correction used -56.8" in vector_pages[7]


def test_separable_production(model, vector_pages):
    """observatory.separable-production: every object has a native forge boundary."""
    assert len(vector_pages) == 20
    assert all(marker in vector_pages[0] for marker in O.PAGE_MARKERS[1:])
    assert all(marker in page for marker, page in zip(O.PAGE_MARKERS, vector_pages))
    assert len(O.ARTIFACT_SPECS) == 19
    for artifact_id, class_name, page_index in O.ARTIFACT_SPECS:
        assert class_name in registry.CLASSES
        facts = O.public_artifact_facts(model, artifact_id)
        assert facts["artifact_id"] == artifact_id
        assert facts["document_class"] == class_name
        assert facts["page_marker"] == O.PAGE_MARKERS[page_index]
        assert facts["represented_object_count"] == 1
    # Exercise the first, defect-bearing, and last public boundaries. The
    # registry/spec assertions above protect the complete static mapping.
    for artifact_id in ("night_observing_log", "clock_correction",
                        "gatehouse_time_card"):
        _identifier, _class_name, page_index = O._ARTIFACT_BY_ID[artifact_id]
        defect = ({"correction_sign": "reverse"}
                  if artifact_id == "clock_correction" else None)
        data = O.render_artifact(model, artifact_id=artifact_id, metadata=META,
                                 defect=defect, scan_dpi=45)
        doc = pdfium.PdfDocument(io.BytesIO(data))
        assert len(doc) == 1
        text = " ".join((doc[0].get_textpage().get_text_range() or "").split())
        assert text == ""
        assert any(type(obj).__name__ == "PdfImage" for obj in doc[0].get_objects())


def test_scan_class_honesty(pdf):
    """observatory.scan-class-honesty: pages are modern scans with capture metadata."""
    doc = pdfium.PdfDocument(io.BytesIO(pdf))
    assert len(doc) == 20
    for page in doc:
        assert any(type(obj).__name__ == "PdfImage" for obj in page.get_objects())
    metadata = doc.get_metadata_dict()
    assert "2020" in metadata["CreationDate"]
    assert metadata["CreationDate"] == metadata["ModDate"]
    assert b"ReportLab" not in pdf


def test_public_display_facts(model):
    """observatory.public-display-facts: the manifest carries accessible display canon."""
    _data, manifest = registry.emit("observatory_packet_1937", seed=19370117,
                                    canon=dict(O.DEFAULT_CANON))
    facts = manifest["display_facts"]
    assert facts["represented_object_count"] == len(O.PAGE_MARKERS)
    assert facts["page_inventory"] == list(O.PAGE_MARKERS)
    assert facts["restricted_balance"] == (
        facts["restricted_principal"] - facts["diverted_amount"])
    assert set(O.DEFAULT_CANON) <= set(facts)


def test_seeded_offline():
    """observatory.seeded-offline: identical inputs are byte-stable across processes."""
    script = """
import hashlib, json
from mattermill import registry
from mattermill.observatory import DEFAULT_CANON
data, manifest = registry.emit('observatory_packet_1937', seed=19370117, canon=dict(DEFAULT_CANON))
artifact, artifact_manifest = registry.emit('observatory_night_log_1937', seed=19370117, canon=dict(DEFAULT_CANON))
print(json.dumps({'sha': hashlib.sha256(data).hexdigest(), 'manifest': manifest,
                  'artifact_sha': hashlib.sha256(artifact).hexdigest(),
                  'artifact_manifest': artifact_manifest}, sort_keys=True))
"""
    runs = [subprocess.check_output([sys.executable, "-c", script], text=True)
            for _ in range(2)]
    assert runs[0] == runs[1]
    payload = json.loads(runs[0])
    assert payload["manifest"]["sha256"] == "sha256:" + payload["sha"]


def test_explicit_defect(model):
    """observatory.explicit-defect: unsupported mutations fail and the hook is one delta."""
    clean, _ = O._compose_vector(model, None)
    bad, _ = O._compose_vector(model, {"correction_sign": "reverse"})
    clean_pages, bad_pages = _pages(clean), _pages(bad)
    changed = [(a, b) for a, b in zip(clean_pages, bad_pages) if a != b]
    assert len(changed) == 1
    assert changed[0][0].replace("-56.8", "+56.8") == changed[0][1]
    with pytest.raises(ValueError, match="unsupported observatory defect"):
        O._compose_vector(model, {"ambient_noise": True})
    with pytest.raises(ValueError, match="belongs only to clock_correction"):
        O.render_artifact(model, artifact_id="night_observing_log",
                          metadata=META, defect={"correction_sign": "reverse"},
                          scan_dpi=90)


def test_working_hand_legibility():
    """observatory.working-hand-legibility: record text instantiates real glyphs."""
    sample = assets.handwriting_png(
        17, text="05 48 11.8 / S-2 fast", writer="Thomas Rook")
    changed = assets.handwriting_png(
        17, text="05 48 17.8 / S-2 fast", writer="Thomas Rook")
    image = Image.open(io.BytesIO(sample)).convert("RGBA")
    assert image.getchannel("A").getbbox() is not None
    assert image.width / image.height > 4
    assert sample != changed
    # Digits, signs, decimal points and letters all affect the visible mask;
    # the output is not a name-independent signature flourish.
    difference = ImageChops.difference(
        image, Image.open(io.BytesIO(changed)).convert("RGBA").resize(image.size))
    assert difference.getbbox() is not None


def test_working_hand_writer_stability():
    """hand.writer-stability: a named writer retains physical hand parameters."""
    before = assets.handwriting_style("Thomas Rook")
    after = assets.handwriting_style(" Thomas Rook ")
    assert before == after
    for key in ("slant", "tracking", "pressure", "stroke_width",
                "join_probability", "nib_bias", "ink"):
        assert key in before
    assert before["stroke_width"] == 0
    assert 178 <= before["pressure"] <= 211


def test_working_hand_glyph_instances_vary():
    """hand.glyph-instance-variation: repeated glyphs do not reuse one mask."""
    style = assets.handwriting_style("Thomas Rook")
    font = assets._working_font(str(style["font"]), 72)
    rng = random.Random("glyph-instance-capability")
    glyphs = [assets._working_glyph(
        font, "8", rng=rng, style=style, color=tuple(style["ink"])
    ) for _ in range(5)]
    assert len({glyph.size for glyph in glyphs}) > 1
    assert len({glyph.tobytes() for glyph in glyphs}) == len(glyphs)
    dittos = [assets.handwriting_png(
        seed, text='"', writer="Thomas Rook"
    ) for seed in range(5)]
    assert len(set(dittos)) == len(dittos)


def test_working_hand_record_scale_and_accessibility(model):
    """hand.record-scale-legibility: native marks survive print scale and accessibility stays separate."""
    sample = Image.open(io.BytesIO(assets.handwriting_png(
        51, text="05 48 11.8 / S-2 fast", writer="Thomas Rook"
    ))).convert("RGBA")
    scaled = sample.resize(
        (max(1, round(sample.width * 14 / sample.height)), 14),
        Image.Resampling.LANCZOS,
    )
    alpha = scaled.getchannel("A")
    assert alpha.getbbox() is not None
    assert sum(1 for value in alpha.getdata() if value > 40) > scaled.width
    data = O.render_artifact(model, artifact_id="radio_rate_notebook",
                             metadata=META, scan_dpi=55)
    doc = pdfium.PdfDocument(io.BytesIO(data))
    assert not (doc[0].get_textpage().get_text_range() or "").strip()
    assert O.public_artifact_facts(model, "radio_rate_notebook")["reading_copy"]


def test_distinct_working_hands():
    """observatory.distinct-working-hands: writer identity is stable and distinct."""
    writers = ("Samuel Wren", "Ruth Bell", "Thomas Rook")
    styles = [assets.handwriting_style(writer) for writer in writers]
    assert len({style["font"] for style in styles}) == 3
    assert assets.handwriting_style("Samuel Wren") == styles[0]
    samples = [assets.handwriting_png(8, text="Plate V-1937-0417", writer=writer)
               for writer in writers]
    assert len(set(samples)) == 3
    assert samples[0] == assets.handwriting_png(
        8, text="Plate V-1937-0417", writer="Samuel Wren")


def test_scan_evidence_honesty(model):
    """observatory.scan-evidence-honesty: scans contain no invented margin OCR."""
    data = O.render_artifact(model, artifact_id="night_observing_log",
                             metadata=META, scan_dpi=55)
    doc = pdfium.PdfDocument(io.BytesIO(data))
    assert (doc[0].get_textpage().get_text_range() or "").strip() == ""
    assert any(type(obj).__name__ == "PdfImage" for obj in doc[0].get_objects())
    facts = O.public_artifact_facts(model, "night_observing_log")
    assert facts["page_marker"] == "NIGHT OBSERVING LOG"
    assert any("Vale Observatory" in line for line in facts["reading_copy"])
    assert any("05 47 15.0" in line for line in facts["reading_copy"])


def _paper_preview(material: str) -> Image.Image:
    buffer = io.BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=letter, invariant=1)
    O._paper(c, 0.90, material=material, key="capability-test")
    c.save()
    doc = pdfium.PdfDocument(io.BytesIO(buffer.getvalue()))
    return doc[0].render(scale=1).to_pil().convert("L")


def test_material_locality():
    """observatory.material-locality: substrate effects attach to edges and folds."""
    ledger = _paper_preview("ledger")
    carbon = _paper_preview("carbon")
    assert ImageChops.difference(ledger, carbon).getbbox() is not None
    edge = ledger.crop((0, 0, 24, ledger.height))
    center = ledger.crop((280, 100, 304, ledger.height - 100))
    assert abs(ImageStat.Stat(edge).mean[0] - ImageStat.Stat(center).mean[0]) > 0.25


def test_institutional_anchor(vector_pages):
    """observatory.institutional-anchor: every retained object is locatable."""
    for page in vector_pages[1:]:
        assert "Vale Observatory" in page
    assert "Night Book IV leaf 117" in vector_pages[1]
    assert "Time Book II leaf 36" in vector_pages[6]
    assert "Plant Book III leaf 23" in vector_pages[13]


def test_fiction_safe_identifiers(model, vector_pages):
    """observatory.fiction-safe-identifiers: fictional codes identify local series."""
    text = " ".join(vector_pages)
    assert model["object_name"] == "Bellweather Field B-17 (Vale local provisional)"
    assert "Comet 1936" not in text
    assert "WNBX" not in text
    assert "local series V" in text
    assert "local provisional" in text


def test_no_meta_explanation(vector_pages):
    """artifact.no-self-explaining-clues: working records do not narrate their inference."""
    text = " ".join(vector_pages).lower()
    for banned in ("unrelated worked example", "intentionally left",
                   "listed twice", "item 4 absent", "not an observing record",
                   "fast standard requires a minus sign",
                   "required signed correction", "honest (-) plate close",
                   "posted (+) plate close", "sign separation"):
        assert banned not in text
    assert "3 Repeat plate 0417 3 Repeat plate 0417" in " ".join(vector_pages)


def test_corrected_time_chain(model, vector_pages):
    """observatory.corrected-time-chain: contacts, correction, midpoint and HA agree."""
    times = O._time_facts(model)
    assert times == {
        "raw_midpoint_lst": "05 48 56.8",
        "corrected_start_lst": "05 47 15.0",
        "corrected_stop_lst": "05 48 45.0",
        "expected_lst": "05 48 00.0",
        "hour_angle": "+00 10 40.0 W",
    }
    for value in times.values():
        assert value in vector_pages[7] or value == "05 48 56.8"
    assert times["corrected_start_lst"] in vector_pages[1]
    assert times["corrected_stop_lst"] in vector_pages[1]


def test_rate_chain(vector_pages):
    """observatory.rate-chain: daily errors recompute to the stated precision."""
    page = vector_pages[6]
    errors = (56.70, 56.75, 56.80)
    assert [round(errors[i + 1] - errors[i], 2) for i in range(2)] == [0.05, 0.05]
    for token in ("U.S.N.O.", "S-2", "56.70", "56.75", "56.80",
                  "+0.05 S/D", "T.R."):
        assert token in page


def test_chronograph_duration(model, vector_pages):
    """observatory.chronograph-duration: the trace and contacts both span 90 seconds."""
    duration = (O._hms_seconds(model["raw_stop_lst"]) -
                O._hms_seconds(model["raw_start_lst"])) % (24 * 3600)
    page = vector_pages[4]
    assert duration == 90.0
    assert O.CHRONOGRAPH_BEAT_COUNT == 90
    assert "1 SECOND PER BEAT / 10 SECONDS PER LINE" in page
    assert "open 05 48 11.8" in page and "close 05 49 41.8" in page


def test_plate_operational_fields(vector_pages):
    """observatory.plate-operational-fields: every plate object carries its role fields."""
    log, jacket, contact, early, raking = (vector_pages[i] for i in (1, 2, 3, 17, 18))
    for token in ("local", "plate", "Vale Observatory"):
        assert all(token.lower() in page.lower()
                   for page in (log, jacket, contact, early, raking))
    for token in ("RA", "Dec", "corrected LST", "exposure", "observer"):
        assert token.lower() in log.lower()
    for token in ("telescope", "plate", "issued", "returned"):
        assert token.lower() in jacket.lower()


def test_time_service_fields(vector_pages):
    """observatory.time-service-fields: time records name authority, epoch and actor."""
    clock, rate, reduction, chronograph = (vector_pages[i] for i in (5, 6, 7, 4))
    assert all("S-2" in page for page in (clock, rate, reduction, chronograph))
    assert "U.S. Naval Observatory" in clock
    assert "Comparison prepared T. ROOK" in clock
    assert "CORRECTION ENTERED BY F. MERCER" in clock
    assert "Reduced S. Wren" in reduction
    assert "OP. T.R." in chronograph


def test_controlled_record_fields(vector_pages):
    """observatory.controlled-record-fields: operational records expose control state."""
    text = " ".join(vector_pages)
    for token in ("Plant Book III leaf 22", "Plant Book III leaf 23",
                  "Plant Book III leaf 24", "status posted",
                  "retained desk carbon / draft 2", "not issued",
                  "Dome Order O-37-016 / issued"):
        assert token.lower() in text.lower()


def test_plan_contract(vector_pages):
    """observatory.plan-contract: the plan has executable drawing furniture."""
    page = vector_pages[14].lower()
    for token in ("drawing d-4", "revision 1", "sheet 4 of 6", "scale",
                  "north arrow", "30 foot inside diameter", "isolation joint",
                  "weight travel", "locked access", "service clearance",
                  "d-1", "8 risers", "switchboard", "drawn", "checked"):
        assert token in page


def test_raking_light_contract(vector_pages):
    """observatory.raking-light-contract: relief and alteration order are explicit."""
    page = vector_pages[18].lower()
    for token in ("raking light from left", "22.5 degrees",
                  "probable minor planet", "s.w. candidate", "copy rl-0416-1"):
        assert token in page
    description = " ".join(
        O.public_artifact_facts(
            O.sample_packet(random.Random(19370117)), "plate_raking_copy"
        )["visual_description"]
    ).lower()
    for token in ("indentation", "surface abrasion", "does not establish when"):
        assert token in description
    assert "written later" not in description
    image = Image.open(io.BytesIO(O._raking_jacket_png(
        1900, writer="Samuel Wren"))).convert("L")
    left = ImageStat.Stat(image.crop((0, 0, image.width // 4, image.height))).mean[0]
    right = ImageStat.Stat(image.crop((3 * image.width // 4, 0,
                                       image.width, image.height))).mean[0]
    assert abs(left - right) > 3.0


def test_accessibility_evidence_parity(model):
    """observatory.accessibility-evidence-parity: reading copies retain decisive text."""
    facts = O.public_display_facts(model)
    pages = [" ".join(page) for page in facts["reading_copy_pages"]]
    expected = {
        2: ("DATE-NIGHT", "do not clean reverse notes"),
        8: ("JAN 15 | rate check", "JAN 16 | dome drive", "JAN 16 | chase C"),
        9: ("Jan. 16, 10 P.M. EST", "R.A. 05h 37m", "Decl. +32 10"),
        10: ("RESTRICTED INSTRUMENT ENDOWMENT", "Second trustee ....... [blank]"),
        11: ("published the result under my name", "independent audit"),
        15: ("8:40 P.M.", "9:31 P.M.", "10:03:14", "10:05 P.M.", "ALL NIGHT"),
        16: ("Night January 16–17",),
    }
    for page_index, tokens in expected.items():
        assert all(token in pages[page_index] for token in tokens)


def test_visible_description_separation(model):
    """observatory.visible-description-separation: transcription and visual evidence differ."""
    facts = O.public_display_facts(model)
    pages = [" ".join(page) for page in facts["reading_copy_pages"]]
    descriptions = [" ".join(page) for page in facts["visual_description_pages"]]
    assert "comparison stars" not in pages[3].lower()
    assert "not lettered" in descriptions[3].lower()
    assert "operator Thomas Rook" not in pages[4]
    assert "OP. T.R." in pages[4]
    assert "opens panel to" not in pages[13].lower()
    assert "indentation" not in pages[18].lower()
    assert "indentation" in descriptions[18].lower()


def test_accessibility_typed_parity(model):
    """observatory.accessibility-typed-parity: all artifacts separate exact text, geometry, and inference."""
    for artifact_id, _class_name, page_index in O.ARTIFACT_SPECS:
        facts = O.public_artifact_facts(
            model,
            artifact_id,
            defect={"correction_sign": "reverse"}
            if artifact_id == "clock_correction" else None,
        )
        contract = facts["accessibility"]
        assert facts["accessibility_schema_version"] == "1.0"
        assert contract["editorial_identification"]["page_marker"] == O.PAGE_MARKERS[page_index]
        assert contract["visible_content"]
        assert contract["interpretation"] == []
        assert facts["reading_copy"] == O._flatten_visible_content(
            contract["visible_content"]
        )

    jacket = O.public_artifact_facts(model, "plate_jacket")["accessibility"]
    assert jacket["editorial_identification"]["page_marker"].startswith("PLATE JACKET")
    assert not any(
        "paper envelope recto" in line
        for line in O._flatten_visible_content(jacket["visible_content"])
    )

    plate = O.public_artifact_facts(model, "plate_contact")["accessibility"]
    plate_text = " ".join(O._flatten_visible_content(plate["visible_content"]))
    plate_visual = " ".join(plate["visual_description"]).lower()
    assert "CONTACT REPRODUCTION" not in plate_text
    assert 'SCALE 60"/MM' in plate_text
    assert "diffuse source" in plate_visual
    assert "vertical streaks" in plate_visual

    chronograph = O.public_artifact_facts(model, "chronograph_strip")["accessibility"]
    chrono_text = " ".join(O._flatten_visible_content(chronograph["visible_content"]))
    chrono_visual = " ".join(chronograph["visual_description"]).lower()
    assert "OPEN" in chrono_text and "CLOSE" in chrono_text
    assert "Vale Observatory" not in chrono_text
    assert "continuous" in chrono_visual and "nine successive" in chrono_visual

    correction = O.public_artifact_facts(
        model, "clock_correction", defect={"correction_sign": "reverse"}
    )["accessibility"]
    correction_text = " ".join(O._flatten_visible_content(correction["visible_content"]))
    assert "Comparison prepared: T. ROOK" in correction_text
    assert "CORRECTION ENTERED BY F. MERCER ... +56.8 seconds" in correction_text
    assert "cursive ink signature" in " ".join(correction["visual_description"])

    radio = O.public_artifact_facts(model, "radio_rate_notebook")["accessibility"]
    radio_table = next(block for block in radio["visible_content"] if block["kind"] == "table")
    assert radio_table["columns"] == ["DATE / EST", "AUTHORITY", "CLOCK", "FAST", "RATE", "OP."]
    assert radio_table["rows"][2][3] == "56.80 S"

    reduction = " ".join(O.public_artifact_facts(
        model, "reduction_worksheet"
    )["reading_copy"])
    assert "Clock correction used: -56.8 seconds / T.R." in reduction
    assert "CIVIL TIE" not in reduction

    key_register = O.public_artifact_facts(model, "service_key_register")["accessibility"]
    key_table = next(block for block in key_register["visible_content"] if block["kind"] == "table")
    assert key_table["columns"] == ["DATE", "HOLDER", "OUT", "IN", "PURPOSE"]

    appointment = " ".join(O.public_artifact_facts(
        model, "vault_appointment"
    )["reading_copy"])
    assert "FELIX -" in appointment
    assert "PLATE VAULT. TEN O'CLOCK." in appointment

    plan = " ".join(O.public_artifact_facts(model, "dome_plan")["reading_copy"])
    assert "PROJECT: DRIVE & TIME-SERVICE ALTERATIONS" in plan
    assert "0    2    4    6    8 FT" in plan
    assert "Body of Dr. Alistair Vale recovered from chase C. T.R." in plan

    raking = O.public_artifact_facts(model, "plate_raking_copy")["accessibility"]
    raking_text = " ".join(O._flatten_visible_content(raking["visible_content"]))
    raking_visual = " ".join(raking["visual_description"]).lower()
    assert "PLATE JACKET" not in raking_text
    assert "written later" not in raking_visual


def test_correction_entry_authorship(vector_pages):
    """observatory.correction-entry-authorship: measurement and entry have distinct actors."""
    page = vector_pages[5]
    assert "Comparison prepared T. ROOK" in page
    assert "Measured result S-2 FAST 56.8 SEC." in page
    assert "CORRECTION ENTERED BY F. MERCER" in page
    assert "Checked" not in page


def test_sidereal_civil_conversion(model, vector_pages):
    """observatory.sidereal-civil-conversion: a sidereal delta converts before changing civil time."""
    facts = O._civil_facts(model)
    assert facts == {
        "honest_plate_close_civil_time": "10:02:14.0 P.M. E.S.T.",
        "false_plate_close_civil_time": "10:04:07.3 P.M. E.S.T.",
        "library_entry_civil_time": "10:04 P.M. E.S.T.",
        "sidereal_shift_seconds": 113.6,
        "civil_shift_seconds": 113.3,
    }
    civil_difference = round(
        O._civil_seconds(facts["false_plate_close_civil_time"])
        - O._civil_seconds(facts["honest_plate_close_civil_time"]), 1
    )
    assert civil_difference == facts["civil_shift_seconds"]
    assert civil_difference != model["correction_shift_seconds"]
    assert round(
        model["correction_shift_seconds"]
        / O.SIDEREAL_SECONDS_PER_MEAN_SOLAR_SECOND, 1
    ) == facts["civil_shift_seconds"]
    for value in (facts["honest_plate_close_civil_time"],
                  facts["false_plate_close_civil_time"],
                  facts["library_entry_civil_time"]):
        assert str(value) in vector_pages[19]
    assert "sign separation" not in vector_pages[7].lower()


def test_library_entry_precision(model):
    """observatory.library-entry-precision: the public register records a containing minute."""
    facts = O._civil_facts(model)
    assert model["library_entry_time"] == "10:04 P.M. E.S.T."
    assert facts["library_entry_civil_time"] == "10:04 P.M. E.S.T."
    assert ":07" not in facts["library_entry_civil_time"]
    assert int(O._civil_seconds(facts["false_plate_close_civil_time"]) // 60) == int(
        O._civil_seconds(facts["library_entry_civil_time"]) // 60
    )


def test_gatehouse_source_contract(model):
    """observatory.gatehouse-source-contract: L-2 is source-bounded and names its time-service fields."""
    facts = O.public_artifact_facts(model, "gatehouse_time_card")
    assert facts["source_claim"] == O.GATEHOUSE_FORM_CLAIM
    assert "not an exact historic form" in facts["source_claim"]
    text = " ".join(facts["reading_copy"])
    for token in (
        "GATEHOUSE CHRONOMETER CARD L-2",
        "U.S. NAVAL OBSERVATORY RADIO TIME",
        "6:00 P.M. E.S.T.",
        "M-1 E.S.T.",
        "S-2 CORRECTED L.S.T.",
        "OP.",
        "REFERENCE",
        "T.R.",
    ):
        assert token in text


def test_gatehouse_coherence(model, vector_pages):
    """observatory.gatehouse-coherence: L-2 and R-17 derive from one canonical time chain."""
    card = vector_pages[19]
    reduction = vector_pages[7]
    tf = O._time_facts(model)
    cf = O._civil_facts(model)
    for value in (tf["corrected_stop_lst"], cf["honest_plate_close_civil_time"],
                  cf["false_plate_close_civil_time"], cf["library_entry_civil_time"]):
        assert value in card
    for value in (tf["corrected_stop_lst"], tf["expected_lst"],
                  str(model["true_correction_seconds"])):
        assert value in reduction
    assert "TIME BOOK II S-2 FAST 56.8 SEC." in card


def test_gatehouse_separable_production(model):
    """observatory.gatehouse-separable-production: L-2 emits as one deterministic scan."""
    first, first_manifest = registry.emit(
        "observatory_gatehouse_time_card_1937",
        seed=19370117,
        canon=dict(O.DEFAULT_CANON),
    )
    second, second_manifest = registry.emit(
        "observatory_gatehouse_time_card_1937",
        seed=19370117,
        canon=dict(O.DEFAULT_CANON),
    )
    assert first == second
    assert first_manifest == second_manifest
    doc = pdfium.PdfDocument(io.BytesIO(first))
    assert len(doc) == 1
    assert any(type(obj).__name__ == "PdfImage" for obj in doc[0].get_objects())
    assert (doc[0].get_textpage().get_text_range() or "").strip() == ""
    display = first_manifest["display_facts"]
    assert display["artifact_id"] == "gatehouse_time_card"
    assert display["accessibility"]["interpretation"] == []


def test_accessibility_literal_transcription(model):
    """observatory.accessibility-literal-transcription: visible tokens and table roles remain literal."""
    expected = {
        "radio_rate_notebook": ("DATE / EST", "AUTHORITY", "CLOCK", "FAST", "RATE", "OP."),
        "service_key_register": ("DATE", "HOLDER", "OUT", "IN", "PURPOSE"),
        "storm_power_log": ("TIME E.S.T.", "SYSTEM", "OBSERVATION"),
        "reduction_worksheet": ("Clock correction used: -56.8 seconds / T.R.",),
        "gatehouse_time_card": ("TIME-SERVICE CROSS-CHECK", "LIBRARY REGISTER (MINUTE ENTRY):"),
    }
    for artifact_id, tokens in expected.items():
        text = " ".join(O.public_artifact_facts(model, artifact_id)["reading_copy"])
        assert all(token in text for token in tokens)


def test_accessibility_visual_evidence(model):
    """observatory.accessibility-visual-evidence: decisive non-text evidence is objective and complete."""
    expected = {
        "plate_contact": ("diffuse source", "vertical streaks"),
        "chronograph_strip": ("continuous", "OPEN", "CLOSE"),
        "clock_correction": ("signature", "does not authenticate"),
        "endowment_advice": ("signature", "blank"),
        "dome_plan": ("route", "scale bar", "P-3"),
        "plate_raking_copy": ("indentation", "abrasion", "does not establish when"),
        "gatehouse_time_card": ("handwritten", "does not authenticate"),
    }
    for artifact_id, tokens in expected.items():
        description = " ".join(
            O.public_artifact_facts(model, artifact_id)["visual_description"]
        )
        assert all(token.lower() in description.lower() for token in tokens)


def test_non_graphic_death_recovery(vector_pages):
    """observatory.non-graphic-death-recovery: evidence names body, panel, and chase."""
    page = vector_pages[14]
    assert "SERVICE RECOVERY NOTE / PLANT BOOK III" in page
    assert "17 Jan 10:42 — panel P-3 opened" in page
    assert "Body of Dr. Alistair Vale recovered from chase C. T.R." in page
    assert all(token not in page.lower() for token in ("blood", "wound", "trauma"))
