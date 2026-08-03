"""acord: ACORD 126 (2009/08) — Commercial General Liability Section, seeded.

Template-faithful rebuild. The layout contract — 4 pages, section inventory,
question text, grid anatomy, footer marks — is transcribed from the real
ACORD 126 (2009/08) form, not authored from memory. The wordmark is drawn
as text (no harvested raster trademark ships in the package).

Realism is structural and *filled-coherent*:
- Schedule of Hazards foots: premium = exposure/1,000 x rate, separately for
  Prem/Ops and Products columns; the page-1 PREMIUMS box sums the schedule.
- Limits honor the hierarchy (aggregates >= each occurrence).
- Every "Y" answer on the 35 numbered questions carries an explanation that
  surfaces in the page-4 REMARKS block (the form's own instruction:
  "EXPLAIN ALL 'YES' RESPONSES").
- No loss-history table and no signature block: those live on ACORD 125, and
  their presence on a 126 is itself a tell (our v1 made that mistake).

Defect hooks touch exactly one place each: a schedule premium that unfoots,
a PREMIUMS-box total that mis-adds, an occurrence limit exceeding the
aggregate.

Known limitation (candidate for reference-data ingestion): class codes are
plausible-form 5-digit values, not verified against the ISO CGL manual.
"""

from __future__ import annotations

import io
import random

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as rl_canvas

from . import legalpdf

PAGE_W, PAGE_H = letter
ML, MR = 24.0, 588.0  # left margin, right edge of content

# ---------------------------------------------------------------------------
# Template contract — every string below appears on the real 2009/08 form.
# Tests assert these page-by-page (in stream order) against the render.
# ---------------------------------------------------------------------------

FOOTER_MARK = "ACORD 126 (2009/08)"
COPYRIGHT_MARK = "© 1993-2009 ACORD CORPORATION.  All rights reserved."
REGISTERED_MARK = "The ACORD name and logo are registered marks of ACORD"

CONTRACTOR_QS = [
    "DOES APPLICANT DRAW PLANS, DESIGNS, OR SPECIFICATIONS FOR OTHERS?",
    "DO ANY OPERATIONS INCLUDE BLASTING OR UTILIZE OR STORE EXPLOSIVE MATERIAL?",
    "DO ANY OPERATIONS INCLUDE EXCAVATION, TUNNELING, UNDERGROUND WORK OR EARTH MOVING?",
    "DO YOUR SUBCONTRACTORS CARRY COVERAGES OR LIMITS LESS THAN YOURS?",
    "ARE SUBCONTRACTORS ALLOWED TO WORK WITHOUT PROVIDING YOU WITH A CERTIFICATE OF INSURANCE?",
    "DOES APPLICANT LEASE EQUIPMENT TO OTHERS WITH OR WITHOUT OPERATORS?",
]

PRODUCT_QS = [
    "DOES APPLICANT INSTALL, SERVICE OR DEMONSTRATE PRODUCTS?",
    'FOREIGN PRODUCTS SOLD, DISTRIBUTED, USED AS COMPONENTS?  (If "YES", attach ACORD 815)',
    "RESEARCH AND DEVELOPMENT CONDUCTED OR NEW PRODUCTS PLANNED?",
    "GUARANTEES, WARRANTIES, HOLD HARMLESS AGREEMENTS?",
    "PRODUCTS RELATED TO AIRCRAFT/SPACE INDUSTRY?",
    "PRODUCTS RECALLED, DISCONTINUED, CHANGED?",
    "PRODUCTS OF OTHERS SOLD OR RE-PACKAGED UNDER APPLICANT LABEL?",
    "PRODUCTS UNDER LABEL OF OTHERS?",
    "VENDORS COVERAGE REQUIRED?",
    "DOES ANY NAMED INSURED SELL TO OTHER NAMED INSUREDS?",
]

GENERAL_QS = [
    "ANY MEDICAL FACILITIES PROVIDED OR MEDICAL PROFESSIONALS EMPLOYED OR CONTRACTED?",
    "ANY EXPOSURE TO RADIOACTIVE/NUCLEAR MATERIALS?",
    "DO/HAVE PAST, PRESENT OR DISCONTINUED OPERATIONS INVOLVE(D) STORING, TREATING, DISCHARGING, APPLYING, DISPOSING, OR\n"
    "TRANSPORTING OF HAZARDOUS MATERIAL?  (e.g. landfills, wastes, fuel tanks, etc)",
    "ANY OPERATIONS SOLD, ACQUIRED, OR DISCONTINUED IN LAST FIVE (5) YEARS?",
    "MACHINERY OR EQUIPMENT LOANED OR RENTED TO OTHERS?",
    "ANY WATERCRAFT, DOCKS, FLOATS OWNED, HIRED OR LEASED?",
    "ANY PARKING FACILITIES OWNED/RENTED?",
    "IS A FEE CHARGED FOR PARKING?",
    "RECREATION FACILITIES PROVIDED?",
    "IS THERE A SWIMMING POOL ON THE PREMISES?",
    "SPORTING OR SOCIAL EVENTS SPONSORED?",
    "ANY STRUCTURAL ALTERATIONS CONTEMPLATED?",
    "ANY DEMOLITION EXPOSURE CONTEMPLATED?",
    "HAS APPLICANT BEEN ACTIVE IN OR IS CURRENTLY ACTIVE IN JOINT VENTURES?",
    "DO YOU LEASE EMPLOYEES TO OR FROM OTHER EMPLOYERS?",
    "IS THERE A LABOR INTERCHANGE WITH ANY OTHER BUSINESS OR SUBSIDIARIES?",
    "ARE DAY CARE FACILITIES OPERATED OR CONTROLLED?",
    "HAVE ANY CRIMES OCCURRED OR BEEN ATTEMPTED ON YOUR PREMISES WITHIN THE LAST THREE (3) YEARS?",
    "IS THERE A FORMAL, WRITTEN SAFETY AND SECURITY POLICY IN EFFECT?",
    "DOES THE BUSINESSES' PROMOTIONAL LITERATURE MAKE ANY REPRESENTATIONS ABOUT THE SAFETY OR SECURITY OF THE PREMISES?",
]

