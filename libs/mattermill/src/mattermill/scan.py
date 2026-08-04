"""Seeded scan emulation: a vector page tree in, a period-honest scan out.

Shared by every emitter whose artifact represents paper. Two documents need
this for different reasons and the pipeline is the same for both:

- the ORIGINAL predates PDF (vintage: a 1987 agreement cannot be a vector
  file — the format shipped in 1993);
- the artifact is a PRODUCTION SET (diligence: originals of any era, copied
  and bates-stamped for discovery, digitized as images later).

Either way the honest file is images with digitization-era metadata plus the
invisible text layer a Paper-Capture workflow leaves behind — which keeps the
artifact searchable and testable through the same text-extraction lens.

The caller supplies the text layer because only the caller knows its own line
geometry; `rng` is threaded in so scan texture is part of the caller's seed.
"""

from __future__ import annotations

import io
import random

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas

from . import legalpdf

PAGE_W, PAGE_H = letter


def scan_page_jpeg(img: Image.Image, rng: random.Random) -> bytes:
    """One page through the scanner: deskew error, toner speckle, an
    occasional roller streak, optical blur, brightness/contrast drift, and
    grayscale JPEG at the quality a document scanner actually writes."""
    img = img.convert("L")
    img = img.rotate(rng.uniform(-0.55, 0.55), resample=Image.BICUBIC,
                     expand=False, fillcolor=246)
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for _ in range(rng.randint(140, 320)):          # toner speckle
        x, y = rng.randrange(w), rng.randrange(h)
        draw.point((x, y), fill=rng.randint(70, 180))
    if rng.random() < 0.5:                          # faint roller streak
        x = rng.randrange(int(w * 0.1), int(w * 0.9))
        draw.line([(x, 0), (x, h)], fill=238, width=1)
    img = img.filter(ImageFilter.GaussianBlur(0.4))
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.97, 1.0))
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(1.03, 1.10))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return buf.getvalue()


def rescan(vector: bytes, *, rng: random.Random, metadata: dict,
           text_layer=None, dpi: int = 150) -> bytes:
    """Rasterize `vector`, scan each page, re-embed as JPEG with an invisible
    (render mode 3) text layer.

    text_layer: callable(page_index, textobject) drawing the OCR text for that
    page — the caller owns its geometry. metadata dates the DIGITIZATION, not
    the original; it must land in the PDF era.
    """
    try:
        import pypdfium2 as pdfium
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("scan emulation needs pypdfium2") from e

    doc = pdfium.PdfDocument(vector)
    pw, ph = doc[0].get_size()           # preserve the source's sheet: a
    buf = io.BytesIO()                   # folio stays folio, letter stays letter
    c = rl_canvas.Canvas(buf, pagesize=(pw, ph), invariant=1)
    c.setTitle("")
    c.setProducer(metadata["producer"])
    c.setCreator(metadata["creator"])
    for idx, page in enumerate(doc):
        jpeg = scan_page_jpeg(page.render(scale=dpi / 72).to_pil(), rng)
        c.drawImage(ImageReader(io.BytesIO(jpeg)), 0, 0, width=pw, height=ph)
        if text_layer is not None:
            t = c.beginText()
            t.setTextRenderMode(3)                  # invisible OCR layer
            text_layer(idx, t)
            c.drawText(t)
        c.showPage()
    c.save()
    # ReportLab writes its own name in harmless PDF comments even after the
    # Info dictionary has been set to the actual capture device.  A scanner
    # export should not leak the authoring renderer in those comments.  These
    # padded same-length substitutions preserve every xref offset.
    captured = buf.getvalue()
    for old in (b"ReportLab Generated PDF document (opensource)",
                b"ReportLab generated PDF document -- digest (opensource)"):
        replacement = b"Captured document image archive".ljust(len(old), b" ")
        captured = captured.replace(old, replacement)
    out = legalpdf._fix_dates(captured, created=metadata.get("created"),
                              modified=metadata.get("modified"))
    return legalpdf._fix_id(out)
