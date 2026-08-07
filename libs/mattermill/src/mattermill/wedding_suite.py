"""Contemporary wedding invitation suites as coordinated print proofs.

The caller supplies the event world.  Venue, date, capacity, address and every
couple-specific field have one owner in the model, so the invitation, details
card and RSVP card cannot quietly drift apart.  Unsupplied send-critical facts
remain conspicuous placeholders; the renderer never invents a room block,
dress code, response URL or ceremony time.
"""

from __future__ import annotations

import datetime as dt
import io
import math
import random

from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from . import legalpdf

INVITATION_SIZE = (5 * inch, 7 * inch)
ENCLOSURE_SIZE = (5 * inch, 3.5 * inch)

DEFAULT_CANON = {
    "wedding_date": "2026-10-03",
    "venue_name": "The Simsbury Inn",
    "venue_address": "397 Hopmeadow Street",
    "venue_city": "Simsbury",
    "venue_state": "Connecticut",
    "venue_postal": "06070",
    "venue_capacity": 200,
}

DEFAULT_PINS = {
    "couple_one": "[FIRST FULL NAME]",
    "couple_two": "[SECOND FULL NAME]",
    "ceremony_time": "[INSERT CEREMONY TIME]",
    "reception_details": "[ADD RECEPTION DETAILS]",
    "rsvp_by": "[INSERT RSVP DEADLINE]",
    "rsvp_method": "[INSERT RSVP METHOD]",
    "attire": "[INSERT DRESS CODE]",
    "accommodations": "[ADD LODGING OR TRAVEL DETAILS]",
    "wedding_website": "[ADD WEDDING WEBSITE]",
    "invited_count": 200,
    "party_allocation": 2,
}

_REQUIRED_CANON = frozenset(DEFAULT_CANON)
_ALLOWED_PINS = frozenset(DEFAULT_PINS)
_MONTHS = (
    "", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
    "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
)
_ORDINALS = {
    1: "FIRST", 2: "SECOND", 3: "THIRD", 4: "FOURTH", 5: "FIFTH",
    6: "SIXTH", 7: "SEVENTH", 8: "EIGHTH", 9: "NINTH", 10: "TENTH",
    11: "ELEVENTH", 12: "TWELFTH", 13: "THIRTEENTH", 14: "FOURTEENTH",
    15: "FIFTEENTH", 16: "SIXTEENTH", 17: "SEVENTEENTH",
    18: "EIGHTEENTH", 19: "NINETEENTH", 20: "TWENTIETH",
    21: "TWENTY-FIRST", 22: "TWENTY-SECOND", 23: "TWENTY-THIRD",
    24: "TWENTY-FOURTH", 25: "TWENTY-FIFTH", 26: "TWENTY-SIXTH",
    27: "TWENTY-SEVENTH", 28: "TWENTY-EIGHTH", 29: "TWENTY-NINTH",
    30: "THIRTIETH", 31: "THIRTY-FIRST",
}

INK = HexColor("#24352A")
COPPER = HexColor("#985C42")
SAGE = HexColor("#6D7C65")
OCHRE = HexColor("#B48745")
IVORY = HexColor("#F5F0E6")
PALE = HexColor("#DED6C7")


def _year_words(year: int) -> str:
    if year == 2026:
        return "TWO THOUSAND TWENTY-SIX"
    return str(year)


def _written_date(value: dt.date) -> str:
    return (f"{value.strftime('%A').upper()}  ·  {_MONTHS[value.month]} "
            f"{_ORDINALS[value.day]}  ·  {_year_words(value.year)}")


