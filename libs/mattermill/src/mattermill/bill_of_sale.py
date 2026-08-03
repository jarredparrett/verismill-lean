"""bill_of_sale: a bill of sale of a vessel, England 1642 — seeded.

Built against a SOURCED genre contract
(foundry/reference/templates/bill_of_sale_1642/contract.json): the clause
anatomy and formulas come from a verbatim 1536 High Court of Admiralty
exemplar (Select Pleas in the Court of Admiralty I, no. 15), calibrated to
1640s orthography by printed records of the exact decade (New Haven
1638-1649; Massachusetts Bay vol. I). Nothing is authored from memory.

Round-8 blind review (3 judges, synthetic at 0.95-0.97) drove the repairs
recorded here: price is coupled to the vessel (tuns x a per-tun rate), the
defeasance bond matures only after the warranty year it secures, execution
is literacy-coupled ('hand and seal' vs 'seal and mark' with the scribe's
'marke of' annotation), witness names are engrossed legibly with an
attestation variant, the formula scaffold carries period orthography, the
substrate is toned parchment with fold creases on a folio sheet, and a dorse
endorsement rides on page 2. Regnal/Lady Day dating as before.

Known limitations (open sourcing targets): the body hand is an italic-serif
approximation with word-level jitter, not a true secretary hand, and the
substrate lacks chain lines/show-through — both are tool gaps recorded in
the spec (a manuscript hand engine is the L2 candidate). Per-tun price
rates are a bounded approximation (period vessel-price data is an open data
target). The bond/receipt convention mix (words vs roman numerals) is
exemplar-attested; one round-8 judge flagged it — tension recorded in
contract.json. The double-value penal bond is common-law convention, not
exemplar-attested (OCR doubt). Form B (deed-poll salutation) is an
attested-composite variant.
"""

from __future__ import annotations

import io
import math
import random

from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas

from . import assets, scan

# Geometry from the sourced visual exemplar (the 1613 Blackfriars conveyance,
# provenance.json): an engrossed instrument is a LANDSCAPE membrane, not a
# portrait sheet — long lines run the full width of the skin, the head carries
# the chirograph (indenture) cut, and the foot turns up as a plica carrying the
# seal tag. Signatures sit on the plica; witnesses subscribe the dorse.
MEMBRANE = (864.0, 558.0)            # ~12in x 7.75in skin, landscape
PAGE_W, PAGE_H = MEMBRANE
BLEED = 22.0                         # scanner background outside the skin
ML = 54.0                            # manuscript left margin
LEADING = 16.5
CHARS = 150                          # engrossed line width across the skin
PLICA_H = 96.0                       # the turn-up carrying seal tag + signature
SKIN_Y0 = 70.0                       # skin's foot; the seal tag hangs below it
HAND = ("Times-Italic", 10.5)
DISPLAY = ("Times-BoldItalic", 16.0) # the engrosser's display script
TEXT = ("Times-Roman", 10.5)

# Formula words the engrosser writes LARGE, in display script — the exemplar
# emphasises the instrument's joints, not arbitrary phrases.
# The beheaded variants are the same runs after the cadel initial has taken
# the first letter ("This bill made" -> a drawn T, then "his bill made").
DISPLAY_RUNS = ["This bill made", "his bill made",
                "To all to whom these presents shall come",
                "o all to whom these presents shall come",
                "witnesseth", "Know ye", "And the saide", "And also",
                "In witnesse whereof", "Sealed and delivered"]

# ---------------------------------------------------------------------------
# Texture pools — invented, period-plausible (no exemplar parties, no real
# transactions; ports/counties are factual geography)
# ---------------------------------------------------------------------------

FORENAMES = ["William", "Thomas", "John", "Robert", "Edward", "Henry",
             "George", "Richard", "Samuel", "Edmund", "Walter", "Nicholas"]
SURNAMES = ["Carter", "Whitfield", "Marlow", "Draper", "Fletcher", "Colman",
            "Granger", "Tanner", "Harpur", "Redman", "Sexton", "Palfrey",
            "Alden", "Crowe", "Burrell", "Stanhope", "Ledbetter", "Vinter"]
