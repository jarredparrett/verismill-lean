"""Contemporary museum-investigation records, coherent and seeded.

These seven classes are the producing-system layer for a facilitated mystery.
They deliberately do not share one visible house template: a curator's memo,
laboratory report, access-control export, property ledger, mobile-device report,
and equipment card should look as though they came from different systems.

Load-bearing source contracts (acquired at authoring time, never at render time):

* NPS Museum Handbook II, Museum Records, for accession-folder research notes,
  conservation records, record custody, and archival citation anatomy.
* NPS Museum Handbook I.14 and its Key Issuance Form for controlled-space
  access fields and custody expectations.
* NIST OSAC 2022-S-0019, Standard Guide for Forensic Examination of Fibers,
  for case assessment, evidence handling, observations, evaluation,
  limitations, documentation, and independent verification.
* Kantech EntraPass Quick/Historical Report manuals for event sequence, date
  and time, event message, card number, door/controller descriptions, filters,
  and PDF export behavior.
* New Jersey DCA Lease Information Bulletin and Truth in Renting for the
  landlord/tenant, premises, term, rent, deposit, and record-copy field world.
  This emitter is an account-system record, not a lease and not legal prose.
* Apple iPhone User Guide, "Check your voicemail," for sender/call identity,
  duration, playback/transcription, sharing, and the warning that transcription
  is a derived convenience rather than the audio itself.
* EPA CMOM and pump-station O&M guidance plus OSHA 29 CFR 1910.147 guidance for
  equipment identity, emergency procedure availability, alarm/inspection
  records, energy isolation, stored-energy warning, and verification.

The named organizations, systems, people, properties, and cases rendered by
the defaults are invented.  The structural contracts above are not.
"""

from __future__ import annotations

from copy import deepcopy
from functools import partial
import io
import random
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from . import legalpdf


KINDS = (
    "museum_research_note",
    "curatorial_chronology",
    "conservation_examination",
    "access_event_report",
    "tenant_account_ledger",
    "voicemail_evidence_report",
    "pump_emergency_card",
)