FRAUD_PARAGRAPHS = [
    "ANY PERSON WHO KNOWINGLY AND WITH INTENT TO DEFRAUD ANY INSURANCE COMPANY OR ANOTHER PERSON FILES AN APPLICATION FOR INSURANCE OR "
    "STATEMENT OF CLAIM CONTAINING ANY MATERIALLY FALSE INFORMATION, OR CONCEALS FOR THE PURPOSE OF MISLEADING INFORMATION CONCERNING ANY "
    "FACT MATERIAL THERETO, COMMITS A FRAUDULENT INSURANCE ACT, WHICH IS A CRIME AND SUBJECTS THE PERSON TO CRIMINAL AND [NY: SUBSTANTIAL] CIVIL "
    "PENALTIES.  (Not applicable in CO, DC, FL, HI, MA, NE, OH, OK, OR, VT or WA; in LA, ME, TN and VA, insurance benefits may also be denied)",
    "IN THE DISTRICT OF COLUMBIA, WARNING:  IT IS A CRIME TO PROVIDE FALSE OR MISLEADING INFORMATION TO AN INSURER FOR THE PURPOSE OF DEFRAUDING "
    "THE INSURER OR ANY OTHER PERSON.  PENALTIES INCLUDE IMPRISONMENT AND/OR FINES.",
    "IN FLORIDA, ANY PERSON WHO KNOWINGLY AND WITH INTENT TO INJURE, DEFRAUD, OR DECEIVE ANY INSURER FILES A STATEMENT OF CLAIM OR AN "
    "APPLICATION CONTAINING ANY FALSE, INCOMPLETE, OR MISLEADING INFORMATION IS GUILTY OF A FELONY OF THE THIRD DEGREE.",
    "IN MASSACHUSETTS, NEBRASKA, OREGON AND VERMONT, ANY PERSON WHO KNOWINGLY AND WITH INTENT TO DEFRAUD ANY INSURANCE COMPANY OR "
    "ANOTHER PERSON FILES AN APPLICATION FOR INSURANCE OR STATEMENT OF CLAIM CONTAINING ANY MATERIALLY FALSE INFORMATION, OR CONCEALS FOR "
    "THE PURPOSE OF MISLEADING INFORMATION CONCERNING ANY FACT MATERIAL THERETO, MAY BE COMMITTING A FRAUDULENT INSURANCE ACT, WHICH MAY BE "
    "A CRIME AND MAY SUBJECT THE PERSON TO CRIMINAL AND CIVIL PENALTIES.",
    "IN WASHINGTON, IT IS A CRIME TO KNOWINGLY PROVIDE FALSE, INCOMPLETE, OR MISLEADING INFORMATION TO AN INSURANCE COMPANY FOR THE PURPOSE OF "
    "DEFRAUDING THE COMPANY.  PENALTIES INCLUDE IMPRISONMENT, FINES, AND DENIAL OF INSURANCE BENEFITS.",
]

RATING_LEGEND = [
    "(S) GROSS SALES - PER $1,000/SALES", "(P) PAYROLL - PER $1,000/PAY",
    "(A) AREA - PER 1,000/SQ FT", "(C) TOTAL COST - PER $1,000/COST",
    "(M) ADMISSIONS - PER 1,000/ADM", "(U) UNIT - PER UNIT", "(T) OTHER",
]

# In-stream-order markers per page, for the capability test.
PAGE_MARKERS = {
    1: ["AGENCY CUSTOMER ID:", "COMMERCIAL GENERAL LIABILITY SECTION",
        "DATE (MM/DD/YYYY)", "CARRIER", "NAIC CODE", "POLICY NUMBER",
        "APPLICANT / FIRST NAMED INSURED", "COVERAGES", "LIMITS",
        "OWNER'S & CONTRACTOR'S PROTECTIVE", "DEDUCTIBLES", "GENERAL AGGREGATE",
        "LIMIT APPLIES PER:", "PRODUCTS & COMPLETED OPERATIONS AGGREGATE",
        "PERSONAL & ADVERTISING INJURY", "EACH OCCURRENCE",
        "DAMAGE TO RENTED PREMISES (each occurrence)",
        "MEDICAL EXPENSE (Any one person)", "EMPLOYEE BENEFITS", "PREMIUMS",
        "PREMISES/OPERATIONS", "OTHER COVERAGES, RESTRICTIONS AND/OR ENDORSEMENTS",
        "SCHEDULE OF HAZARDS", "RATING AND PREMIUM BASIS",
        'CLAIMS MADE (Explain all "Yes" responses)',
        "EMPLOYEE BENEFITS LIABILITY", FOOTER_MARK, "Attach to ACORD 125",
        REGISTERED_MARK],
    2: ["CONTRACTORS", "DESCRIBE THE TYPE OF WORK SUBCONTRACTED",
        "PRODUCTS / COMPLETED OPERATIONS", "ANNUAL GROSS SALES",
        "INTENDED USE", "PRINCIPAL COMPONENTS", "Page 2 of 4"],
    3: ["ADDITIONAL INTEREST / CERTIFICATE RECIPIENT",
        "ACORD 45 attached for additional names", "ADDITIONAL INSURED",
        "LIENHOLDER", "LOSS PAYEE", "MORTGAGEE", "REFERENCE / LOAN #:",
        "GENERAL INFORMATION", "Page 3 of 4"],
    4: ["GENERAL INFORMATION (continued)",
        "REMARKS (Attach ACORD 101, Additional Remarks Schedule, if more space is required)",
        "IN WASHINGTON", "Page 4 of 4"],
}

_LABEL = ("Helvetica-Bold", 5.0)
_Q = ("Helvetica", 7.0)
_FILL = ("Helvetica", 7.5)
_SECTION = ("Helvetica-Bold", 8.5)


def _wordmark(c, x, y_top, w=82, h=35):
    """The form's top-left wordmark block, drawn as text. No harvested raster
    trademark ships in the package; the layout keeps the real form's block."""
    c.setFillGray(0.12)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(x + 2, y_top - 24, "ACORD")
    c.setFont("Helvetica", 7)
    c.drawString(x + 62, y_top - 16, "\u00ae")
    c.setFont("Helvetica-Bold", 5.5)
    c.drawString(x + 2, y_top - 32, "FORMS")
    c.setFillGray(0)


# ---------------------------------------------------------------------------
# Sampled model — coherent by construction
# ---------------------------------------------------------------------------

