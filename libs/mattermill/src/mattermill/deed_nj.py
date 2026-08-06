"""1997 New Jersey residential bargain-and-sale deed recording package.

The target is a later county digitization of an executed paper original.  The
clause anatomy comes from a New Jersey bargain-and-sale form; scan furniture
and the contemporaneous RTF-1 come from a recorded June 1997 New Jersey deed
package; the fee arithmetic comes from the Division of Taxation's 1997 Annual
Report.  Exact Morris County 1997 stamp typography remains unsourced.
"""

from __future__ import annotations

import datetime as dt
import io
import math
import random

from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from . import assets, scan

PAGE_W, PAGE_H = letter

DEFAULT_CANON = {
    "municipality": "Madison", "county": "Morris", "state": "NEW JERSEY",
    "street": "18 Quillstone Mews", "zip": "07940", "block": "4101",
    "lot": "17", "account": "SYNTHETIC-CANON",
    "legal_description": (
        "BEGINNING at an iron pin set in the northerly sideline of Quillstone "
        "Mews, said pin being distant 210.00 feet easterly, measured along that "
        "sideline, from its intersection with the easterly sideline of Fablewood "
        "Rise; thence (1) North 21 degrees 14 minutes East 142.60 feet to an "
        "iron pin; thence (2) South 68 degrees 46 minutes East 81.25 feet to an "
        "iron pin; thence (3) South 21 degrees 14 minutes West 142.60 feet to "
        "the northerly sideline of Quillstone Mews; thence (4) along the same "
        "North 68 degrees 46 minutes West 81.25 feet to the point and place of "
        "BEGINNING. Being the same premises shown on a survey prepared for "
        "the grantee dated May 14, 1997 and more particularly described in the "
        "prior deed cited herein."),
    "prior_book": "5188", "prior_page": "214",
}
_CANON_KEYS = frozenset(DEFAULT_CANON)
_PINS = {"execution_date", "consideration", "grantor_married", "notary_name",
         "new_construction", "partial_exemption"}

FIRST = ["Adrian", "Camille", "Daniel", "Elena", "Farah", "Gabriel", "Hannah",
         "Isabel", "Julian", "Katherine", "Lucas", "Naomi", "Omar", "Priya"]
MALE_FIRST = ["Adrian", "Daniel", "Gabriel", "Julian", "Lucas", "Omar"]
FEMALE_FIRST = ["Camille", "Elena", "Farah", "Hannah", "Isabel", "Katherine",
                "Naomi", "Priya"]
LAST = ["Ashford", "Beaumont", "Carrington", "Delacroix", "Emerson", "Ferrante",
        "Holloway", "Kearney", "Larkin", "Marchetti", "Novak", "Quinlan"]

PAGE_MARKERS = {
    1: ["BARGAIN AND SALE", "TRANSFER OF TITLE", "TAX MAP REFERENCE",
        "BEING THE SAME LAND AND PREMISES"],
    2: ["PROMISES BY GRANTOR", "SIGNATURES", "I CERTIFY"],
    3: ["SCHEDULE A", "LEGAL DESCRIPTION"],
    4: ["AFFIDAVIT OF CONSIDERATION OR EXEMPTION", "RTF-1 (Rev. 1/85)",
        "FOR OFFICIAL USE ONLY", "END OF DOCUMENT"],
}

_CLERK_HOLIDAYS_1997 = {
    dt.date(1997, 1, 1), dt.date(1997, 1, 20), dt.date(1997, 2, 17),
    dt.date(1997, 5, 26), dt.date(1997, 7, 4), dt.date(1997, 9, 1),
    dt.date(1997, 10, 13), dt.date(1997, 11, 11), dt.date(1997, 11, 27),
    dt.date(1997, 12, 25),
}


def _next_clerk_day(value: dt.date) -> dt.date:
    while value.weekday() >= 5 or value in _CLERK_HOLIDAYS_1997:
        value += dt.timedelta(days=1)
    return value