DEFAULTS: dict[str, dict[str, Any]] = {
    "museum_research_note": {
        "organization": "Hudson Palisade History Center",
        "department": "Research & Interpretation",
        "organization_address": "14 River Street · Hoboken, New Jersey 07030",
        "record_id": "RIM-26-041",
        "repository_code": "HPHC-NJ",
        "records_series": "ER-2026-02 / inquiry 06",
        "project": "Temporary exhibition research — The Rogers Case",
        "loan_number": "L2026.002",
        "object_id": "TEMP-L2026.002.001",
        "receipt_id": "TC-2026-014",
        "lender": "Elias Crane",
        "record_status": "UNACCESSIONED TEMPORARY CUSTODY",
        "current_location": "Collections workroom CW-2 / cabinet 4 / folder 14",
        "handling_class": "Research handling only; polyester support required",
        "rights_status": "Private lender; internal research reproduction only",
        "object_description": "Private-lender packet: an 1841 newspaper clipping with a later handwritten note attached at the upper edge.",
        "object_custody": "Received 2026-02-10 from Elias Crane under temporary-custody receipt TC-2026-014; held in collections workroom cabinet CW-2 pending return.",
        "represented_date": "2026-02-11",
        "exported_at": "2026-02-11 16:42:00",
        "prepared_by": "Ada Bell, Ph.D., contract historian",
        "reviewed_by": "Miriam Quill, curator",
        "subject": "Poe, Mary Rogers, and the claimed Sybil's Cave visit",
        "question": "Does the surviving publication record support a claim that Edgar Allan Poe investigated inside Sybil's Cave?",
        "finding": "Not supported by the sources reviewed. They document Poe's use of press accounts and his fictional relocation of the Rogers case to Paris, but none supplies affirmative evidence of a visit inside Sybil's Cave. This record does not determine the authorship or date of the questioned note on examination item Q-3.",
        "sources": [
            ["S-01", "Digital scholarly transcription of Poe to George Roberts, 4 June 1842, LTR-136", "Contemporary letter text; real-case basis and press-analysis design"],
            ["S-02", "Ladies' Companion 17 (Nov. 1842): 15-20; 17 (Dec. 1842): 93-99; 18 (Feb. 1843): 162-167", "Digitized first publication; three serialized parts"],
            ["S-03", "Poe, 'The Mystery of Marie Roget,' Tales (Wiley & Putnam, 1845); EAPoe text 1845-01", "Digital scholarly transcription of revised text"],
            ["S-04", "E. A. Poe Society work record PT040, rev. 29 Apr. 2023", "Editorial publication history; manuscript-status note"],
        ],
        "source_locators": [
            "S-01 — https://www.eapoe.org/works/letters/p4206040.htm — LTR-136 — ER-WEB-26-031; captured 2026-02-11 08:54 ET",
            "S-02a — https://www.eapoe.org/works/tales/rogeta1.htm — Part I — ER-WEB-26-032; captured 2026-02-11 09:51 ET",
            "S-02b — https://www.eapoe.org/works/tales/rogeta2.htm — Part II — ER-WEB-26-033; captured 2026-02-11 09:53 ET",
            "S-02c — https://www.eapoe.org/works/tales/rogeta3.htm — Part III — ER-WEB-26-034; captured 2026-02-11 09:55 ET",
            "S-03 — https://www.eapoe.org/works/tales/rogetb.htm — 1845 text — ER-WEB-26-035; captured 2026-02-11 11:14 ET",
            "S-04 — https://www.eapoe.org/works/info/pt040.htm — work record — ER-WEB-26-036; captured 2026-02-11 13:28 ET",
        ],
        "research_log": [
            ["09:12 ET", "S-01 / ER-WEB-26-031", "Ada Bell; checked letter heading and the paragraphs beginning ‘I have handled my theme’ and ‘I examine.’"],
            ["10:05 ET", "S-02a-c / ER-WEB-26-032–034", "Ada Bell; searched Hoboken | cave | visit | New York; zero hits for Hoboken or cave; New York occurs in the tale's case framing."],
            ["11:28 ET", "S-03 / ER-WEB-26-035", "Ada Bell; repeated the same query set in the 1845 text; read every newspaper and press hit in context."],
            ["13:40 ET", "S-04 / ER-WEB-26-036", "Ada Bell; checked publication-state list and manuscript-status note; referred Q-3 to ATCL-26-00387."],
        ],
        "review_authority": "Curator delegation 2025-11 / exhibition research files",
        "reviewed_at": "11 February 2026",
        "retention": "Retain with ER-2026-02 through 2033-06; return lender object under L2026.002",
        "limitations": "The four named records were consulted as scholarly digital transcriptions or reproductions, not originals. No draft manuscript or scratch notes for the tale are known to survive. Lack of affirmative visit evidence does not prove Poe never entered Hoboken. Note authorship and date are outside scope.",
    },
    "curatorial_chronology": {
        "organization": "Hudson Palisade History Center",
        "department": "Collections & Exhibitions",
        "record_id": "CHR-26-017",
        "represented_date": "2026-02-11",
        "exported_at": "2026-02-11 21:24:00",
        "title": "Working event chronology — ER-2026-02",
        "prepared_by": "Ada Bell, Ph.D., contract historian",
        "scope": "Documented publication history compared with preview-night observations. Times are local Eastern Time unless a source states otherwise.",
        "rows": [
            ["1841-07-28", "Mary Cecilia Rogers's body is recovered from the Hudson near Weehawken.", "historical", "H-01 / NY Herald, 1841-07-29 / HPHC-PRESS-1841-0729"],
            ["1841-07-29 (asserted)", "Q-3 states that Poe examined the cave after the recovery. The date and authorship are unverified.", "claim", "Q-3 / TC-2026-014"],
            ["1842-06-04", "Poe describes a completed parallel analysis relocating the Rogers case to Paris.", "historical", "S-01 / LTR-136 / ER-WEB-26-031"],
            ["1842-11 to 1843-02", "The three installments of The Mystery of Marie Roget appear in Ladies' Companion.", "historical", "S-02a-c / ER-WEB-26-032–034"],
            ["2026-02-11 20:20", "Ada Bell photographs TEMP-L2026.002.001 in preview case 3; Q-3 is attached to clipping Q-3B.", "observed", "IMG-221 / frame 04"],
            ["2026-02-11 20:31", "Credential CRANE-04 is recorded at the pump corridor; the event does not identify the person using it.", "system", "access export AX-8814"],
            ["2026-02-11 20:38", "The Quill device account receives an interrupted voicemail naming the pump housing; MER-26-19 does not identify the speaker.", "device", "device report MER-26-19"],
            ["2026-02-11 21:10", "Missing-person protocol begins.", "observed", "incident log IR-26-07"],
        ],
        "source_notes": [
            ["H-01", "New York Herald, 29 July 1841, clipping file HPHC-PRESS-1841-0729; event date only"],
            ["S-01", "Poe to George Roberts, 4 June 1842, LTR-136; E. A. Poe Society transcription"],
            ["S-02a-c", "Ladies' Companion 17 (Nov.–Dec. 1842) and 18 (Feb. 1843); three-part first publication"],
            ["Q-3", "Questioned note in TEMP-L2026.002.001; examination report ATCL-26-00387 addresses manufacture, not authorship"],
        ],
        "conclusion": "This chronology does not verify Q-3's asserted 29 July 1841 date or authorship. The historical sources document the Rogers recovery, Poe's June 1842 account of his method, and later publication. Preview-night entries establish only the recorded observation, credential event, device record, or incident action stated in each row.",
    },
    "conservation_examination": {
        "organization": "Alder Trace Conservation Laboratory",
        "department": "Paper & Trace Materials",
        "record_id": "ATCL-26-00387",
        "represented_date": "2026-02-11",
        "exported_at": "2026-02-11 19:06:00",
        "case_reference": "HPHC preview / item Q-3",
        "examiner": "Morgan Voss, paper conservator",
        "technical_reviewer": "Leena Park, senior materials examiner",
        "items": [
            ["Q-3A", "Questioned note; handwriting-like black line on tea-toned paper", "sealed polyester sleeve"],
            ["Q-3B", "Attached printed clipping fragment", "same sleeve; no separation performed"],
        ],
        "derived_samples": [
            ["C-1", "Loose black particulate lifted from Q-3A during dry examination", "glassine fold / seal 0417"],
            ["F-1", "Loose surface fiber recovered from Q-3A", "glass slide / mount 26-387-F1"],
        ],
        "methods": [
            ["VIS", "stereo visual examination, 10x-40x", "ATCL-MIC-04", "IMG-387-01–08", "non-destructive"],
            ["UV", "long-wave ultraviolet examination", "ATCL-UV-02 / 365 nm", "IMG-387-09–12", "non-destructive"],
            ["FTIR-ATR", "binder screening on particulate C-1", "ATCL-FTIR-01", "FTIR-387-C1-01", "C-1 consumed"],
            ["FIB", "transmitted-light morphology of fiber F-1", "ATCL-CMP-03", "IMG-387-F1-01–04", "mount retained"],
        ],
        "observations": [
            "Q-3A carries fused, rounded black particles with edge gloss inconsistent with iron-gall handwriting or letterpress transfer.",
            "The questioned line crosses a tea-toned tide mark; toner sits above the stain boundary rather than beneath it.",
            "A bright trilobal synthetic fiber is embedded in the surface sizing of Q-3A. The adjacent clipping Q-3B is compatible with rag-based historic paper under the limited examination performed.",
        ],
        "conclusion": "The packet is composite. Results support modern electrophotographic toner on artificially toned paper associated with an older clipping; they do not support common manufacture or common age of Q-3A and Q-3B.",
        "limitations": "Class characteristics cannot identify a unique printer, person, or source. No destructive dating of Q-3B was authorized. The conclusion applies only to the items and methods listed.",
    },
    "access_event_report": {
        "organization": "Hudson Palisade History Center",
        "system": "Northstar Access Control 8.4",
        "record_id": "AX-8814",
        "represented_date": "2026-02-11",
        "exported_at": "2026-02-11 21:14:00",
        "report_name": "Historical access events — pump corridor",
        "filter": "2026-02-11 20:15:00 through 21:12:00; doors PUMP-COR and SERVICE-RECESS; normal and abnormal events",
        "events": [
            ["384771", "20:24:03", "QUILL-01", "Miriam Quill", "PUMP-COR / exterior", "Access granted", "ENTRY"],
            ["384779", "20:31:16", "CRANE-04", "Elias Crane", "PUMP-COR / exterior", "Access granted", "ENTRY"],
            ["384786", "20:36:42", "QUILL-01", "Miriam Quill", "SERVICE-RECESS", "Access granted", "OPEN"],
            ["384791", "20:43:08", "CRANE-04", "Elias Crane", "PUMP-COR / interior REX", "Request-to-exit", "EXIT"],
            ["384818", "21:10:11", "HOST-00", "Incident controller", "SYSTEM", "Missing-person protocol", "ACK"],
        ],
        "integrity_note": "Sequence numbers are controller-assigned. This report reflects stored event records, not video verification of the person using a credential.",
    },
    "tenant_account_ledger": {
        "organization": "Riverglass Residential Management, LLC",
        "system": "Resident Accounts / Portfolio 03",
        "record_id": "TA-4C-2026-02-11",
        "represented_date": "2026-02-11",
        "exported_at": "2026-02-11 21:22:00",
        "property": "Loom House",
        "street": "47 Loomwright Mews",
        "unit": "4C",
        "municipality": "Hoboken",
        "state": "NJ",
        "zip": "07030",
        "tenant": "Elias Crane",
        "account_number": "LM-004C-26",
        "term_start": "2026-01-01",
        "term_end": "2026-12-31",
        "monthly_rent": 2800,
        "deposit": 4200,
        "occupancy_status": "ACTIVE",
        "authorized_use": "Residential occupancy; tenant-declared paper storage in interior closets",
        "transactions": [
            ["2025-12-18", "Security deposit received", "DEP", "4,200.00", "0.00"],
            ["2026-01-01", "January rent charge", "RNT", "2,800.00", "2,800.00"],
            ["2026-01-02", "ACH receipt 98114", "PMT", "(2,800.00)", "0.00"],
            ["2026-02-01", "February rent charge", "RNT", "2,800.00", "2,800.00"],
            ["2026-02-03", "ACH receipt 99402", "PMT", "(2,800.00)", "0.00"],
        ],
        "record_note": "Account extract identifies the tenant of record and payment status. It is not the executed lease and does not expand permitted use of the dwelling.",
    },
    "voicemail_evidence_report": {
        "organization": "Hudson Palisade History Center",
        "department": "Incident Review",
        "record_id": "MER-26-019",
        "represented_date": "2026-02-11",
        "exported_at": "2026-02-11 21:26:00",
        "device": "Apple iPhone / asset HPHC-MQ-07",
        "account": "+1 201 555 0148",
        "from_name": "Miriam Quill",
        "to_name": "Elias Crane",
        "received_at": "2026-02-11 20:38:14 EST",
        "duration": "00:00:19",
        "audio_hash": "SHA-256 90E4 8896 7B31 2D08 ... C12A",
        "segments": [
            ["00:00.0", "Elias, the proof cannot survive either test. The visit never happened, and Morgan found—", "speech; clipped ending"],
            ["00:08.1", "[metal latch; low mechanical vibration]", "non-speech sound"],
            ["00:12.7", "Behind the pump housing. He has shut the—", "speech; connection loss"],
            ["00:18.9", "[recording ends]", "carrier termination"],
        ],
        "limitations": "Transcript was prepared for review and may contain recognition or punctuation errors. The retained audio is the source record. Speaker labels reflect device account data and are not biometric identification.",
    },
    "pump_emergency_card": {
        "organization": "Hudson Palisade History Center",
        "record_id": "P-2 / EIC-04",
        "represented_date": "2025-09-18",
        "exported_at": "2025-09-18 14:30:00",
        "equipment": "PUMP HOUSING P-2",
        "location": "LOWER CAVE SERVICE CORRIDOR",
        "revision": "REV 4 · 18 SEP 2025",
        "warning": "DRY SERVICE RECESS — NO OCCUPANCY. LATCH HAS NO INTERIOR RELEASE.",
        "steps": [
            "Call site emergency control. Do not enter the recess alone.",
            "Press P-2 STOP. Isolate electrical disconnect DS-2 before reaching behind the guard.",
            "Lift the brass guard on the east side of P-2 and pull the RED EMERGENCY RELEASE RING fully outward.",
            "Verify the latch is open. Keep the door blocked until the space is cleared and inspected.",
        ],
        "footer": "After use: tag P-2 out of service and record the release in the plant log.",
    },
}


