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

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas

from . import legalpdf

PAGE_W, PAGE_H = letter
DEFAULT_PROFILE = "office_grayscale"
ARCHIVAL_COLOR_PROFILE = "archival_color"
SCAN_PROFILES = frozenset({DEFAULT_PROFILE, ARCHIVAL_COLOR_PROFILE})
LOOSE_SHEET = "loose_sheet"
BOUND_LEFT = "bound_left"
BOUND_RIGHT = "bound_right"
CAPTURE_CONTEXTS = frozenset({LOOSE_SHEET, BOUND_LEFT, BOUND_RIGHT})


def _default_scan_page_jpeg(img: Image.Image, rng: random.Random) -> bytes:
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


def _coherent_field(size: tuple[int, int], rng: random.Random, *,
                    cells: tuple[int, int], floor: int, span: int) -> Image.Image:
    """Seeded low-frequency material field, expanded without pixel noise."""
    count = cells[0] * cells[1]
    raw = Image.frombytes("L", cells, rng.randbytes(count))
    raw = raw.filter(ImageFilter.GaussianBlur(1.2))
    raw = raw.resize(size, Image.Resampling.BICUBIC)
    return raw.point(lambda value: floor + int(value * span / 255))


def _edge_field(size: tuple[int, int], *, bound_edge: str | None) -> Image.Image:
    """Return deterministic handling darkening attached to physical edges."""
    w, h = size
    mask = Image.new("L", size, 0)
    pixels = mask.load()
    edge_width = max(6, w // 38)
    gutter_width = max(edge_width, w // 12)
    for y in range(h):
        for x in range(w):
            distance = min(x, y, w - 1 - x, h - 1 - y)
            value = max(0, 28 - round(28 * distance / edge_width))
            if bound_edge == "left":
                value += max(0, 42 - round(42 * x / gutter_width))
            elif bound_edge == "right":
                value += max(0, 42 - round(42 * (w - 1 - x) / gutter_width))
            pixels[x, y] = min(76, value)
    return mask.filter(ImageFilter.GaussianBlur(max(1.0, w / 520)))


def _irregular_sheet_mask(size: tuple[int, int], rng: random.Random) -> Image.Image:
    """A complete but imperfectly cut leaf silhouette."""
    w, h = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    step = max(10, h // 44)
    amplitude = max(2, w // 245)
    left = [(rng.randint(0, amplitude), y) for y in range(0, h, step)] + [(0, h - 1)]
    right = [(w - 1 - rng.randint(0, amplitude), y)
             for y in range(h - 1, -1, -step)] + [(w - 1, 0)]
    draw.polygon(left + right, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(0.45))


def _archival_color_page(img: Image.Image, rng: random.Random, *,
                         capture_context: str = LOOSE_SHEET) -> Image.Image:
    """Place a period record in a source-aware photographed capture.

    The source remains fully inside the frame. Variation is attached to the
    sheet, its folds, edges and handling path; the capture bed receives a
    different material field. This is deliberately unlike the default office
    scanner profile and is opt-in so existing emitters retain their bytes.
    """
    if capture_context not in CAPTURE_CONTEXTS:
        raise ValueError(f"unknown capture context: {capture_context!r}")
    source = img.convert("RGB")
    w, h = source.size
    bound_edge = ("left" if capture_context == BOUND_LEFT else
                  "right" if capture_context == BOUND_RIGHT else None)

    # Preserve the source's colored ink while shifting neutral paper toward a
    # warm archival stock. Dark marks remain blue-black instead of being
    # collapsed into the same neutral ramp as the substrate.
    warm = ImageOps.colorize(
        source.convert("L"), black=(18, 25, 31), white=(229, 225, 181)
    )
    source = Image.blend(warm, source, 0.30)
    source = ImageEnhance.Color(source).enhance(1.28)
    paper_field = _coherent_field(
        source.size, rng, cells=(31, 43), floor=230, span=25
    )
    source = ImageChops.multiply(source, paper_field.convert("RGB"))

    # Long fibers, edge wear, and weak verso show-through are attached to the
    # leaf.  Nothing here is a free-floating circular "old paper" decoration.
    material = Image.new("RGBA", source.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(material, "RGBA")
    for _ in range(rng.randint(18, 29)):
        y = rng.randrange(max(2, h // 30), max(3, h - h // 30))
        x = rng.randrange(0, max(1, w - w // 4))
        length = rng.randrange(max(8, w // 18), max(9, w // 4))
        draw.line(
            (x, y, min(w, x + length), y + rng.choice((-1, 0, 1))),
            fill=(118, 91, 57, rng.randrange(4, 12)), width=1,
        )
    material = material.filter(ImageFilter.GaussianBlur(max(0.8, w / 900)))
    source = Image.alpha_composite(source.convert("RGBA"), material).convert("RGB")

    edge_tone = Image.new("RGBA", source.size, (82, 62, 37, 0))
    edge_tone.putalpha(_edge_field(source.size, bound_edge=bound_edge))
    source = Image.alpha_composite(source.convert("RGBA"), edge_tone).convert("RGB")

    # A bound working volume commonly shows faint structure from the reverse
    # side.  Deriving it from the source luminance keeps the variation causal
    # and local without inventing readable words.
    if bound_edge is not None:
        verso = ImageOps.invert(source.convert("L")).transpose(
            Image.Transpose.FLIP_LEFT_RIGHT
        ).filter(ImageFilter.GaussianBlur(max(1.5, w / 360)))
        verso = verso.point(lambda value: int(value * 0.035))
        ghost = Image.new("RGBA", source.size, (73, 68, 51, 0))
        ghost.putalpha(verso)
        source = Image.alpha_composite(source.convert("RGBA"), ghost).convert("RGB")

    # Folds have coupled highlights and troughs; independent speckle cannot
    # create this material geometry. Bound ledgers use the source-observed
    # vertical cockling, while loose sheets retain one handling fold.
    fold = Image.new("RGBA", source.size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(fold, "RGBA")
    if bound_edge is None:
        fold_y = rng.randrange(2 * h // 5, 4 * h // 5)
        slope = rng.choice((-1, 1)) * rng.uniform(0.001, 0.006)
        end_y = fold_y + slope * w
        fd.line((0, fold_y - 2, w, end_y - 2), fill=(255, 248, 218, 24), width=2)
        fd.line((0, fold_y + 2, w, end_y + 2), fill=(77, 57, 39, 23), width=2)
    else:
        for _ in range(rng.randint(2, 4)):
            fold_x = rng.randrange(w // 5, 9 * w // 10)
            drift = rng.randint(-max(4, w // 55), max(5, w // 55))
            start_y = rng.randrange(0, max(1, h // 5))
            end_y = rng.randrange(4 * h // 5, h + 1)
            span = end_y - start_y
            points = [
                (fold_x, start_y),
                (fold_x + drift // 2, start_y + span // 3),
                (fold_x - drift // 3, start_y + 2 * span // 3),
                (fold_x + drift, end_y),
            ]
            fd.line([(x - 1, y) for x, y in points],
                    fill=(255, 249, 213, rng.randrange(10, 18)), width=1)
            fd.line([(x + 1, y) for x, y in points],
                    fill=(72, 57, 39, rng.randrange(9, 17)), width=1)
    fold = fold.filter(ImageFilter.GaussianBlur(max(0.7, w / 1100)))
    source = Image.alpha_composite(source.convert("RGBA"), fold)

    # Frame the complete object against a distinct capture bed. Bound contexts
    # include a neighboring leaf and a gutter; loose sheets retain four free
    # edges. In both cases the full source stays inside the PDF crop.
    inset_x = max(12, int(w * rng.uniform(0.030, 0.046)))
    inset_y = max(12, int(h * rng.uniform(0.024, 0.038)))
    if bound_edge is not None:
        inset_x = max(16, int(w * rng.uniform(0.050, 0.066)))
    target = (w - 2 * inset_x, h - 2 * inset_y)
    source.thumbnail(target, Image.Resampling.LANCZOS)
    angle = rng.uniform(-0.34, 0.34)
    source = source.rotate(
        angle, resample=Image.Resampling.BICUBIC, expand=True,
        fillcolor=(0, 0, 0, 0),
    )
    bed_field = _coherent_field((w, h), rng, cells=(18, 24), floor=184, span=24)
    bed = ImageOps.colorize(
        bed_field, black=(26, 28, 27), white=(54, 56, 51)
    ).convert("RGBA")
    x = (w - source.width) // 2
    y = (h - source.height) // 2
    if bound_edge is not None:
        leaf = Image.new("RGBA", (source.width, source.height), (213, 207, 166, 255))
        leaf_shadow = Image.new("RGBA", (source.width, source.height), (39, 35, 28, 60))
        offset = max(7, w // 42)
        leaf_x = x - offset if bound_edge == "left" else x + offset
        bed.alpha_composite(leaf_shadow, (leaf_x, y + max(3, h // 180)))
        bed.alpha_composite(leaf, (leaf_x, y))

    source.putalpha(_irregular_sheet_mask(source.size, rng))
    alpha = source.getchannel("A")
    shadow = Image.new("L", (w, h), 0)
    shadow.paste(alpha, (x + max(2, w // 280), y + max(3, h // 230)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(3.0, w / 175)))
    shadow_rgba = Image.new("RGBA", (w, h), (12, 10, 8, 0))
    shadow_rgba.putalpha(shadow.point(lambda value: int(value * 0.46)))
    bed = Image.alpha_composite(bed, shadow_rgba)
    bed.alpha_composite(source, (x, y))

    if bound_edge is not None:
        # The dark gutter and its coupled highlight follow the binding edge;
        # they are capture geometry, not an arbitrary page-wide vignette.
        gutter = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(gutter, "RGBA")
        gx = x + max(2, source.width // 55) if bound_edge == "left" \
            else x + source.width - max(2, source.width // 55)
        width = max(5, source.width // 32)
        gd.line((gx, y, gx, y + source.height), fill=(29, 27, 21, 128), width=width)
        highlight_x = gx + width // 2 if bound_edge == "left" else gx - width // 2
        gd.line((highlight_x, y + 2, highlight_x, y + source.height - 2),
                fill=(245, 239, 197, 48), width=max(2, width // 4))
        gutter = gutter.filter(ImageFilter.GaussianBlur(max(1.5, w / 260)))
        bed = Image.alpha_composite(bed, gutter)
    return bed.convert("RGB")


def scan_page_jpeg(img: Image.Image, rng: random.Random, *,
                   profile: str = DEFAULT_PROFILE,
                   capture_context: str = LOOSE_SHEET) -> bytes:
    """Capture one page through the selected deterministic device profile."""
    if profile == DEFAULT_PROFILE:
        return _default_scan_page_jpeg(img, rng)
    if profile != ARCHIVAL_COLOR_PROFILE:
        raise ValueError(f"unknown scan profile: {profile!r}")
    captured = _archival_color_page(
        img, rng, capture_context=capture_context
    )
    captured = ImageEnhance.Contrast(captured).enhance(rng.uniform(1.01, 1.045))
    captured = captured.filter(ImageFilter.GaussianBlur(0.22))
    buf = io.BytesIO()
    captured.save(buf, "JPEG", quality=88, subsampling=0, optimize=False)
    return buf.getvalue()


def rescan(vector: bytes, *, rng: random.Random, metadata: dict,
           text_layer=None, dpi: int = 150,
           profile: str = DEFAULT_PROFILE,
           capture_context: str | object = LOOSE_SHEET) -> bytes:
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
        context = capture_context(idx) if callable(capture_context) else capture_context
        jpeg = scan_page_jpeg(
            page.render(scale=dpi / 72).to_pil(), rng, profile=profile,
            capture_context=context,
        )
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