def rtf_1997(consideration: int, *, new_construction: bool = False,
             partial_exemption: str = "none") -> float:
    """1997 rate: $1.75/$500, plus $0.75/$500 above $150,000.

    Fractions of $500 count as a full unit. New construction receives the
    period $1/$500 exemption on the first $150,000.
    """
    units = math.ceil(consideration / 500)
    fee = units * 1.75
    excess = max(0, consideration - 150_000)
    fee += math.ceil(excess / 500) * 0.75
    if partial_exemption not in {"none", "senior", "blind", "disabled"}:
        raise ValueError("partial_exemption must be none, senior, blind, or disabled")
    if new_construction or partial_exemption != "none":
        fee -= math.ceil(min(consideration, 150_000) / 500) * 1.0
    return round(fee, 2)


def _name(rng: random.Random, *, sex: str | None = None) -> str:
    first = MALE_FIRST if sex == "male" else FEMALE_FIRST if sex == "female" else FIRST
    return f"{rng.choice(first)} {rng.choice(LAST)}"


def _first_name(rng: random.Random, *, sex: str | None = None) -> str:
    first = MALE_FIRST if sex == "male" else FEMALE_FIRST if sex == "female" else FIRST
    return rng.choice(first)


def sample_deed(rng: random.Random, *, pins: dict | None = None,
                canon: dict | None = None) -> dict:
    pins = dict(pins or {})
    bad = set(pins) - _PINS
    if bad:
        raise ValueError(f"unknown pins: {sorted(bad)}")
    cn = dict(DEFAULT_CANON if canon is None else canon)
    missing = _CANON_KEYS - set(cn)
    if missing:
        raise ValueError(f"canon missing required keys: {sorted(missing)}")
    if cn["state"].upper() not in {"NEW JERSEY", "NJ"} or \
            cn["municipality"] != "Madison" or cn["county"] != "Morris":
        raise ValueError("only the Madison, Morris County, New Jersey recording world is sourced")
    execution = pins.get("execution_date") or dt.date(
        1997, rng.randint(2, 11), rng.randint(2, 24))
    if isinstance(execution, str):
        execution = dt.date.fromisoformat(execution)
    if execution.year != 1997:
        raise ValueError("this emitter's sourced recording world is 1997")
    grantor_sex = rng.choice(["female", "male"])
    grantor = _name(rng, sex=grantor_sex)
    grantee = _name(rng)
    # The grantee represents a different household.  A shared surname made a
    # later spouse signature look like a party mismatch even though each field
    # was locally populated correctly.
    while grantee.split()[-1] == grantor.split()[-1]:
        grantee = _name(rng)
    consideration = int(pins.get("consideration", rng.randrange(175_000, 451_000, 500)))
    recorded = _next_clerk_day(execution + dt.timedelta(days=rng.randint(3, 14)))
    # Recording furniture is one fact, not three independent guesses.  The
    # default is explicitly synthetic in the manifest; a sourced recording
    # reference can replace this whole canon in a later climb.
    recording_key = rng.randrange(0, 126_000)
    book = str(5300 + recording_key // 700)
    page = str(100 + recording_key % 700)
    instrument = f"1997{recorded:%m%d}{recording_key:06d}"
    new_construction = bool(pins.get("new_construction", False))
    married = bool(pins.get("grantor_married", rng.choice([True, False])))
    spouse_sex = "female" if grantor_sex == "male" else "male"
    spouse = (
        f"{_first_name(rng, sex=spouse_sex)} {grantor.split()[-1]}"
        if married else None
    )
    while spouse == grantor:
        spouse = f"{_first_name(rng, sex=spouse_sex)} {grantor.split()[-1]}"
    notary = str(pins.get("notary_name", "Avery North")).strip()
    if not notary:
        raise ValueError("notary_name must be non-empty")
    if notary in {grantor, grantee, spouse}:
        raise ValueError("notary_name must not collide with a deed party")
    partial_exemption = str(pins.get("partial_exemption", "none"))
    # A period RTF-1 is load-bearing only for an actual exemption claim (or
    # new construction).  A routine sale that fully recites consideration in
    # the deed and acknowledgment does not acquire an invented extra form.
    rtf1_required = new_construction or partial_exemption != "none"
    full_rtf = rtf_1997(consideration)
    actual_rtf = rtf_1997(consideration, new_construction=new_construction,
                          partial_exemption=partial_exemption)
    return {
        **cn, "execution_date": execution, "recorded_date": recorded,
        "grantor": grantor, "grantee": grantee, "grantor_married": married,
        "grantor_sex": grantor_sex,
        "grantor_spouse": spouse,
        "notary": notary,
        "grantor_address": "27 Fablewood Rise, Madison, New Jersey 07940",
        "grantee_address": "6 Quillstone Court, Madison, New Jersey 07940",
        "consideration": consideration, "rtf": actual_rtf,
        "rtf_before_exemption": full_rtf,
        "rtf_exemption_credit": round(full_rtf - actual_rtf, 2),
        "new_construction": new_construction, "book": book, "page": page,
        "partial_exemption": partial_exemption,
        "rtf1_required": rtf1_required,
        "instrument": instrument, "prepared_by": "Morgan Vale, Esq.",
        "return_to": "Vale & Alder, 44 Fablewood Passage, Madison, NJ 07940",
        "scan_seed": rng.randrange(1, 2**31),
    }


def _money(value: float | int) -> str:
    return f"${value:,.2f}"


def _wrap(c, text: str, x: float, y: float, width: float, *, leading=12,
          font="Times-Roman", size=10) -> float:
    c.setFont(font, size)
    words, line = text.split(), ""
    for word in words:
        trial = f"{line} {word}".strip()
        if c.stringWidth(trial, font, size) <= width:
            line = trial
        else:
            c.drawString(x, y, line)
            y -= leading
            line = word
    if line:
        c.drawString(x, y, line)
        y -= leading
    return y


def _signature(c, name: str, x: float, y: float, seed: int, *,
               width: float = 150, height: float = 44,
               draw_label: bool = True) -> None:
    png = assets.signature_png(seed, name=name)
    c.drawImage(ImageReader(io.BytesIO(png)), x, y, width=width, height=height,
                preserveAspectRatio=True, mask="auto")
    c.line(x, y, x + width + 30, y)
    if draw_label:
        c.setFont("Times-Roman", 9)
        c.drawString(x, y - 11, name)


def _footer(c, m: dict, page: int, total: int) -> None:
    c.setFont("Helvetica", 7)
    c.drawCentredString(PAGE_W / 2, 17,
        f"Morris County Clerk  Instrument {m['instrument']}  Book: {m['book']} "
        f"Page: {m['page']}  Page {page} of {total}")


def _footer_text(m: dict, page: int, total: int) -> str:
    return (f"Morris County Clerk Instrument {m['instrument']} Book {m['book']} "
            f"Page {m['page']} Page {page} of {total}")


def _render_vector(m: dict, defect: dict | None) -> tuple[bytes, list[list[str]]]:
    defect = defect or {}
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter, invariant=1)
    texts: list[list[str]] = []
    deed_price = defect.get("consideration_deed", m["consideration"])
    displayed_fee = defect.get("rtf_fee", m["rtf"])
    total_pages = 4 if m["rtf1_required"] else 3

    # Page 1 — deed anatomy.
    lines = ["PLEASE RECORD AND RETURN TO", m["return_to"], "Prepared by",
             m["prepared_by"], "BARGAIN AND SALE",
             "Covenants as to Grantor's Acts"]
    c.setFont("Helvetica-Bold", 8)
    c.drawString(48, 752, "PLEASE RECORD AND RETURN TO:")
    c.drawString(345, 752, "Prepared by")
    c.setFont("Helvetica", 8)
    c.drawString(48, 738, m["return_to"])
    _signature(c, m["prepared_by"].removesuffix(", Esq."), 345, 720,
               m["scan_seed"] + 11, width=105, height=25, draw_label=False)
    c.setFont("Helvetica", 7)
    c.drawString(345, 708, m["prepared_by"])
    c.setFont("Times-Bold", 12)
    c.drawCentredString(PAGE_W / 2, 680, "BARGAIN AND SALE")
    c.setFont("Times-Roman", 9)
    c.drawCentredString(PAGE_W / 2, 666, "(Covenants as to Grantor's Acts)")
    y = 638
    body = [
        ("DEED", f"This Deed is made on {m['execution_date']:%B %d, %Y}."),
        ("BETWEEN", f"{m['grantor']}, {'a married person' if m['grantor_married'] else 'an unmarried person'}, "
                    f"whose address is {m['grantor_address']}, referred to as the Grantor, AND "
                    f"{m['grantee']}, whose address is {m['grantee_address']}, "
                    "referred to as the Grantee."),
        ("TRANSFER OF TITLE", "The Grantor does hereby grant and convey the property "
                              "described below to the Grantee."),
        ("CONSIDERATION", f"This transfer of ownership is made for the sum and "
                          f"consideration of {_money(deed_price)}. The Grantor "
                          "acknowledges receipt of this money."),
        ("TAX MAP REFERENCE", f"The property is located in the Borough of "
                              f"{m['municipality']}, {m['county']} County, Block "
                              f"No. {m['block']}, Lot No. {m['lot']}, commonly "
                              f"known as {m['street']}, {m['municipality']}, NJ {m['zip']}."),
        ("PROPERTY DESCRIPTION", "The property consists of all land, buildings, "
                                 "structures and improvements and is described in "
                                 "Schedule A attached and made a part hereof."),
        ("BEING THE SAME LAND AND PREMISES", f"conveyed to the Grantor by deed "
                                             f"recorded in Deed Book {m['prior_book']}, "
                                             f"Page {m['prior_page']}."),
    ]
    for heading, text in body:
        c.setFont("Times-Bold", 10)
        c.drawString(48, y, heading + ".")
        lines.append(heading)
        y -= 14
        y = _wrap(c, text, 48, y, 516)
        lines.append(text)
        y -= 9
    if m["new_construction"]:
        c.setFont("Helvetica-Bold", 11); c.drawString(48, 684, "NEW CONSTRUCTION")
        lines.append("NEW CONSTRUCTION")
    _footer(c, m, 1, total_pages); lines.append(_footer_text(m, 1, total_pages))
    c.showPage(); texts.append(lines)

    # Page 2 — covenant, execution, acknowledgment.
    lines = []
    y = 735
    c.setFont("Times-Bold", 11); c.drawString(48, y, "PROMISES BY GRANTOR")
    lines.append("PROMISES BY GRANTOR")
    y = _wrap(c, "The Grantor promises and warrants that Grantor, by acts of the "
                 "Grantor, has not encumbered the property and has not allowed "
                 "anyone else to obtain any legal right affecting it.", 48, y-18, 516)
    lines.append("The Grantor by acts of the Grantor has not encumbered the property.")
    c.setFont("Times-Bold", 11); c.drawString(48, y-15, "SIGNATURES")
    lines.append("SIGNATURES")
    _signature(c, m["grantor"], 320, y-76, m["scan_seed"] + 101)
    lines.append(m["grantor"])
    if m["grantor_spouse"]:
        _signature(c, m["grantor_spouse"], 320, y-142,
                   m["scan_seed"] + 211)
        c.setFont("Times-Roman", 8)
        c.drawString(320, y-166, "Spouse joining solely to release matrimonial rights")
        lines.extend([m["grantor_spouse"],
                      "Spouse joining solely to release matrimonial rights"])
        y -= 195
    else:
        y -= 125
    acknowledgers = m["grantor"]
    if m["grantor_spouse"]:
        acknowledgers += f" and {m['grantor_spouse']}"
    if m["grantor_spouse"]:
        acknowledgment = (
            "that they are the persons named in and personally signed this Deed; "
            "that they signed, sealed and delivered it as their act and deed"
        )
    else:
        acknowledgment = (
            "that the Grantor is the person named in and personally signed this "
            "Deed; that the Grantor signed, sealed and delivered it as the "
            "Grantor's act and deed"
        )
    ack = (f"STATE OF NEW JERSEY, COUNTY OF MORRIS, ss. I CERTIFY that on "
           f"{m['execution_date']:%B %d, %Y}, {acknowledgers} personally came "
           f"before me and acknowledged, to my satisfaction, {acknowledgment} "
           "for the uses and purposes expressed in it; and that "
           f"{_money(m['consideration'])} is the full and actual consideration.")
    y = _wrap(c, ack, 48, y, 516, leading=14)
    lines.extend(["I CERTIFY", ack])
    _signature(c, m["notary"], 48, y-62, m["scan_seed"] + 307,
               draw_label=False)
    c.setFont("Times-Roman", 8)
    c.drawString(48, y-86, f"{m['notary']}, Notary Public of New Jersey")
    c.drawString(48, y-97, "My Commission Expires October 18, 1999")
    lines.extend([f"{m['notary']}, Notary Public of New Jersey",
                  "My Commission Expires October 18, 1999"])
    c.setFont("Helvetica-Bold", 13); c.saveState(); c.translate(370, 190); c.rotate(8)
    c.drawString(0, 0, f"RECORDED {m['recorded_date']:%b %d %Y}")
    c.restoreState(); lines.append(f"RECORDED {m['recorded_date']:%b %d %Y}")
    c.setFont("Helvetica-Bold", 8)
    c.drawString(370, 174, f"RTF PAID {_money(m['rtf'])}")
    lines.append(f"RTF PAID {_money(m['rtf'])}")
    _footer(c, m, 2, total_pages); lines.append(_footer_text(m, 2, total_pages))
    c.showPage(); texts.append(lines)

    # Page 3 — schedule A.
    lines = ["SCHEDULE A", "LEGAL DESCRIPTION", m["legal_description"]]
    c.setFont("Times-Bold", 13); c.drawCentredString(PAGE_W/2, 735, "SCHEDULE A")
    c.setFont("Times-Bold", 11); c.drawCentredString(PAGE_W/2, 712, "LEGAL DESCRIPTION")
    _wrap(c, m["legal_description"], 62, 675, 488, leading=15, size=11)
    c.setFont("Times-Roman", 10)
    c.drawString(62, 535, f"Tax Block {m['block']}, Lot {m['lot']} — Borough of Madison")
    lines.append(f"Tax Block {m['block']} Lot {m['lot']} Borough of Madison")
    _footer(c, m, 3, total_pages); lines.append(_footer_text(m, 3, total_pages))
    c.showPage(); texts.append(lines)

    # Page 4 — contemporaneous RTF-1, only when the transaction actually
    # requires one.  Its dense anatomy follows the sourced June 1997 sheet.
    if not m["rtf1_required"]:
        c.save()
        return buf.getvalue(), texts
    lines = ["AFFIDAVIT OF CONSIDERATION OR EXEMPTION",
             "RTF-1 (Rev. 1/85) 06/92-R2", "PARTIAL EXEMPTION"]
    c.rect(38, 35, 536, 725)
    c.setFont("Helvetica", 6.5)
    c.drawString(48, 742, "NC1645 - Affidavit of Consideration")
    c.drawString(48, 733, "RTF-1 (Rev. 1/85) 06/92-R2")
    c.setFont("Times-Bold", 10)
    c.drawCentredString(PAGE_W/2, 744, "STATE OF NEW JERSEY")
    c.drawCentredString(PAGE_W/2, 731, "AFFIDAVIT OF CONSIDERATION OR")
    c.drawCentredString(PAGE_W/2, 718, "EXEMPTION")
    c.setFont("Times-Bold", 8)
    c.drawCentredString(PAGE_W/2, 706, "(C. 49, P.L. 1968)")
    c.drawCentredString(PAGE_W/2, 695, "PARTIAL EXEMPTION (C. 176, P.L. 1975)")
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(PAGE_W/2, 682,
        "To Be Recorded With Deed Pursuant to C. 49, P.L. 1968, as Amended")
    c.line(48, 675, 564, 675)
    c.setFont("Times-Bold", 8)
    c.drawString(48, 660, "STATE OF NEW JERSEY")
    c.drawString(48, 647, "COUNTY OF MORRIS                         SS.")
    c.rect(335, 638, 220, 34)
    c.setFont("Helvetica", 6.5)
    c.drawString(341, 660, f"Consideration  {_money(m['consideration'])}")
    c.drawString(341, 649, f"Realty Transfer Fee  {_money(displayed_fee)}")
    c.drawString(455, 649, f"Credit  {_money(m['rtf_exemption_credit'])}")
    c.drawString(341, 640, f"Recorded  {m['recorded_date']:%B %d, %Y}")
    lines.extend([f"Consideration {_money(m['consideration'])}",
                  f"Realty Transfer Fee {_money(displayed_fee)}",
                  f"Partial Exemption Credit {_money(m['rtf_exemption_credit'])}",
                  f"Recorded {m['recorded_date']:%B %d, %Y}"])

    c.setFont("Times-Bold", 8)
    c.drawString(48, 622, "(1) PARTY OR LEGAL REPRESENTATIVE")
    c.setFont("Times-Roman", 7.5)
    party_line = (f"Deponent, {m['grantor']}, being duly sworn according to law "
                  "upon oath, deposes and says that deponent is the Grantor")
    _wrap(c, party_line, 58, 607, 492, leading=10, size=7.5)
    deed_line = (f"in a deed dated {m['execution_date']:%B %d, %Y}, transferring "
                 f"real property identified as Block {m['block']}, Lot {m['lot']}, "
                 f"located at {m['street']}, Madison, Morris County, and annexed hereto.")
    _wrap(c, deed_line, 58, 575, 492, leading=10, size=7.5)
    lines.extend([party_line, deed_line])

    c.setFont("Times-Bold", 8)
    c.drawString(48, 530, "(2) CONSIDERATION")
    c.setFont("Times-Roman", 6.8)
    consideration_text = (
        "Deponent states that, with respect to the deed hereto annexed, the actual "
        "amount of money and the monetary value of any other thing of value "
        "constituting the entire compensation paid or to be paid for transfer of "
        f"title is {_money(m['consideration'])}, with no prior mortgage assumed.")
    _wrap(c, consideration_text, 58, 516, 492, leading=9, size=6.8)
    lines.append(consideration_text)

    c.setFont("Times-Bold", 8)
    c.drawString(48, 468, "(3) FULL EXEMPTION FROM FEE")
    c.setFont("Times-Roman", 6.8)
    c.drawString(58, 456, "No full exemption is claimed.")
    lines.append("No full exemption is claimed")
    c.line(48, 447, 564, 447)
    c.setFont("Times-Bold", 8)
    c.drawString(48, 433, "(4) PARTIAL EXEMPTION FROM FEE")
    c.setFont("Times-Roman", 6.5)
    c.drawString(58, 420, "All boxes in the appropriate category must be checked.")
    labels = [("SENIOR CITIZEN", "senior"), ("BLIND", "blind"),
              ("DISABLED", "disabled"), ("NEW CONSTRUCTION", "new_construction")]
    yy = 402
    for label, key in labels:
        c.rect(62, yy-2, 8, 8)
        selected = ((key == "new_construction" and m["new_construction"]) or
                    key == m["partial_exemption"])
        if selected:
            c.setFont("Helvetica-Bold", 8); c.drawString(63, yy-1, "X")
        c.setFont("Times-Bold", 7); c.drawString(76, yy, label)
        if selected:
            detail = ("Grantor is 62 years of age or over; property was owned "
                      "and occupied by grantor as principal residence at time of sale."
                      if key == "senior" else
                      "Grantor qualifies for the checked partial exemption.")
            c.setFont("Times-Roman", 6.5); c.drawString(190, yy, detail)
            lines.extend([label, detail])
        yy -= 21
    c.line(48, 310, 564, 310)

    affirmation = ("Deponent makes this Affidavit to induce the County Clerk or "
                   "Register of Deeds to record the deed and accept the fee "
                   "submitted herewith in accordance with C. 49, P.L. 1968.")
    _wrap(c, affirmation, 58, 296, 492, leading=9, size=6.8)
    lines.append(affirmation)
    c.setFont("Times-Roman", 7)
    c.drawString(48, 252, f"Subscribed and sworn to before me this {m['execution_date']:%d} day of {m['execution_date']:%B}, 1997")
    _signature(c, m["notary"], 48, 202, m["scan_seed"] + 509,
               width=115, height=32, draw_label=False)
    c.setFont("Times-Roman", 6.5)
    c.drawString(48, 190, f"{m['notary']}, Notary Public of New Jersey")
    c.drawString(48, 181, "My Commission Expires October 18, 1999")
    _signature(c, m["grantor"], 340, 202, m["scan_seed"] + 401,
               width=120, height=34, draw_label=False)
    c.setFont("Times-Roman", 6.5)
    c.drawString(340, 190, m["grantor"])
    c.drawString(340, 181, m["grantor_address"])
    lines.extend(["Subscribed and sworn to before me", f"{m['notary']}, Notary Public of New Jersey",
                  "My Commission Expires October 18, 1999", m["grantor"],
                  m["grantor_address"]])

    c.rect(230, 126, 325, 43)
    c.setFont("Times-Bold", 7); c.drawString(236, 158, "FOR OFFICIAL USE ONLY")
    c.setFont("Times-Roman", 6.5)
    c.drawString(236, 146, f"Instrument {m['instrument']}   County Morris")
    c.drawString(236, 135, f"Deed Book {m['book']}  Page {m['page']}  Recorded {m['recorded_date']:%m/%d/%Y}")
    lines.extend(["FOR OFFICIAL USE ONLY",
                  f"Instrument {m['instrument']} County Morris",
                  f"Deed Book {m['book']} Page {m['page']}"])
    c.setFont("Helvetica-Bold", 14); c.drawCentredString(PAGE_W/2, 77, "END OF DOCUMENT")
    lines.append("END OF DOCUMENT")
    _footer(c, m, 4, 4); lines.append(_footer_text(m, 4, 4))
    c.showPage(); texts.append(lines)
    c.save()
    return buf.getvalue(), texts


