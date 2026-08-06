"""Image assets for document realism: signatures, stamps, seals.

Two sources, one contract (seeded PNG bytes out):

1. procedural (this module, Pillow): seeded ink-stroke signatures and stamp
   boxes. v0 texture — plausible at document scale, fully in-repo.
2. nano-banana (external, asset-authoring time only): richer photographic
   assets (wet-ink, seals, equipment photos for appraisal exhibits). NEVER a
   worldgen runtime dependency — generated assets are committed to
   foundry/assets/ and sampled under seed control. Requires a Gemini API key
   provided by the operator; generation scripts live outside the seeded path.
"""

from __future__ import annotations

import io
import hashlib
import math
import random
from importlib import resources

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


def _smooth_path(rng: random.Random, w: int, h: int, n_points: int) -> list[tuple]:
    """A flowing hand-like stroke: random walk with sinusoidal smoothing."""
    pts = []
    x, y = w * 0.08, h * rng.uniform(0.45, 0.65)
    phase = rng.uniform(0, math.pi)
    for i in range(n_points):
        x += w * 0.9 / n_points * rng.uniform(0.7, 1.3)
        y += math.sin(i * 0.55 + phase) * h * 0.09 + rng.uniform(-h * 0.06, h * 0.06)
        y = max(h * 0.12, min(h * 0.88, y))
        pts.append((x, y))
    return pts


_ASCENDERS = set("bdhklt")
_DESCENDERS = set("gjpqyz")
_WIDE = {"m": 3, "w": 3, "n": 2, "u": 2, "h": 2}


def _spline(pts: list[tuple], samples: int = 12) -> list[tuple]:
    """Catmull-Rom through the control points — turns letter skeletons into
    flowing pen strokes."""
    if len(pts) < 3:
        return pts
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(len(P) - 3):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for j in range(samples):
            t = j / samples
            t2, t3 = t * t, t * t * t
            out.append((
                0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)))
    out.append(pts[-1])
    return out


def _name_strokes(name: str, rng: random.Random, h: float):
    """Skeleton strokes for a pseudo-cursive rendition of `name`: capital
    initials, x-height humps with the name's true ascender/descender rhythm,
    trailing compression, pen lifts between words, i-dots and t-bars.
    Returns (strokes, extras) in un-slanted letter space (y up = negative)."""
    strokes, extras = [], []
    x = 0.0
    letters = [ch for w in name.split() for ch in w]
    n_total = max(len(letters), 1)
    idx = 0
    cap_style = rng.randrange(3)
    for word in name.split():
        pts = []
        word = word.rstrip(".")
        for k, ch in enumerate(word):
            comp = 1.0 - 0.45 * (idx / n_total)          # trailing compression
            amp = h * (1.0 - 0.25 * (idx / n_total))
            j = lambda s=0.08: rng.uniform(-s, s) * h
            if k == 0 and ch.isupper():
                w_ = h * rng.uniform(1.0, 1.3) * comp
                top = -amp * rng.uniform(2.2, 2.7)
                if cap_style == 0:      # sweeping oval entry
                    pts += [(x, -amp * 0.4 + j()), (x + w_ * 0.2, top + j()),
                            (x + w_ * 0.7, top * 0.75 + j()),
                            (x + w_ * 0.5, -amp * 0.3 + j()), (x + w_, j())]
                elif cap_style == 1:    # tall downstroke with lead-in hook
                    pts += [(x + w_ * 0.45, top * 0.85 + j()),
                            (x + w_ * 0.2, top + j()),
                            (x + w_ * 0.55, -amp * 0.9 + j()), (x + w_ * 0.75, j())]
                else:                   # angular flourish
                    pts += [(x, top * 0.6 + j()), (x + w_ * 0.5, top + j()),
                            (x + w_ * 0.35, -amp * 0.8 + j()), (x + w_, j())]
                x += w_
            else:
                lo = ch.lower()
                humps = _WIDE.get(lo, 1)
                w_ = h * 0.52 * humps * comp
                if lo in _ASCENDERS:
                    pts += [(x + w_ * 0.3, -amp * rng.uniform(1.9, 2.3) + j()),
                            (x + w_ * 0.55, -amp * 0.8 + j()), (x + w_, j())]
                    if lo == "t":
                        extras.append([(x - h * 0.15, -amp * 1.35),
                                       (x + w_ + h * 0.25, -amp * 1.5)])
                elif lo in _DESCENDERS:
                    pts += [(x + w_ * 0.35, -amp * 0.85 + j()),
                            (x + w_ * 0.6, amp * rng.uniform(1.1, 1.5) + j()),
                            (x + w_ * 0.8, amp * 0.5 + j()), (x + w_, j())]
                elif lo == "i":
                    pts += [(x + w_ * 0.5, -amp * 0.95 + j()), (x + w_, j())]
                    if rng.random() < 0.8:
                        extras.append([(x + w_ * 0.45, -amp * 1.5),
                                       (x + w_ * 0.55, -amp * 1.55)])
                else:
                    for hh in range(humps):
                        pts += [(x + w_ * (hh + 0.5) / humps, -amp * 0.9 + j()),
                                (x + w_ * (hh + 1.0) / humps, j())]
                x += w_
            idx += 1
        if pts:
            pts.insert(0, (pts[0][0] - h * 0.35, h * 0.3))   # entry stroke
            strokes.append(pts)
        x += h * rng.uniform(0.5, 0.8)                        # pen lift gap
    # terminal tail off the last stroke
    if strokes:
        lx, ly = strokes[-1][-1]
        strokes[-1] += [(lx + h * 0.5, ly - h * rng.uniform(0.1, 0.5)),
                        (lx + h * rng.uniform(0.9, 1.5), ly + h * 0.2)]
    return strokes, extras