CLASSIFICATIONS = [
    # (description, class_code, basis_code, exposure sampler, premops rate rng, products rate rng or None)
    ("Sawmills — kiln drying & planing", "58663", "(S)", ("sales", 8_000, 26_000), (1.2, 3.4), (0.6, 1.8)),
    ("Logging — mechanized harvesting", "97005", "(P)", ("payroll", 1_100, 3_600), (11.0, 24.0), None),
    ("Lumberyards — new materials only", "55371", "(S)", ("sales", 3_000, 9_000), (0.9, 2.2), (0.4, 1.1)),
    ("Timberland — owned or managed", "97047", "(P)", ("payroll", 400, 1_400), (7.0, 14.0), None),
]


def sample_126(rng: random.Random, *, insured: str | None = None) -> dict:
    """Sample a coherent ACORD 126 (2009/08) fill: limits honoring the
    aggregate hierarchy, a Schedule of Hazards that foots with split
    Prem/Ops / Products rates, and Y-answers that all carry explanations."""
    insured = insured or rng.choice([
        "Meridian Timber Products, Inc.", "Cascade Forest Products, LLC",
        "Olympic Ridge Lumber Co.", "Blue Line Timber Holdings, Inc."])
    short = insured.split()[0].upper()[:5]
    occ = rng.choice([1_000_000, 2_000_000])
    limits = {
        "general_aggregate": occ * 2,
        "products_aggregate": occ * 2,
        "personal_injury": occ,
        "each_occurrence": occ,
        "rented_premises": rng.choice([100_000, 300_000]),
        "medical_expense": rng.choice([5_000, 10_000]),
        "employee_benefits": 1_000_000,
    }
    classes = rng.sample(CLASSIFICATIONS, k=rng.randint(2, 3))
    schedule = []
    for i, (desc, code, basis, (kind, lo, hi), po_r, pr_r) in enumerate(classes, 1):
        exposure = rng.randint(lo, hi) * 1000
        rate_po = round(rng.uniform(*po_r), 3)
        rate_pr = round(rng.uniform(*pr_r), 3) if pr_r else None
        schedule.append({
            "loc": 1 if i < 3 else 2, "haz": i, "classification": desc,
            "class_code": code, "basis": basis, "exposure": exposure,
            "terr": rng.choice(["501", "502", "503"]),
            "rate_premops": rate_po, "rate_products": rate_pr,
            "prem_premops": round(exposure / 1000 * rate_po),
            "prem_products": round(exposure / 1000 * rate_pr) if rate_pr else 0,
        })
    ebl_premium = rng.randint(5, 11) * 100

    # Answers are COUPLED, not independently drawn: the same underlying fact
    # answers every question it touches, across pages. Independent draws are
    # how cross-field contradictions happen (external review, round 4:
    # "leases equipment: Y" on page 2 vs "machinery rented to others: N" on
    # page 3 is an instant underwriter flag).
    work_desc = "Log hauling, road building, site preparation and reforestation planting"
    contractors_ans = {i: "N" for i in range(1, 7)}
    contractors_exp = {}
    # the work description discloses road building/site prep -> the
    # earth-moving question cannot honestly be "N"
    contractors_ans[3] = "Y"
    contractors_exp[3] = ("Road building and site preparation are subcontracted; "
                          "certificates with equal or greater limits and written "
                          "indemnity agreements required.")
    if rng.random() < 0.5:
        contractors_ans[4] = "Y"
        contractors_exp[4] = ("Two log-hauling subcontractors carry $500,000 CSL; "
                              "certificates and indemnity agreements on file.")
    leases_equipment = rng.random() < 0.3
    if leases_equipment:
        contractors_ans[6] = "Y"
        contractors_exp[6] = "One wheel loader leased with operator to affiliated landowner (annual contract)."

    products_ans = {i: "N" for i in range(1, 11)}
    products_exp = {4: "Standard mill-grade warranties only; hold-harmless clauses in customer purchase orders."}
    products_ans[4] = "Y"

    general_ans = {i: "N" for i in range(1, 21)}
    general_exp = {3: ("Two 10,000-gallon aboveground diesel tanks at Mill No. 1; "
                       "OSFM installation approval on file; SPCC plan maintained; "
                       "pollution supplemental attached.")}
    general_ans[3] = "Y"
    general_ans[19] = "Y"
    general_exp[19] = "Formal written safety and security program; monthly supervisor safety meetings."
    if leases_equipment:  # same fact as Contractors Item 6, page-3 phrasing
        general_ans[5] = "Y"
        general_exp[5] = "One wheel loader leased with operator to affiliated landowner — see Contractors Item 6."

    full_time = rng.randint(46, 58)
    part_time = rng.randint(4, 12)
    covered = full_time - rng.randint(2, 6)   # a few FT waive coverage
    sawmill_rows = [r for r in schedule if r["class_code"] == "58663"]
    gross_sales = sawmill_rows[0]["exposure"] if sawmill_rows else rng.randint(8_000, 20_000) * 1000
    eff_month = rng.randint(1, 12)
    eff = f"{eff_month:02d}/01/2026"
    form = "OCCURRENCE" if rng.random() < 0.85 else "CLAIMS MADE"
    claims_made = ({"retro_date": eff, "entry_date": eff, "q3": "N", "q4": "N"}
                   if form == "CLAIMS MADE" else
                   {"retro_date": "", "entry_date": "", "q3": "", "q4": ""})
    return {
        "date": f"{max(1, eff_month - 1):02d}/{rng.randint(3, 27):02d}/2026",
        "agency_customer_id": f"{short}-{rng.randint(10000, 99999)}",
        "agency": rng.choice(["Cascade Risk Partners, Inc. — Portland, OR",
                              "Pacific Insurance Group — Eugene, OR"]),
        "carrier": rng.choice(["Pacific Cascade Mutual Insurance Company",
                               "Northwest Specialty Insurance Company"]),
        "naic_code": str(rng.randint(20000, 39999)),
        "policy_number": f"CPP {rng.randint(100, 999)} {rng.randint(1000, 9999)} {rng.randint(10, 99)}",
        "effective_date": eff,
        "insured": insured,
        "form": form,
        "ocp": False,
        "deductibles": {"property_damage": rng.choice([None, 1_000, 2_500]),
                        "bodily_injury": None, "per": "CLAIM"},
        "limit_applies_per": "POLICY",
        "limits": limits,
        "other_coverages": (
            "Blanket additional insured — owners, lessees or contractors (CG 20 33) and "
            "completed operations (CG 20 37) where required by written contract; waiver of "
            "transfer of rights of recovery (CG 24 04) in favor of certificate holders "
            "where required by written contract. "
            "Hired/non-owned auto to be covered under Business Auto Section, ACORD 137."),
        "schedule": schedule,
        "ebl_premium": ebl_premium,
        "claims_made": claims_made,
        "employee_benefits": {"deductible": 1_000,
                              "employees": full_time + part_time,
                              "covered": covered,
                              # EBL is claims-made coverage regardless of the
                              # CGL form: a continuous-coverage retro date is
                              # always present, never "N/A"
                              "retro_date": f"{eff_month:02d}/01/{2026 - rng.randint(4, 12)}"},
        "contractors": {
            "answers": contractors_ans, "explanations": contractors_exp,
            "work_desc": work_desc,
            "paid_subs": rng.randint(350, 1_400) * 1000,
            "pct_sub": rng.randint(10, 30),
            "full_time": full_time, "part_time": part_time},
        "products_section": {
            "rows": [{"name": "Dimensional lumber",
                      "gross_sales": gross_sales, "units": "N/A",
                      "time_market": "40 YRS", "expected_life": "50+ YRS",
                      "use": "Structural framing lumber",
                      "components": "Kiln-dried fir, hemlock"}],
            "answers": products_ans, "explanations": products_exp},
        "additional_interest": {
            "interest": "ADDITIONAL INSURED",
            "name_addr": ["Cascadia First Bank, N.A.", "840 SW Broadway, Suite 1100",
                          "Portland, OR 97205"],
            "certificate": True, "reference": f"L-{rng.randint(2000, 4999)}-{rng.randint(1000, 9999)}",
            "location": "001", "building": "001",
            "item_desc": "Premises liability — additional insured per written loan agreement"},
        "general_info": {"answers": general_ans, "explanations": general_exp},
    }