def render_deed(m: dict, *, metadata: dict, defect: dict | None = None) -> bytes:
    vector, pages = _render_vector(m, defect)
    def ocr(page_index, text):
        text.setFont("Helvetica", 6)
        text.setTextOrigin(40, 760)
        for line in pages[page_index]:
            text.textLine(line)
    return scan.rescan(vector, rng=random.Random(m["scan_seed"]), metadata=metadata,
                       text_layer=ocr, dpi=150)


def public_display_facts(m: dict, *, defect: dict | None = None) -> dict:
    """Return the displayed fields safe for downstream accessible renditions."""
    return {
        "instrument_type": "Bargain and Sale Deed",
        "county": m["county"],
        "municipality": m["municipality"],
        "state": m["state"],
        "street": m["street"],
        "zip": m["zip"],
        "block": m["block"],
        "lot": m["lot"],
        "execution_date": m["execution_date"].isoformat(),
        "consideration": m["consideration"],
        "grantor_name": m["grantor"],
        "grantor_address": m["grantor_address"],
        "grantee_name": m["grantee"],
        "grantee_address": m["grantee_address"],
        "grantor_spouse_name": m["grantor_spouse"],
        "signatory_names": [
            name for name in (m["grantor"], m["grantor_spouse"]) if name
        ],
        "acknowledgment_names": [
            name for name in (m["grantor"], m["grantor_spouse"]) if name
        ],
        "grantor_married": m["grantor_married"],
        "new_construction": m["new_construction"],
        "partial_exemption": m["partial_exemption"],
        "prior_book": m["prior_book"],
        "prior_page": m["prior_page"],
        "notary_name": m["notary"],
    }
