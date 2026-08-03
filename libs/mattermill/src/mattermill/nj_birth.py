"""nj_birth: a New Jersey return of a birth, 1878-1900, as a period-honest scan.

Built against a SOURCED statutory contract. Section 2 of New Jersey's registry
act prescribes exactly what a birth return must contain, and the Bureau of
Vital Statistics pamphlet reproducing it is the reference
(foundry/reference/templates/nj_birth_1878_1900/). The statute is a stronger
source for a form's field inventory than a specimen would be: it is what the
blank was printed to satisfy.

What the statute gives, and what this module treats as law rather than taste:

- the return is made by the physician, midwife, or other person present at the
  birth — and in case there be no physician or midwife present, by the PARENT.
  So an attendant-less birth cannot name an attending physician.
- it goes to the proper officer within THIRTY DAYS, penalty thirty dollars.
- that officer is the township ASSESSOR or the CITY CLERK. Which one is not a
  style choice: it follows from whether the municipality is a township or an
  incorporated city.
- assessors and city clerks forward on the 15th of each month, the certificates
  up to the 1st.
- a township assessor who finds a birth unreturned at annual assessment may
  fill the usual blank himself, sign as assessor, and mark it "special return"
  — valid as a record, and not a defence for the attendant.

The era decides the delivery. An 1878-1900 document cannot be a vector PDF
(the format shipped in 1993), so the artifact is a scan of a printed blank
filled in by hand.

HONEST LIMIT, declared rather than discovered: the OBJECT is not sourced. The
1878-1900 forms are microfilm, in-person use only, and no facsimile was
obtained. Sheet size, rule work, the blank's layout and the printer's imprint
are invented. Round 8 measured this exact shape — sourced words, unsourced
object — at forensic authenticity 5. This class therefore ships `unreviewed`
and says so in the registry.
"""

from __future__ import annotations

import datetime as _dt
import io
import random

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas

from . import assets, scan

PAGE_W, PAGE_H = 612.0, 468.0        # a foolscap-ish printed blank, landscape
ML, MR = 46.0, 46.0
FORM = ("Times-Roman", 9.0)
HAND = ("Times-Italic", 10.0)
RULE = 0.6

# Canon — caller-supplied. The default is an invented New Jersey township.
# Nothing here names a real person: a vital record is a breeder document, and
# a realistic one bearing a living person's identity is not a research asset.
DEFAULT_CANON = {
    "state": "NEW JERSEY",
    "county": "UNION",
    "municipality": "FAIRMOUNT",
    # township | city — this DRIVES the receiving officer, it does not decorate
    "municipality_kind": "township",
    "officer_name": "ELIAS T. HOBART",
    "printer": "Printed by order of the Bureau of Vital Statistics, Trenton",
}
_CANON_KEYS = frozenset(DEFAULT_CANON)

SURNAMES = ["Whitcomb", "Ackerman", "Doremus", "Vreeland", "Tunison",
            "Hedden", "Bonnell", "Crowell", "Littell", "Meeker"]
GIVEN_M = ["Josiah", "Ezra", "Amos", "Peter", "Cornelius", "Lewis", "Aaron"]
GIVEN_F = ["Hannah", "Phebe", "Sarah", "Lavinia", "Esther", "Rachel", "Ann"]
OCCUPATIONS = ["farmer", "carpenter", "wheelwright", "hat finisher", "mason",
               "blacksmith", "shoemaker", "teamster", "quarryman"]
BIRTHPLACES = ["New Jersey", "New Jersey", "New York", "Ireland", "Germany",
               "Pennsylvania", "England"]
# "the sex and color of the child" — the statute's own words; period returns
# record it as a one-word entry.
COLORS = ["White", "White", "White", "Colored"]
PHYSICIANS = ["Dr. Silas P. Winton", "Dr. Marcus H. Deare", "Dr. J. B. Coriell"]
MIDWIVES = ["Mrs. Catharine Ludlow", "Mrs. Margaret Ryerson"]


def _officer_title(canon: dict) -> str:
    """Township => assessor, city => city clerk. Sourced, not stylistic."""
    return "Assessor" if canon["municipality_kind"] == "township" else "City Clerk"