PLACES = [("Gravesend", "Kent"), ("Erith", "Kent"), ("Barking", "Essex"),
          ("Ratcliff", "Middlesex"), ("Wapping", "Middlesex"),
          ("Limehouse", "Middlesex"), ("Deptford", "Kent"),
          ("Plymouth", "Devon"), ("Dartmouth", "Devon"),
          ("Bristol", "Gloucestershire"), ("Southampton", "Hampshire"),
          ("Ipswich", "Suffolk"), ("King's Lynn", "Norfolk"),
          ("Hull", "Yorkshire"), ("Newcastle upon Tyne", "Northumberland"),
          ("Harwich", "Essex"), ("Dover", "Kent"), ("Sandwich", "Kent")]
OCCUPATIONS = ["mariner", "shipwright", "carpenter", "merchant", "yeoman",
               "fisherman", "chandler", "salter", "draper", "ironmonger"]
# (type, tuns range, £/tun band) — rates from the round-8 review's
# £5-10/tun building-cost anchor, discounted for resale; a bounded
# approximation pending period vessel-price data (open data target).
VESSEL_TYPES = [("ship", 80, 400, 6, 10), ("bark", 20, 60, 5, 9),
                ("pinnace", 15, 50, 5, 9), ("ketch", 15, 40, 5, 9),
                ("flyboat", 40, 120, 4, 8), ("pink", 40, 120, 4, 8),
                ("hoy", 10, 30, 4, 7), ("shallop", 3, 8, 4, 8)]
VESSEL_NAMES = ["Hopewell", "Blessing", "Increase", "Fortune", "Content",
                "Unity", "Prosperous", "Dolphin", "Swan", "Endeavour",
                "Mary and Anne", "Elizabeth", "Sarah", "Judith", "Patience"]
SHARES = [(2, "one half", "half a", "moiety"),
          (4, "one fourth part", "one fourth part of a", "one fourth part"),
          (8, "one eighth part", "one eighth part of a", "one eighth part"),
          (16, "one sixteenth part", "one sixteenth part of a",
           "one sixteenth part"),
          (32, "one thirty-second part", "one thirty-second part of a",
           "one thirty-second part")]
FIXED_FEASTS = [("the Purification of the Virgin Mary", 2, 2),
                ("the Annunciation of the Virgin Mary", 3, 25),
                ("the Nativity of Saint John the Baptist", 6, 24),
                ("Saint Michael the Archangel", 9, 29),
                ("All Saints", 11, 1),
                ("Saint Martin", 11, 11),
                ("the Nativity of our Lord", 12, 25)]

_ONES = ["one", "two", "three", "four", "five", "six", "seven", "eight",
         "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
         "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty",
         "ninety"]
_ORDS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh",
         "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth",
         "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth",
         "nineteenth", "twentieth", "twenty first", "twenty second",
         "twenty third", "twenty fourth", "twenty fifth", "twenty sixth",
         "twenty seventh", "twenty eighth", "twenty ninth", "thirtieth",
         "thirty first"]
