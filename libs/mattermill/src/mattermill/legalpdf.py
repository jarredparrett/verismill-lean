"""Legal-document PDF renderer (reportlab-backed).

Renders court documents with real structural texture: the two-column
bankruptcy caption with ')' separators, Times-Roman justified body, auto-
numbered paragraphs, signature blocks, certificates of service, ECF-style
header stamps, bates footers, and page numbers.

Determinism: Canvas(invariant=1) makes everything stable except the trailer
/ID, which reportlab randomizes per build. We overwrite it with a hash of
the document content — deterministic AND content-addressed, which is what
real PDF tools that hash content produce.
"""

from __future__ import annotations

import hashlib
import io
import re
from functools import partial

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

_BODY = ParagraphStyle("body", fontName="Times-Roman", fontSize=11,
                       leading=15, alignment=4, firstLineIndent=0.35 * inch,
                       spaceAfter=8)
_INTRO = ParagraphStyle("intro", parent=_BODY, firstLineIndent=0)
_HEAD = ParagraphStyle("head", parent=_BODY, alignment=1, spaceBefore=10,
                       spaceAfter=8)


def _caption_table(caption: dict) -> Table:
    court = caption["court"].upper()
    head = (court if court.startswith("UNITED STATES")
            else f"UNITED STATES BANKRUPTCY COURT<br/>{court}")
    left = (f"{head}<br/><br/>"
            f"In re:<br/><b>{caption['debtor'].upper()}</b>,<br/>"
            f"&nbsp;&nbsp;&nbsp;&nbsp;Debtor.")
    right = (
        f"Case No. {caption['case_no']}<br/>"
        f"Chapter {caption.get('chapter', '11')}<br/><br/>"
        + (f"({caption['related']})<br/>" if caption.get("related") else "")
        + (f"Hearing: {caption['hearing']}" if caption.get("hearing") else "")
    )
    sep = "<br/>".join(")" for _ in range(9))
    tbl = Table([[Paragraph(left, ParagraphStyle("cl", fontName="Times-Roman",
                                                 fontSize=11, leading=14)),
                  Paragraph(sep, ParagraphStyle("cs", fontName="Times-Roman",
                                                fontSize=11, leading=14)),
                  Paragraph(right, ParagraphStyle("cr", fontName="Times-Roman",
                                                  fontSize=11, leading=14))]],
                colWidths=[3.0 * inch, 0.3 * inch, 3.2 * inch])
    tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return tbl