def _validate_kind(kind: str) -> None:
    if kind not in DEFAULTS:
        raise KeyError(f"unknown investigation artifact kind: {kind}")


def sample_artifact(
    rng: random.Random,
    *,
    kind: str,
    pins: dict | None = None,
    canon: dict | None = None,
) -> dict[str, Any]:
    """Build one canonical record from caller facts; no derived fact is sampled."""
    _validate_kind(kind)
    model = deepcopy(DEFAULTS[kind])
    model.update(deepcopy(canon or {}))
    model.update(deepcopy(pins or {}))
    model["kind"] = kind
    # Stable, producing-system detail; it never changes a caller-owned fact.
    model["export_job"] = f"{rng.randrange(1_000_000):06d}"
    return model


def export_created(model: dict[str, Any]) -> str:
    return str(model["exported_at"])


def _display_model(model: dict[str, Any], defect: dict | None) -> dict[str, Any]:
    shown = deepcopy(model)
    if not defect:
        return shown
    if set(defect) != {"field", "value"}:
        raise ValueError("investigation defect requires exactly field and value")
    field = defect["field"]
    if not isinstance(field, str) or field not in shown:
        raise ValueError("investigation defect field must name one displayed scalar")
    if isinstance(shown[field], (list, dict)):
        raise ValueError("investigation defect may alter only one displayed scalar")
    shown[field] = defect["value"]
    return shown