_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def _words(n: int) -> str:
    """320 -> 'three hundred and twenty'."""
    out = []
    if n >= 100:
        out.append(_ONES[n // 100 - 1] + " hundred")
        n %= 100
        if n:
            out.append("and")
    if n >= 20:
        out.append(_TENS[n // 10 - 2])
        n %= 10
    if n:
        out.append(_ONES[n - 1])
    return " ".join(out)


def _roman(n: int) -> str:
    """23 -> 'xxiij' — lowercase roman with terminal j, the period form."""
    vals = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"),
            (90, "xc"), (50, "l"), (40, "xl"), (10, "x"), (9, "ix"),
            (5, "v"), (4, "iv"), (1, "i")]
    out = []
    for v, s in vals:
        while n >= v:
            out.append(s)
            n -= v
    r = "".join(out)
    return r[:-1] + "j" if r.endswith("i") else r


def _julian_easter(year: int) -> tuple[int, int]:
    """Julian Easter (month, day) by the computus — movable feasts are
    computable, not sampled, or the calendar stops being honest."""
    a, b, c = year % 4, year % 7, year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    return (d + e + 114) // 31, (d + e + 114) % 31 + 1


_DIM = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _add_days(month: int, day: int, days: int) -> tuple[int, int]:
    month, day = month - 1, day - 1
    for _ in range(days):
        day += 1
        if day >= _DIM[month]:
            month, day = (month + 1) % 12, 0
    return month + 1, day + 1


def _doy(month: int, day: int) -> int:
    return sum(_DIM[:month - 1]) + day


def _feasts(year_hist: int) -> list[tuple[str, int, int]]:
    em, ed = _julian_easter(year_hist)
    pm, pd = _add_days(em, ed, 49)
    return sorted(FIXED_FEASTS + [("Pentecost", pm, pd)],
                  key=lambda f: (f[1], f[2]))


def _feast_after(month: int, day: int, min_days: int) -> str:
    """The first feast at least `min_days` after the bill date — the bond
    must mature no sooner than the warranty it secures (round-8 tell)."""
    base = _doy(month, day)
    for name, fm, fd in _feasts(1642):
        if _doy(fm, fd) - base >= min_days:
            return name
    for name, fm, fd in _feasts(1643):
        if _doy(fm, fd) + 365 - base >= min_days:
            return name
    raise AssertionError("no feast found")


# ---------------------------------------------------------------------------
# Sampled model — coherent by construction
# ---------------------------------------------------------------------------

def _person(rng: random.Random, used: set[str]) -> dict:
    while True:
        name = f"{rng.choice(FORENAMES)} {rng.choice(SURNAMES)}"
        if name not in used:
            used.add(name)
            break
    place, county = rng.choice(PLACES)
    return {"name": name, "place": place, "county": county,
            "occupation": rng.choice(OCCUPATIONS)}


def sample_bill(rng: random.Random, *, pins: dict | None = None) -> dict:
    """Sample a coherent 1642 English vessel bill of sale. `pins` may fix
    caller-owned facts: seller, buyer, vessel_name, tuns, former (a former
    vessel name), share (2/4/8/16/32), price_pounds, sale_month, sale_day,
    salutation (the deed-poll form B). Everything else is texture drawn
    under seed — and every repeated fact reads from one sampled variable."""
    pins = pins or {}
    used: set[str] = set()
    seller = _person(rng, used)
    buyer = _person(rng, used)
    if pins.get("seller"):
        seller["name"] = pins["seller"]
    if pins.get("buyer"):
        buyer["name"] = pins["buyer"]

    vtype, lo, hi, rlo, rhi = rng.choice(VESSEL_TYPES)
    former = pins.get("former") if "former" in pins else rng.random() < 0.35
    vname = pins.get("vessel_name") or rng.choice(VESSEL_NAMES)
    vessel = {"type": vtype, "name": vname, "port": seller["place"],
              "tuns": pins.get("tuns") or rng.randint(lo, hi),
              "rate": rng.randint(rlo, rhi),
              "former": (rng.choice([n for n in VESSEL_NAMES if n != vname])
                         if former else None)}

    den = pins.get("share") or rng.choice([s[0] for s in SHARES])
    share = next(s for s in SHARES if s[0] == den)
    # the price is derived, never drawn: whole value = tuns x rate; the
    # consideration is the share of it (round-8 money-realism tell).
    whole = vessel["tuns"] * vessel["rate"]
    price = pins.get("price_pounds") or max(1, round(whole / den))
    bond = price * 2

    month = pins.get("sale_month") or rng.randint(1, 12)
    day = pins.get("sale_day") or rng.randint(1, 28)
    if (month, day) < (3, 25):
        regnal, legal_year, dual = "seventeenth", 1641, True
    else:
        regnal, legal_year, dual = "eighteenth", 1642, False
    feast = _feast_after(month, day, 360)

    intermediary = _person(rng, used) if rng.random() < 0.5 else None
    witnesses = [_person(rng, used) for _ in range(rng.randint(2, 3))]
    return {
        "era_year": 1642,
        "date": {"day": day, "day_ord": _ORDS[day - 1], "month": month,
                 "month_name": _MONTHS[month - 1],
                 "regnal": regnal, "legal_year": legal_year, "dual": dual},
        "seller": seller, "buyer": buyer, "vessel": vessel,
        "share": {"den": share[0], "of_a": share[2], "said": share[3],
                  "for_the": share[1]},
        "whole_pounds": whole,
        "price_pounds": price, "price_roman": _roman(price),
        "price_words": _words(price),
        "bond_pounds": bond, "bond_words": _words(bond),
        "feast": feast,
        "intermediary": intermediary,
        "witnesses": witnesses, "with_other": rng.random() < 0.5,
        "literate": rng.random() < 0.7,
        "attestation": rng.random() < 0.5,
        "salutation": (pins["salutation"] if "salutation" in pins
                       else rng.random() < 0.35),
        "scan_seed": rng.randint(1, 10**6),
    }


# ---------------------------------------------------------------------------
# Composition — the engrossed text (couplings live here: every repeated fact
# reads the same model field)
# ---------------------------------------------------------------------------

def _wrap(text: str, width: int = CHARS, indent: int = 6) -> list[str]:
    words, lines, cur = text.split(), [], " " * indent
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur.rstrip())
            cur = ""
        cur += w + " "
    lines.append(cur.rstrip())
    return lines


def compose_bill(m: dict, defect: dict | None = None) -> list[dict]:
    """The manuscript as structured lines: {"text": ...} in the scribe's
    hand (OCR-visible), {"sig": name} as an individual cursive hand, or
    {"mark": name} for the illiterate's X (OCR reads neither hand). Two
    attested forms (contract.json). Defect hooks alter exactly one
    displayed value."""
    d, s, b, v, sh = m["date"], m["seller"], m["buyer"], m["vessel"], m["share"]
    regnal, feast = d["regnal"], m["feast"]
    receipt_share, receipt_price = sh["for_the"], m["price_roman"]
    if defect:
        regnal = defect.get("regnal_year", regnal)          # regnal_mismatch
        feast = defect.get("feast", feast)                  # feast_inverted
        receipt_share = defect.get("receipt_share", receipt_share)
        receipt_price = defect.get("receipt_price", receipt_price)

    seller_of = f"{s['name']} of {s['place']} within the county of {s['county']} {s['occupation']}"
    buyer_of = f"{b['name']} of {b['place']} within the county of {b['county']} {b['occupation']}"
    naming = (f"called the {v['name']}, sometime called the {v['former']},"
              if v["former"] else f"called the {v['name']}")
    tonnage = f"of the burthen of {_words(v['tuns'])} tunnes "
    app_share = (defect.get("receipt_share", sh["said"])
                 if (defect and m["salutation"]) else sh["said"])
    appurtenances = (f"with all manner of implements and tackling to the "
                     f"{app_share} of the same {v['type']} appertaining or "
                     f"belonging")
    machinery = (
        f"And the saide {s['name']} binds himself his executors and assigns "
        f"by these presents in the sum of {m['bond_words']} pounds of lawfull "
        f"money of England to be paid to the said {b['name']} his executors "
        f"or assigns at the feast of {feast} next coming after the end of one "
        f"whole yeere from the date {'of these presents' if m['salutation'] else 'hereof'} that I the saide {s['name']} shall "
        f"warraunt and discharge the said {sh['said']} of the said "
        f"{v['type']} against all men by the space of one whole yeere that "
        f"then all the contents within this said bill to be voyde and of none "
        f"effect or else to stand in full strength and vertue")
    execution = ("have set my hand and seale" if m["literate"]
                 else "have set my seale and marke")

    if m["salutation"]:
        # Form B — deed-poll salutation; date moves to the testimonium.
        body = (
            f"To all to whom these presents shall come, greeting. Know ye "
            f"that I, {seller_of}, for and in consideration of the sum of "
            f"{defect.get('receipt_price', m['price_words']) if defect else m['price_words']} "
            f"pounds of lawfull money of England to me in hand paid before "
            f"the sealing and delivery of these presents by {buyer_of}, the "
            f"receipt whereof I do hereby acknowledge, have bargained and "
            f"sold and by these presents do bargain and sell unto the said "
            f"{b['name']} {sh['of_a']} {v['type']} {naming} of {v['port']} "
            f"{tonnage}{appurtenances} {machinery} In witnesse whereof I the "
            f"same {s['name'].split()[0]} {execution} given the {d['day_ord']} "
            f"daye of {d['month_name']} in the {regnal} yeere of the reigne "
            f"of our soveraigne lord King Charles"
        )
    else:
        # Form A — the sourced 1536 exemplar (date-led bill).
        body = (
            f"This bill made the {d['day_ord']} daye of {d['month_name']} in "
            f"the {regnal} yeere of the reigne of our soveraigne lord King "
            f"Charles witnesseth that I, {seller_of}, have bargained and "
            f"sold the day and yeere aforesaid unto {buyer_of} {sh['of_a']} "
            f"{v['type']} {naming} of {v['port']} {tonnage}{appurtenances} "
            f"{machinery} And also I the same {s['name'].split()[0]} "
            f"knowledge myself to have receaved the day and yeere aforesaid "
            f"of {b['name']}"
        )
        if m["intermediary"]:
            body += f" by the hands of {m['intermediary']['name']} his servant"
        body += (
            f" {receipt_price} li. of lawfull money of England for the full "
            f"payment of bargain and sale for the {receipt_share} of the "
            f"same {v['type']} In witnesse whereof I the same "
            f"{s['name'].split()[0]} {execution} given the day and yeere "
            f"abovesaid"
        )

    lines: list[dict] = [{"text": ln} for ln in _wrap(body)]
    # The attestation and the witnesses subscribe the DORSE, not the face —
    # the visual exemplar carries the sealing memorandum and the witnesses'
    # own signatures on the back, with only the party's name on the plica.
    names_list = [w["name"] for w in m["witnesses"]]
    if m["attestation"]:
        att = ("Sealed and delivered in the presence of "
               + (names_list[0] if len(names_list) == 1
                  else ", ".join(names_list[:-1]) + " and " + names_list[-1]))
    else:
        att = f"Witnesses to the saide bargain and sale: {', '.join(names_list)}"
    if m["with_other"]:
        att += " with other"
    for ln in _wrap(att, indent=0):
        lines.append({"dorse": True, "text": ln})
    for w in m["witnesses"]:
        lines.append({"dorse": True, "sig": w["name"]})
    return lines


# ---------------------------------------------------------------------------
# Stage 1: the manuscript sheet (vector underlay for rasterization)
# ---------------------------------------------------------------------------

def _segments(text: str) -> list[tuple[str, bool]]:
    """Split a line into (run, is_display) — the engrosser writes the
    instrument's joints large and the rest small, on one baseline."""
    out: list[tuple[str, bool]] = []
    i = 0
    while i < len(text):
        hit = None
        for run in DISPLAY_RUNS:
            if text.startswith(run, i):
                hit = run
                break
        if hit:
            out.append((hit, True))
            i += len(hit)
        else:
            j = i
            while j < len(text) and not any(text.startswith(r, j)
                                            for r in DISPLAY_RUNS):
                j += 1
            out.append((text[i:j], False))
            i = j
    return out


def _hand_line(c, rng: random.Random, x: float, y: float, text: str) -> None:
    """One engrossed line: display script for the formula joints, the small
    hand for the rest, word-level spacing jitter and a whisper of rotation."""
    c.saveState()
    c.translate(x, y)
    c.rotate(rng.uniform(-0.30, 0.30))
    cx = 0.0
    for run, big in _segments(text):
        font = DISPLAY if big else HAND
        c.setFillGray(rng.uniform(0.08, 0.13) if big
                      else rng.uniform(0.13, 0.22))   # iron-gall ink variance
        c.setFont(*font)
        for word in run.split(" "):
            if word:
                c.drawString(cx, 0, word)
                cx += c.stringWidth(word, *font)
            cx += c.stringWidth(" ", *font) + rng.uniform(-0.6, 0.8)
    c.restoreState()


def _skin_path(c, rng: random.Random, ph: float):
    """The membrane's own outline: a scalloped chirograph cut across the head
    (this is one half of an indenture — the cut proves the counterpart), and
    the soft irregular edges of a skin, never a guillotined rectangle."""
    x0, x1 = BLEED, PAGE_W - BLEED
    y0, y1 = SKIN_Y0, ph - BLEED
    p = c.beginPath()
    p.moveTo(x0, y0)
    p.lineTo(x0 + rng.uniform(-3, 3), y1 - 6)
    n = rng.randint(7, 10)                            # the indenture scallops
    w = (x1 - x0) / n
    for i in range(n):
        xa = x0 + i * w
        p.curveTo(xa + w * 0.25, y1 - rng.uniform(20, 30),
                  xa + w * 0.75, y1 + rng.uniform(2, 9),
                  xa + w, y1 - rng.uniform(4, 12))
    p.lineTo(x1 + rng.uniform(-3, 3), y0 + rng.uniform(2, 7))
    p.close()
    return p


def _substrate(c, rng: random.Random, ph: float):
    """Parchment: the skin's outline, mottled tone, grimed folds. Everything
    is CLIPPED to the skin — stain and crease stop at the edge of the animal,
    and what lies outside is the scanner's own background."""
    c.setFillGray(0.97)                               # platen background
    c.rect(0, 0, PAGE_W, ph, stroke=0, fill=1)
    skin = _skin_path(c, rng, ph)
    c.setFillGray(rng.uniform(0.80, 0.85))
    c.drawPath(skin, stroke=0, fill=1)
    c.saveState()
    c.clipPath(skin, stroke=0, fill=0)
    for _ in range(rng.randint(90, 150)):             # mottling and staining
        x = rng.uniform(BLEED, PAGE_W - BLEED)
        y = rng.uniform(SKIN_Y0, ph - BLEED)
        c.setFillGray(rng.uniform(0.66, 0.93))
        c.setFillAlpha(rng.uniform(0.05, 0.18))
        c.circle(x, y, rng.uniform(6, 40), stroke=0, fill=1)
    c.setFillGray(0.55)                               # grime along the edges
    for _ in range(rng.randint(8, 14)):
        c.setFillAlpha(rng.uniform(0.04, 0.10))
        side = rng.random()
        x = (BLEED if side < 0.5 else PAGE_W - BLEED) + rng.uniform(-18, 18)
        c.circle(x, rng.uniform(SKIN_Y0, ph - BLEED), rng.uniform(20, 55),
                 stroke=0, fill=1)
    c.setFillAlpha(1)
    c.setLineWidth(0.9)                               # the folded packet's grid
    for fx in (PAGE_W * 0.34, PAGE_W * 0.67):
        c.setStrokeGray(rng.uniform(0.60, 0.70))
        pts = [(fx + rng.uniform(-2.5, 2.5), y)
               for y in range(int(SKIN_Y0), int(ph), 40)]
        p = c.beginPath()
        p.moveTo(*pts[0])
        for pt in pts[1:]:
            p.lineTo(*pt)
        c.drawPath(p, stroke=1, fill=0)
    c.setStrokeGray(rng.uniform(0.62, 0.72))
    fy = SKIN_Y0 + (ph - SKIN_Y0) * 0.52
    pts = [(x, fy + rng.uniform(-2.5, 2.5))
           for x in range(int(BLEED), int(PAGE_W), 45)]
    p = c.beginPath()
    p.moveTo(*pts[0])
    for pt in pts[1:]:
        p.lineTo(*pt)
    c.drawPath(p, stroke=1, fill=0)
    c.restoreState()
    return skin


def _cadel(c, rng: random.Random, x: float, y: float, letter: str) -> float:
    """The engrosser's opening initial: an oversized letter inside a cage of
    knotwork strokes. Returns the x the first line resumes at."""
    c.saveState()
    c.setFillGray(rng.uniform(0.08, 0.14))
    c.setStrokeGray(rng.uniform(0.10, 0.16))
    size = 40.0
    c.setFont("Times-BoldItalic", size)
    c.drawString(x, y - 6, letter)
    w = c.stringWidth(letter, "Times-BoldItalic", size)
    c.setLineWidth(rng.uniform(0.7, 1.2))
    for k in range(rng.randint(4, 6)):                # knotwork flourishes
        y0 = y + 2 + k * rng.uniform(4, 7)
        p = c.beginPath()
        p.moveTo(x - 6, y0)
        p.curveTo(x + w * 0.3, y0 + rng.uniform(6, 16),
                  x + w * 0.7, y0 - rng.uniform(6, 16),
                  x + w + rng.uniform(-4, 6), y0 + rng.uniform(-6, 6))
        c.drawPath(p, stroke=1, fill=0)
    c.restoreState()
    return x + w + 6.0


def _mark(c, rng: random.Random, x: float, y: float, h: float = 22.0) -> None:
    """The illiterate's X — two uneven crossing strokes, no penmanship."""
    c.setLineWidth(1.6)
    c.setStrokeGray(0.15)
    c.line(x, y, x + h * rng.uniform(0.6, 0.9), y + h * rng.uniform(0.9, 1.1))
    c.line(x + h * rng.uniform(0.6, 0.9), y,
           x + h * rng.uniform(-0.1, 0.1), y + h * rng.uniform(0.9, 1.1))


def _plica(c, rng: random.Random, m: dict, skin) -> None:
    """The foot of the skin: the turn-up (plica) folded up to carry the seal,
    the party's name engrossed in a ruled panel on it, and the parchment tag
    threaded through the fold with the wax pendent from it. From the visual
    exemplar — execution does NOT float in the text block."""
    fold_y = SKIN_Y0 + PLICA_H
    c.saveState()
    c.clipPath(skin, stroke=0, fill=0)                # the turn-up is the skin
    c.setFillGray(rng.uniform(0.70, 0.76))            # doubled skin, darker
    c.rect(BLEED - 4, SKIN_Y0 - 4, PAGE_W - 2 * BLEED + 8, PLICA_H + 4,
           stroke=0, fill=1)
    c.restoreState()
    c.setStrokeGray(rng.uniform(0.62, 0.70))          # the fold itself
    c.setLineWidth(1.2)
    pts = [(x, fold_y + rng.uniform(-1.8, 1.8))
           for x in range(int(BLEED), int(PAGE_W - BLEED), 40)]
    p = c.beginPath()
    p.moveTo(*pts[0])
    for pt in pts[1:]:
        p.lineTo(*pt)
    c.drawPath(p, stroke=1, fill=0)

    panel_x, panel_y = PAGE_W - BLEED - 210, SKIN_Y0 + 26   # ruled name panel
    c.setStrokeGray(0.42)
    c.setLineWidth(0.7)
    c.rect(panel_x, panel_y, 132, 46, stroke=1, fill=0)
    if m["literate"]:
        png = assets.signature_png(m["scan_seed"] % 997 + 3,
                                   name=m["seller"]["name"])
        ir = ImageReader(io.BytesIO(png))
        iw, ih = ir.getSize()
        c.drawImage(ir, panel_x + 8, panel_y + 4, width=38.0 * iw / ih,
                    height=38.0, mask="auto")
    else:
        c.setFont(*HAND)
        c.setFillGray(0.14)
        c.drawString(panel_x + 8, panel_y + 30,
                     f"the marke of {m['seller']['name']}")
        _mark(c, rng, panel_x + 52, panel_y + 6, h=18.0)

    tag_x = panel_x - 96                              # tag through the fold
    c.setFillGray(rng.uniform(0.74, 0.80))
    c.setStrokeGray(0.66)
    c.setLineWidth(0.6)
    p = c.beginPath()
    p.moveTo(tag_x, fold_y - 6)
    p.lineTo(tag_x + 17, fold_y - 6)
    p.lineTo(tag_x + 21 + rng.uniform(-2, 2), SKIN_Y0 - 34)
    p.lineTo(tag_x - 5 + rng.uniform(-2, 2), SKIN_Y0 - 34)
    p.close()
    c.drawPath(p, stroke=1, fill=1)
    x0, y0 = tag_x + 8, SKIN_Y0 - 44                  # wax, in grayscale
    c.setFillGray(0.42)
    p = c.beginPath()
    for i in range(10):                             # irregular blob edge
        a1, a2 = i * 0.628, (i + 1) * 0.628
        r1 = 13 + rng.uniform(-2.2, 2.2)
        r2 = 13 + rng.uniform(-2.2, 2.2)
        if i == 0:
            p.moveTo(x0 + r1 * math.cos(a1), y0 + r1 * math.sin(a1))
        p.curveTo(x0 + r1 * math.cos(a1 + 0.2), y0 + r1 * math.sin(a1 + 0.2),
                  x0 + r2 * math.cos(a2 - 0.2), y0 + r2 * math.sin(a2 - 0.2),
                  x0 + r2 * math.cos(a2), y0 + r2 * math.sin(a2))
    p.close()
    c.drawPath(p, stroke=0, fill=1)
    c.setStrokeGray(0.30)                            # signet impression
    c.setLineWidth(1.1)
    c.ellipse(x0 - 7, y0 - 7, x0 + 7, y0 + 7)
    c.line(x0 - 4, y0 + 4, x0 + 4, y0 - 4)
    c.line(x0 - 4, y0 - 4, x0 + 4, y0 + 4)


def _dorse(c, rng: random.Random, m: dict, recto: list[dict],
           dorse_lines: list[dict], ph: float) -> None:
    """The back of the same skin: the recto's ink showing through the
    membrane in mirror, the sealing memorandum and witnesses' own hands, and
    the docket written along the fold panel — read sideways, because the
    instrument was docketed folded. All three are from the visual exemplar."""
    _substrate(c, rng, ph)
    c.saveState()                                     # show-through, mirrored
    c.translate(PAGE_W, 0)
    c.scale(-1, 1)
    c.setFillGray(0.55)
    c.setFillAlpha(0.09)
    y = ph - 58.0
    for ln in recto:
        if ln.get("text"):
            c.saveState()
            c.translate(ML, y)
            c.rotate(rng.uniform(-0.3, 0.3))
            for run, big in _segments(ln["text"]):
                c.setFont(*(DISPLAY if big else HAND))
                c.drawString(0, 0, run)
                c.translate(c.stringWidth(run, *(DISPLAY if big else HAND)), 0)
            c.restoreState()
        y -= LEADING
    c.setFillAlpha(1)
    c.restoreState()

    y = ph - 96                                       # attestation + hands
    for ln in dorse_lines:
        if "sig" in ln:
            png = assets.signature_png(
                (m["scan_seed"] + len(ln["sig"])) % 991 + 11, name=ln["sig"])
            ir = ImageReader(io.BytesIO(png))
            iw, ih = ir.getSize()
            c.drawImage(ir, ML + 26 + rng.uniform(-6, 6), y - 26,
                        width=40.0 * iw / ih, height=40.0, mask="auto")
            y -= 46
        else:
            _hand_line(c, rng, ML + rng.uniform(-2, 2), y, ln["text"])
            y -= LEADING

    d, v, s, b = m["date"], m["vessel"], m["seller"], m["buyer"]
    c.saveState()                                     # the docket, read sideways
    c.translate(PAGE_W * 0.70, SKIN_Y0 + (ph - SKIN_Y0) * 0.18)
    c.rotate(90)
    for n, ln in enumerate([f"The bill of sale of the {v['name']} of {v['port']}",
                            f"{s['name']} to {b['name']}",
                            f"{d['day_ord']} daye of {d['month_name']} "
                            f"{d['legal_year']}"]):
        _hand_line(c, rng, 0, -n * LEADING * 1.5, ln)
    c.restoreState()
    c.showPage()


def _manuscript_pdf(lines: list[dict], rng: random.Random,
                    m: dict) -> tuple[bytes, list[list[dict]], float]:
    """One skin, cut to its text: an engrossed bill is a single membrane, so
    the sheet's height follows the line count rather than the text stopping
    halfway down a stock page. Returns the page height for the OCR layer."""
    recto = [ln for ln in lines if not ln.get("dorse")]
    dorse_lines = [ln for ln in lines if ln.get("dorse")]
    body = [ln for ln in recto if ln.get("text")]
    ph = max(380.0, 58.0 + (len(body) - 0.7) * LEADING + SKIN_Y0 + PLICA_H
             + 26.0)
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(PAGE_W, ph), invariant=1)
    skin = _substrate(c, rng, ph)
    y = ph - 58.0
    for n, ln in enumerate(body):
        x = ML + rng.uniform(-2.2, 2.2)
        text = ln["text"]
        if n == 0:                                    # the opening initial
            text = text.lstrip()
            x = _cadel(c, rng, x, y, text[0])
            text = text[1:]
        _hand_line(c, rng, x, y + rng.uniform(-0.8, 0.8), text)
        y -= LEADING * (1.3 if n == 0 else 1.0)
    _plica(c, rng, m, skin)
    c.showPage()
    _dorse(c, rng, m, recto, dorse_lines, ph)
    c.save()
    return buf.getvalue(), [recto, dorse_lines], ph


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def render_bill(model: dict, *, metadata: dict, defect: dict | None = None,
                scan_dpi: int = 150) -> bytes:
    """Render the bill as a scan of the engrossed manuscript. Defect hooks:
    {"regnal_year": "fifteenth"} — regnal numeral contradicts the date;
    {"receipt_share": "one fourth part"} — receipt share vs bargain share;
    {"receipt_price": "xcix li."} — receipt sum vs stated consideration;
    {"feast": "the Purification of the Virgin Mary"} — a payment feast that
    precedes the bill date. `metadata` dates the DIGITIZATION (PDF era; a
    planetary scanner, not a sheetfed one), never the 1642 original."""
    rng = random.Random(model.get("scan_seed", 1642))
    lines = compose_bill(model, defect)
    vector, pages, ph = _manuscript_pdf(lines, rng, model)

    def text_layer(idx, t):
        t.setFont(*TEXT)
        dorse = idx == len(pages) - 1
        y0 = ph - 96 if dorse else ph - 58.0
        n = 0
        for ln in pages[idx]:
            if "sig" in ln or "mark" in ln:
                n += 2                                   # hands read as nothing
                continue
            t.setTextOrigin(ML, y0 - n * LEADING)
            t.textOut(ln["text"])
            n += 1
        if dorse:                                        # the docket, engrossed
            d, v, s, b = (model["date"], model["vessel"], model["seller"],
                          model["buyer"])
            t.setTextOrigin(ML, y0 - (n + 2) * LEADING)
            t.textOut(f"The bill of sale of the {v['name']} of {v['port']} "
                      f"{s['name']} to {b['name']} {d['day_ord']} daye of "
                      f"{d['month_name']} {d['legal_year']}")

    return scan.rescan(vector, rng=rng, metadata=metadata,
                       text_layer=text_layer, dpi=scan_dpi)