def sample_suite(rng: random.Random, *, pins: dict | None = None,
                 canon: dict | None = None) -> dict:
    """Sample only visual texture; event facts remain caller-owned canon."""
    world = dict(DEFAULT_CANON if canon is None else canon)
    missing = _REQUIRED_CANON - set(world)
    if missing:
        raise ValueError(f"wedding suite canon missing {sorted(missing)}")
    unknown_canon = set(world) - _REQUIRED_CANON
    if unknown_canon:
        raise ValueError(f"unknown wedding suite canon keys {sorted(unknown_canon)}")

    values = dict(DEFAULT_PINS)
    if pins:
        unknown = set(pins) - _ALLOWED_PINS
        if unknown:
            raise ValueError(f"unknown wedding suite pins {sorted(unknown)}")
        values.update(pins)

    date = dt.date.fromisoformat(str(world["wedding_date"]))
    capacity = int(world["venue_capacity"])
    invited = int(values["invited_count"])
    allocation = int(values["party_allocation"])
    if capacity < 1:
        raise ValueError("venue_capacity must be positive")
    if not 1 <= invited <= capacity:
        raise ValueError(f"invited_count must be between 1 and {capacity}")
    if not 1 <= allocation <= invited:
        raise ValueError("party_allocation must be within the invited count")

    palette = rng.choice(("copper", "ochre", "mixed"))
    leaves = []
    for _ in range(18):
        leaves.append({
            "x": rng.uniform(0.04, 0.96),
            "y": rng.uniform(0.04, 0.96),
            "angle": rng.uniform(-48, 48),
            "scale": rng.uniform(0.72, 1.22),
            "tone": rng.randrange(3),
        })

    return {
        **world,
        **values,
        "wedding_date": date.isoformat(),
        "weekday": date.strftime("%A"),
        "written_date": _written_date(date),
        "palette": palette,
        "leaves": leaves,
        "party_allocation_display": (
            str(allocation) if pins and "party_allocation" in pins else "____"
        ),
    }


def export_created(model: dict) -> str:
    """A fixed proof-export moment derived from the represented event date."""
    date = dt.date.fromisoformat(model["wedding_date"]) - dt.timedelta(days=90)
    return f"{date.isoformat()} 10:30:00"


def _background(c: canvas.Canvas, size: tuple[float, float]) -> None:
    width, height = size
    c.setFillColor(IVORY)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setStrokeColor(PALE)
    c.setLineWidth(0.65)
    c.rect(0.22 * inch, 0.22 * inch,
           width - 0.44 * inch, height - 0.44 * inch, fill=0, stroke=1)


def _leaf(c: canvas.Canvas, x: float, y: float, angle: float,
          scale: float, color) -> None:
    c.saveState()
    c.translate(x, y)
    c.rotate(angle)
    c.scale(scale, scale)
    c.setFillColor(color)
    c.setStrokeColor(color)
    p = c.beginPath()
    p.moveTo(0, -1)
    p.curveTo(7, 2, 9, 11, 0, 17)
    p.curveTo(-9, 11, -7, 2, 0, -1)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.setStrokeColor(IVORY)
    c.setLineWidth(0.35)
    c.line(0, 0, 0, 13)
    c.restoreState()


def _foliage(c: canvas.Canvas, model: dict,
             size: tuple[float, float], *, sparse: bool = False) -> None:
    width, height = size
    tones = ((COPPER, SAGE, OCHRE) if model["palette"] == "mixed" else
             ((COPPER, SAGE, COPPER) if model["palette"] == "copper" else
              (OCHRE, SAGE, OCHRE)))
    selected = model["leaves"][::2] if sparse else model["leaves"]
    for index, leaf in enumerate(selected):
        # Keep foliage in the border band so the writing field remains calm.
        side = index % 4
        if side == 0:
            x, y = 0.19 * inch, leaf["y"] * height
        elif side == 1:
            x, y = width - 0.19 * inch, leaf["y"] * height
        elif side == 2:
            x, y = leaf["x"] * width, 0.19 * inch
        else:
            x, y = leaf["x"] * width, height - 0.19 * inch
        _leaf(c, x, y, leaf["angle"], leaf["scale"], tones[leaf["tone"]])


def _center(c: canvas.Canvas, text: str, y: float, font: str,
            size: float, color=INK, *, tracking: float | None = None) -> None:
    c.setFillColor(color)
    if tracking is None:
        c.setFont(font, size)
        c.drawCentredString(c._pagesize[0] / 2, y, text)
        return
    obj = c.beginText()
    obj.setTextOrigin(c._pagesize[0] / 2, y)
    obj.setFont(font, size)
    obj.setFillColor(color)
    obj.setCharSpace(tracking)
    width = c.stringWidth(text, font, size) + max(0, len(text) - 1) * tracking
    obj.moveCursor(-width / 2, 0)
    obj.textOut(text)
    c.drawText(obj)