def sample_birth(rng: random.Random, *, pins: dict | None = None,
                 canon: dict | None = None) -> dict:
    """One return, coherent by construction. Every derived value is computed
    from its inputs; nothing that two fields must agree on is drawn twice."""
    canon = dict(DEFAULT_CANON if canon is None else canon)
    missing = _CANON_KEYS - set(canon)
    if missing:
        raise ValueError(f"canon missing required keys: {sorted(missing)}")
    pins = dict(pins or {})

    year = pins.get("year", rng.randint(1878, 1899))
    if not 1878 <= year <= 1899:
        raise ValueError(
            f"year {year} is outside the certificate era. New Jersey birth "
            "records are REGISTER format until 1878; before May 1848 no civil "
            "birth record exists at all.")

    born = _dt.date(year, rng.randint(1, 12), rng.randint(1, 28))
    # the statute's thirty days is a ceiling, and a late return is the reason
    # the assessor's special return exists
    lag = pins.get("return_lag_days", rng.randint(2, 29))
    returned = born + _dt.timedelta(days=int(lag))

    # one draw decides the attendant, and every dependent field follows it
    attendant_kind = pins.get("attendant", rng.choice(
        ["physician", "physician", "midwife", "none"]))
    special = bool(pins.get("special_return", attendant_kind == "none"
                            and rng.random() < 0.6))
    if attendant_kind == "physician":
        attendant, reporter = rng.choice(PHYSICIANS), "attending physician"
    elif attendant_kind == "midwife":
        attendant, reporter = rng.choice(MIDWIVES), "midwife present"
    else:
        attendant, reporter = None, "father of the child"
    if special:                      # the assessor filled the blank himself
        reporter = f"{_officer_title(canon)}, special return"

    surname = pins.get("surname", rng.choice(SURNAMES))
    maiden = rng.choice([s for s in SURNAMES if s != surname])   # never equal
    sex = pins.get("sex", rng.choice(["Male", "Female"]))
    named = pins.get("named", rng.random() < 0.72)   # "its name, if it be named"
    given = rng.choice(GIVEN_M if sex == "Male" else GIVEN_F)

    residence = f"{canon['municipality'].title()}, {canon['county'].title()} County"
    return {
        **canon,
        "officer_title": _officer_title(canon),
        "date_of_birth": born,
        "return_date": returned,
        # forwarded on the 15th of the month after the return reaches the officer
        "transmittal_date": _dt.date(returned.year + (returned.month == 12),
                                     returned.month % 12 + 1, 15),
        "child_name": f"{given} {surname}" if named else None,
        "child_sex": sex,
        "child_color": rng.choice(COLORS),
        "father_name": f"{rng.choice(GIVEN_M)} {surname}",
        "mother_name": f"{rng.choice(GIVEN_F)} {surname}",
        "mother_maiden_name": maiden,
        "father_birthplace": rng.choice(BIRTHPLACES),
        "mother_birthplace": rng.choice(BIRTHPLACES),
        "father_occupation": rng.choice(OCCUPATIONS),
        "mother_occupation": "housewife",
        "parents_residence": residence,
        "place_of_residence": residence,
        "attendant": attendant,
        "attendant_kind": attendant_kind,
        "reporter": reporter,
        "special_return": special,
        "scan_seed": rng.randrange(1 << 30),
    }


def _fmt(d: _dt.date) -> str:
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def compose_birth(m: dict, defect: dict | None = None) -> list[tuple]:
    """(label, value) rows in the statutory order, plus the execution block.
    A value of None is a genuinely blank field on the blank."""
    d = defect or {}
    name = d.get("child_name", m["child_name"])
    rows = [
        ("Name of child, if named", name if name else "—"),
        ("Sex", d.get("child_sex", m["child_sex"])),
        ("Color", m["child_color"]),
        ("Day and year of birth", _fmt(d.get("date_of_birth", m["date_of_birth"]))),
        ("Precise place of residence", m["place_of_residence"]),
        ("Name of father", m["father_name"]),
        ("Name of mother", m["mother_name"]),
        ("Maiden name of mother", d.get("mother_maiden_name",
                                        m["mother_maiden_name"])),
        ("Birthplace of father", m["father_birthplace"]),
        ("Birthplace of mother", m["mother_birthplace"]),
        ("Residence of parents", m["parents_residence"]),
        ("Occupation of father", m["father_occupation"]),
        ("Occupation of mother", m["mother_occupation"]),
        ("Name of attending physician",
         d.get("attendant", m["attendant"]) or "None in attendance"),
    ]
    return rows