def public_display_facts(
    model: dict[str, Any], *, defect: dict | None = None
) -> dict[str, Any]:
    shown = _display_model(model, defect)
    return {
        "document_class": shown["kind"],
        "record_id": shown["record_id"],
        "represented_date": shown["represented_date"],
        "reading_copy": _reading_copy(shown),
        "accessibility": {
            "required": True,
            "source": "embedded PDF text layer",
            "interpretation": [],
        },
    }


_BASE = getSampleStyleSheet()
BODY = ParagraphStyle(
    "InvestigationBody", parent=_BASE["BodyText"], fontName="Helvetica",
    fontSize=9.2, leading=12.2, textColor=colors.HexColor("#1f2933"),
    spaceAfter=6,
)
SMALL = ParagraphStyle(
    "InvestigationSmall", parent=BODY, fontSize=7.6, leading=9.4,
    textColor=colors.HexColor("#485563"),
)
H1 = ParagraphStyle(
    "InvestigationH1", parent=_BASE["Title"], fontName="Helvetica-Bold",
    fontSize=17, leading=20, alignment=TA_LEFT,
    textColor=colors.HexColor("#172b3a"), spaceAfter=8,
)
H2 = ParagraphStyle(
    "InvestigationH2", parent=_BASE["Heading2"], fontName="Helvetica-Bold",
    fontSize=9, leading=11, textTransform="uppercase", tracking=0.7,
    textColor=colors.HexColor("#28566f"), spaceBefore=10, spaceAfter=5,
)
MONO = ParagraphStyle(
    "InvestigationMono", parent=SMALL, fontName="Courier", fontSize=7.1,
    leading=8.7,
)
TABLE_HEADER = ParagraphStyle(
    "InvestigationTableHeader", parent=SMALL, fontName="Helvetica-Bold",
    textColor=colors.white,
)


def _escape(value: Any) -> str:
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _p(value: Any, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(_escape(value), style)


def _table(
    rows: list[list[Any]], widths: list[float], *, header: bool = True,
    font_size: float = 7.6,
) -> Table:
    cells = [
        [
            _p(value, TABLE_HEADER if header and row_index == 0 else SMALL)
            for value in row
        ]
        for row_index, row in enumerate(rows)
    ]
    table = Table(cells, colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#9aa7b1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1),
         [colors.white, colors.HexColor("#f3f6f7")]),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173f56")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])
    table.setStyle(TableStyle(commands))
    return table


DOCUMENT_TITLES = {
    "museum_research_note": "Collections research note",
    "curatorial_chronology": "Curatorial chronology",
    "conservation_examination": "Preliminary examination report",
    "access_event_report": "Historical access event report",
    "tenant_account_ledger": "Tenant account record",
    "voicemail_evidence_report": "Voicemail evidence report",
    "pump_emergency_card": "Emergency release instruction card",
}


def _document_title(model: dict[str, Any]) -> str:
    return str(
        model.get("title")
        or model.get("report_name")
        or DOCUMENT_TITLES[model["kind"]]
    )


def _document_author(model: dict[str, Any]) -> str:
    return str(
        model.get("prepared_by")
        or model.get("examiner")
        or model["organization"]
    )


def _document_subject(model: dict[str, Any]) -> str:
    return str(
        model.get("subject")
        or model.get("case_reference")
        or f"{DOCUMENT_TITLES[model['kind']]} {model['record_id']}"
    )


def _ensure_office_fonts() -> None:
    """Register ReportLab's redistributable embedded office-style family."""
    try:
        pdfmetrics.getFont("VeraOffice")
    except KeyError:
        pdfmetrics.registerFont(TTFont("VeraOffice", "Vera.ttf"))
        pdfmetrics.registerFont(TTFont("VeraOffice-Bold", "VeraBd.ttf"))
        pdfmetrics.registerFont(TTFont("VeraOffice-Italic", "VeraIt.ttf"))
        pdfmetrics.registerFontFamily(
            "VeraOffice",
            normal="VeraOffice",
            bold="VeraOffice-Bold",
            italic="VeraOffice-Italic",
            boldItalic="VeraOffice-Bold",
        )


def _footer_callback(model: dict[str, Any], metadata: dict[str, Any]):
    def draw(c: canvas.Canvas, doc) -> None:
        c.saveState()
        c.setCreator(metadata["creator"])
        c.setProducer(metadata["producer"])
        c.setTitle(_document_title(model))
        c.setAuthor(_document_author(model))
        c.setSubject(_document_subject(model))
        c.setStrokeColor(colors.HexColor("#aab4bc"))
        c.line(doc.leftMargin, 0.52 * inch, doc.pagesize[0] - doc.rightMargin, 0.52 * inch)
        c.setFillColor(colors.HexColor("#596875"))
        c.setFont("Helvetica", 7)
        c.drawString(doc.leftMargin, 0.37 * inch, str(model["record_id"]))
        c.drawCentredString(doc.pagesize[0] / 2, 0.37 * inch,
                            f"RECORD DATE · {model['represented_date']}")
        c.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.37 * inch,
                          f"Page {doc.page}")
        c.restoreState()
    return draw