def _fit_center(c: canvas.Canvas, text: str, y: float, font: str,
                preferred: float, max_width: float, color=INK,
                minimum: float = 8) -> None:
    size = preferred
    while size > minimum and c.stringWidth(text, font, size) > max_width:
        size -= 0.5
    _center(c, text, y, font, size, color)


def _fit_column(c: canvas.Canvas, text: str, center_x: float, y: float,
                font: str, preferred: float, max_width: float, color=INK,
                minimum: float = 8) -> None:
    size = preferred
    while size > minimum and c.stringWidth(text, font, size) > max_width:
        size -= 0.5
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawCentredString(center_x, y, text)


def _checkbox(c: canvas.Canvas, x: float, y: float, label: str) -> None:
    c.setStrokeColor(INK)
    c.setLineWidth(0.8)
    c.rect(x, y - 1, 7, 7, fill=0, stroke=1)
    c.setFillColor(INK)
    c.setFont("Helvetica", 8.5)
    c.drawString(x + 13, y - 1, label)


def _draw_invitation(c: canvas.Canvas, model: dict, defect: dict) -> None:
    width, height = INVITATION_SIZE
    c.setPageSize(INVITATION_SIZE)
    _background(c, INVITATION_SIZE)
    _foliage(c, model, INVITATION_SIZE)

    _center(c, "TOGETHER WITH THEIR FAMILIES", height - 0.86 * inch,
            "Helvetica", 8, SAGE, tracking=1.25)
    _center(c, "invite you to celebrate the marriage of", height - 1.16 * inch,
            "Times-Italic", 10.5, INK)
    _fit_center(c, model["couple_one"], height - 2.06 * inch,
                "Times-Roman", 26, width - 1.0 * inch, COPPER, minimum=12)
    _center(c, "&", height - 2.48 * inch, "Times-Italic", 15, SAGE)
    _fit_center(c, model["couple_two"], height - 2.94 * inch,
                "Times-Roman", 26, width - 1.0 * inch, COPPER, minimum=12)

    written = model["written_date"]
    if "weekday" in defect:
        written = written.replace(model["weekday"].upper(), str(defect["weekday"]).upper(), 1)
    date_parts = [part.strip() for part in written.split("·")]
    _fit_center(c, f"{date_parts[0]}  ·  {date_parts[1]}",
                height - 3.58 * inch, "Helvetica", 8.5,
                width - 0.80 * inch, INK, minimum=8)
    _fit_center(c, date_parts[2], height - 3.84 * inch, "Helvetica", 8.5,
                width - 0.80 * inch, INK, minimum=8)
    _center(c, model["ceremony_time"], height - 4.18 * inch,
            "Helvetica", 8.5, INK, tracking=0.55)

    c.setStrokeColor(COPPER)
    c.setLineWidth(0.8)
    c.line(1.58 * inch, height - 4.50 * inch,
           width - 1.58 * inch, height - 4.50 * inch)
    _fit_center(c, model["venue_name"], height - 4.90 * inch,
                "Times-Roman", 17, width - 0.9 * inch, INK)
    _center(c, f"{model['venue_city']}, {model['venue_state']}",
            height - 5.23 * inch, "Helvetica", 8.5, SAGE, tracking=0.6)
    _center(c, model["reception_details"], height - 5.76 * inch,
            "Helvetica", 8, INK, tracking=1.0)