def compute_totals(model: dict) -> dict:
    po = sum(r["prem_premops"] for r in model["schedule"])
    pr = sum(r["prem_products"] for r in model["schedule"])
    return {"premises_operations": po, "products": pr,
            "other": model["ebl_premium"], "total": po + pr + model["ebl_premium"]}


def remarks_lines(model: dict) -> list[str]:
    """Every Y answer surfaces here — coherence with the form's own
    'EXPLAIN ALL YES RESPONSES' instruction."""
    out = []
    for section, key in (("CONTRACTORS", "contractors"),
                         ("PRODUCTS/COMPLETED OPS", "products_section"),
                         ("GENERAL INFORMATION", "general_info")):
        block = model[key]
        for num in sorted(block["explanations"]):
            if block["answers"].get(num) == "Y":
                out.append(f"{section} ITEM {num}: {block['explanations'][num]}")
    return out


# ---------------------------------------------------------------------------
# Drawing helpers (top-down coordinates)
# ---------------------------------------------------------------------------

def _y(top: float) -> float:
    return PAGE_H - top


def _box(c, x, top, w, h):
    c.rect(x, _y(top) - h, w, h)


def _text(c, x, top, s, font=_Q, right=False, center_w=None):
    c.setFont(*font)
    if center_w is not None:
        c.drawCentredString(x + center_w / 2, _y(top), s)
    elif right:
        c.drawRightString(x, _y(top), s)
    else:
        c.drawString(x, _y(top), s)


def _label(c, x, top, s):
    _text(c, x + 2, top + 6.5, s, font=_LABEL)


def _fill(c, x, top, s, right=False):
    _text(c, x, top, s, font=_FILL, right=right)


def _check(c, x, top, checked=False, size=7.5):
    # `top` is the baseline of the adjacent label; box sits centered on it
    c.rect(x, _y(top) - 1.5, size, size)
    if checked:
        c.setFont("Helvetica-Bold", size - 1)
        c.drawCentredString(x + size / 2, _y(top) - 0.5, "X")


def _section_hdr(c, x, top, s):
    _text(c, x, top, s, font=_SECTION)


def _agency_customer_id(c, value):
    _text(c, 306, 40, "AGENCY CUSTOMER ID:", font=("Helvetica-Bold", 7))
    c.setLineWidth(0.7)
    c.line(392, _y(41.5), MR, _y(41.5))
    _text(c, 398, 40, value, font=_FILL)


def _footer(c, page_num):
    c.setLineWidth(0.9)
    _text(c, ML, 762, FOOTER_MARK, font=("Helvetica-Bold", 8.5))
    if page_num == 1:
        _text(c, 306, 762, "Attach to ACORD 125", font=("Helvetica-Bold", 8.5), center_w=0)
        _text(c, MR, 762, COPYRIGHT_MARK, font=("Helvetica-Bold", 8.5), right=True)
        _text(c, 306, 774, REGISTERED_MARK, font=("Helvetica-Bold", 8.5), center_w=0)
    else:
        _text(c, 306, 762, f"Page {page_num} of 4", font=("Helvetica-Bold", 8.5), center_w=0)