def _cursive_signature(name: str, rng: random.Random, ink: tuple) -> Image.Image:
    h = 30.0
    strokes, extras = _name_strokes(name, rng, h)
    slant = math.tan(math.radians(rng.uniform(10, 24)))
    drift = rng.uniform(-0.04, 0.02)
    sheared = []
    for s in strokes:
        sheared.append([(px - py * slant, py + px * drift)
                        for px, py in _spline(s)])
    for e in extras:
        sheared.append([(px - py * slant, py + px * drift) for px, py in e])
    # optional paraph: underline swoosh beneath the name
    xs = [p[0] for s in sheared for p in s]
    ys = [p[1] for s in sheared for p in s]
    if rng.random() < 0.6 and xs:
        y0 = max(ys) + h * 0.35
        x0, x1 = min(xs) + h * 0.3, max(xs) - h * rng.uniform(0.0, 1.0)
        sheared.append(_spline([(x1, y0 - h * 0.1), (x0 + (x1 - x0) * 0.4, y0),
                                (x0, y0 - h * rng.uniform(0.0, 0.3))]))
        ys.append(y0 + h * 0.2)
    # fit into canvas
    pad = 14
    W, H = 560, 190
    sx = (W - 2 * pad) / max(max(xs) - min(xs), 1e-6)
    sy = (H - 2 * pad) / max(max(ys) - min(ys), 1e-6)
    sc = min(sx, sy, 3.2)
    ox, oy = min(xs), min(ys)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for s in sheared:
        pts = [((px - ox) * sc + pad, (py - oy) * sc + pad) for px, py in s]
        for i in range(1, len(pts)):
            dy = pts[i][1] - pts[i - 1][1]
            dx = pts[i][0] - pts[i - 1][0]
            speed = math.hypot(dx, dy) + 1e-6
            width = max(1, int(round(2.9 * (0.55 + 0.75 * max(dy, 0) / speed))))
            draw.line([pts[i - 1], pts[i]], fill=ink + (235,), width=width)
    img = img.filter(ImageFilter.GaussianBlur(0.55))
    return img.rotate(rng.uniform(-2.0, 2.0), expand=True,
                      fillcolor=(0, 0, 0, 0))