def _draw_details(c: canvas.Canvas, model: dict, defect: dict) -> None:
    width, height = ENCLOSURE_SIZE
    c.setPageSize(ENCLOSURE_SIZE)
    _background(c, ENCLOSURE_SIZE)
    _foliage(c, model, ENCLOSURE_SIZE, sparse=True)

    _center(c, "THE DETAILS", height - 0.57 * inch,
            "Times-Roman", 17, INK)
    venue = str(defect.get("details_venue", model["venue_name"]))
    _fit_center(c, venue, height - 0.90 * inch, "Helvetica", 8.5,
                width - 0.85 * inch, COPPER)
    address = (f"{model['venue_address']}  ·  {model['venue_city']}, "
               f"{model['venue_state']} {model['venue_postal']}")
    _fit_center(c, address, height - 1.15 * inch, "Helvetica", 8,
                width - 0.75 * inch, SAGE)

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(0.55 * inch, height - 1.65 * inch, "ATTIRE")
    c.drawString(2.67 * inch, height - 1.65 * inch, "LODGING & TRAVEL")
    c.setFont("Helvetica", 8)
    c.drawString(0.55 * inch, height - 1.91 * inch, model["attire"])
    _fit_column(c, model["accommodations"], 3.63 * inch,
                height - 1.91 * inch, "Helvetica", 8,
                1.86 * inch, INK, minimum=8)

    c.setStrokeColor(PALE)
    c.line(0.55 * inch, height - 2.20 * inch,
           width - 0.55 * inch, height - 2.20 * inch)
    _center(c, "WEDDING WEBSITE", height - 2.55 * inch,
            "Helvetica-Bold", 8, INK, tracking=0.8)
    _fit_center(c, model["wedding_website"], height - 2.84 * inch,
                "Helvetica", 8.5, width - 1.1 * inch, COPPER)
    _center(c, "For updates and directions, please visit the wedding website.",
            0.39 * inch, "Helvetica-Oblique", 8, SAGE)


def _draw_rsvp(c: canvas.Canvas, model: dict, defect: dict) -> None:
    width, height = ENCLOSURE_SIZE
    c.setPageSize(ENCLOSURE_SIZE)
    _background(c, ENCLOSURE_SIZE)
    _foliage(c, model, ENCLOSURE_SIZE, sparse=True)

    _center(c, "KINDLY REPLY", height - 0.56 * inch,
            "Times-Roman", 17, INK)
    _fit_center(c, f"by {model['rsvp_by']}", height - 0.88 * inch,
                "Helvetica", 8.5, width - 1.1 * inch, COPPER)
    c.setFillColor(INK)
    c.setFont("Times-Italic", 10)
    c.drawString(0.57 * inch, height - 1.30 * inch,
                 "M" + "_" * 53)
    _checkbox(c, 0.63 * inch, height - 1.73 * inch, "JOYFULLY ACCEPTS")
    _checkbox(c, 2.73 * inch, height - 1.73 * inch, "REGRETFULLY DECLINES")

    allocation = defect.get("rsvp_allocation", model["party_allocation_display"])
    c.setFillColor(INK)
    c.setFont("Helvetica", 8.5)
    _center(c, f"NUMBER ATTENDING  ______  OF  {allocation}",
            height - 2.18 * inch, "Helvetica-Bold", 8.5, INK)
    c.setStrokeColor(PALE)
    c.line(0.63 * inch, height - 2.42 * inch,
           width - 0.63 * inch, height - 2.42 * inch)
    _fit_center(c, f"RESPOND VIA  {model['rsvp_method']}", height - 2.71 * inch,
                "Helvetica-Bold", 8, width - 1.0 * inch, INK)
    _center(c, "Your household allocation helps us plan every place with care.",
            0.38 * inch, "Helvetica-Oblique", 8, SAGE)


def render_suite(model: dict, *, metadata: dict,
                 defect: dict | None = None) -> bytes:
    """Render the invitation, details enclosure, and RSVP enclosure."""
    defect = dict(defect or {})
    allowed = {"weekday", "details_venue", "rsvp_allocation"}
    unknown = set(defect) - allowed
    if unknown:
        raise ValueError(f"unknown wedding suite defects {sorted(unknown)}")

    # ReportLab caches font objects process-wide.  Earlier document renders can
    # otherwise change later object numbering, so a clean standard-font cache
    # is part of this emitter's deterministic boundary.
    pdfmetrics._reset()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=INVITATION_SIZE, invariant=1,
                      pageCompression=0)
    c.setProducer(metadata["producer"])
    c.setCreator(metadata["creator"])
    c.setTitle(metadata.get("title", "Wedding Invitation Suite"))
    _draw_invitation(c, model, defect)
    c.showPage()
    _draw_details(c, model, defect)
    c.showPage()
    _draw_rsvp(c, model, defect)
    c.save()

    out = legalpdf._fix_dates(buf.getvalue(), created=metadata.get("created"),
                              modified=metadata.get("modified"))
    return legalpdf._fix_id(out)