def _yn_block(c, top, questions, answers, explanations, row_h, bar_note=""):
    """The EXPLAIN-ALL-YES question grid: full-width box per question, Y/N
    answer box at right, explanation text under Y answers."""
    bar_h = 11
    c.setLineWidth(0.7)
    _box(c, ML, top, MR - ML, bar_h)
    _text(c, ML + 2, top + 8.2,
          'EXPLAIN ALL "YES" RESPONSES (For all past or present operations)' if not bar_note else bar_note,
          font=("Helvetica-Bold", 6))
    _text(c, MR - 22, top + 8.2, "Y / N", font=("Helvetica-Bold", 6))
    y = top + bar_h
    for i, q in enumerate(questions, 1):
        h = row_h * (1.55 if "\n" in q else 1.0)
        _box(c, ML, y, MR - ML, h)
        lines = q.split("\n")
        for j, ln in enumerate(lines):
            _text(c, ML + 4 + (10 if j else 0), y + 9 + j * 8.2,
                  (f"{i}." if j == 0 else "") + ("  " if j == 0 else "") + ln, font=_Q)
        ans = answers.get(i, "")
        bx = MR - 20
        c.rect(bx, _y(y + h - 3), 11, 10)
        if ans:
            c.setFont("Helvetica", 7.5)
            c.drawCentredString(bx + 5.5, _y(y + h - 3) + 2.2, ans)
        if answers.get(i) == "Y" and i in explanations:
            _fill(c, ML + 16, y + h - 5, explanations[i])
        y += h
    return y


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def _page1(c, m, totals, defect):
    _agency_customer_id(c, m["agency_customer_id"])
    _wordmark(c, ML, _y(76) + 35)
    _text(c, 300, 70, "COMMERCIAL GENERAL LIABILITY SECTION",
          font=("Helvetica-Bold", 14.5), center_w=0)
    c.setLineWidth(0.9)
    _box(c, 494, 50, MR - 494, 26)
    _label(c, 494, 50, "DATE (MM/DD/YYYY)")
    _fill(c, 500, 70, m["date"])

    # id rows
    _box(c, ML, 80, 300, 24); _label(c, ML, 80, "AGENCY")
    _fill(c, ML + 4, 98, m["agency"])
    _box(c, 324, 80, 204, 24); _label(c, 324, 80, "CARRIER")
    _fill(c, 328, 98, m["carrier"])
    _box(c, 528, 80, MR - 528, 24); _label(c, 528, 80, "NAIC CODE")
    _fill(c, 532, 98, m["naic_code"])
    _box(c, ML, 104, 240, 24); _label(c, ML, 104, "POLICY NUMBER")
    _fill(c, ML + 4, 122, m["policy_number"])
    _box(c, 264, 104, 84, 24); _label(c, 264, 104, "EFFECTIVE DATE")
    _fill(c, 268, 122, m["effective_date"])
    _box(c, 348, 104, MR - 348, 24); _label(c, 348, 104, "APPLICANT / FIRST NAMED INSURED")
    _fill(c, 352, 122, m["insured"])

    # coverages / limits / premiums
    _section_hdr(c, ML, 140, "COVERAGES")
    _section_hdr(c, 234, 140, "LIMITS")
    top, bot = 144, 268
    _box(c, ML, top, 206, bot - top)          # left: coverages
    _box(c, 230, top, 256, bot - top)         # mid: limits
    _box(c, 486, top, MR - 486, bot - top)    # right: premiums

    _check(c, ML + 4, top + 13, checked=True)
    _text(c, ML + 16, top + 13, "COMMERCIAL GENERAL LIABILITY", font=("Helvetica-Bold", 6.3))
    _check(c, ML + 18, top + 27, checked=m["form"] == "CLAIMS MADE")
    _text(c, ML + 30, top + 27, "CLAIMS MADE", font=_Q)
    _check(c, ML + 90, top + 27, checked=m["form"] == "OCCURRENCE")
    _text(c, ML + 102, top + 27, "OCCURRENCE", font=_Q)
    _check(c, ML + 4, top + 42, checked=m["ocp"])
    _text(c, ML + 16, top + 42, "OWNER'S & CONTRACTOR'S PROTECTIVE", font=("Helvetica-Bold", 6.3))
    _text(c, ML + 4, top + 60, "DEDUCTIBLES", font=("Helvetica-Bold", 6.3))
    ded = m["deductibles"]
    _text(c, ML + 10, top + 74, "PROPERTY DAMAGE", font=_Q)
    _text(c, ML + 88, top + 74, "$", font=_Q)
    if ded["property_damage"]:
        _fill(c, ML + 96, top + 74, f"{ded['property_damage']:,}")
    _text(c, ML + 10, top + 88, "BODILY INJURY", font=_Q)
    _text(c, ML + 88, top + 88, "$", font=_Q)
    if ded["bodily_injury"]:
        _fill(c, ML + 96, top + 88, f"{ded['bodily_injury']:,}")
    _text(c, ML + 88, top + 102, "$", font=_Q)
    _check(c, ML + 148, top + 74, checked=ded["per"] == "CLAIM", size=6.5)
    _text(c, ML + 157, top + 71, "PER", font=("Helvetica", 5)); _text(c, ML + 157, top + 77, "CLAIM", font=("Helvetica", 5))
    _check(c, ML + 148, top + 90, checked=ded["per"] == "OCCURRENCE", size=6.5)
    _text(c, ML + 157, top + 87, "PER", font=("Helvetica", 5)); _text(c, ML + 157, top + 93, "OCCURRENCE", font=("Helvetica", 5))

    lim = dict(m["limits"])
    if defect and "each_occurrence" in defect:
        lim["each_occurrence"] = defect["each_occurrence"]
    lx, lv = 234, 424
    rows = [("GENERAL AGGREGATE", lim["general_aggregate"]), (None, None),
            ("PRODUCTS & COMPLETED OPERATIONS AGGREGATE", lim["products_aggregate"]),
            ("PERSONAL & ADVERTISING INJURY", lim["personal_injury"]),
            ("EACH OCCURRENCE", lim["each_occurrence"]),
            ("DAMAGE TO RENTED PREMISES (each occurrence)", lim["rented_premises"]),
            ("MEDICAL EXPENSE (Any one person)", lim["medical_expense"]),
            ("EMPLOYEE BENEFITS", lim["employee_benefits"]), ("", None)]
    ly = top + 12
    for label_txt, val in rows:
        if label_txt is None:  # LIMIT APPLIES PER row
            _text(c, lx, ly, "LIMIT APPLIES PER:", font=("Helvetica-Bold", 6.3))
            px = lx + 70
            for opt in ("POLICY", "LOCATION", "PROJECT", "OTHER:"):
                _check(c, px, ly, checked=m["limit_applies_per"] == opt.rstrip(":"), size=6)
                _text(c, px + 8, ly, opt, font=_Q)
                px += 46 if opt != "LOCATION" else 50
        else:
            if label_txt:
                _text(c, lx, ly, label_txt, font=("Helvetica-Bold", 6.3))
            _text(c, lv, ly, "$", font=_Q)
            if val is not None:
                _fill(c, lv + 8, ly, f"{val:,}")
        ly += 13.5

    px_, pv = 490, MR - 4
    _text(c, 490 + (MR - 490) / 2, top + 11, "PREMIUMS", font=("Helvetica-Bold", 6.5), center_w=0)
    shown_total = defect["premium_total"] if defect and "premium_total" in defect else totals["total"]
    for i, (label_txt, val) in enumerate([
            ("PREMISES/OPERATIONS", totals["premises_operations"]),
            ("PRODUCTS", totals["products"]),
            ("OTHER", totals["other"]),
            ("TOTAL", shown_total)]):
        yy = top + 26 + i * 24
        _text(c, px_, yy, label_txt, font=("Helvetica-Bold", 6.3))
        _text(c, px_, yy + 12, "$", font=_Q)
        _fill(c, pv, yy + 12, f"{val:,}", right=True)

    # other coverages
    _box(c, ML, 272, MR - ML, 62)
    _text(c, ML + 2, 280, "OTHER COVERAGES, RESTRICTIONS AND/OR ENDORSEMENTS (For hired/non-owned auto coverages attach the applicable state Business Auto Section, ACORD 137)",
          font=("Helvetica-Bold", 5.8))
    words = m["other_coverages"].split()
    line, yy = "", 292
    for w in words:
        if c.stringWidth(line + " " + w, *_FILL) > MR - ML - 16:
            _fill(c, ML + 6, yy, line.strip()); yy += 9.5; line = w
        else:
            line += " " + w
    _fill(c, ML + 6, yy, line.strip())

    # schedule of hazards
    _section_hdr(c, ML, 346, "SCHEDULE OF HAZARDS")
    cols = [ML, 46, 68, 208, 244, 288, 352, 380, 428, 476, 532, MR]
    head_top, head_h = 350, 20
    _box(c, ML, head_top, MR - ML, head_h)
    for x in cols[1:-1]:
        c.line(x, _y(head_top), x, _y(head_top + head_h))
    hdr = ["LOC\n#", "HAZ\n#", "CLASSIFICATION", "CLASS\nCODE", "PREMIUM\nBASIS",
           "EXPOSURE", "TERR"]
    for i, htxt in enumerate(hdr):
        cx = (cols[i] + cols[i + 1]) / 2
        for j, ln in enumerate(htxt.split("\n")):
            c.setFont("Helvetica-Bold", 5.3)
            c.drawCentredString(cx, _y(head_top + 8 + j * 6 + (3 if "\n" not in htxt else 0)), ln)
    # RATE / PREMIUM spanning headers
    c.line(cols[7], _y(head_top + 10), cols[9], _y(head_top + 10))
    c.line(cols[9], _y(head_top + 10), cols[11], _y(head_top + 10))
    c.setFont("Helvetica-Bold", 5.3)
    c.drawCentredString((cols[7] + cols[9]) / 2, _y(head_top + 7.5), "RATE")
    c.drawCentredString((cols[9] + cols[11]) / 2, _y(head_top + 7.5), "PREMIUM")
    for cx0, cx1, s in ((cols[7], cols[8], "PREM/OPS"), (cols[8], cols[9], "PRODUCTS"),
                        (cols[9], cols[10], "PREM/OPS"), (cols[10], cols[11], "PRODUCTS")):
        c.drawCentredString((cx0 + cx1) / 2, _y(head_top + 17), s)

    row_top, row_h, n_rows = head_top + head_h, 24, 8
    for r in range(n_rows):
        _box(c, ML, row_top + r * row_h, MR - ML, row_h)
        for x in cols[1:-1]:
            c.line(x, _y(row_top + r * row_h), x, _y(row_top + (r + 1) * row_h))
    for i, row in enumerate(m["schedule"]):
        yy = row_top + i * row_h + 13
        prem_po = row["prem_premops"]
        if defect and "premium_row" in defect and defect["premium_row"][0] == i:
            prem_po = defect["premium_row"][1]
        c.setFont(*_FILL)
        c.drawCentredString((cols[0] + cols[1]) / 2, _y(yy), str(row["loc"]))
        c.drawCentredString((cols[1] + cols[2]) / 2, _y(yy), str(row["haz"]))
        _fill(c, cols[2] + 3, yy, row["classification"])
        c.drawCentredString((cols[3] + cols[4]) / 2, _y(yy), row["class_code"])
        c.drawCentredString((cols[4] + cols[5]) / 2, _y(yy), row["basis"])
        _fill(c, cols[6] - 4, yy, f"{row['exposure']:,}", right=True)
        c.drawCentredString((cols[6] + cols[7]) / 2, _y(yy), row["terr"])
        _fill(c, cols[8] - 4, yy, f"{row['rate_premops']:.3f}", right=True)
        if row["rate_products"]:
            _fill(c, cols[9] - 4, yy, f"{row['rate_products']:.3f}", right=True)
        _fill(c, cols[10] - 4, yy, f"{prem_po:,}", right=True)
        if row["prem_products"]:
            _fill(c, cols[11] - 4, yy, f"{row['prem_products']:,}", right=True)

    leg_top = row_top + n_rows * row_h + 4
    _text(c, ML, leg_top + 6, "RATING AND PREMIUM BASIS", font=("Helvetica-Bold", 6.3))
    for i, item in enumerate(RATING_LEGEND):
        col, r_ = i % 3, i // 3
        _text(c, ML + 130 + col * 155, leg_top + r_ * 8 + 2, item, font=("Helvetica", 5.6))

    # claims made
    cm_top = leg_top + 24
    _section_hdr(c, ML, cm_top + 6, 'CLAIMS MADE (Explain all "Yes" responses)')
    bar_top = cm_top + 9
    _box(c, ML, bar_top, MR - ML, 10)
    _text(c, ML + 2, bar_top + 7.5, 'EXPLAIN ALL "YES" RESPONSES', font=("Helvetica-Bold", 6))
    _text(c, MR - 22, bar_top + 7.5, "Y / N", font=("Helvetica-Bold", 6))
    cm = m["claims_made"]
    qy = bar_top + 10
    for txt, val, has_box in [
            ("1.  PROPOSED RETROACTIVE DATE:", cm["retro_date"], False),
            ("2.  ENTRY DATE INTO UNINTERRUPTED CLAIMS MADE COVERAGE:", cm["entry_date"], False),
            ("3.  HAS ANY PRODUCT, WORK, ACCIDENT, OR LOCATION BEEN EXCLUDED, UNINSURED OR SELF-INSURED FROM ANY PREVIOUS COVERAGE?", cm["q3"], True),
            ("4.  WAS TAIL COVERAGE PURCHASED UNDER ANY PREVIOUS POLICY?", cm["q4"], True)]:
        h = 15 if not has_box else 22
        _box(c, ML, qy, MR - ML, h)
        _text(c, ML + 4, qy + 9, txt, font=_Q)
        if has_box:
            c.rect(MR - 20, _y(qy + h - 3), 11, 10)
            if val and m["form"] == "CLAIMS MADE":
                c.setFont("Helvetica", 7.5)
                c.drawCentredString(MR - 14.5, _y(qy + h - 3) + 2.2, val)
        elif val:
            _fill(c, ML + 220, qy + 9, val)
        qy += h

    # employee benefits liability
    _section_hdr(c, ML, qy + 12, "EMPLOYEE BENEFITS LIABILITY")
    eb, eb_top = m["employee_benefits"], qy + 15
    half = (ML + MR) / 2
    _box(c, ML, eb_top, half - ML, 13); _box(c, half, eb_top, MR - half, 13)
    _box(c, ML, eb_top + 13, half - ML, 13); _box(c, half, eb_top + 13, MR - half, 13)
    _text(c, ML + 3, eb_top + 9.5, "1.  DEDUCTIBLE PER CLAIM:   $", font=_Q)
    _fill(c, ML + 120, eb_top + 9.5, f"{eb['deductible']:,}")
    _text(c, half + 3, eb_top + 9.5, "3.  NUMBER OF EMPLOYEES COVERED BY EMPLOYEE BENEFITS PLANS", font=_Q)
    _fill(c, MR - 8, eb_top + 9.5, str(eb["covered"]), right=True)
    _text(c, ML + 3, eb_top + 22.5, "2.  NUMBER OF EMPLOYEES:", font=_Q)
    _fill(c, ML + 120, eb_top + 22.5, str(eb["employees"]))
    _text(c, half + 3, eb_top + 22.5, "4.  RETROACTIVE DATE:", font=_Q)
    _fill(c, half + 95, eb_top + 22.5, eb["retro_date"])
    _footer(c, 1)