def signature_png(seed: int, *, name: str | None = None,
                  ink: tuple = (10, 20, 90)) -> bytes:
    """Procedural wet-ink signature. With `name`, synthesizes pseudo-cursive
    from the signer's actual letters — capital initials, the name's true
    ascender/descender rhythm, slant, trailing compression, i-dots, t-bars,
    pen lifts between words, optional paraph. Without, the legacy abstract
    scrawl (kept for existing artifacts)."""
    rng = random.Random(seed if name is None else f"{seed}:{name}")
    if name is not None:
        img = _cursive_signature(name, rng, ink)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()
    w, h = 480, 160
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for _ in range(rng.randint(2, 4)):
        pts = _smooth_path(rng, w, h, rng.randint(24, 40))
        for i in range(1, len(pts)):
            width = max(1, int(3.2 * (0.55 + 0.45 * math.sin(i * 0.8))))
            draw.line([pts[i - 1], pts[i]], fill=ink + (235,), width=width)
    # underline flourish (common in real signatures)
    if rng.random() < 0.6:
        y = h * rng.uniform(0.72, 0.85)
        draw.line([(w * 0.1, y), (w * rng.uniform(0.5, 0.9), y + rng.uniform(-4, 4))],
                  fill=ink + (220,), width=2)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img = img.rotate(rng.uniform(-3.5, 3.5), expand=True, fillcolor=(0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


_WORKING_HAND_FONTS = (
    "Caveat-Regular.ttf",
    "PatrickHand-Regular.ttf",
    "HomemadeApple-Regular.ttf",
)


def handwriting_style(writer: str) -> dict[str, object]:
    """Return the stable physical style assigned to one working hand.

    The writer identity, rather than the field seed, chooses the glyph source,
    slant, tracking, pressure and default ink.  A writer therefore keeps one
    recognizable hand across documents while each entry still has small
    seeded pen-placement variation.
    """
    if not writer.strip():
        raise ValueError("a working-hand writer identity is required")
    digest = hashlib.sha256(writer.casefold().strip().encode("utf-8")).digest()
    palettes = (
        (24, 30, 45),      # blue-black fountain ink
        (45, 39, 34),      # aged black/brown ink
        (31, 38, 43),      # neutral iron-black ink
        (48, 45, 55),      # faint violet-black ink
    )
    return {
        "font": _WORKING_HAND_FONTS[digest[0] % len(_WORKING_HAND_FONTS)],
        "slant": -0.10 + (digest[1] / 255.0) * 0.22,
        "tracking": 0.91 + (digest[2] / 255.0) * 0.13,
        "pressure": 178 + digest[3] % 34,
        "stroke_width": 0,
        "ink": palettes[digest[5] % len(palettes)],
        "join_probability": 0.22 + (digest[7] / 255.0) * 0.46,
        "nib_bias": -0.045 + (digest[8] / 255.0) * 0.09,
    }


def _working_font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    path = resources.files("mattermill").joinpath("data", "fonts", filename)
    return ImageFont.truetype(str(path), size=size)


def _working_glyph(font: ImageFont.FreeTypeFont, ch: str, *,
                   rng: random.Random, style: dict[str, object],
                   color: tuple[int, int, int]) -> Image.Image:
    """Instantiate one glyph through a seeded pen event.

    The bundled face supplies a legible skeleton, but the displayed mark is a
    locally rescaled, sheared, rotated and pressure-varied instance. Repeated
    letters therefore do not reuse one font mask, while the writer-level
    slant, nib and joining tendencies remain stable.
    """
    canvas = Image.new("RGBA", (180, 170), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    pressure = max(154, min(224, int(style["pressure"]) + rng.randint(-18, 13)))
    stroke = int(style["stroke_width"])
    draw.text(
        (28, 106), ch, font=font, anchor="ls", fill=color + (pressure,),
        stroke_width=stroke,
        stroke_fill=color + (max(156, pressure - 14),),
    )
    bbox = canvas.getbbox()
    if bbox is None:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    glyph = canvas.crop((max(0, bbox[0] - 8), max(0, bbox[1] - 8),
                         min(canvas.width, bbox[2] + 8),
                         min(canvas.height, bbox[3] + 8)))
    width_factor = rng.uniform(0.77, 1.22)
    height_factor = rng.uniform(0.88, 1.11)
    glyph = glyph.resize(
        (max(2, round(glyph.width * width_factor)),
         max(2, round(glyph.height * height_factor))),
        Image.Resampling.BICUBIC,
    )
    local_shear = float(style["nib_bias"]) + rng.uniform(-0.055, 0.055)
    extra = int(abs(local_shear) * glyph.height) + 4
    glyph = glyph.transform(
        (glyph.width + extra, glyph.height), Image.Transform.AFFINE,
        (1, -local_shear, extra if local_shear > 0 else 0, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )
    glyph = glyph.rotate(
        rng.uniform(-3.1, 3.1), resample=Image.Resampling.BICUBIC,
        expand=True, fillcolor=(0, 0, 0, 0),
    )
    # A light upstroke occasionally loses an edge pixel.  This changes the
    # physical outline without the uniform inflation that made earlier output
    # look like a modern felt-tip marker.
    if rng.random() < 0.24 and min(glyph.size) > 4:
        alpha = glyph.getchannel("A").filter(ImageFilter.MinFilter(3))
        if alpha.getbbox() is not None:
            glyph.putalpha(alpha)
    # Low-frequency deposition variation follows the nib path within each
    # mark. It remains subtle at record scale but avoids a perfectly uniform
    # digital stroke even when the glyph skeleton is similar.
    alpha = glyph.getchannel("A")
    deposition = Image.new("L", glyph.size, 255)
    dd = ImageDraw.Draw(deposition)
    phase = rng.uniform(0, math.tau)
    for y in range(glyph.height):
        strength = 218 + round(25 * math.sin(phase + y * 0.19))
        dd.line((0, y, glyph.width, y), fill=max(186, min(244, strength)))
    glyph.putalpha(ImageChops.multiply(alpha, deposition))
    bbox = glyph.getbbox()
    return glyph.crop(bbox) if bbox else glyph


def handwriting_png(seed: int, *, text: str, writer: str,
                    ink: tuple[int, int, int] | None = None) -> bytes:
    """Render legible seeded working text in a stable writer-specific hand.

    This is deliberately separate from :func:`signature_png`: record entries
    instantiate the actual glyphs, numerals and punctuation supplied by the
    caller instead of turning an entire field into a signature-like flourish.
    Font files are bundled authoring assets, so the renderer remains offline.
    """
    if not text:
        raise ValueError("working-hand text must not be empty")
    style = handwriting_style(writer)
    font = _working_font(str(style["font"]), 72)
    rng = random.Random(f"working-hand:{seed}:{writer}:{text}")
    color = tuple(ink or style["ink"])
    tracking = float(style["tracking"])

    if text == '"':
        # Ditto marks in working ledgers are two quick pen gestures, not a
        # repeated typographic quotation glyph. Their span, pressure, angle,
        # and relative baseline vary per entry while retaining the writer's
        # stable slant and ink.
        image = Image.new("RGBA", (58, 54), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        for index in range(2):
            x = 15 + index * rng.randint(17, 22) + rng.randint(-2, 2)
            y0 = rng.randint(11, 17)
            y1 = rng.randint(34, 43)
            lean = rng.randint(4, 10)
            alpha = max(146, min(222, int(style["pressure"]) + rng.randint(-24, 12)))
            draw.line((x + lean, y0, x, y1), fill=color + (alpha,),
                      width=rng.choice((1, 1, 2)))
        image = image.rotate(
            rng.uniform(-3.5, 3.5), resample=Image.Resampling.BICUBIC,
            expand=True, fillcolor=(0, 0, 0, 0),
        )
        bbox = image.getbbox()
        if bbox:
            image = image.crop(bbox)
        buf = io.BytesIO()
        image.save(buf, "PNG")
        return buf.getvalue()

    advances = [max(8.0, font.getlength(ch) * tracking) for ch in text]
    width = max(32, int(sum(advances) * 1.18 + 76))
    height = 146
    baseline = 102
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    x = 26.0
    previous_alnum = False
    for index, (ch, advance) in enumerate(zip(text, advances)):
        if ch.isspace():
            x += advance
            previous_alnum = False
            continue
        # Low-amplitude, correlated baseline motion reads as ordinary working
        # pen placement at document scale without damaging character identity.
        wave = math.sin(index * 0.72 + (seed % 17)) * 1.9
        y = baseline + wave + rng.uniform(-1.15, 1.15)
        glyph = _working_glyph(font, ch, rng=rng, style=style, color=color)
        if previous_alnum and ch.isalnum() and \
                rng.random() < float(style["join_probability"]):
            join_y = y + rng.uniform(-0.8, 0.8)
            join_alpha = max(112, int(style["pressure"]) - rng.randint(38, 64))
            draw.line(
                (x - max(3.0, advance * 0.16), join_y,
                 x + max(2.0, advance * 0.06), join_y + rng.uniform(-1.0, 1.0)),
                fill=color + (join_alpha,), width=1,
            )
        descender = 7 if ch.lower() in _DESCENDERS else 0
        image.alpha_composite(
            glyph,
            (round(x - 5), round(y - glyph.height + 10 + descender)),
        )
        x += advance * rng.uniform(0.87, 1.13) + rng.uniform(-0.65, 0.65)
        previous_alnum = ch.isalnum()

    bbox = image.getbbox()
    if bbox is None:  # pragma: no cover - guarded by nonempty text
        raise ValueError("working-hand text produced no visible glyphs")
    image = image.crop((max(0, bbox[0] - 8), max(0, bbox[1] - 8),
                        min(image.width, bbox[2] + 8), min(image.height, bbox[3] + 8)))

    # Writer-specific shear supplies a stable slant. Pillow's affine matrix
    # maps output coordinates back to source coordinates, hence the negative.
    shear = float(style["slant"])
    extra = int(abs(shear) * image.height) + 6
    image = image.transform(
        (image.width + extra, image.height), Image.Transform.AFFINE,
        (1, -shear, extra if shear > 0 else 0, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )
    image = image.rotate(
        ((hashlib.sha256(writer.encode("utf-8")).digest()[6] / 255.0) - 0.5)
        * 1.8 + rng.uniform(-0.22, 0.22),
        resample=Image.Resampling.BICUBIC, expand=True,
        fillcolor=(0, 0, 0, 0),
    )
    image = image.filter(ImageFilter.GaussianBlur(0.18))
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    buf = io.BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


def stamp_png(seed: int, *, lines: list[str]) -> bytes:
    """Rectangular received/filed stamp: bordered box, small caps lines,
    slight rotation and ink unevenness."""
    rng = random.Random(seed)
    from PIL import ImageFont
    font = ImageFont.load_default()
    w = 360
    h = 40 + 34 * len(lines)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    ink = (140, 20, 20)
    draw.rectangle([4, 4, w - 4, h - 4], outline=ink + (230,), width=3)
    draw.rectangle([9, 9, w - 9, h - 9], outline=ink + (180,), width=1)
    y = 18
    for line in lines:
        # letter-spaced small caps look, properly centered (fits inside box)
        spaced = " ".join(line.upper())
        spacing = max(1, min(2, (w - 40) // max(1, len(spaced))))
        spaced = (" " * spacing).join(line.upper())
        tw = draw.textlength(spaced, font=font)
        draw.text((max(14, (w - tw) / 2), y), spaced, fill=ink + (225,), font=font)
        y += 32
    img = img.filter(ImageFilter.GaussianBlur(0.4))
    img = img.rotate(rng.uniform(-4, 4), expand=True, fillcolor=(0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
