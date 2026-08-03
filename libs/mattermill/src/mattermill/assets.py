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
import math
import random

from PIL import Image, ImageDraw, ImageFilter


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