def _page2(c, m):
    _agency_customer_id(c, m["agency_customer_id"])
    _section_hdr(c, ML, 56, "CONTRACTORS")
    ct = m["contractors"]
    y = _yn_block(c, 59, CONTRACTOR_QS, ct["answers"], ct["explanations"], 44)
    # subcontract detail row
    _box(c, ML, y, MR - ML, 40)
    xs = [ML, 250, 388, 470, 528, MR]
    for x in xs[1:-1]:
        c.line(x, _y(y), x, _y(y + 40))
    labels = ["DESCRIBE THE TYPE OF WORK SUBCONTRACTED", "$ PAID TO SUB-\nCONTRACTORS:",
              "% OF WORK\nSUBCONTRACTED:", "# FULL-\nTIME STAFF:", "# PART-\nTIME STAFF:"]
    for i, lab in enumerate(labels):
        for j, ln in enumerate(lab.split("\n")):
            _text(c, xs[i] + 2, y + 7 + j * 6, ln, font=("Helvetica-Bold", 5.3))
    for j, ln in enumerate(_wrap(c, ct["work_desc"], 250 - ML - 8, _FILL)):
        _fill(c, ML + 4, y + 22 + j * 9, ln)
    _fill(c, xs[1] + 4, y + 28, f"{ct['paid_subs']:,}")
    _fill(c, xs[2] + 4, y + 28, f"{ct['pct_sub']}%")
    _fill(c, xs[3] + 4, y + 28, str(ct["full_time"]))
    _fill(c, xs[4] + 4, y + 28, str(ct["part_time"]))
    y += 48

    _section_hdr(c, ML + 8, y + 8, "PRODUCTS / COMPLETED OPERATIONS")
    y += 12
    pcols = [ML, 130, 232, 300, 342, 384, 486, MR]
    _box(c, ML, y, MR - ML, 14)
    for x in pcols[1:-1]:
        c.line(x, _y(y), x, _y(y + 14))
    for i, htxt in enumerate(["PRODUCTS", "ANNUAL GROSS SALES", "# OF UNITS",
                              "TIME IN\nMARKET", "EXPECTED\nLIFE", "INTENDED USE",
                              "PRINCIPAL COMPONENTS"]):
        cx = (pcols[i] + pcols[i + 1]) / 2
        lines = htxt.split("\n")
        for j, ln in enumerate(lines):
            c.setFont("Helvetica-Bold", 5.3)
            c.drawCentredString(cx, _y(y + (9 if len(lines) == 1 else 6 + j * 6)), ln)
    y += 14
    ps = m["products_section"]
    for r in range(3):
        _box(c, ML, y, MR - ML, 26)
        for x in pcols[1:-1]:
            c.line(x, _y(y), x, _y(y + 26))
        if r < len(ps["rows"]):
            row = ps["rows"][r]
            _fill(c, ML + 3, y + 12, row["name"])
            _fill(c, pcols[2] - 4, y + 12, f"{row['gross_sales']:,}", right=True)
            c.setFont(*_FILL)
            c.drawCentredString((pcols[2] + pcols[3]) / 2, _y(y + 12), row["units"])
            c.drawCentredString((pcols[3] + pcols[4]) / 2, _y(y + 12), row["time_market"])
            c.drawCentredString((pcols[4] + pcols[5]) / 2, _y(y + 12), row["expected_life"])
            _fill(c, pcols[5] + 3, y + 12, row["use"])
            _fill(c, pcols[6] + 3, y + 12, row["components"])
        y += 26
    _yn_block(c, y + 4, PRODUCT_QS, ps["answers"], ps["explanations"], 25,
              bar_note='EXPLAIN ALL "YES" RESPONSES (For all past or present products or operations)    PLEASE ATTACH LITERATURE, BROCHURES, LABELS, WARNINGS, ETC.')
    _footer(c, 2)