def _memo_footer_callback(model: dict[str, Any], metadata: dict[str, Any]):
    def draw(c: canvas.Canvas, doc) -> None:
        c.saveState()
        c.setCreator(metadata["creator"])
        c.setProducer(metadata["producer"])
        c.setTitle(_document_title(model))
        c.setAuthor(_document_author(model))
        c.setSubject(_document_subject(model))
        c.setStrokeColor(colors.HexColor("#858585"))
        c.line(doc.leftMargin, 0.52 * inch,
               doc.pagesize[0] - doc.rightMargin, 0.52 * inch)
        c.setFillColor(colors.HexColor("#555555"))
        _ensure_office_fonts()
        c.setFont("VeraOffice", 7.5)
        if doc.page > 1:
            c.setFillColor(colors.HexColor("#666666"))
            c.drawString(
                doc.leftMargin,
                doc.pagesize[1] - 0.34 * inch,
                f"{model['record_id']} · RESEARCH NOTE · continued",
            )
            c.setStrokeColor(colors.HexColor("#b0b0b0"))
            c.line(
                doc.leftMargin,
                doc.pagesize[1] - 0.43 * inch,
                doc.pagesize[0] - doc.rightMargin,
                doc.pagesize[1] - 0.43 * inch,
            )
            c.setFillColor(colors.HexColor("#555555"))
        c.drawString(doc.leftMargin, 0.35 * inch, str(model["record_id"]))
        c.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.35 * inch,
                          f"Page {doc.page}")
        c.restoreState()
    return draw


def _finalize(raw: bytes, metadata: dict[str, Any]) -> bytes:
    fixed = legalpdf._fix_dates(
        raw, created=metadata.get("created"), modified=metadata.get("modified")
    )
    return legalpdf._fix_id(fixed)


def _document(
    model: dict[str, Any], metadata: dict[str, Any], story: list[Any], *,
    pagesize=letter, margins=(0.7, 0.7, 0.7, 0.72), footer_factory=None,
) -> bytes:
    target = io.BytesIO()
    left, right, top, bottom = (item * inch for item in margins)
    doc = SimpleDocTemplate(
        target, pagesize=pagesize, leftMargin=left, rightMargin=right,
        topMargin=top, bottomMargin=bottom,
        title=_document_title(model),
    )
    callback = (footer_factory or _footer_callback)(model, metadata)
    doc.build(
        story, onFirstPage=callback, onLaterPages=callback,
        canvasmaker=partial(canvas.Canvas, invariant=1),
    )
    return _finalize(target.getvalue(), metadata)


def _masthead(model: dict[str, Any], kicker: str) -> list[Any]:
    return [
        _p(model["organization"], ParagraphStyle(
            "Org", parent=SMALL, fontName="Helvetica-Bold", fontSize=8.5,
            leading=10, textColor=colors.HexColor("#28566f"),
        )),
        _p(kicker, ParagraphStyle(
            "Kicker", parent=SMALL, fontSize=7.4, leading=9,
            textColor=colors.HexColor("#6f7b84"),
        )),
        Spacer(1, 8),
    ]


def _render_research(model: dict[str, Any], metadata: dict[str, Any]) -> bytes:
    _ensure_office_fonts()
    memo_body = ParagraphStyle(
        "ResearchMemoBody", parent=BODY, fontName="VeraOffice",
        fontSize=10.2, leading=12.8, textColor=colors.black, spaceAfter=6,
    )
    memo_small = ParagraphStyle(
        "ResearchMemoSmall", parent=memo_body, fontSize=8.9, leading=11,
        textColor=colors.HexColor("#333333"),
    )
    memo_heading = ParagraphStyle(
        "ResearchMemoHeading", parent=memo_body, fontName="VeraOffice-Bold",
        fontSize=10.2, leading=12.8, spaceBefore=8, spaceAfter=4,
    )
    memo_title = ParagraphStyle(
        "ResearchMemoTitle", parent=memo_body, fontName="VeraOffice-Bold",
        fontSize=14, leading=17, spaceAfter=9,
    )
    label = ParagraphStyle(
        "ResearchMemoLabel", parent=memo_small, fontName="VeraOffice-Bold",
        fontSize=8.9,
    )
    header_rows = [
        [_p("TO", label), _p(model["reviewed_by"], memo_small)],
        [_p("FROM", label), _p(model["prepared_by"], memo_small)],
        [_p("DATE", label), _p(model["represented_date"], memo_small)],
        [_p("FILE", label), _p(f"{model['records_series']} · {model['record_id']}", memo_small)],
        [_p("STATUS", label), _p("FINAL", memo_small)],
        [_p("REVIEW", label), _p(
            f"{model['reviewed_by']} — {model['reviewed_at']}", memo_small,
        )],
        [_p("SUBJECT", label), _p(model["subject"], memo_small)],
        [_p("OBJECT REF.", label), _p(
            f"Unaccessioned lender packet {model['object_id']}, received under "
            f"{model['receipt_id']}; questioned handwriting is item Q-3 in "
            "examination report ATCL-26-00387.",
            memo_small,
        )],
        [_p("RELATED", label), _p(
            "TC-2026-014 temporary-custody record; ATCL-26-00387 conservation "
            "examination; CHR-26-017 curatorial chronology.",
            memo_small,
        )],
    ]
    header = Table(header_rows, colWidths=[0.9*inch, 5.7*inch])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6, colors.HexColor("#666666")),
    ]))
    story = [
        _p(model["organization"], ParagraphStyle(
            "MemoOrg", parent=memo_body, fontName="VeraOffice-Bold",
            fontSize=10.5, leading=12.5, spaceAfter=1,
        )),
        _p(f"{model['department']} · {model['organization_address']}", memo_small),
        Spacer(1, 7),
        _p("RESEARCH NOTE", memo_title),
        header,
        _p("Question", memo_heading),
        _p(model["question"], memo_body),
        _p("Conclusion and scope", memo_heading),
        _p(model["finding"], memo_body),
        _p("Sources reviewed", memo_heading),
    ]
    for ref, source, use in model["sources"]:
        story.append(_p(f"{ref}  {source}. {use}.", memo_small))
    story += [
        PageBreak(),
        _p("Captured-source register", memo_heading),
        *[_p(locator, memo_small) for locator in model["source_locators"]],
        _p("Method", memo_heading),
        _p(
            "S-01 was read as a scholarly transcription of a contemporary letter. "
            "The three parts of S-02 were compared with the revised S-03 text; S-04 "
            "was used only for publication and manuscript history. The captured PDFs "
            "in ER-2026-02/web-captures were searched for Hoboken, cave, visit, New "
            "York, newspaper, and press. Every hit was read in context. The capture "
            "register preserves the consulted rendering; this was documentary "
            "research only; Q-3 was not examined.",
            memo_body,
        ),
        _p("Research notes", memo_heading),
        *[
            _p(f"{at} — {source} — {action}", memo_small)
            for at, source, action in model["research_log"]
        ],
        _p("Discussion", memo_heading),
        _p(
            "In S-01 Poe describes the tale as a parallel Paris narrative based on "
            "the Rogers case and says, ‘I examine, each by each, the opinions and "
            "arguments of the press upon the subject.’ S-02 and S-03 likewise use "
            "newspaper files as Dupin's evidence. No searched passage supplies an "
            "affirmative first-person account of a cave visit. The narrow historical "
            "result is therefore ‘not supported by the sources reviewed,’ not "
            "‘did not happen.’",
            memo_body,
        ),
        _p("Limitations", memo_heading),
        _p(model["limitations"], memo_body),
        _p("Record action", memo_heading),
        _p(
            f"Filed by Ada Bell in {model['records_series']} on 11 February 2026. "
            f"Web captures remain with that inquiry. The lender packet remains "
            f"controlled under {model['receipt_id']}; custody and return actions are "
            "recorded there, not in this note.",
            memo_body,
        ),
    ]
    return _document(
        model, metadata, story, margins=(0.7, 0.7, 0.55, 0.58),
        footer_factory=_memo_footer_callback,
    )


