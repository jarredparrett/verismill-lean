"""scan capability tests — the shared period-honest scan pipeline.

`scan.rescan` is what makes a 1642 deed or a 1987 agreement an honest artifact
rather than an anachronism: a vector page tree goes in, images with
digitisation-era metadata and an invisible OCR layer come out. Every scan-class
emitter routes through it, so a regression here is a regression in all of them
at once — which is why it gets tests of its own rather than only being covered
incidentally by its callers.
"""

from __future__ import annotations

import hashlib
import io
import random
import re
import subprocess
import sys

import pypdfium2 as pdfium
import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageStat
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as rl_canvas

from mattermill import scan

META = {"producer": "Zeutschel OS 12002 / Adobe Paper Capture",
        "creator": "Zeutschel OS 12002", "created": "2019-03-14 09:22:11",
        "modified": None}


def _vector(pages=2, size=letter) -> bytes:
    """A minimal multi-page vector PDF standing in for a composed document."""
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=size, invariant=1)
    for i in range(pages):
        c.setFont("Helvetica", 12)
        c.drawString(72, size[1] - 96, f"page {i + 1} body text")
        c.showPage()
    c.save()
    return buf.getvalue()


def _text_layer(page_index, textobject):
    textobject.setTextOrigin(72, 600)
    textobject.textLine(f"searchable page {page_index + 1}")


def test_output_is_images_not_vectors():
    """billofsale.manuscript-scan / vintage.period-honest-scan: the pages come
    back as embedded JPEGs. A represented era that predates PDF (1993) cannot
    honestly ship as a vector file — that is the tell, not the avoidance."""
    out = scan.rescan(_vector(2), rng=random.Random(1), metadata=META,
                      text_layer=_text_layer)
    assert out.count(b"/DCTDecode") >= 2, "each page must be a JPEG"
    assert len(re.findall(rb"/Subtype\s*/Image", out)) >= 2
    assert pdfium.PdfDocument(io.BytesIO(out)).__len__() == 2


def test_sheet_size_is_preserved():
    """The scanner does not resize the paper: a folio stays folio and letter
    stays letter. Rescanning to a fixed page size silently reformats every
    artifact whose substrate is the point — a membrane rendered onto US Letter
    is exactly the round-8 substrate tell."""
    folio = (864.0, 558.0)                      # landscape membrane
    out = scan.rescan(_vector(1, size=folio), rng=random.Random(2),
                      metadata=META, text_layer=_text_layer)
    w, h = pdfium.PdfDocument(io.BytesIO(out))[0].get_size()
    assert (round(w), round(h)) == (round(folio[0]), round(folio[1]))
    assert w > h, "a landscape source must not come back portrait"


def test_ocr_layer_is_present_and_invisible():
    """The invisible (render mode 3) text layer is what a Paper-Capture
    workflow leaves behind. Without it the artifact is unsearchable, which is
    itself a tell; with it visible, the page is obviously composited."""
    out = scan.rescan(_vector(2), rng=random.Random(3), metadata=META,
                      text_layer=_text_layer)
    from mattermill import lens
    stream = lens._flate_streams(out).decode("latin-1", "replace")
    assert "3 Tr" in stream, "the OCR layer must be render mode 3"
    doc = pdfium.PdfDocument(io.BytesIO(out))
    text = " ".join((p.get_textpage().get_text_range() or "") for p in doc)
    assert "searchable page 1" in text and "searchable page 2" in text


def test_metadata_dates_the_digitisation():
    """Invariant 6: metadata describes the artifact as a FILE — when it was
    captured — never the era the document claims. ModDate equals CreationDate
    for a flattened export, and never the epoch placeholder."""
    out = scan.rescan(_vector(1), rng=random.Random(4), metadata=META,
                      text_layer=_text_layer)
    created = re.search(rb"/CreationDate \((D:[0-9]+)", out).group(1)
    modified = re.search(rb"/ModDate \((D:[0-9]+)", out).group(1)
    assert created == modified
    assert int(created[2:6]) >= 1993, "PDF did not exist before 1993"
    assert not created.startswith(b"D:00000000")
    assert re.search(rb"/Producer \(([^)]*)\)", out).group(1).decode() \
        == META["producer"]


def test_seeded_and_texture_actually_varies():
    """seeded.everywhere: the same rng reproduces the scan byte for byte, and
    a different one does not. Determinism that is really constancy would make
    the seed decorative and every replayed measurement meaningless."""
    v = _vector(1)
    a = scan.rescan(v, rng=random.Random(7), metadata=META,
                    text_layer=_text_layer)
    b = scan.rescan(v, rng=random.Random(7), metadata=META,
                    text_layer=_text_layer)
    c = scan.rescan(v, rng=random.Random(8), metadata=META,
                    text_layer=_text_layer)
    assert a == b, "same seed must reproduce the scan exactly"
    assert a != c, "a different seed must change the scan texture"