def _page3(c, m):
    _agency_customer_id(c, m["agency_customer_id"])
    ai = m["additional_interest"]
    _section_hdr(c, ML, 58, "ADDITIONAL INTEREST / CERTIFICATE RECIPIENT")
    _check(c, 262, 58, checked=False)
    _text(c, 274, 58, "ACORD 45 attached for additional names", font=("Helvetica-Bold", 7))
    top, h = 62, 96
    _box(c, ML, top, MR - ML, h)
    c.line(130, _y(top), 130, _y(top + h))
    c.line(486, _y(top), 486, _y(top + h))
    _text(c, ML + 2, top + 8, "INTEREST", font=("Helvetica-Bold", 5.3))
    for i, opt in enumerate(["ADDITIONAL INSURED", "EMPLOYEE AS LESSOR", "LIENHOLDER",
                             "LOSS PAYEE", "MORTGAGEE"]):
        _check(c, ML + 6, top + 17 + i * 13, checked=ai["interest"] == opt, size=6.5)
        _text(c, ML + 16, top + 17 + i * 13, opt, font=("Helvetica-Bold", 5.8))
    _text(c, 134, top + 8, "NAME AND ADDRESS   RANK:", font=("Helvetica-Bold", 5.3))
    _text(c, 254, top + 8, "EVIDENCE:", font=("Helvetica-Bold", 5.3))
    _check(c, 296, top + 8, size=6)
    _text(c, 316, top + 8, "CERTIFICATE", font=("Helvetica-Bold", 5.3))
    _check(c, 366, top + 8, checked=ai["certificate"], size=6)
    for i, ln in enumerate(ai["name_addr"]):
        _fill(c, 138, top + 24 + i * 10, ln)
    c.line(130, _y(top + 78), 486, _y(top + 78))
    _text(c, 134, top + 86, "REFERENCE / LOAN #:", font=("Helvetica-Bold", 5.3))
    _fill(c, 216, top + 86, ai["reference"])
    _text(c, 490, top + 8, "INTEREST IN ITEM NUMBER", font=("Helvetica-Bold", 5.3))
    _text(c, 490, top + 22, "LOCATION:", font=("Helvetica-Bold", 5.3))
    _fill(c, 528, top + 22, ai["location"])
    _text(c, 490, top + 36, "BUILDING:", font=("Helvetica-Bold", 5.3))
    _fill(c, 528, top + 36, ai["building"])
    _text(c, 490, top + 50, "ITEM DESCRIPTION", font=("Helvetica-Bold", 5.3))
    for i, w in enumerate(_wrap(c, ai["item_desc"], MR - 494, _FILL)):
        _fill(c, 490, top + 60 + i * 9, w)

    _section_hdr(c, ML, top + h + 14, "GENERAL INFORMATION")
    gi = m["general_info"]
    _yn_block(c, top + h + 17, GENERAL_QS[:15], gi["answers"], gi["explanations"], 35)
    _footer(c, 3)