def render_court_pdf(model: dict, *, header_stamp: str | None = None,
                     bates_prefix: str | None = None, metadata: dict) -> bytes:
    """model: {caption, title, intro, sections:[{heading, paras}], prayer,
    dated, signature, certificate}. metadata: {producer, creator, created}."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=1.0 * inch, rightMargin=1.0 * inch,
        topMargin=0.9 * inch, bottomMargin=0.8 * inch,
        title=model["title"],
        canvasmaker=partial(rl_canvas.Canvas, invariant=1))

    state = {"page_count": [0]}

    def on_page(canv, _doc):
        canv.setProducer(metadata["producer"])
        canv.setCreator(metadata["creator"])
        if metadata.get("title"):
            canv.setTitle(metadata["title"])
        state["page_count"][0] += 1
        page = state["page_count"][0]
        canv.saveState()
        canv.setFont("Courier", 7.5)
        if header_stamp:
            canv.drawString(0.6 * inch, letter[1] - 0.45 * inch, header_stamp
                            .replace("{page}", str(page)))
        canv.setFont("Times-Roman", 9)
        if bates_prefix:
            canv.drawRightString(letter[0] - 0.6 * inch, 0.4 * inch,
                                 f"{bates_prefix}{page:06d}")
        canv.drawCentredString(letter[0] / 2, 0.4 * inch, f"{page}")
        canv.restoreState()

    story = [_caption_table(model["caption"]), Spacer(1, 14),
             Paragraph(f"<b>{model['title']}</b>",
                       ParagraphStyle("t", parent=_HEAD, fontSize=12)),
             Spacer(1, 6)]
    if model.get("intro"):
        story.append(Paragraph(model["intro"], _INTRO))
    n = [0]
    for section in model.get("sections", []):
        if section.get("heading"):
            story.append(Paragraph(f"<b>{section['heading']}</b>", _HEAD))
        for para in section.get("paras", []):
            n[0] += 1
            story.append(Paragraph(f"{n[0]}.&nbsp;&nbsp;&nbsp;{para}", _BODY))
    if model.get("prayer"):
        story.append(Paragraph(model["prayer"], _INTRO))
    if model.get("dated"):
        story += [Spacer(1, 14), Paragraph(f"Dated: {model['dated']}", _INTRO)]
    if model.get("signature"):
        story.append(Spacer(1, 10))
        for line in model["signature"]:
            story.append(Paragraph(line, _INTRO))
    if model.get("certificate"):
        cert = model["certificate"]
        story += [Spacer(1, 18),
                  Paragraph("<b>CERTIFICATE OF SERVICE</b>", _HEAD),
                  Paragraph(
                      f"I hereby certify that on {cert['date']}, I caused the "
                      f"foregoing to be served {cert['method']} upon the "
                      f"parties on the attached service list. /s/ {cert['name']}",
                      _INTRO)]

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    out = _fix_dates(buf.getvalue(), created=metadata.get("created"),
                     modified=metadata.get("modified"))
    return _fix_id(out)


def _fix_id(pdf: bytes) -> bytes:
    """Replace reportlab's randomized trailer /ID with a content hash.
    Pipeline tail for every emitter — also rebuilds the xref, because the
    byte-level metadata edits upstream shift object offsets."""
    pdf = _scrub_renderer_comments(pdf)
    digest = hashlib.sha256(re.sub(rb"/ID\s*\[.*?\]", b"", pdf, flags=re.S)
                            ).hexdigest()
    id_pair = f"/ID [<{digest}><{digest}>]".encode()
    return _rebuild_xref(
        re.sub(rb"/ID\s*\[.*?\]", id_pair, pdf, count=1, flags=re.S))


def _scrub_renderer_comments(pdf: bytes) -> bytes:
    """Remove authoring-library fingerprints from PDF header comments.

    ReportLab writes its own name outside the Info dictionary.  Leaving that
    comment in a file whose governed metadata names the represented export
    tool creates a direct forensic contradiction.  Same-length substitutions
    preserve object offsets before the shared finalizer rebuilds the xref.
    """
    for old in (
        b"ReportLab Generated PDF document (opensource)",
        b"ReportLab generated PDF document -- digest (opensource)",
    ):
        replacement = b"%\xe2\xe3\xcf\xd3".ljust(len(old), b" ")
        pdf = pdf.replace(old, replacement)
    return pdf


def _fix_dates(pdf: bytes, *, created: str | None, modified: str | None) -> bytes:
    """Rewrite /CreationDate and /ModDate to the represented dates. reportlab
    stamps render time; a document representing an April filing must not
    claim a July creation — forensic authenticity is metadata too. A missing
    modified date defaults to created: a flattened export carries
    ModDate == CreationDate, never the epoch placeholder (an impossible
    modified-before-created chronology is a forensic tell)."""
    modified = modified or created

    def pdf_date(iso: str) -> str:
        date, _, tm = iso.strip().partition(" ")
        zone = ""
        if tm.endswith("Z"):
            tm = tm[:-1]
            zone = "Z"
        else:
            offset = re.search(r"([+-])(\d{2}):?(\d{2})$", tm)
            if offset:
                tm = tm[:offset.start()]
                zone = f"{offset.group(1)}{offset.group(2)}'{offset.group(3)}'"
        return f"D:{date.replace('-', '')}{tm.replace(':', '')}{zone}"
    if created:
        pdf = re.sub(rb"/CreationDate\s*\((?:\\.|[^()\\])*\)",
                     f"/CreationDate ({pdf_date(created)})".encode(), pdf)
    if modified:
        pdf = re.sub(rb"/ModDate\s*\((?:\\.|[^()\\])*\)",
                     f"/ModDate ({pdf_date(modified)})".encode(), pdf)
    return pdf


def _rebuild_xref(pdf: bytes) -> bytes:
    """Recompute xref offsets and startxref after byte-level edits changed
    object positions. A stale table parses leniently in viewers but reads as
    'malformed cross-reference' under strict/forensic parsing."""
    offsets = {int(m.group(1)): m.start()
               for m in re.finditer(rb"(?m)^(\d+) 0 obj", pdf)}
    xref_pos = pdf.rfind(b"\nxref\n")
    if xref_pos < 0 or not offsets:
        return pdf
    xref_pos += 1
    head = re.match(rb"xref\s+(\d+) (\d+)\s*\n", pdf[xref_pos:])
    if not head:
        return pdf
    first, count = int(head.group(1)), int(head.group(2))
    out = bytearray(pdf)
    entries_start = xref_pos + head.end()
    for i in range(max(first, 1), first + count):
        pos = entries_start + (i - first) * 20
        if i in offsets:
            out[pos:pos + 20] = f"{offsets[i]:010d} 00000 n \n".encode()
    tail = bytes(out)
    sx = tail.rfind(b"startxref")
    return tail[:sx] + re.sub(rb"startxref\s+\d+",
                              b"startxref\n" + str(xref_pos).encode(),
                              tail[sx:], count=1)