def test_scan_page_jpeg_is_seeded_and_lossy():
    """The per-page primitive is itself seeded, so a caller that scans pages
    independently still gets a reproducible artifact."""
    from PIL import Image
    img = Image.new("L", (200, 260), color=255)
    for x in range(40, 160):                     # something to compress
        img.putpixel((x, 130), 0)
    a = scan.scan_page_jpeg(img, random.Random(5))
    b = scan.scan_page_jpeg(img, random.Random(5))
    c = scan.scan_page_jpeg(img, random.Random(6))
    assert a == b and a != c
    assert a[:2] == b"\xff\xd8", "must be JPEG"
    assert Image.open(io.BytesIO(a)).mode in ("L", "RGB")


def _archival_source() -> Image.Image:
    image = Image.new("RGB", (420, 560), (246, 237, 205))
    draw = ImageDraw.Draw(image)
    for y in range(80, 500, 34):
        draw.line((32, y, 388, y), fill=(170, 93, 82), width=2)
    draw.line((70, 35, 70, 525), fill=(77, 111, 142), width=2)
    draw.text((96, 112), "S-2 fast 56.8 sec", fill=(24, 34, 53))
    return image


def test_archival_color_separation():
    """scan.archival-color-separation: paper, marks and bed remain chromatically distinct."""
    captured = Image.open(io.BytesIO(scan.scan_page_jpeg(
        _archival_source(), random.Random(41),
        profile=scan.ARCHIVAL_COLOR_PROFILE,
    ))).convert("RGB")
    means = ImageStat.Stat(captured).mean
    assert max(means) - min(means) > 5.0
    center = captured.crop((80, 55, 340, 505))
    red, _green, blue = center.split()
    assert ImageStat.Stat(red).mean[0] != pytest.approx(
        ImageStat.Stat(blue).mean[0], abs=2,
    )


def test_archival_object_boundary():
    """scan.object-boundary: the entire sheet sits inside a visible capture bed."""
    captured = Image.open(io.BytesIO(scan.scan_page_jpeg(
        _archival_source(), random.Random(42),
        profile=scan.ARCHIVAL_COLOR_PROFILE,
    ))).convert("RGB")
    gray = captured.convert("L")
    corners = [gray.getpixel(point)
               for point in ((2, 2), (417, 2), (2, 557), (417, 557))]
    center = ImageStat.Stat(gray.crop((100, 100, 320, 460))).mean[0]
    assert max(corners) < center - 70
    assert gray.crop((18, 18, 402, 542)).getbbox() is not None
    bound = Image.open(io.BytesIO(scan.scan_page_jpeg(
        _archival_source(), random.Random(42),
        profile=scan.ARCHIVAL_COLOR_PROFILE,
        capture_context=scan.BOUND_LEFT,
    ))).convert("L")
    assert bound.tobytes() != gray.tobytes()
    left_gutter = ImageStat.Stat(bound.crop((22, 55, 58, 505))).mean[0]
    right_edge = ImageStat.Stat(bound.crop((362, 55, 398, 505))).mean[0]
    assert left_gutter < right_edge - 4


def test_archival_material_variation_is_coherent():
    """scan.coherent-material-variation: aging is low-frequency material behavior, not uniform speckle."""
    captured = Image.open(io.BytesIO(scan.scan_page_jpeg(
        _archival_source(), random.Random(43),
        profile=scan.ARCHIVAL_COLOR_PROFILE,
    ))).convert("L")
    paper = captured.crop((85, 65, 335, 500))
    low_frequency = paper.filter(ImageFilter.GaussianBlur(11))
    assert ImageStat.Stat(low_frequency).stddev[0] > 2.0
    assert ImageStat.Stat(low_frequency).stddev[0] > \
        ImageStat.Stat(paper).stddev[0] * 0.08


def test_archival_profile_is_cross_process_deterministic():
    """scan.archival-profile-determinism: identical profile inputs are byte-stable across processes."""
    script = """
import hashlib, random
from PIL import Image, ImageDraw
from mattermill import scan
image = Image.new('RGB', (420, 560), (246, 237, 205))
draw = ImageDraw.Draw(image)
draw.line((32, 80, 388, 80), fill=(170, 93, 82), width=2)
draw.text((96, 112), 'S-2 fast 56.8 sec', fill=(24, 34, 53))
data = scan.scan_page_jpeg(image, random.Random(44), profile=scan.ARCHIVAL_COLOR_PROFILE)
print(hashlib.sha256(data).hexdigest())
"""
    runs = [subprocess.check_output([sys.executable, "-c", script], text=True)
            for _ in range(2)]
    assert runs[0] == runs[1]


def test_default_profile_preserves_existing_bytes():
    """scan.default-profile-backcompatibility: opting in does not change existing emitters."""
    output = scan.rescan(
        _vector(1), rng=random.Random(11), metadata=META, dpi=110,
    )
    assert hashlib.sha256(output).hexdigest() == \
        "635e991973e028210f6db629f72fe2008ede837f80c1995bd606622bac1eb2ca"


@pytest.mark.parametrize("dpi", [110, 150])
def test_dpi_changes_resolution_not_page_size(dpi):
    """Raster resolution is a quality knob; the sheet is a fact about the
    object. Raising dpi must not silently reflow the page."""
    out = scan.rescan(_vector(1), rng=random.Random(9), metadata=META,
                      text_layer=_text_layer, dpi=dpi)
    w, h = pdfium.PdfDocument(io.BytesIO(out))[0].get_size()
    assert (round(w), round(h)) == (round(letter[0]), round(letter[1]))