def _page4(c, m):
    _agency_customer_id(c, m["agency_customer_id"])
    _section_hdr(c, ML, 58, "GENERAL INFORMATION (continued)")
    gi = m["general_info"]
    q16 = GENERAL_QS[15:]
    bar_h, y = 11, 61
    c.setLineWidth(0.7)
    _box(c, ML, y, MR - ML, bar_h)
    _text(c, ML + 2, y + 8.2, 'EXPLAIN ALL "YES" RESPONSES (For all past or present operations)',
          font=("Helvetica-Bold", 6))
    _text(c, MR - 22, y + 8.2, "Y / N", font=("Helvetica-Bold", 6))
    y += bar_h
    for i, q in enumerate(q16, 16):
        h = 36
        _box(c, ML, y, MR - ML, h)
        _text(c, ML + 4, y + 9, f"{i}.  {q}", font=_Q)
        ans = gi["answers"].get(i, "")
        c.rect(MR - 20, _y(y + h - 3), 11, 10)
        if ans:
            c.setFont("Helvetica", 7.5)
            c.drawCentredString(MR - 14.5, _y(y + h - 3) + 2.2, ans)
        if ans == "Y" and i in gi["explanations"]:
            _fill(c, ML + 16, y + h - 5, gi["explanations"][i])
        y += h

    _section_hdr(c, ML, y + 14, "REMARKS (Attach ACORD 101, Additional Remarks Schedule, if more space is required)")
    rem_top = y + 18
    rem_h = 640 - rem_top
    _box(c, ML, rem_top, MR - ML, rem_h)
    yy = rem_top + 14
    for line in remarks_lines(m):
        for w in _wrap(c, line, MR - ML - 16, _FILL):
            _fill(c, ML + 6, yy, w)
            yy += 10
        yy += 3

    fy = 648
    for para in FRAUD_PARAGRAPHS:
        lines = _wrap(c, para, MR - ML - 8, ("Helvetica", 6.4))
        for ln in lines:
            _text(c, ML + 4, fy, ln, font=("Helvetica", 6.4))
            fy += 7.0
        fy += 2.5
    _footer(c, 4)


def _wrap(c, text, width, font):
    words, out, line = text.split(), [], ""
    for w in words:
        cand = (line + " " + w).strip()
        if c.stringWidth(cand, *font) > width and line:
            out.append(line)
            line = w
        else:
            line = cand
    if line:
        out.append(line)
    return out


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def render_126(model: dict, *, metadata: dict, defect: dict | None = None) -> bytes:
    """Render a filled ACORD 126 (2009/08) as a 4-page PDF. Defect hooks:
    {"premium_row": (idx, value)} — one schedule Prem/Ops premium unfoots;
    {"premium_total": value} — the PREMIUMS box TOTAL mis-adds;
    {"each_occurrence": value} — occurrence limit exceeds the aggregate."""
    totals = compute_totals(model)
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=letter, invariant=1)
    c.setTitle("ACORD 126 - Commercial General Liability Section")
    c.setProducer(metadata["producer"])
    c.setCreator(metadata["creator"])
    c.setLineWidth(0.7)
    for page_fn in (_page1, _page2, _page3, _page4):
        c.setLineWidth(0.7)
        if page_fn is _page1:
            page_fn(c, model, totals, defect)
        else:
            page_fn(c, model)
        c.showPage()
    c.save()
    out = legalpdf._fix_dates(buf.getvalue(), created=metadata.get("created"),
                              modified=metadata.get("modified"))
    return legalpdf._fix_id(out)