def _render_chronology(model: dict[str, Any], metadata: dict[str, Any]) -> bytes:
    _ensure_office_fonts()
    sheet_body = ParagraphStyle(
        "ChronologySheetBody", parent=BODY, fontName="VeraOffice",
        fontSize=9, leading=10.8, textColor=colors.black, spaceAfter=4,
    )
    sheet_small = ParagraphStyle(
        "ChronologySheetSmall", parent=sheet_body, fontSize=8, leading=9.5,
    )
    sheet_heading = ParagraphStyle(
        "ChronologySheetHeading", parent=sheet_body,
        fontName="VeraOffice-Bold", fontSize=14, leading=17, spaceAfter=7,
    )
    chronology_cells = [
        [_p(value, ParagraphStyle(
            f"Chronology-{row_index}-{column_index}", parent=sheet_small,
            fontName=("VeraOffice-Bold" if row_index == 0 else "VeraOffice"),
            fontSize=8.4, leading=10, textColor=colors.black,
        )) for column_index, value in enumerate(row)]
        for row_index, row in enumerate(
            [["Date / time", "Event or assertion", "Source class", "Source record / locator"], *model["rows"]]
        )
    ]
    chronology = Table(
        chronology_cells,
        colWidths=[1.35 * inch, 4.55 * inch, 0.95 * inch, 2.55 * inch],
        repeatRows=1,
    )
    chronology.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#777777")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    controls = Table([
        [_p("FILE", sheet_small), _p("ER-2026-02 / inquiry 06", sheet_small),
         _p("RECORD", sheet_small), _p(model["record_id"], sheet_small),
         _p("THROUGH", sheet_small), _p("2026-02-11 21:10 ET", sheet_small)],
        [_p("BY", sheet_small), _p(model["prepared_by"], sheet_small),
         _p("UPDATED", sheet_small), _p("2026-02-11 21:24 ET", sheet_small),
         _p("STATUS", sheet_small), _p("working", sheet_small)],
    ], colWidths=[0.65*inch, 2.65*inch, 0.75*inch, 1.45*inch, 0.75*inch, 2.55*inch])
    controls.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#888888")),
        ("FONTNAME", (0, 0), (-1, -1), "VeraOffice"),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eeeeee")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eeeeee")),
        ("BACKGROUND", (4, 0), (4, -1), colors.HexColor("#eeeeee")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story = [
        _p(model["organization"], ParagraphStyle(
            "ChronologyOrg", parent=sheet_body, fontName="VeraOffice-Bold",
            fontSize=10, leading=12, spaceAfter=1,
        )),
        _p(model["department"], sheet_small),
        Spacer(1, 5),
        _p("WORKING EVENT CHRONOLOGY", sheet_heading),
        controls,
        Spacer(1, 6),
        _p(model["scope"], sheet_small),
        Spacer(1, 5),
        chronology,
        Spacer(1, 7),
        _p("ANALYST NOTE", ParagraphStyle(
            "ChronologyNoteHeading", parent=sheet_small,
            fontName="VeraOffice-Bold", spaceAfter=2,
        )),
        _p(model["conclusion"], sheet_small),
    ]
    return _document(
        model, metadata, story, pagesize=landscape(letter),
        margins=(0.65, 0.65, 0.5, 0.58),
        footer_factory=_memo_footer_callback,
    )


def _render_conservation(model: dict[str, Any], metadata: dict[str, Any]) -> bytes:
    story = _masthead(model, model["department"])
    story += [_p("PRELIMINARY EXAMINATION REPORT", H1),
              _table([["Laboratory no.", model["record_id"], "Case", model["case_reference"]],
                      ["Examiner", model["examiner"], "Report date", model["represented_date"]],
                      ["Technical review", model["technical_reviewer"], "Status", "LIMITED EXAMINATION / FINAL"]],
                     [0.9*inch, 2.2*inch, 0.8*inch, 2.3*inch], header=False),
              _p("Items received and custody", H2),
              _table([["Item", "Description", "Packaging / condition"], *model["items"]],
                     [0.65*inch, 3.4*inch, 2.15*inch]),
              _p("Examination-derived samples", H2),
              _table([["Sample", "Origin / preparation", "Storage / disposition"], *model["derived_samples"]],
                     [0.7*inch, 3.35*inch, 2.15*inch]),
              _p("Requested examination", H2),
              _p("Characterize the questioned writing medium, surface treatment, and loose fiber; assess whether the examined components support common manufacture or common age. No authorship, printer-source, or destructive paper dating examination was requested."),
              _p("Methods", H2),
              _table([["Code", "Procedure", "Instrument", "Output ref.", "Effect"], *model["methods"]],
                     [0.5*inch, 2.15*inch, 1.25*inch, 1.3*inch, 1.0*inch]),
              _p("Observations", H2)]
    story.extend(_p(f"{index}. {value}") for index, value in enumerate(model["observations"], 1))
    story += [_p("Evaluation", H2), _p(model["conclusion"]),
              _p("Reporting limitations", H2), _p(model["limitations"]),
              _p("Quality review", H2),
              _p(
                  "Technical reviewer Leena Park, senior materials examiner, compared "
                  "IMG-387-01–12, FTIR-387-C1-01, and IMG-387-F1-01–04 with "
                  "the observations and conclusion. Review completed 2026-02-11 "
                  "19:06; report released by Morgan Voss."
              )]
    return _document(
        model, metadata, story, margins=(0.6, 0.6, 0.45, 0.5)
    )


def _render_access(model: dict[str, Any], metadata: dict[str, Any]) -> bytes:
    story = _masthead(model, model["system"])
    story += [_p(model["report_name"], H1),
              _table([["Report ID", model["record_id"], "Generated", model["exported_at"]],
                      ["Filter", model["filter"], "Job", model["export_job"]]],
                     [0.7*inch, 4.55*inch, 0.65*inch, 1.8*inch], header=False),
              Spacer(1, 8),
              _table([["Sequence", "Time", "Credential", "Cardholder", "Door / device", "Event message", "Dir."], *model["events"]],
                     [0.7*inch, 0.7*inch, 0.85*inch, 1.2*inch, 1.65*inch, 1.45*inch, 0.55*inch], font_size=6.8),
              Spacer(1, 10), _p(model["integrity_note"], SMALL),
              _p("REPORT PARAMETERS", H2),
              _p("Event type: access, door, and operator · Include: normal and abnormal · Sort: controller event sequence · Output: PDF · Time zone: America/New_York", MONO)]
    return _document(model, metadata, story, pagesize=landscape(letter),
                     margins=(0.45, 0.45, 0.5, 0.65))


def _money(value: Any) -> str:
    return f"${float(value):,.2f}"


def _render_tenant(model: dict[str, Any], metadata: dict[str, Any]) -> bytes:
    address = (f"{model['street']}, Apt {model['unit']}, {model['municipality']}, "
               f"{model['state']} {model['zip']}")
    story = _masthead(model, model["system"])
    story += [_p("TENANT ACCOUNT RECORD", H1),
              _table([["Property", model["property"], "Unit", model["unit"]],
                      ["Premises", address, "Account", model["account_number"]],
                      ["Tenant of record", model["tenant"], "Status", model["occupancy_status"]]],
                     [0.85*inch, 2.65*inch, 0.65*inch, 2.0*inch], header=False),
              _p("Term and recurring charge", H2),
              _table([["Term start", "Term end", "Monthly rent", "Deposit held"],
                      [model["term_start"], model["term_end"], _money(model["monthly_rent"]), _money(model["deposit"])]],
                     [1.55*inch]*4),
              _p("Account ledger", H2),
              _table([["Posting date", "Description", "Code", "Amount", "Running balance"], *model["transactions"]],
                     [1.0*inch, 2.5*inch, 0.6*inch, 1.0*inch, 1.1*inch]),
              _p("Occupancy record", H2),
              _table([["Authorized use", model["authorized_use"]],
                      ["Mailing / notice address", address],
                      ["Account standing", "Current as of " + model["represented_date"]]],
                     [1.25*inch, 4.95*inch], header=False),
              _p("Record limitation", H2), _p(model["record_note"]),
              _p("Export certification", H2),
              _p(f"Generated from {model['system']} at {model['exported_at']} under export job {model['export_job']}. This export reflects posted transactions through the represented date; later reversals or adjustments are not included."),
              Spacer(1, 18),
              _table([["Portfolio", "03 / Hudson County", "Record ID", model["record_id"]],
                      ["Management office", model["organization"], "Page purpose", "tenant account verification"]],
                     [0.9*inch, 2.15*inch, 0.85*inch, 2.3*inch], header=False)]
    return _document(model, metadata, story)


def _render_voicemail(model: dict[str, Any], metadata: dict[str, Any]) -> bytes:
    story = _masthead(model, model["department"])
    story += [_p("VOICEMAIL EVIDENCE REPORT", H1),
              _table([["Report", model["record_id"], "Prepared", model["exported_at"]],
                      ["Device", model["device"], "Account", model["account"]],
                      ["From", model["from_name"], "To", model["to_name"]],
                      ["Received", model["received_at"], "Duration", model["duration"]]],
                     [0.75*inch, 2.4*inch, 0.75*inch, 2.25*inch], header=False),
              _p("Source record", H2),
              _p("The voicemail was shared from the assigned device to the incident-review repository without editing. The retained audio file is the source record; this PDF is a review rendition."),
              _p(model["audio_hash"], MONO),
              _p("Time-aligned transcript", H2),
              _table([["Offset", "Transcript / audible event", "Annotation"], *model["segments"]],
                     [0.75*inch, 3.9*inch, 1.55*inch]),
              _p("Device presentation", H2),
              _table([["Display field", "Recorded value"],
                      ["Caller / account label", model["from_name"]],
                      ["Received", model["received_at"]],
                      ["Playback duration", model["duration"]],
                      ["Share action", "incident-review repository / MER-26-019"]],
                     [1.55*inch, 4.65*inch]),
              _p("Limitations", H2), _p(model["limitations"]),
              _p("Review note", H2),
              _p("Mechanical sounds are described, not source-attributed. No enhancement, speaker comparison, or biometric identification was performed. Device time should be compared with independent system records before chronology is inferred."),
              Spacer(1, 14),
              _table([["Prepared by", "Incident Review / operator 07", "Status", "source audio retained"],
                      ["Record hash", model["audio_hash"], "Access", "case principals only"]],
                     [0.85*inch, 2.6*inch, 0.65*inch, 2.1*inch], header=False)]
    return _document(model, metadata, story)


def _wrap_lines(c: canvas.Canvas, text: str, font: str, size: float,
                width: float) -> list[str]:
    words = text.split()
    result: list[str] = []
    line = ""
    for word in words:
        trial = f"{line} {word}".strip()
        if c.stringWidth(trial, font, size) <= width:
            line = trial
        else:
            if line:
                result.append(line)
            line = word
    if line:
        result.append(line)
    return result


def _render_card(model: dict[str, Any], metadata: dict[str, Any]) -> bytes:
    width, height = 6 * inch, 4 * inch
    target = io.BytesIO()
    c = canvas.Canvas(target, pagesize=(width, height), invariant=1)
    c.setCreator(metadata["creator"]); c.setProducer(metadata["producer"])
    c.setTitle(_document_title(model)); c.setAuthor(_document_author(model))
    c.setSubject(_document_subject(model))
    c.setFillColor(colors.HexColor("#f4edcf")); c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#b32025")); c.rect(0, height-0.72*inch, width, 0.72*inch, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 17)
    c.drawString(0.28*inch, height-0.43*inch, "EMERGENCY RELEASE")
    c.setFont("Helvetica-Bold", 8); c.drawRightString(width-0.25*inch, height-0.42*inch, model["record_id"])
    y = height-0.95*inch
    c.setFillColor(colors.HexColor("#20272c")); c.setFont("Helvetica-Bold", 13)
    c.drawString(0.3*inch, y, model["equipment"])
    c.setFont("Helvetica", 7.5); c.drawRightString(width-0.3*inch, y+1, model["revision"])
    y -= 0.28*inch
    c.setFillColor(colors.HexColor("#9c1c20")); c.setFont("Helvetica-Bold", 8.2)
    for line in _wrap_lines(c, model["warning"], "Helvetica-Bold", 8.2, width-0.6*inch):
        c.drawString(0.3*inch, y, line); y -= 0.14*inch
    y -= 0.04*inch
    c.setFillColor(colors.HexColor("#20272c"));
    for index, step in enumerate(model["steps"], 1):
        c.setFont("Helvetica-Bold", 9); c.drawString(0.32*inch, y, str(index))
        c.circle(0.36*inch, y+2.5, 8, fill=0, stroke=1)
        lines = _wrap_lines(c, step, "Helvetica", 7.8, width-0.86*inch)
        c.setFont("Helvetica", 7.8)
        for line in lines:
            c.drawString(0.62*inch, y, line); y -= 0.125*inch
        y -= 0.07*inch
    c.setStrokeColor(colors.HexColor("#7f887f")); c.line(0.3*inch, 0.48*inch, width-0.3*inch, 0.48*inch)
    c.setFillColor(colors.HexColor("#30383d")); c.setFont("Helvetica-Bold", 6.8)
    c.drawString(0.3*inch, 0.31*inch, model["footer"])
    c.setFont("Helvetica", 6.4); c.drawRightString(width-0.3*inch, 0.13*inch, model["location"])
    c.showPage(); c.save()
    return _finalize(target.getvalue(), metadata)


RENDERERS = {
    "museum_research_note": _render_research,
    "curatorial_chronology": _render_chronology,
    "conservation_examination": _render_conservation,
    "access_event_report": _render_access,
    "tenant_account_ledger": _render_tenant,
    "voicemail_evidence_report": _render_voicemail,
    "pump_emergency_card": _render_card,
}


def render_artifact(
    model: dict[str, Any], *, metadata: dict[str, Any],
    defect: dict | None = None,
) -> bytes:
    shown = _display_model(model, defect)
    return RENDERERS[shown["kind"]](shown, metadata)


def _reading_copy(model: dict[str, Any]) -> list[str]:
    """Literal, non-interpretive strings exposed by the artifact."""
    kind = model["kind"]
    common = [model["organization"], model["record_id"], model["represented_date"]]
    if kind == "museum_research_note":
        return common + [model["records_series"], model["project"],
                         model["loan_number"], model["object_id"],
                         model["receipt_id"], model["lender"],
                         model["record_status"], model["current_location"],
                         model["handling_class"], model["rights_status"],
                         model["object_description"],
                         model["object_custody"], model["subject"],
                         model["question"], model["finding"],
                         *(cell for row in model["sources"] for cell in row),
                         *model["source_locators"],
                         *(cell for row in model["research_log"] for cell in row),
                         model["review_authority"], model["reviewed_at"],
                         model["retention"],
                         model["limitations"]]
    if kind == "curatorial_chronology":
        return common + [model["title"], model["scope"],
                         *(cell for row in model["rows"] for cell in row),
                         *(cell for row in model["source_notes"] for cell in row),
                         model["conclusion"]]
    if kind == "conservation_examination":
        return common + [model["case_reference"], model["examiner"],
                         *(cell for row in model["items"] for cell in row),
                         *(cell for row in model["derived_samples"] for cell in row),
                         *(cell for row in model["methods"] for cell in row),
                         *model["observations"], model["conclusion"], model["limitations"]]
    if kind == "access_event_report":
        return common + [model["report_name"], model["filter"],
                         *(cell for row in model["events"] for cell in row), model["integrity_note"]]
    if kind == "tenant_account_ledger":
        return common + [model["property"], model["tenant"], model["account_number"],
                         model["term_start"], model["term_end"], str(model["monthly_rent"]),
                         *(cell for row in model["transactions"] for cell in row), model["record_note"]]
    if kind == "voicemail_evidence_report":
        return common + [model["device"], model["from_name"], model["to_name"],
                         model["received_at"], *(cell for row in model["segments"] for cell in row),
                         model["limitations"]]
    return common + [model["equipment"], model["location"], model["warning"],
                     *model["steps"], model["footer"]]


sample_research_note = partial(sample_artifact, kind="museum_research_note")
sample_chronology = partial(sample_artifact, kind="curatorial_chronology")
sample_conservation = partial(sample_artifact, kind="conservation_examination")
sample_access = partial(sample_artifact, kind="access_event_report")
sample_tenant_account = partial(sample_artifact, kind="tenant_account_ledger")
sample_voicemail = partial(sample_artifact, kind="voicemail_evidence_report")
sample_pump_card = partial(sample_artifact, kind="pump_emergency_card")