def _blank(c, rng: random.Random, m: dict, rows: list[tuple]) -> None:
    """The printed blank plus the clerk's entries. Everything about the SHEET
    is invented — see the module docstring; only the fields are sourced."""
    c.setFillGray(0.12)
    c.setFont("Times-Bold", 12.5)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 44, "RETURN OF A BIRTH")
    c.setFont("Times-Roman", 9.5)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 60,
                        f"{m['municipality_kind'].title()} of "
                        f"{m['municipality'].title()}, County of "
                        f"{m['county'].title()}, State of {m['state'].title()}")
    if m["special_return"]:
        c.setFont("Times-BoldItalic", 10.5)
        c.drawRightString(PAGE_W - MR, PAGE_H - 44, "SPECIAL RETURN")

    y = PAGE_H - 88
    lw = 176.0
    for label, value in rows:
        c.setFont(*FORM)
        c.setFillGray(0.25)
        c.drawString(ML, y, f"{label}")
        c.setStrokeGray(0.45)
        c.setLineWidth(RULE)
        c.line(ML + lw, y - 2.4, PAGE_W - MR, y - 2.4)
        c.setFont(*HAND)
        c.setFillGray(0.08)
        c.saveState()
        c.translate(ML + lw + 6 + rng.uniform(-1.2, 1.2), y + rng.uniform(-0.7, 0.9))
        c.rotate(rng.uniform(-0.5, 0.5))
        c.drawString(0, 0, str(value))
        c.restoreState()
        y -= 21.5

    y -= 6
    c.setFont(*FORM)
    c.setFillGray(0.25)
    c.drawString(ML, y, "Returned by")
    c.setFont(*HAND)
    c.setFillGray(0.08)
    c.drawString(ML + 70, y, m["reporter"])
    c.setFont(*FORM)
    c.setFillGray(0.25)
    c.drawString(PAGE_W / 2, y, "Date of return")
    c.setFont(*HAND)
    c.setFillGray(0.08)
    c.drawString(PAGE_W / 2 + 74, y, _fmt(m["return_date"]))

    y -= 24
    c.setFont(*FORM)
    c.setFillGray(0.25)
    c.drawString(ML, y, f"Received and forwarded by the {m['officer_title']}")
    c.line(ML + 214, y - 2.4, ML + 400, y - 2.4)
    png = assets.signature_png(m["scan_seed"], name=m["officer_name"].title(),
                               ink=(18, 22, 36))
    c.drawImage(ImageReader(io.BytesIO(png)), ML + 220, y - 3,
                width=118, height=26, mask="auto")
    c.setFont(*FORM)
    c.setFillGray(0.25)
    c.drawString(PAGE_W - MR - 168, y, f"Forwarded {_fmt(m['transmittal_date'])}")

    c.setFont("Times-Italic", 7.2)
    c.setFillGray(0.42)
    c.drawCentredString(PAGE_W / 2, 30, m["printer"])


def render_birth(model: dict, *, metadata: dict, defect: dict | None = None,
                 dpi: int = 150) -> bytes:
    """A scan of the filled blank. An 1878-1900 document cannot be a vector
    file, so the honest artifact is a digitisation with an invisible OCR layer
    and metadata dated at capture."""
    rows = compose_birth(model, defect)
    rng = random.Random(model["scan_seed"])
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H), invariant=1)
    c.setTitle("")
    _blank(c, rng, model, rows)
    c.showPage()
    c.save()

    # The OCR layer must carry everything a reader can SEE. A text layer that
    # omits visible words — the title, the special-return mark — is itself a
    # forensic tell: real Paper-Capture output reads the whole sheet.
    lines = ["RETURN OF A BIRTH" + ("    SPECIAL RETURN"
                                    if model["special_return"] else ""),
             f"{model['municipality_kind'].title()} of "
             f"{model['municipality'].title()}, County of "
             f"{model['county'].title()}, State of {model['state'].title()}"]
    lines += [f"{label}  {value}" for label, value in rows]
    lines += [f"Returned by {model['reporter']}",
              f"Date of return {_fmt(model['return_date'])}",
              f"Received and forwarded by the {model['officer_title']} "
              f"{model['officer_name'].title()}",
              f"Forwarded {_fmt(model['transmittal_date'])}",
              model["printer"]]

    def text_layer(page_index, textobject):
        textobject.setTextOrigin(ML, PAGE_H - 88)
        for ln in lines:
            textobject.textLine(ln)

    return scan.rescan(buf.getvalue(), rng=random.Random(model["scan_seed"]),
                       metadata=metadata, text_layer=text_layer, dpi=dpi)
