"""acord130: ACORD 130 (2017/05) — Workers Compensation Application, seeded.

A sibling of `acord`, not an extension of it. The 126 is a General Liability
SECTION that attaches to a 125; the 130 is a standalone application that
carries its own state rating worksheet and its own premium algebra. Same
family, different instrument.

The layout contract — 4 pages, section inventory, the 24-question battery,
the preprinted state fraud paragraphs, the per-page footer structure — is
transcribed from the real ACORD 130 (2017/05), read as rasterised images
before any code was written.

That fixes the blank. It fixes nothing about how a FILLED one is filled,
which is the half that decides whether an underwriter believes it. So the
jurisdiction was sourced separately, from MWCIA — Minnesota's licensed data
service organisation, not NCCI:

- The classification is DERIVED. A gasoline station is Code 8380, 8006 or
  8381 depending on whether the insured pumps gas and on what share of total
  receipts gasoline is. Two facts about the risk decide the code; the code is
  never sampled beside them.
- The premium build-up follows the Minnesota order: manual premium, then the
  experience modification (only if the risk is eligible for one), then
  increased employers-liability limits, giving STANDARD PREMIUM — which by
  rule excludes the expense constant, the Special Compensation Fund surcharge
  and Terrorism. Those three are added afterwards, and Terrorism is subject to
  no modification at all.
- The state is a GATE, not a label. `MN_RATING` is the only rating world
  sourced, so asking for another state raises rather than rendering a
  worksheet whose premium box belongs to no bureau.

The guard list is the part worth reading twice. Minnesota's User's Guide
publishes which pricing programs exist here, and three rows the form prints
are unavailable in this state: ARAP, the Assigned Risk Surcharge, and
Catastrophe (a non-ratable element, and non-ratable elements do not apply in
Minnesota). CCPAP is printed with NCCI's name; Minnesota's counterpart is
MCPAP and it is a contractor program, so a mercantile gasoline station earns
nothing under either. And the NCCI RISK ID box belongs to a risk in an NCCI
state — a Minnesota risk fills OTHER RATING BUREAU ID instead. Filling any of
them is the fault this module exists to make impossible.

Defect hooks each touch exactly one displayed value: a worksheet row whose
manual premium stops footing, a total that mis-adds, an experience
modification on a risk that is not eligible for one, and an ARAP charge in a
state that has no ARAP.

Not sourced, and therefore not invented: the NAIC company code and the
National Producer Number are left blank. An identifier that fails lookup is a
worse tell than an absent one, because it advertises that it should resolve.
"""

from __future__ import annotations

import datetime as _dt
import io
import random

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as rl_canvas

from . import legalpdf
from .acord import _box, _check, _fill, _label, _section_hdr, _text, _wrap, _y

PAGE_W, PAGE_H = letter
ML, MR = 24.0, 588.0

FOOTER_MARK = "ACORD 130 (2017/05)"
COPYRIGHT_MARK = "© 1980-2017 ACORD CORPORATION.  All rights reserved."
REGISTERED_MARK = "The ACORD name and logo are registered marks of ACORD"

_LABEL = ("Helvetica-Bold", 5.0)
_Q = ("Helvetica", 7.0)
_FILL = ("Helvetica", 7.5)

# ---------------------------------------------------------------------------
# Template contract — every string below appears on the real 2017/05 form.
# ---------------------------------------------------------------------------

GENERAL_QS = [
    "DOES APPLICANT OWN, OPERATE OR LEASE AIRCRAFT / WATERCRAFT?",
    "DO / HAVE PAST, PRESENT OR DISCONTINUED OPERATIONS INVOLVE(D) STORING, TREATING, DISCHARGING, APPLYING, DISPOSING, OR\n"
    "TRANSPORTING OF HAZARDOUS MATERIAL? (e.g. landfills, wastes, fuel tanks, etc)",
    "ANY WORK PERFORMED UNDERGROUND OR ABOVE 15 FEET?",
    "ANY WORK PERFORMED ON BARGES, VESSELS, DOCKS, BRIDGE OVER WATER?",
    "IS APPLICANT ENGAGED IN ANY OTHER TYPE OF BUSINESS?",
    'ARE SUB-CONTRACTORS USED? (If "YES", give % of work subcontracted)',
    'ANY WORK SUBLET WITHOUT CERTIFICATES OF INSURANCE?  (If "YES", payroll for this work must be included in the State Rating Worksheet on Page 2)',
    "IS A WRITTEN SAFETY PROGRAM IN OPERATION?",
    "ANY GROUP TRANSPORTATION PROVIDED?",
    "ANY EMPLOYEES UNDER 16 OR OVER 60 YEARS OF AGE?",
    "ANY SEASONAL EMPLOYEES?",
    'IS THERE ANY VOLUNTEER OR DONATED LABOR?  (If "YES", please specify)',
    "ANY EMPLOYEES WITH PHYSICAL HANDICAPS?",
    'DO EMPLOYEES TRAVEL OUT OF STATE?  (If "YES", indicate state(s) of travel and frequency)',
    "ARE ATHLETIC TEAMS SPONSORED?",
    "ARE PHYSICALS REQUIRED AFTER OFFERS OF EMPLOYMENT ARE MADE?",
    "ANY OTHER INSURANCE WITH THIS INSURER?",
    "ANY PRIOR COVERAGE DECLINED / CANCELLED / NON-RENEWED IN THE LAST THREE (3) YEARS? (Missouri Applicants - Do not answer this question)",
    "ARE EMPLOYEE HEALTH PLANS PROVIDED?",
    "DO ANY EMPLOYEES PERFORM WORK FOR OTHER BUSINESSES OR SUBSIDIARIES?",
    "DO YOU LEASE EMPLOYEES TO OR FROM OTHER EMPLOYERS?",
    'DO ANY EMPLOYEES PREDOMINANTLY WORK AT HOME?  If "YES", # of Employees:  ______',
    'ANY TAX LIENS OR BANKRUPTCY WITHIN THE LAST FIVE (5) YEARS?  (If "YES", please specify)',
    "ANY UNDISPUTED AND UNPAID WORKERS COMPENSATION PREMIUM DUE FROM YOU OR ANY COMMONLY MANAGED OR OWNED ENTERPRISES?\n"
    "IF YES, EXPLAIN INCLUDING ENTITY NAME(S) AND POLICY NUMBER(S).",
]

NATURE_OF_BUSINESS_PROMPT = (
    "GIVE COMMENTS AND DESCRIPTIONS OF BUSINESS, OPERATIONS AND PRODUCTS: MANUFACTURING - RAW MATERIALS, PROCESSES, PRODUCT, EQUIPMENT; CONTRACTOR - TYPE\n"
    "OF WORK, SUB-CONTRACTS; MERCANTILE - MERCHANDISE, CUSTOMERS, DELIVERIES; SERVICE - TYPE, LOCATION; FARM - ACREAGE, ANIMALS, MACHINERY, SUB-CONTRACTS.")

PRIVACY_NOTICE = (
    "PERSONAL INFORMATION ABOUT YOU, INCLUDING INFORMATION FROM A CREDIT OR OTHER INVESTIGATIVE REPORT, MAY BE COLLECTED FROM PERSONS "
    "OTHER THAN YOU IN CONNECTION WITH THIS APPLICATION FOR INSURANCE AND SUBSEQUENT AMENDMENTS AND RENEWALS. SUCH INFORMATION AS WELL AS "
    "OTHER PERSONAL AND PRIVILEGED INFORMATION COLLECTED BY US OR OUR AGENTS MAY IN CERTAIN CIRCUMSTANCES BE DISCLOSED TO THIRD PARTIES "
    "WITHOUT YOUR AUTHORIZATION. CREDIT SCORING INFORMATION MAY BE USED TO HELP DETERMINE EITHER YOUR ELIGIBILITY FOR INSURANCE OR THE "
    "PREMIUM YOU WILL BE CHARGED. WE MAY USE A THIRD PARTY IN CONNECTION WITH THE DEVELOPMENT OF YOUR SCORE. YOU MAY HAVE THE RIGHT TO "
    "REVIEW YOUR PERSONAL INFORMATION IN OUR FILES AND REQUEST CORRECTION OF ANY INACCURACIES. YOU MAY ALSO HAVE THE RIGHT TO REQUEST IN "
    "WRITING THAT WE CONSIDER EXTRAORDINARY LIFE CIRCUMSTANCES IN CONNECTION WITH THE DEVELOPMENT OF YOUR CREDIT SCORE. THESE RIGHTS MAY "
    "BE LIMITED IN SOME STATES. PLEASE CONTACT YOUR AGENT OR BROKER TO LEARN HOW THESE RIGHTS MAY APPLY IN YOUR STATE OR FOR INSTRUCTIONS ON "
    "HOW TO SUBMIT A REQUEST TO US FOR A MORE DETAILED DESCRIPTION OF YOUR RIGHTS AND OUR PRACTICES REGARDING PERSONAL INFORMATION.")

# The state list this parenthetical carries is the reason Minnesota matters
# here: MN is named, so a Minnesota applicant does not initial the notice.
PRIVACY_STATE_NOTE = ("(Not applicable in AZ, CA, DE, KS, MA, MN, ND, NY, OR, VA, or WV.  "
                      "Specific ACORD 38s are available for applicants in these states.)")

FRAUD_PARAGRAPHS = [
    ("Applicable in AL, AR, DC, LA, MD, NM, RI and WV:",
     "Any person who knowingly (or willfully)* presents a false or fraudulent claim for payment of a loss or "
     "benefit or knowingly (or willfully)* presents false information in an application for insurance is guilty of a crime and may be subject to fines and confinement in "
     "prison. *Applies in MD Only."),
    ("Applicable in CO:",
     "It is unlawful to knowingly provide false, incomplete, or misleading facts or information to an insurance company for the purpose of "
     "defrauding or attempting to defraud the company. Penalties may include imprisonment, fines, denial of insurance and civil damages. Any insurance "
     "company or agent of an insurance company who knowingly provides false, incomplete, or misleading facts or information to a policyholder or claimant for the "
     "purpose of defrauding or attempting to defraud the policyholder or claimant with regard to a settlement or award payable from insurance proceeds shall be "
     "reported to the Colorado Division of Insurance within the Department of Regulatory Agencies."),
    ("Applicable in FL and OK:",
     "Any person who knowingly and with intent to injure, defraud, or deceive any insurer files a statement of claim or an application "
     "containing any false, incomplete, or misleading information is guilty of a felony (of the third degree)*. *Applies in FL Only."),
    ("Applicable in KS:",
     "Any person who, knowingly and with intent to defraud, presents, causes to be presented or prepares with knowledge or belief that it will be "
     "presented to or by an insurer, purported insurer, broker or any agent thereof, any written, electronic, electronic impulse, facsimile, magnetic, oral, or "
     "telephonic communication or statement as part of, or in support of, an application for the issuance of, or the rating of an insurance policy for personal or "
     "commercial insurance, or a claim for payment or other benefit pursuant to an insurance policy for commercial or personal insurance which such person knows "
     "to contain materially false information concerning any fact material thereto; or conceals, for the purpose of misleading, information concerning any fact "
     "material thereto commits a fraudulent insurance act."),
    ("Applicable in KY, NY, OH and PA:",
     "Any person who knowingly and with intent to defraud any insurance company or other person files an application for "
     "insurance or statement of claim containing any materially false information or conceals for the purpose of misleading, information concerning any fact material "
     "thereto commits a fraudulent insurance act, which is a crime and subjects such person to criminal and civil penalties (not to exceed five thousand dollars and "
     "the stated value of the claim for each such violation)*. *Applies in NY Only."),
    ("Applicable in ME, TN, VA and WA:",
     "It is a crime to knowingly provide false, incomplete or misleading information to an insurance company for the purpose "
     "of defrauding the company. Penalties (may)* include imprisonment, fines and denial of insurance benefits. *Applies in ME Only."),
    ("Applicable in NJ:",
     "Any person who includes any false or misleading information on an application for an insurance policy is subject to criminal and civil "
     "penalties."),
    ("Applicable in OR:",
     "Any person who knowingly and with intent to defraud or solicit another to defraud the insurer by submitting an application containing a "
     "false statement as to any material fact may be violating state law."),
    ("Applicable in PR:",
     "Any person who knowingly and with the intention of defrauding presents false information in an insurance application, or presents, helps, "
     "or causes the presentation of a fraudulent claim for the payment of a loss or any other benefit, or presents more than one claim for the same damage or loss, "
     "shall incur a felony and, upon conviction, shall be sanctioned for each violation by a fine of not less than five thousand dollars ($5,000) and not more than ten "
     "thousand dollars ($10,000), or a fixed term of imprisonment for three (3) years, or both penalties. Should aggravating circumstances [be] present, the penalty "
     "thus established may be increased to a maximum of five (5) years, if extenuating circumstances are present, it may be reduced to a minimum of two (2) "
     "years."),
    ("Applicable in UT:",
     "Any person who knowingly presents false or fraudulent underwriting information, files or causes to be filed a false or fraudulent claim for "
     "disability compensation or medical benefits, or submits a false or fraudulent report or billing for health care fees or other professional services is guilty of a "
     "crime and may be subject to fines and confinement in state prison."),
]

REPRESENTATION = (
    "THE UNDERSIGNED IS AN AUTHORIZED REPRESENTATIVE OF THE APPLICANT AND REPRESENTS THAT REASONABLE INQUIRY HAS BEEN MADE TO OBTAIN THE "
    "ANSWERS TO QUESTIONS ON THIS APPLICATION.  HE/SHE REPRESENTS THAT THE ANSWERS ARE TRUE, CORRECT AND COMPLETE TO THE BEST OF HIS/HER "
    "KNOWLEDGE.")

# In-stream-order markers per page, for the capability test.
PAGE_MARKERS = {
    1: ["WORKERS COMPENSATION APPLICATION", "DATE (MM/DD/YYYY)",
        "AGENCY NAME AND ADDRESS", "PRODUCER NAME:", "AGENCY CUSTOMER ID:",
        "COMPANY:", "UNDERWRITER:", "APPLICANT NAME:", "YRS IN BUS:", "SIC:",
        # Stream order follows the form's two rows of entity boxes:
        # UNINCORPORATED ASSOCIATION closes the first row, SUBCHAPTER "S" CORP
        # sits in the second.
        "NAICS:", "SOLE PROPRIETOR", "UNINCORPORATED", "SUBCHAPTER",
        "FEDERAL EMPLOYER ID NUMBER", "NCCI RISK ID NUMBER",
        "OTHER RATING BUREAU ID OR STATE", "STATUS OF SUBMISSION",
        "BILLING / AUDIT INFORMATION", "ASSIGNED RISK (Attach ACORD 133)",
        "LOCATIONS", "HIGHEST", "STREET, CITY, COUNTY, STATE, ZIP CODE",
        "POLICY INFORMATION", "PROPOSED EFF DATE", "ANNIVERSARY RATING DATE",
        "PART 1 - WORKERS", "PART 2 - EMPLOYER'S LIABILITY", "EACH ACCIDENT",
        "DISEASE-POLICY LIMIT", "DISEASE-EACH EMPLOYEE", "PART 3 - OTHER",
        "DEDUCTIBLES", "OTHER COVERAGES", "U.S.L. & H.",
        "DIVIDEND PLAN/SAFETY GROUP",
        "SPECIFY ADDITIONAL COVERAGES / ENDORSEMENTS",
        "TOTAL ESTIMATED ANNUAL PREMIUM - ALL STATES",
        "TOTAL MINIMUM PREMIUM ALL STATES", "CONTACT INFORMATION",
        "ACCTNG", "INDIVIDUALS INCLUDED / EXCLUDED",
        "Exclusions in Missouri must meet the requirements of Section 287.090 RSMo.",
        "INC/EXC", "REMUNERATION/PAYROLL", FOOTER_MARK, "Page 1 of 4",
        COPYRIGHT_MARK, REGISTERED_MARK],
    2: ["STATE RATING SHEET #", "STATE RATING WORKSHEET",
        "FOR  MULTIPLE STATES, ATTACH AN ADDITIONAL PAGE 2 OF THIS FORM",
        "RATING INFORMATION - STATE:", "CLASS CODE", "DESCR",
        "CATEGORIES, DUTIES, CLASSIFICATIONS", "# EMPLOYEES",
        "ESTIMATED ANNUAL", "REMUNERATION/", "PREMIUM", "FACTORED PREMIUM",
        "INCREASED LIMITS", "SCHEDULE RATING", "DEDUCTIBLE", "CCPAP",
        "EXPERIENCE OR MERIT", "STANDARD PREMIUM", "TERRORISM",
        "PREMIUM DISCOUNT", "CATASTROPHE", "EXPENSE CONSTANT",
        "ASSIGNED RISK SURCHARGE", "TAXES / ASSESSMENTS", "ARAP",
        "N / A in Wisconsin", "TOTAL ESTIMATED ANNUAL PREMIUM",
        "MINIMUM PREMIUM", "DEPOSIT PREMIUM",
        "REMARKS (ACORD 101, Additional Remarks Schedule, may be attached if more space is required)",
        FOOTER_MARK, "Page 2 of 4"],
    3: ["PRIOR CARRIER INFORMATION / LOSS HISTORY",
        "PROVIDE INFORMATION FOR THE PAST 5 YEARS AND USE THE REMARKS SECTION FOR LOSS DETAILS",
        "LOSS RUN ATTACHED", "CARRIER & POLICY NUMBER", "ANNUAL PREMIUM",
        "# CLAIMS", "AMOUNT PAID", "RESERVE",
        "NATURE OF BUSINESS / DESCRIPTION OF OPERATIONS", "GENERAL INFORMATION",
        'EXPLAIN ALL "YES" RESPONSES', FOOTER_MARK, "Page 3 of 4"],
    4: ["GENERAL INFORMATION (continued)", "SIGNATURE",
        "Copy of the Notice of Information Practices (Privacy) has been given to the applicant.",
        "(Applicant's Initials):", "Applicable in AL, AR, DC, LA, MD, NM, RI and WV:",
        "Applicable in UT:", "APPLICANT'S SIGNATURE (Must be Officer, Owner or Partner)",
        "PRODUCER'S SIGNATURE", "NATIONAL PRODUCER NUMBER",
        FOOTER_MARK, "Page 4 of 4"],
}

# ---------------------------------------------------------------------------
# The Minnesota rating world — sourced, not authored.
#
# Everything here comes from MWCIA: the Minnesota Basic Manual (2006 Edition,
# printing effective July 15 2026), the Minnesota Classification Index
# (7/29/2026), and Circular 25-1867 (1/1/2026 Assigned Risk Rates). See
# foundry/reference/templates/acord130/provenance.json for what each source
# was read for, and contract.json for the rules in full.
#
# This is a dict keyed by state because the state is a GATE. A rating world is
# a jurisdiction's own arithmetic — its available pricing programs, its
# assessments, its eligibility thresholds — and none of it transfers. Adding a
# state means sourcing that state, not copying this one.
# ---------------------------------------------------------------------------

MN_RATING = {
    "state": "MN",
    "state_name": "MINNESOTA",
    "bureau": "MWCIA",
    "bureau_name": "Minnesota Workers' Compensation Insurers Association",
    # Minnesota is one of ten independent data service organisations; NCCI
    # serves most other states. So the NCCI RISK ID box stays empty and the
    # bureau file number goes in OTHER RATING BUREAU ID.
    "is_ncci_state": False,
    "rates": {            # (assigned-risk rate per $100, class minimum premium)
        "8006": (2.404, 250),
        "8380": (3.064, 267),
        "8381": (1.924, 238),
        "8810": (0.135, 193),
        "8742": (0.299, 197),
    },
    "expense_constant_assigned_risk": 190,
    "terrorism_per_100_payroll": 0.010,
    "scf_assessment_pct": 1.9,      # Special Compensation Fund surcharge
    "el_standard_limits": (100_000, 500_000, 100_000),
    # Rule 3-A-14 Table 1 — voluntary market, percentage of manual premium
    "el_increased_limits_pct": {(500_000, 500_000, 500_000): 0.8,
                                (1_000_000, 1_000_000, 1_000_000): 1.1},
    # Circular 25-1867 — assigned risk plan, whichever is greater
    "el_increased_limits_assigned_risk": {(500_000, 500_000, 500_000): (1.0, 50),
                                          (1_000_000, 1_000_000, 1_000_000): (5.0, 150)},
    "experience_rating_eligibility_premium": 15_000,
    "officer_weekly_max": 5_692,
    "officer_weekly_min": 1_423,
    # Programs the User's Guide publishes as unavailable in Minnesota. Each
    # names a row the form prints, and each must stay empty.
    "unavailable_programs": {
        "ARAP": "Assigned Risk Adjustment Program — NO in Minnesota",
        "ASSIGNED RISK SURCHARGE": "Assigned Risk Surcharge Program — NO in Minnesota",
        "CATASTROPHE": "non-ratable element; non-ratable elements do not apply in Minnesota",
        "CCPAP": "Minnesota's counterpart is MCPAP, a contractor program; a mercantile "
                 "risk is not eligible under either name",
    },
}

# Appendix A, Table 1 — Type A carriers advisory premium discount. The
# brackets are contiguous and the discount is 0.1% x bracket index, so only
# the upper bounds need transcribing. Transcribed through $30,645 (7.9%),
# which covers any risk this class emits; beyond it the emitter raises rather
# than guessing at a table it did not read.
PREMIUM_DISCOUNT_BRACKETS = [
    5026, 5080, 5135, 5191, 5248, 5307, 5367, 5428, 5491, 5555,
    5621, 5688, 5757, 5828, 5900, 5974, 6050, 6129, 6209, 6291,
    6375, 6462, 6551, 6643, 6737, 6834, 6934, 7037, 7142, 7251,
    7364, 7480, 7599, 7723, 7851, 7983, 8119, 8260, 8407, 8558,
    8715, 8878, 9047, 9223, 9405, 9595, 9793, 9999, 10215, 10439,
    10674, 10919, 11176, 11445, 11728, 12025, 12337, 12666, 13013, 13380,
    13768, 14179, 14615, 15079, 15573, 16101, 16666, 17272, 17924, 18627,
    19387, 20212, 21111, 22093, 23170, 24358, 25675, 27142, 28787, 30645,
]

# Minnesota Basic Manual, CLASSIFICATIONS, heading GASOLINE STATION. The
# diamond in the manual marks these MERCANTILE.
GASOLINE_STATION_CLASSES = {
    "8380": "Gasoline Station: NOC — Retail & Drivers",
    "8006": "Gasoline Station: Self-Service and Convenience/Grocery — Retail",
    "8381": "Gasoline Station: Self-Service Only — Retail",
}

SIC_GASOLINE_SERVICE_STATIONS = "5541"      # OSHA SIC Manual, Major Group 55
NAICS_WITH_CONVENIENCE_STORE = "457110"     # 2022 NAICS (was 447110)
NAICS_OTHER_GASOLINE_STATIONS = "457120"

DEFAULT_CANON = {
    "agency", "agency_addr", "producer", "cs_representative",
    "carrier", "underwriter", "insured", "insured_addr",
    "city", "county", "zip", "owner", "owner_title", "brand",
}

CANON = {
    "agency": "Northline Risk Advisors, Inc.",
    "agency_addr": ["1220 Wayzata Boulevard East, Suite 340", "Wayzata, MN 55391"],
    "producer": "K. R. LINDGREN",
    "cs_representative": "M. T. OSWALD",
    "carrier": "Great Northern Casualty Insurance Company",
    "underwriter": "D. HALVORSEN",
    "insured": "Birchwood Fuel & Market, Inc.",
    "insured_addr": ["4180 Kandi Trail North"],
    "city": "Willmar",
    "county": "Kandiyohi",
    "zip": "56201-4180",
    "owner": "Arne P. Holmquist",
    "owner_title": "President",
    "brand": "Birchwood Corner Market",
}


def _check_canon(canon: dict) -> dict:
    missing = DEFAULT_CANON - set(canon)
    if missing:
        raise ValueError(f"canon missing required keys: {sorted(missing)}")
    return canon


# ---------------------------------------------------------------------------
# Classification and premium — both derived
# ---------------------------------------------------------------------------

def classify_station(*, full_service: bool, gasoline_share: float,
                     food_service_share: float) -> str:
    """Minnesota's gasoline-station classification, as the Basic Manual states
    it. The code follows from what the station does; it is never a free choice.

    Full service — pumping gas, checking fluids, attended car wash, or any
    automobile maintenance or repair — is 8380, and so is a station doing both
    full and self service. A self-service station whose gasoline receipts reach
    90% of the total is 8381. Below that, with a store, it is 8006.
    """
    if full_service:
        return "8380"
    if gasoline_share >= 0.90:
        return "8381"
    if food_service_share >= 0.50:
        raise ValueError(
            "receipts from the service of food or beverages reach 50% of total "
            "receipts, so Code 8006 does not apply and a restaurant "
            "classification is in play. That split has not been sourced here.")
    return "8006"


def premium_discount_pct(standard_premium: float) -> float:
    """Appendix A Table 1 (Type A carriers): bracket index x 0.1%."""
    for i, upper in enumerate(PREMIUM_DISCOUNT_BRACKETS):
        if standard_premium <= upper:
            return round(i * 0.1, 1)
    raise ValueError(
        f"standard premium ${standard_premium:,.0f} is above the transcribed "
        f"range of Minnesota premium discount Table 1 "
        f"(${PREMIUM_DISCOUNT_BRACKETS[-1]:,}). The rest of the table was not "
        f"read, and guessing at it would be an unsourced premium.")


def compute_premium(model: dict) -> dict:
    """The Minnesota build-up, in the manual's order.

    Standard premium excludes the expense constant, the SCF surcharge and
    Terrorism by rule, so those three are added after the discount is taken.
    Terrorism is calculated on total payroll and is subject to no other
    modification at all — not the mod, not schedule rating, not the discount.
    """
    r = MN_RATING
    rows = model["worksheet"]
    manual = sum(row["premium"] for row in rows)
    total_payroll = sum(row["payroll"] for row in rows)

    mod = model["experience_mod"]                       # None when ineligible
    modified = round(manual * mod) if mod else manual
    mod_delta = modified - manual

    sched = model["schedule_rating"]                    # None when not filed
    scheduled = round(modified * sched) if sched else modified
    sched_delta = scheduled - modified

    il = model["el_increased_limits_charge"]
    standard = scheduled + il

    disc_pct = premium_discount_pct(standard)
    discount = round(standard * disc_pct / 100)

    expense_constant = model["expense_constant"]
    terrorism = round(total_payroll / 100 * r["terrorism_per_100_payroll"])
    scf = round(standard * r["scf_assessment_pct"] / 100)

    total = standard - discount + expense_constant + terrorism + scf
    minimum = max(r["rates"][row["class_code"]][1] for row in rows)
    return {
        "manual_premium": manual,
        "total_payroll": total_payroll,
        "experience_mod_charge": mod_delta,
        "schedule_rating_charge": sched_delta,
        "increased_limits": il,
        "standard_premium": standard,
        "premium_discount_pct": disc_pct,
        "premium_discount": discount,
        "expense_constant": expense_constant,
        "terrorism": terrorism,
        "scf_surcharge": scf,
        "total_estimated_annual": max(total, minimum),
        "minimum_premium": minimum,
        "deposit_premium": round(max(total, minimum) / 4),
    }


# ---------------------------------------------------------------------------
# Sampled model — coherent by construction
# ---------------------------------------------------------------------------

_PIN_KEYS = {"state", "market", "full_service", "gasoline_share",
             "food_service_share", "el_limits", "year", "car_wash",
             "annual_payroll", "seed_year"}


def sample_130(rng: random.Random, *, pins: dict | None = None,
               canon: dict | None = None) -> dict:
    """Sample a coherent Minnesota workers compensation application for a
    gasoline station. Two facts — whether the station pumps gas and what share
    of receipts gasoline is — decide the class code, the rate, the narrative
    and half the question answers."""
    pins = dict(pins or {})
    bad = set(pins) - _PIN_KEYS
    if bad:
        raise ValueError(f"unknown pins: {sorted(bad)}")
    cn = _check_canon(dict(canon or CANON))

    state = pins.get("state", "MN")
    if state != MN_RATING["state"]:
        raise ValueError(
            f"no rating world sourced for {state!r}. This emitter has "
            f"{MN_RATING['state']!r} only, sourced from "
            f"{MN_RATING['bureau']}. A state's rating world is its own "
            f"arithmetic — available pricing programs, assessments, "
            f"eligibility thresholds — and none of it transfers. Rendering a "
            f"{state} worksheet on Minnesota's algebra would produce a "
            f"premium box no bureau ever printed.")
    r = MN_RATING

    market = pins.get("market", "voluntary")
    if market not in ("voluntary", "assigned_risk"):
        raise ValueError("market must be 'voluntary' or 'assigned_risk'")

    # -- what the station actually is ---------------------------------------
    full_service = pins.get("full_service", rng.random() < 0.35)
    gasoline_share = pins.get(
        "gasoline_share",
        round(rng.uniform(0.90, 0.96), 2) if rng.random() < 0.25
        else round(rng.uniform(0.62, 0.86), 2))
    food_service_share = pins.get("food_service_share",
                                  round(rng.uniform(0.04, 0.18), 2))
    car_wash = pins.get("car_wash", full_service and rng.random() < 0.5)
    class_code = classify_station(full_service=full_service,
                                  gasoline_share=gasoline_share,
                                  food_service_share=food_service_share)
    has_store = class_code in ("8006", "8380")
    naics = (NAICS_WITH_CONVENIENCE_STORE if class_code == "8006"
             else NAICS_OTHER_GASOLINE_STATIONS)

    # -- staffing and payroll ----------------------------------------------
    # The counts on the worksheet are the same people the general-information
    # answers describe; nothing about the staff is drawn twice.
    ft = rng.randint(3, 7)
    pt = rng.randint(4, 11)
    year = pins.get("year", 2026)

    # The owner is an included officer, so Minnesota's weekly remuneration
    # limits bound the payroll reported for them — and that payroll is PART OF
    # the station's rating payroll, which is what the form's own instruction
    # requires ("Remuneration/Payroll to be included must be part of rating
    # information section"). Sampling the two independently is how the station
    # row stops containing the officer it is supposed to contain.
    owner_weekly = rng.randint(r["officer_weekly_min"] // 10,
                               r["officer_weekly_max"] // 10) * 10
    owner_annual = owner_weekly * 52
    owner_age = rng.randint(41, 66)
    staff_payroll = pins.get("annual_payroll", rng.randint(2_600, 4_900) * 100)
    annual_payroll = staff_payroll + owner_annual
    clerical_payroll = rng.randint(280, 480) * 100          # one bookkeeper

    # Rate: MWCIA files pure premium base rates and each carrier files its own
    # multiplier, so a voluntary rate sits below the assigned-risk schedule.
    # We derive from the schedule and record the derivation rather than
    # presenting an invented rate as filed.
    def _rate(code: str) -> float:
        base = r["rates"][code][0]
        if market == "assigned_risk":
            return base
        return round(base * rng.uniform(0.72, 0.92), 3)

    station_rate = _rate(class_code)
    clerical_rate = _rate("8810")
    worksheet = [
        {"loc": 1, "class_code": class_code,
         "description": GASOLINE_STATION_CLASSES[class_code],
         "ft": ft, "pt": pt, "sic": SIC_GASOLINE_SERVICE_STATIONS,
         "naics": naics, "payroll": annual_payroll, "rate": station_rate,
         "premium": round(annual_payroll / 100 * station_rate)},
        {"loc": 1, "class_code": "8810",
         "description": "Clerical Office Employees NOC",
         "ft": 1, "pt": 0, "sic": "", "naics": "",
         "payroll": clerical_payroll, "rate": clerical_rate,
         "premium": round(clerical_payroll / 100 * clerical_rate)},
    ]

    # -- eligibility decides the mod, rather than the mod being sampled -----
    manual = sum(row["premium"] for row in worksheet)
    eligible = manual >= r["experience_rating_eligibility_premium"]
    experience_mod = round(rng.uniform(0.84, 1.18), 2) if eligible else None

    el_limits = tuple(pins.get("el_limits", r["el_standard_limits"]))
    if el_limits == tuple(r["el_standard_limits"]):
        il_charge = 0
    elif market == "assigned_risk":
        pct, floor = r["el_increased_limits_assigned_risk"][el_limits]
        il_charge = max(round(manual * pct / 100), floor)
    else:
        il_charge = round(manual * r["el_increased_limits_pct"][el_limits] / 100)

    eff_month = rng.randint(1, 12)
    eff = _dt.date(year, eff_month, 1)
    exp = _dt.date(year + 1, eff_month, 1)
    app_date = eff - _dt.timedelta(days=rng.randint(18, 45))

    # -- the 24 questions, answered from the facts already sampled ----------
    ans = {i: "N" for i in range(1, 25)}
    exp_txt: dict[int, str] = {}

    # Q2 names fuel tanks in its own text. A gasoline station stores motor
    # fuel; there is no honest "N" here.
    tanks = rng.choice([2, 3])
    gal = rng.choice([10_000, 12_000, 15_000])
    ans[2] = "Y"
    exp_txt[2] = (f"{tanks} underground motor fuel storage tanks "
                  f"({gal:,} gal each) at Loc 1, registered with the Minnesota "
                  f"Pollution Control Agency; annual tank and line testing by "
                  f"licensed contractor; no employee entry into tank areas.")
    if car_wash:
        ans[5] = "Y"
        exp_txt[5] = ("Attended car wash operated at the same location — see "
                      "Nature of Business.")
    pct_sub = rng.randint(3, 9)
    ans[6] = "Y"
    exp_txt[6] = (f"Approximately {pct_sub}% — tank testing and cathodic "
                  f"protection, fuel dispenser service, refrigeration service "
                  f"and snow removal. Certificates of insurance required and "
                  f"on file for all.")
    ans[8] = "Y"
    exp_txt[8] = ("Written safety program covering fuel handling and spill "
                  "response, robbery procedure, slip/fall and wet floor "
                  "control; documented monthly review with all staff.")
    ans[10] = "Y"
    under16, over60 = rng.randint(1, 3), rng.randint(1, 2)
    exp_txt[10] = (f"{under16} part-time cashier{'s' if under16 > 1 else ''} "
                   f"under 16, permitted hours only; {over60} "
                   f"employee{'s' if over60 > 1 else ''} over 60.")
    if rng.random() < 0.7:
        ans[11] = "Y"
        exp_txt[11] = ("Additional part-time cashiers June through August; "
                       "same duties and classification as regular staff.")
    ans[17] = "Y"
    exp_txt[17] = ("Commercial package policy written by the same insurer "
                   "covering the premises, the canopy and dispensers, and "
                   "storage tank pollution liability.")
    if ft >= 5 and rng.random() < 0.5:
        ans[19] = "Y"
        exp_txt[19] = "Group health offered to full-time employees after 90 days."

    service_txt = ("full service — attendants pump fuel and check fluid levels"
                   if full_service else "self-service only; no attendant pumping")
    repair_txt = (" Minor automobile maintenance and repair performed in one "
                  "service bay." if full_service else
                  " No automobile maintenance, repair or towing performed.")
    store_txt = (f" Convenience store selling packaged foods, beverages, "
                 f"tobacco, sundries and automobile accessories; no fresh meat "
                 f"handling. Gasoline sales are approximately "
                 f"{gasoline_share * 100:.0f}% of total receipts and prepared "
                 f"food and beverage service approximately "
                 f"{food_service_share * 100:.0f}%, both excluding lottery."
                 if has_store else
                 f" Gasoline sales are approximately "
                 f"{gasoline_share * 100:.0f}% of total receipts, excluding "
                 f"lottery.")
    nature = (
        f"Retail gasoline station, {service_txt}, operating as "
        f"{cn['brand']} at one location in {cn['city']}, "
        f"{cn['county']} County, Minnesota."
        f"{store_txt}{repair_txt}"
        f"{' Attended car wash on premises.' if car_wash else ''} "
        f"Open {rng.choice(['5:30 a.m. to 11:00 p.m. daily', '24 hours'])}; "
        f"no deliveries made by the applicant. Classified Code {class_code} — "
        f"{GASOLINE_STATION_CLASSES[class_code]}.")

    loss_years = []
    for back in range(1, 6):
        y = year - back
        claims = rng.choice([0, 0, 0, 1, 1, 2])
        paid = sum(rng.randint(4, 90) * 100 for _ in range(claims))
        loss_years.append({
            "year": y,
            "carrier": (cn["carrier"] if back <= 2 else
                        "Lakes Regional Mutual Insurance Company"),
            "policy": f"WC {rng.randint(100, 999)}-{rng.randint(10000, 99999)}",
            "premium": round(manual * rng.uniform(0.86, 1.09)),
            # No mod is promulgated for a risk below the eligibility
            # threshold, so the column stays empty rather than carrying 1.00.
            "mod": f"{experience_mod:.2f}" if experience_mod else "",
            "claims": claims,
            "paid": paid,
            "reserve": rng.randint(0, 12) * 100 if claims else 0,
        })

    return {
        "state": state,
        "market": market,
        "date": app_date,
        "agency": cn["agency"],
        "agency_addr": cn["agency_addr"],
        "producer": cn["producer"],
        "cs_representative": cn["cs_representative"],
        "agency_customer_id": f"{cn['insured'].split()[0].upper()[:5]}-"
                              f"{rng.randint(10000, 99999)}",
        "carrier": cn["carrier"],
        "underwriter": cn["underwriter"],
        # Not sourced, so not filled. See provenance.json.
        "naic_code": "",
        "national_producer_number": "",
        "insured": cn["insured"],
        "insured_addr": cn["insured_addr"],
        "city": cn["city"],
        "county": cn["county"],
        "zip": cn["zip"],
        "legal_entity": "CORPORATION",
        # A business cannot predate its owner's working life. Years in business
        # is drawn against the owner's age rather than beside it.
        "yrs_in_bus": rng.randint(6, max(7, min(34, owner_age - 24))),
        "sic": SIC_GASOLINE_SERVICE_STATIONS,
        "naics": naics,
        "fein": f"41-{rng.randint(1000000, 9999999)}",
        # Minnesota is not an NCCI state: the file number is MWCIA's and goes
        # in the OTHER RATING BUREAU box.
        "ncci_risk_id": "",
        "other_bureau_id": f"MN {rng.randint(100000, 999999)}",
        "submission": "QUOTE" if market == "voluntary" else "ASSIGNED RISK",
        "billing_plan": rng.choice(["AGENCY BILL", "DIRECT BILL"]),
        "payment_plan": rng.choice(["ANNUAL", "QUARTERLY"]),
        "audit": "AT EXPIRATION",
        "highest_floor": 1,
        "effective_date": eff,
        "expiration_date": exp,
        "el_limits": el_limits,
        "el_increased_limits_charge": il_charge,
        "other_states": "ALL STATES EXCEPT MN, ND, OH, WA, WY AND STATES "
                        "LISTED IN ITEM 3.A.",
        "full_service": full_service,
        "car_wash": car_wash,
        "gasoline_share": gasoline_share,
        "food_service_share": food_service_share,
        "class_code": class_code,
        "worksheet": worksheet,
        "experience_rating_eligible": eligible,
        "experience_mod": experience_mod,
        "schedule_rating": None,
        "expense_constant": (r["expense_constant_assigned_risk"]
                             if market == "assigned_risk"
                             else rng.choice([150, 175, 190, 200, 225])),
        "employees": {"ft": ft, "pt": pt},
        "owner": cn["owner"],
        "owner_title": cn["owner_title"],
        "owner_weekly": owner_weekly,
        "owner_annual": owner_annual,
        "owner_class_code": class_code,
        "owner_dob": _dt.date(year - owner_age, rng.randint(1, 12),
                              rng.randint(1, 28)),
        "nature_of_business": nature,
        "loss_history": loss_years,
        "answers": ans,
        "explanations": exp_txt,
    }


def premium_rows(model: dict, prem: dict, defect: dict | None = None):
    """The two columns of the page-2 PREMIUM box, as (label, factor, amount).

    This is where the Minnesota guard list is enforced, and it is a function
    rather than inline drawing so the guard can be asserted directly instead of
    inferred from extracted text. An amount of `None` prints an empty cell; it
    is not a zero, and the difference matters — a zero is a computed charge and
    an empty cell is a program that does not exist in this state.
    """
    defect = defect or {}
    left = [
        ("TOTAL", "N / A", prem["manual_premium"]),
        ("INCREASED LIMITS", "", prem["increased_limits"] or None),
        ("DEDUCTIBLE *", "", None),
        ("EXPERIENCE OR MERIT\nMODIFICATION",
         f"{model['experience_mod']:.2f}" if model["experience_mod"] else "",
         prem["experience_mod_charge"] or None),
        ("TERRORISM", "N / A", prem["terrorism"]),
        # Non-ratable element; non-ratable elements do not apply in Minnesota.
        ("CATASTROPHE", "N / A", None),
        # Assigned Risk Surcharge Program — NO in Minnesota.
        ("ASSIGNED RISK SURCHARGE *", "", None),
        # ARAP — NO in Minnesota. The hook fills it anyway, which is the whole
        # point: a charge under a program the state does not have.
        ("ARAP *", "", defect.get("arap")),
    ]
    right = [
        ("SCHEDULE RATING *", "", prem["schedule_rating_charge"] or None),
        # CCPAP is NCCI's name; Minnesota's is MCPAP, and MCPAP is a
        # contracting program. A mercantile risk earns nothing under either.
        ("CCPAP", "", None),
        ("STANDARD PREMIUM", "", prem["standard_premium"]),
        ("PREMIUM DISCOUNT",
         f"{prem['premium_discount_pct']:.1f}%" if prem["premium_discount"] else "",
         -prem["premium_discount"] if prem["premium_discount"] else None),
        ("EXPENSE CONSTANT", "N / A", prem["expense_constant"]),
        ("TAXES / ASSESSMENTS *", "N / A", prem["scf_surcharge"]),
    ]
    return left, right


#: Rows the sources proved unavailable in Minnesota. Keyed by the label the
#: form prints, so a test can look them up without restating the labels.
UNAVAILABLE_ROWS = ("CATASTROPHE", "ASSIGNED RISK SURCHARGE *", "ARAP *",
                    "CCPAP")


def remarks_lines(model: dict) -> list[str]:
    """Everything the page-2 REMARKS box carries. The eligibility note is the
    one an underwriter looks for: a Minnesota risk under the threshold has no
    modification, and saying so is the difference between a blank field and an
    unexplained blank field."""
    r = MN_RATING
    out = []
    if not model["experience_rating_eligible"]:
        out.append(
            f"Risk develops estimated annual manual premium below the "
            f"${r['experience_rating_eligibility_premium']:,} Minnesota "
            f"intrastate experience rating eligibility amount; no experience "
            f"modification promulgated by {r['bureau']}.")
    else:
        out.append(f"Experience modification {model['experience_mod']:.2f} "
                   f"promulgated by {r['bureau']}.")
    out.append(
        f"ARAP and the Assigned Risk Surcharge Program are not available in "
        f"Minnesota. Catastrophe is a non-ratable element and does not apply "
        f"in Minnesota. CCPAP shown on this form is administered in Minnesota "
        f"as MCPAP and applies to contracting classifications only.")
    out.append(
        f"Taxes / assessments line is the Minnesota Special Compensation Fund "
        f"surcharge at {r['scf_assessment_pct']}% of premium.")
    out.append(
        f"{model['owner_title']} {model['owner']} included; remuneration "
        f"reported at the Minnesota weekly maximum basis "
        f"(${model['owner_weekly']:,}/wk).")
    for i in sorted(model["explanations"]):
        if model["answers"].get(i) == "Y":
            out.append(f"GENERAL INFORMATION ITEM {i}: {model['explanations'][i]}")
    return out


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def _wordmark(c, x, y_top):
    c.setFillGray(0.12)
    c.setFont("Helvetica-Bold", 21)
    c.drawString(x + 2, y_top - 21, "ACORD")
    c.setFont("Helvetica", 6)
    c.drawString(x + 58, y_top - 14, "®")
    c.setFillGray(0)


def _footer(c, page_num):
    _text(c, ML, 762, FOOTER_MARK, font=("Helvetica-Bold", 8.5))
    _text(c, 306, 762, f"Page {page_num} of 4",
          font=("Helvetica-Bold", 8.5), center_w=0)
    if page_num == 1:
        _text(c, MR, 762, COPYRIGHT_MARK, font=("Helvetica-Bold", 8.5), right=True)
        _text(c, 306, 774, REGISTERED_MARK,
              font=("Helvetica-Bold", 8.5), center_w=0)


def _customer_id(c, value):
    _text(c, 306, 40, "AGENCY CUSTOMER ID:", font=("Helvetica-Bold", 7))
    c.setLineWidth(0.7)
    c.line(400, _y(41.5), MR, _y(41.5))
    _text(c, 406, 40, value, font=_FILL)


def _money(v) -> str:
    return f"{v:,.0f}" if v or v == 0 else ""


def _d(date) -> str:
    return date.strftime("%m/%d/%Y")


def _page1(c, m, prem, defect):
    """Page 1. The vertical budget follows the reference form's own section
    tops, measured off the rasterised blank rather than guessed: the identity
    block has to end before STATUS OF SUBMISSION begins, and the individuals
    grid has to fit between the margins."""
    _wordmark(c, ML, _y(38) + 30)
    _text(c, 306, 46, "WORKERS COMPENSATION APPLICATION",
          font=("Helvetica-Bold", 15), center_w=0)
    c.setLineWidth(0.9)
    _box(c, 494, 28, MR - 494, 26)
    _label(c, 494, 28, "DATE (MM/DD/YYYY)")
    _fill(c, 500, 48, _d(m["date"]))

    # -- agency block (left) / company block (right): 56 .. 216 -------------
    top = 56
    _box(c, ML, top, 282, 160)
    _label(c, ML, top, "AGENCY NAME AND ADDRESS")
    _fill(c, ML + 4, top + 22, m["agency"])
    for i, line in enumerate(m["agency_addr"]):
        _fill(c, ML + 4, top + 33 + i * 10, line)
    for i, (lab, val) in enumerate((("PRODUCER NAME:", m["producer"]),
                                    ("CS REPRESENTATIVE NAME:", m["cs_representative"]),
                                    ("OFFICE PHONE (A/C, No, Ext):", ""),
                                    ("MOBILE PHONE:", ""),
                                    ("FAX (A/C, No):", ""),
                                    ("E-MAIL ADDRESS:", ""))):
        _text(c, ML + 2, top + 76 + i * 12, lab, font=_LABEL)
        _fill(c, ML + 104, top + 76 + i * 12, val)
    _text(c, ML + 2, top + 148, "CODE:", font=_LABEL)
    _fill(c, ML + 28, top + 148, m["agency_customer_id"].split("-")[0])
    _text(c, ML + 130, top + 148, "SUB CODE:", font=_LABEL)
    _text(c, ML + 2, top + 158, "AGENCY CUSTOMER ID:", font=_LABEL)
    _fill(c, ML + 92, top + 158, m["agency_customer_id"])

    # The right column has to land exactly on 216 so the FEIN row clears the
    # STATUS OF SUBMISSION header below it. Row heights are budgeted, not
    # accumulated: 39 + 13 + 38 + 12 + 24 + 12 + 22 = 160.
    rx = 306
    for i, (lab, val) in enumerate((("COMPANY:", m["carrier"]),
                                    ("UNDERWRITER:", m["underwriter"]),
                                    ("APPLICANT NAME:", m["insured"]))):
        _box(c, rx, top + i * 13, MR - rx, 13)
        _text(c, rx + 3, top + i * 13 + 9, lab, font=("Helvetica-Bold", 6))
        _fill(c, rx + 92, top + i * 13 + 9, val)
    ph = top + 39
    _box(c, rx, ph, 152, 13)
    _text(c, rx + 3, ph + 9, "OFFICE PHONE:", font=("Helvetica-Bold", 6))
    _box(c, rx + 152, ph, MR - rx - 152, 13)
    _text(c, rx + 155, ph + 9, "MOBILE PHONE:", font=("Helvetica-Bold", 6))

    ad_top = ph + 13
    _box(c, rx, ad_top, 174, 38)
    _label(c, rx, ad_top, "MAILING ADDRESS (including ZIP  + 4 or Canadian Postal Code)")
    for i, line in enumerate(m["insured_addr"] + [f"{m['city']}, MN {m['zip']}"]):
        _fill(c, rx + 4, ad_top + 21 + i * 9, line)
    for i, (lab, val) in enumerate((("YRS IN BUS:", str(m["yrs_in_bus"])),
                                    ("SIC:", m["sic"]),
                                    ("NAICS:", m["naics"]))):
        _box(c, rx + 174, ad_top + i * 12.667, MR - rx - 174, 12.667)
        _text(c, rx + 177, ad_top + i * 12.667 + 9, lab, font=("Helvetica-Bold", 6))
        _fill(c, rx + 224, ad_top + i * 12.667 + 9, val)

    eml = ad_top + 38
    _box(c, rx, eml, 174, 12)
    _text(c, rx + 3, eml + 8.5, "E-MAIL ADDRESS:", font=("Helvetica-Bold", 6))
    _box(c, rx + 174, eml, MR - rx - 174, 12)
    _text(c, rx + 177, eml + 5, "WEBSITE", font=("Helvetica-Bold", 5.2))
    _text(c, rx + 177, eml + 10.5, "ADDRESS:", font=("Helvetica-Bold", 5.2))

    ent_top = eml + 12
    _box(c, rx, ent_top, MR - rx, 24)
    entities = [("SOLE PROPRIETOR", 0, 0), ("CORPORATION", 1, 0), ("LLC", 2, 0),
                ("TRUST", 3, 0), ("UNINCORPORATED\nASSOCIATION", 4, 0),
                ("PARTNERSHIP", 0, 1), ('SUBCHAPTER\n"S" CORP', 1, 1),
                ("JOINT VENTURE", 2, 1), ("OTHER:", 3, 1)]
    for label, col, row in entities:
        x = rx + 5 + col * 56
        y = ent_top + 8 + row * 10.5
        _check(c, x, y, checked=(label == m["legal_entity"]), size=6)
        for j, ln in enumerate(label.split("\n")):
            _text(c, x + 8, y + j * 4.6, ln, font=("Helvetica", 4.5))

    cb = ent_top + 24
    _box(c, rx, cb, 190, 12)
    _text(c, rx + 3, cb + 5, "CREDIT", font=("Helvetica-Bold", 5))
    _text(c, rx + 3, cb + 10.5, "BUREAU NAME:", font=("Helvetica-Bold", 5))
    _box(c, rx + 190, cb, MR - rx - 190, 12)
    _text(c, rx + 193, cb + 8, "ID NUMBER:", font=("Helvetica-Bold", 5))
    idt = cb + 12
    # The OTHER RATING BUREAU column is the widest of the three on the
    # reference blank — it has to hold a two-line label that does not fit in a
    # third of the width, and on a Minnesota risk it is the box that gets used.
    for x, w, lab, val in ((rx, 104, "FEDERAL EMPLOYER ID NUMBER", m["fein"]),
                           (rx + 104, 68, "NCCI RISK ID NUMBER", m["ncci_risk_id"]),
                           (rx + 172, MR - rx - 172,
                            "OTHER RATING BUREAU ID OR STATE\nEMPLOYER REGISTRATION NUMBER",
                            m["other_bureau_id"])):
        _box(c, x, idt, w, 22)
        for j, ln in enumerate(lab.split("\n")):
            _text(c, x + 3, idt + 6 + j * 5.6, ln, font=("Helvetica-Bold", 5))
        _fill(c, x + 4, idt + 20, val)

    # -- status of submission / billing: 223 .. 278 ------------------------
    st = 223
    _section_hdr(c, ML, st, "STATUS OF SUBMISSION")
    _section_hdr(c, 232, st, "BILLING / AUDIT INFORMATION")
    _box(c, ML, st + 5, 208, 50)
    _box(c, 232, st + 5, MR - 232, 50)
    for i, lab in enumerate(("QUOTE", "ISSUE POLICY")):
        _check(c, ML + 6 + i * 92, st + 17, checked=(m["submission"] == lab), size=7)
        _text(c, ML + 18 + i * 92, st + 17, lab, font=("Helvetica", 6.4))
    for i, lab in enumerate(("BOUND (Give date and/or attach copy)",
                             "ASSIGNED RISK (Attach ACORD 133)")):
        _check(c, ML + 6, st + 31 + i * 14,
               checked=(m["submission"] == lab.split(" (")[0]), size=7)
        _text(c, ML + 18, st + 31 + i * 14, lab, font=("Helvetica", 6.4))
    _text(c, 238, st + 15, "BILLING PLAN", font=("Helvetica-Bold", 6))
    _text(c, 328, st + 15, "PAYMENT PLAN", font=("Helvetica-Bold", 6))
    _text(c, 480, st + 15, "AUDIT", font=("Helvetica-Bold", 6))
    c.line(322, _y(st + 5), 322, _y(st + 55))
    c.line(474, _y(st + 5), 474, _y(st + 55))
    for i, lab in enumerate(("AGENCY BILL", "DIRECT BILL")):
        _check(c, 238, st + 28 + i * 13, checked=(m["billing_plan"] == lab), size=7)
        _text(c, 250, st + 28 + i * 13, lab, font=("Helvetica", 6.4))
    for i, lab in enumerate(("ANNUAL", "SEMI-ANNUAL", "QUARTERLY")):
        _check(c, 328, st + 28 + i * 13, checked=(m["payment_plan"] == lab), size=7)
        _text(c, 340, st + 28 + i * 13, lab, font=("Helvetica", 6.4))
    _text(c, 396, st + 54, "% DOWN:", font=("Helvetica", 6.2))
    for i, lab in enumerate(("AT EXPIRATION", "SEMI-ANNUAL", "QUARTERLY")):
        _check(c, 480, st + 28 + i * 13, checked=(m["audit"] == lab), size=7)
        _text(c, 492, st + 28 + i * 13, lab, font=("Helvetica", 6.4))
    _check(c, 544, st + 28, checked=False, size=7)
    _text(c, 556, st + 28, "MONTHLY", font=("Helvetica", 6.4))

    # -- locations: 285 .. 364 ---------------------------------------------
    lt = 285
    _section_hdr(c, ML, lt, "LOCATIONS")
    _box(c, ML, lt + 5, MR - ML, 74)
    _text(c, ML + 4, lt + 16, "LOC #", font=("Helvetica-Bold", 5.5))
    _text(c, ML + 40, lt + 13, "HIGHEST", font=("Helvetica-Bold", 5.5))
    _text(c, ML + 40, lt + 18, "FLOOR", font=("Helvetica-Bold", 5.5))
    _text(c, ML + 92, lt + 16, "STREET, CITY, COUNTY, STATE, ZIP CODE",
          font=("Helvetica-Bold", 5.5))
    c.line(ML, _y(lt + 20), MR, _y(lt + 20))
    c.line(ML + 36, _y(lt + 5), ML + 36, _y(lt + 79))
    c.line(ML + 88, _y(lt + 5), ML + 88, _y(lt + 79))
    for i in range(1, 3):
        c.line(ML, _y(lt + 20 + i * 20), MR, _y(lt + 20 + i * 20))
    _fill(c, ML + 10, lt + 33, "1")
    _fill(c, ML + 48, lt + 33, str(m["highest_floor"]))
    _fill(c, ML + 92, lt + 33,
          f"{m['insured_addr'][0]}, {m['city']}, {m['county']} County, MN {m['zip']}")

    # -- policy information: 378 .. 502 ------------------------------------
    pt = 378
    _section_hdr(c, ML, pt, "POLICY INFORMATION")
    _box(c, ML, pt + 5, MR - ML, 124)
    # Column edges measured off the reference blank. The last column has to
    # END at MR; deriving them from a fixed width instead is what pushed
    # RETRO PLAN and OTHER COVERAGES off the page.
    for x, lab, val in ((ML, "PROPOSED EFF DATE", _d(m["effective_date"])),
                        (ML + 90, "PROPOSED EXP DATE", _d(m["expiration_date"])),
                        (ML + 180, "RATING EFFECTIVE DATE\n(if applicable)", ""),
                        (ML + 270, "ANNIVERSARY RATING DATE\n(if applicable)", "")):
        for j, ln in enumerate(lab.split("\n")):
            _text(c, x, pt + 14 + j * 6, ln, font=("Helvetica-Bold", 5.5),
                  center_w=90)
        _fill(c, x + 16, pt + 32, val)
        if x > ML:
            c.line(x, _y(pt + 5), x, _y(pt + 38))
    for x in (ML + 360, ML + 376, ML + 442):
        c.line(x, _y(pt + 5), x, _y(pt + 38))
    _check(c, ML + 364, pt + 16, checked=False, size=6)
    _text(c, ML + 380, pt + 16, "PARTICIPATING", font=("Helvetica", 6))
    _check(c, ML + 364, pt + 30, checked=True, size=6)
    _text(c, ML + 380, pt + 30, "NON-PARTICIPATING", font=("Helvetica", 6))
    _text(c, ML + 446, pt + 14, "RETRO PLAN", font=("Helvetica-Bold", 5.5))
    c.line(ML, _y(pt + 38), MR, _y(pt + 38))

    _text(c, ML + 3, pt + 47, "PART 1 - WORKERS", font=("Helvetica-Bold", 5.5))
    _text(c, ML + 3, pt + 53, "COMPENSATION (States)", font=("Helvetica-Bold", 5.5))
    _fill(c, ML + 10, pt + 70, MN_RATING["state"])
    c.line(ML + 76, _y(pt + 38), ML + 76, _y(pt + 101))
    _text(c, ML + 80, pt + 47, "PART 2 - EMPLOYER'S LIABILITY",
          font=("Helvetica-Bold", 5.5))
    el = m["el_limits"]
    for i, (amt, lab) in enumerate(((el[0], "EACH ACCIDENT"),
                                    (el[1], "DISEASE-POLICY LIMIT"),
                                    (el[2], "DISEASE-EACH EMPLOYEE"))):
        _text(c, ML + 84, pt + 61 + i * 11, "$", font=("Helvetica-Bold", 6.5))
        _fill(c, ML + 92, pt + 61 + i * 11, _money(amt))
        _text(c, ML + 158, pt + 61 + i * 11, lab, font=("Helvetica", 6.2))
    c.line(ML + 242, _y(pt + 38), ML + 242, _y(pt + 101))
    _text(c, ML + 246, pt + 47, "PART 3 - OTHER", font=("Helvetica-Bold", 5.5))
    _text(c, ML + 246, pt + 53, "STATES INS", font=("Helvetica-Bold", 5.5))
    for j, ln in enumerate(_wrap(c, m["other_states"], 68, ("Helvetica", 5))):
        _text(c, ML + 246, pt + 62 + j * 5.8, ln, font=("Helvetica", 5))
    c.line(ML + 317, _y(pt + 38), ML + 317, _y(pt + 101))
    _text(c, ML + 321, pt + 45, "DEDUCTIBLES", font=("Helvetica-Bold", 5.5))
    _text(c, ML + 321, pt + 51, "(N / A in WI)", font=("Helvetica-Bold", 5))
    for i, lab in enumerate(("MEDICAL", "INDEMNITY")):
        _check(c, ML + 321, pt + 63 + i * 12, checked=False, size=6)
        _text(c, ML + 331, pt + 63 + i * 12, lab, font=("Helvetica", 6))
    c.line(ML + 391, _y(pt + 38), ML + 391, _y(pt + 101))
    _text(c, ML + 395, pt + 45, "AMOUNT / %", font=("Helvetica-Bold", 5.5))
    _text(c, ML + 395, pt + 51, "(N / A in WI)", font=("Helvetica-Bold", 5))
    c.line(ML + 435, _y(pt + 38), ML + 435, _y(pt + 101))
    _text(c, ML + 439, pt + 45, "OTHER COVERAGES", font=("Helvetica-Bold", 5.2))
    for i, lab in enumerate(("U.S.L. & H.", "VOLUNTARY COMP", "FOREIGN COV")):
        _check(c, ML + 439, pt + 58 + i * 11, checked=False, size=6)
        _text(c, ML + 448, pt + 58 + i * 11, lab, font=("Helvetica", 5.2))
    c.line(ML + 497, _y(pt + 38), ML + 497, _y(pt + 101))
    _check(c, ML + 501, pt + 58, checked=False, size=6)
    _text(c, ML + 511, pt + 55, "MANAGED", font=("Helvetica", 5.4))
    _text(c, ML + 511, pt + 61, "CARE OPTION", font=("Helvetica", 5.4))
    c.line(ML, _y(pt + 101), MR, _y(pt + 101))
    _text(c, ML + 3, pt + 109, "DIVIDEND PLAN/SAFETY GROUP",
          font=("Helvetica-Bold", 5.5))
    c.line(ML + 200, _y(pt + 101), ML + 200, _y(pt + 114))
    _text(c, ML + 204, pt + 109, "ADDITIONAL COMPANY INFORMATION",
          font=("Helvetica-Bold", 5.5))
    c.line(ML, _y(pt + 114), MR, _y(pt + 114))
    _text(c, ML + 3, pt + 121,
          "SPECIFY ADDITIONAL COVERAGES / ENDORSEMENTS (Attach ACORD 101, "
          "Additional Remarks Schedule, if more space is required)",
          font=("Helvetica-Bold", 5.5))
    _text(c, ML + 5, pt + 128,
          "WC 00 03 13 Waiver of Our Right to Recover From Others where "
          "required by written contract.", font=("Helvetica", 6.2))

    # -- total estimated annual premium — all states: 516 .. 551 -----------
    tt = 516
    _section_hdr(c, ML, tt, "TOTAL ESTIMATED ANNUAL PREMIUM - ALL STATES")
    _box(c, ML, tt + 5, MR - ML, 30)
    for x, lab, val in ((ML, "TOTAL ESTIMATED ANNUAL PREMIUM ALL STATES",
                         prem["total_estimated_annual"]),
                        (ML + 188, "TOTAL MINIMUM PREMIUM ALL STATES",
                         prem["minimum_premium"]),
                        (ML + 376, "TOTAL DEPOSIT PREMIUM ALL STATES",
                         prem["deposit_premium"])):
        _text(c, x + 4, tt + 15, lab, font=("Helvetica-Bold", 5.5))
        _text(c, x + 4, tt + 30, "$", font=("Helvetica-Bold", 7))
        _fill(c, x + 12, tt + 30, _money(val))
        if x > ML:
            c.line(x, _y(tt + 5), x, _y(tt + 35))

    # -- contact information: 558 .. 605 -----------------------------------
    ct = 558
    _section_hdr(c, ML, ct, "CONTACT INFORMATION")
    _box(c, ML, ct + 5, MR - ML, 47)
    for x, lab in ((ML + 4, "TYPE"), (ML + 64, "NAME"), (ML + 244, "OFFICE PHONE"),
                   (ML + 354, "MOBILE PHONE"), (ML + 464, "E-MAIL")):
        _text(c, x, ct + 15, lab, font=("Helvetica-Bold", 5.5))
    c.line(ML, _y(ct + 18), MR, _y(ct + 18))
    for x in (ML + 60, ML + 240, ML + 350, ML + 460):
        c.line(x, _y(ct + 5), x, _y(ct + 52))
    for i, lab in enumerate(("INSPECTION", "ACCTNG\nRECORD", "CLAIMS\nINFO")):
        y = ct + 18 + i * 11.333
        for j, ln in enumerate(lab.split("\n")):
            _text(c, ML + 3, y + 6 + j * 4.6, ln, font=("Helvetica-Bold", 5))
        if i < 2:
            c.line(ML, _y(y + 11.333), MR, _y(y + 11.333))
        if i == 0:
            _text(c, ML + 64, y + 7.5,
                  f"{m['owner']}, {m['owner_title']}", font=("Helvetica", 6))

    # -- individuals included / excluded: 620 .. 735 -----------------------
    it = 620
    _section_hdr(c, ML, it, "INDIVIDUALS INCLUDED / EXCLUDED")
    _box(c, ML, it + 5, MR - ML, 110)
    _text(c, ML + 3, it + 14,
          "PARTNERS, OFFICERS, RELATIVES ( Must be employed by business "
          "operations) TO BE INCLUDED OR EXCLUDED (Remuneration/Payroll to be "
          "included must be part of rating information section.)",
          font=("Helvetica-Bold", 5))
    _text(c, ML + 3, it + 20,
          "Exclusions in Missouri must meet the requirements of Section "
          "287.090 RSMo.", font=("Helvetica-Bold", 5))
    # Column edges scaled off the reference blank so the last column ends at
    # the right margin instead of running off it.
    edges = [ML, ML + 24, ML + 60, ML + 156, ML + 216, ML + 272, ML + 312,
             ML + 418, ML + 448, ML + 484, MR]
    heads = ["STATE", "LOC #", "NAME", "DATE OF BIRTH", "TITLE/\nRELATIONSHIP",
             "OWNER-\nSHIP %", "DUTIES", "INC/EXC", "CLASS CODE",
             "REMUNERATION/PAYROLL"]
    for i, h in enumerate(heads):
        for j, ln in enumerate(h.split("\n")):
            _text(c, edges[i], it + 29 + j * 5, ln, font=("Helvetica-Bold", 4.4),
                  center_w=edges[i + 1] - edges[i])
    c.line(ML, _y(it + 39), MR, _y(it + 39))
    for x in edges[1:-1]:
        c.line(x, _y(it + 24), x, _y(it + 115))
    for i in range(1, 5):
        c.line(ML, _y(it + 39 + i * 19), MR, _y(it + 39 + i * 19))
    vals = ["MN", "1", m["owner"], _d(m["owner_dob"]), m["owner_title"], "100",
            "Store operations and supervision", "INC", m["owner_class_code"],
            _money(m["owner_annual"])]
    for i, val in enumerate(vals):
        _text(c, edges[i] + 2, it + 51, val, font=("Helvetica", 5.4),
              center_w=(edges[i + 1] - edges[i] - 4) if i not in (2, 6) else None)

    # Page 1 carries no AGENCY CUSTOMER ID header line — the reference blank
    # puts it at the foot of the agency block instead, and only pages 2-4
    # repeat it across the top.
    _footer(c, 1)


def _page2(c, m, prem, defect):
    _text(c, ML, 40, "STATE RATING SHEET #", font=("Helvetica-Bold", 8))
    c.setLineWidth(0.7)
    c.line(ML + 96, _y(41.5), ML + 124, _y(41.5))
    _text(c, ML + 106, 40, "1", font=_FILL)
    _text(c, ML + 130, 40, "OF", font=("Helvetica-Bold", 8))
    c.line(ML + 148, _y(41.5), ML + 176, _y(41.5))
    _text(c, ML + 158, 40, "1", font=_FILL)
    _text(c, ML + 182, 40, "SHEETS", font=("Helvetica-Bold", 8))
    _customer_id(c, m["agency_customer_id"])

    top = 50
    _box(c, ML, top, MR - ML, 500)
    _text(c, 306, top + 12, "STATE RATING WORKSHEET",
          font=("Helvetica-Bold", 8.5), center_w=0)
    _text(c, ML + 4, top + 28,
          "FOR  MULTIPLE STATES, ATTACH AN ADDITIONAL PAGE 2 OF THIS FORM",
          font=("Helvetica-Bold", 7.5))
    _text(c, ML + 4, top + 44, "RATING INFORMATION - STATE:",
          font=("Helvetica-Bold", 7.5))
    _fill(c, ML + 140, top + 44, MN_RATING["state"])

    ht = top + 50
    cols = [ML, ML + 34, ML + 92, ML + 128, ML + 320, ML + 356, ML + 392,
            ML + 424, ML + 460, ML + 500, ML + 528, MR]
    heads = ["LOC #", "CLASS CODE", "DESCR\nCODE",
             "CATEGORIES, DUTIES, CLASSIFICATIONS", "FULL\nTIME", "PART\nTIME",
             "SIC", "NAICS", "ESTIMATED ANNUAL\nREMUNERATION/\nPAYROLL",
             "RATE", "ESTIMATED\nANNUAL MANUAL\nPREMIUM"]
    for i, h in enumerate(heads):
        x, w = cols[i], cols[i + 1] - cols[i]
        if i == 4:
            # the spanner over FULL TIME / PART TIME, emitted in reading order
            # so the layout test can assert page sequence
            _text(c, ML + 322, ht + 8, "# EMPLOYEES", font=("Helvetica-Bold", 4.8))
        for j, ln in enumerate(h.split("\n")):
            _text(c, x, ht + 16 + j * 5.4, ln, font=("Helvetica-Bold", 4.6),
                  center_w=w)
    row_top = ht + 36
    c.line(ML, _y(row_top), MR, _y(row_top))
    for x in cols[1:-1]:
        c.line(x, _y(ht), x, _y(row_top + 13 * 22))
    for i in range(14):
        c.line(ML, _y(row_top + i * 22), MR, _y(row_top + i * 22))

    for i, r in enumerate(m["worksheet"]):
        y = row_top + i * 22 + 14
        _text(c, cols[0], y, str(r["loc"]), font=("Helvetica", 6.4),
              center_w=cols[1] - cols[0])
        _text(c, cols[1], y, r["class_code"], font=("Helvetica", 6.4),
              center_w=cols[2] - cols[1])
        _text(c, cols[3] + 3, y, r["description"], font=("Helvetica", 6.4))
        _text(c, cols[4], y, str(r["ft"]), font=("Helvetica", 6.4),
              center_w=cols[5] - cols[4])
        _text(c, cols[5], y, str(r["pt"]) if r["pt"] else "",
              font=("Helvetica", 6.4), center_w=cols[6] - cols[5])
        _text(c, cols[6], y, r["sic"], font=("Helvetica", 6.4),
              center_w=cols[7] - cols[6])
        _text(c, cols[7], y, r["naics"], font=("Helvetica", 6.4),
              center_w=cols[8] - cols[7])
        _text(c, cols[9] - 4, y, _money(r["payroll"]), font=("Helvetica", 6.4),
              right=True)
        _text(c, cols[10] - 4, y, f"{r['rate']:.3f}", font=("Helvetica", 6.4),
              right=True)
        _text(c, MR - 4, y, _money(r["premium"]), font=("Helvetica", 6.4),
              right=True)

    # -- PREMIUM box --------------------------------------------------------
    pb = row_top + 13 * 22 + 6
    _section_hdr(c, ML, pb, "PREMIUM")
    _box(c, ML, pb + 4, MR - ML, 116)
    mid = ML + 300
    _text(c, ML + 3, pb + 14, "STATE:", font=("Helvetica-Bold", 5.5))
    _fill(c, ML + 34, pb + 14, MN_RATING["state"])
    for x in (ML + 156, ML + 200, mid, mid + 130, mid + 176):
        c.line(x, _y(pb + 4), x, _y(pb + 120))
    for lab, x in (("FACTOR", ML + 158), ("FACTORED PREMIUM", ML + 214),
                   ("FACTOR", mid + 132), ("FACTORED PREMIUM", mid + 190)):
        _text(c, x, pb + 14, lab, font=("Helvetica-Bold", 5.5))
    c.line(ML, _y(pb + 17), MR, _y(pb + 17))

    # Emitted in reading order — left row i, then the right row that shares its
    # line — so the layout test can assert page sequence the way a person sees
    # it rather than the way a loop happened to be written.
    left, right = premium_rows(m, prem, defect)
    for i, (lab, factor, amount) in enumerate(left):
        y = pb + 17 + i * 12
        for j, ln in enumerate(lab.split("\n")):
            _text(c, ML + 3, y + 8 + j * 4.6, ln, font=("Helvetica", 5.4))
        _text(c, ML + 178, y + 8, factor, font=("Helvetica", 5.4), center_w=0)
        _text(c, ML + 205, y + 8, "$", font=("Helvetica-Bold", 5.6))
        if amount is not None:
            _text(c, mid - 6, y + 8, _money(amount), font=("Helvetica", 5.6),
                  right=True)
        if i:
            c.line(ML, _y(y), ML + 300, _y(y))
        if i >= 1 and i - 1 < len(right):
            lab_r, factor_r, amount_r = right[i - 1]
            _text(c, mid + 3, y + 8, lab_r, font=("Helvetica", 5.4))
            _text(c, mid + 150, y + 8, factor_r, font=("Helvetica", 5.4),
                  center_w=0)
            _text(c, mid + 181, y + 8, "$", font=("Helvetica-Bold", 5.6))
            if amount_r is not None:
                _text(c, MR - 6, y + 8, _money(amount_r),
                      font=("Helvetica", 5.6), right=True)
            c.line(mid, _y(y), MR, _y(y))
    _text(c, ML + 3, pb + 119, "*  N / A in Wisconsin", font=("Helvetica", 5.4))

    tt = pb + 120
    _box(c, ML, tt, MR - ML, 26)
    for x, lab, val in ((ML, "TOTAL ESTIMATED ANNUAL PREMIUM",
                         prem["total_estimated_annual"]),
                        (ML + 216, "MINIMUM PREMIUM", prem["minimum_premium"]),
                        (ML + 420, "DEPOSIT PREMIUM", prem["deposit_premium"])):
        _text(c, x + 4, tt + 10, lab, font=("Helvetica-Bold", 5.5))
        _text(c, x + 4, tt + 22, "$", font=("Helvetica-Bold", 6.5))
        _fill(c, x + 12, tt + 22, _money(val))
        if x > ML:
            c.line(x, _y(tt), x, _y(tt + 26))

    rt = tt + 30
    _text(c, ML, rt, "REMARKS (ACORD 101, Additional Remarks Schedule, may be "
          "attached if more space is required)", font=("Helvetica-Bold", 7.5))
    _box(c, ML, rt + 4, MR - ML, 736 - rt)
    y = rt + 16
    for line in remarks_lines(m):
        for j, ln in enumerate(_wrap(c, line, MR - ML - 12, ("Helvetica", 6.2))):
            _text(c, ML + 5 + (8 if j else 0), y, ln, font=("Helvetica", 6.2))
            y += 7.4
        y += 1.6
    _footer(c, 2)


def _page3(c, m, defect):
    _customer_id(c, m["agency_customer_id"])
    _section_hdr(c, ML, 52, "PRIOR CARRIER INFORMATION / LOSS HISTORY")
    _box(c, ML, 56, MR - ML, 148)
    _text(c, ML + 3, 66,
          "PROVIDE INFORMATION FOR THE PAST 5 YEARS AND USE THE REMARKS "
          "SECTION FOR LOSS DETAILS", font=("Helvetica-Bold", 5.5))
    _check(c, 434, 65, checked=True, size=7)
    _text(c, 446, 65, "LOSS RUN ATTACHED", font=("Helvetica", 6.2))
    c.line(ML, _y(70), MR, _y(70))
    cols = [ML, ML + 48, ML + 264, ML + 330, ML + 380, ML + 436, ML + 508, MR]
    heads = ["YEAR", "CARRIER & POLICY NUMBER", "ANNUAL PREMIUM", "MOD",
             "# CLAIMS", "AMOUNT PAID", "RESERVE"]
    for i, h in enumerate(heads):
        _text(c, cols[i], 80, h, font=("Helvetica-Bold", 5.5),
              center_w=cols[i + 1] - cols[i])
    c.line(ML, _y(84), MR, _y(84))
    for x in cols[1:-1]:
        c.line(x, _y(70), x, _y(204))
    c.line(ML + 96, _y(84), ML + 96, _y(204))
    for i, row in enumerate(m["loss_history"]):
        y = 84 + i * 24
        c.line(ML, _y(y), MR, _y(y))
        c.line(ML + 48, _y(y + 12), ML + 264, _y(y + 12))
        _text(c, cols[0], y + 15, str(row["year"]), font=("Helvetica", 6.2),
              center_w=48)
        _text(c, ML + 52, y + 9, "CO:", font=("Helvetica-Bold", 5.5))
        _text(c, ML + 100, y + 9, row["carrier"], font=("Helvetica", 6))
        _text(c, ML + 52, y + 21, "POL #:", font=("Helvetica-Bold", 5.5))
        _text(c, ML + 100, y + 21, row["policy"], font=("Helvetica", 6))
        _text(c, cols[3] - 4, y + 15, _money(row["premium"]),
              font=("Helvetica", 6.2), right=True)
        _text(c, cols[3], y + 15, row["mod"], font=("Helvetica", 6.2),
              center_w=cols[4] - cols[3])
        _text(c, cols[4], y + 15, str(row["claims"]), font=("Helvetica", 6.2),
              center_w=cols[5] - cols[4])
        _text(c, cols[6] - 4, y + 15, _money(row["paid"]) if row["claims"] else "",
              font=("Helvetica", 6.2), right=True)
        _text(c, MR - 4, y + 15, _money(row["reserve"]) if row["claims"] else "",
              font=("Helvetica", 6.2), right=True)

    _section_hdr(c, ML, 214, "NATURE OF BUSINESS / DESCRIPTION OF OPERATIONS")
    _box(c, ML, 218, MR - ML, 150)
    for j, ln in enumerate(NATURE_OF_BUSINESS_PROMPT.split("\n")):
        _text(c, ML + 3, 228 + j * 7, ln, font=("Helvetica-Bold", 5.4))
    y = 252
    for ln in _wrap(c, m["nature_of_business"], MR - ML - 16, ("Helvetica", 7)):
        _text(c, ML + 6, y, ln, font=("Helvetica", 7))
        y += 9.6

    _section_hdr(c, ML, 378, "GENERAL INFORMATION")
    _questions(c, 382, GENERAL_QS[:16], m["answers"], m["explanations"], start=1)
    _footer(c, 3)


def _questions(c, top, questions, answers, explanations, *, start=1,
               header="GENERAL INFORMATION (continued)"):
    bar_h = 11
    c.setLineWidth(0.7)
    _box(c, ML, top, MR - ML, bar_h)
    _text(c, ML + 3, top + 8, 'EXPLAIN ALL "YES" RESPONSES',
          font=("Helvetica-Bold", 6))
    _text(c, MR - 22, top + 8, "Y / N", font=("Helvetica-Bold", 6))
    y = top + bar_h
    for i, q in enumerate(questions, start):
        lines = q.split("\n")
        has_exp = answers.get(i) == "Y" and i in explanations
        wrapped = (_wrap(c, explanations[i], MR - ML - 60, ("Helvetica", 6.2))
                   if has_exp else [])
        # Row height follows the reference blank, which leaves writing room
        # under every question rather than hugging the text.
        h = 8.4 * len(lines) + 13 + 7.2 * len(wrapped)
        _box(c, ML, y, MR - ML, h)
        for j, ln in enumerate(lines):
            _text(c, ML + 4 + (12 if j else 0), y + 9 + j * 8.4,
                  (f"{i}." + ("  " if i < 10 else " ") if j == 0 else "") + ln,
                  font=_Q)
        bx = MR - 20
        c.rect(bx, _y(y + 11), 11, 10)
        if answers.get(i):
            c.setFont("Helvetica", 7.2)
            c.drawCentredString(bx + 5.5, _y(y + 11) + 2.4, answers[i])
        for j, ln in enumerate(wrapped):
            _text(c, ML + 20, y + 9 + 8.4 * len(lines) + j * 7.2, ln,
                  font=("Helvetica", 6.2))
        y += h
    return y


def _page4(c, m, defect):
    _customer_id(c, m["agency_customer_id"])
    _section_hdr(c, ML, 52, "GENERAL INFORMATION (continued)")
    y = _questions(c, 56, GENERAL_QS[16:], m["answers"], m["explanations"],
                   start=17)

    _section_hdr(c, ML, y + 8, "SIGNATURE")
    _box(c, ML, y + 12, MR - ML, 16)
    _check(c, ML + 6, y + 22, checked=True, size=7)
    _text(c, ML + 20, y + 22,
          "Copy of the Notice of Information Practices (Privacy) has been "
          "given to the applicant. (Not required in all states, contact your "
          "agent or broker for your state's requirements.)",
          font=("Helvetica", 5.8))
    pv_top = y + 28
    pv = _wrap(c, PRIVACY_NOTICE, MR - ML - 12, ("Helvetica", 5.4))
    _box(c, ML, pv_top, MR - ML, 10 + 6.6 * (len(pv) + 1))
    for j, ln in enumerate(pv):
        _text(c, ML + 5, pv_top + 9 + j * 6.6, ln, font=("Helvetica", 5.4))
    note_y = pv_top + 9 + len(pv) * 6.6
    _text(c, ML + 5, note_y, PRIVACY_STATE_NOTE, font=("Helvetica", 5.4))
    # Minnesota is named in that parenthetical, so the applicant does not
    # initial here — the field stays empty by jurisdiction, not by oversight.
    _text(c, 470, note_y, "(Applicant's Initials):", font=("Helvetica-Bold", 5.4))
    c.line(538, _y(note_y + 1.5), MR - 4, _y(note_y + 1.5))

    # Lay the fraud block out twice: once to measure, once to draw. The box has
    # to hug its content — a preprinted notice with a page of white space under
    # it is not what the form looks like.
    def _fraud_block(y0, draw):
        y = y0 + 8
        for head, body in FRAUD_PARAGRAPHS:
            hw = c.stringWidth(head, "Helvetica-Bold", 5.4)
            if draw:
                _text(c, ML + 5, y, head, font=("Helvetica-Bold", 5.4))
            first = _wrap(c, body, MR - ML - 14 - hw, ("Helvetica", 5.4))
            if first:
                if draw:
                    _text(c, ML + 7 + hw, y, first[0], font=("Helvetica", 5.4))
                for ln in _wrap(c, " ".join(first[1:]), MR - ML - 14,
                                ("Helvetica", 5.4)):
                    y += 6.4
                    if draw:
                        _text(c, ML + 5, y, ln, font=("Helvetica", 5.4))
            y += 8.2
        return y - y0

    fy = note_y + 10
    fraud_h = _fraud_block(fy, False)
    _box(c, ML, fy, MR - ML, fraud_h)
    _fraud_block(fy, True)

    # The representation and signature blocks follow the notices immediately,
    # as on the reference — they are not anchored to the foot of the page.
    rep_top = fy + fraud_h + 4
    rep = _wrap(c, REPRESENTATION, MR - ML - 12, ("Helvetica-Bold", 5.6))
    _box(c, ML, rep_top, MR - ML, 8 + 6.8 * len(rep))
    for j, ln in enumerate(rep):
        _text(c, ML + 5, rep_top + 8 + j * 6.8, ln, font=("Helvetica-Bold", 5.6))
    sig_top = rep_top + 8 + 6.8 * len(rep)
    _box(c, ML, sig_top, MR - ML, 26)
    # Four cells: applicant signature, date, producer signature, NPN. The NPN
    # stays empty — it is a registry number and was not sourced.
    for x, lab in ((ML + 3, "APPLICANT'S SIGNATURE (Must be Officer, Owner or Partner)"),
                   (200, "DATE"), (292, "PRODUCER'S SIGNATURE"),
                   (491, "NATIONAL PRODUCER NUMBER")):
        _text(c, x, sig_top + 22, lab, font=("Helvetica-Bold", 5.5))
    for x in (197, 289, 488):
        c.line(x, _y(sig_top), x, _y(sig_top + 26))
    _fill(c, 200, sig_top + 12, _d(m["date"]))
    _footer(c, 4)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def render_130(model: dict, *, metadata: dict, defect: dict | None = None) -> bytes:
    """Render a filled ACORD 130 (2017/05) as a 4-page PDF.

    Defect hooks, each altering exactly one displayed value:
      {"worksheet_premium": (idx, value)} — one row's manual premium stops
          footing against its own payroll x rate
      {"premium_total": value} — the TOTAL ESTIMATED ANNUAL PREMIUM mis-adds
      {"experience_mod": value} — a modification appears on a risk below
          Minnesota's eligibility threshold
      {"arap": value} — an ARAP charge in a state that has no ARAP
    """
    defect = defect or {}
    m = dict(model)
    if "worksheet_premium" in defect:
        idx, val = defect["worksheet_premium"]
        ws = [dict(r) for r in m["worksheet"]]
        ws[idx]["premium"] = val
        m["worksheet"] = ws
    if "experience_mod" in defect:
        m["experience_mod"] = defect["experience_mod"]

    prem = compute_premium(m)
    if "premium_total" in defect:
        prem = dict(prem, total_estimated_annual=defect["premium_total"])

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=letter, invariant=1)
    c.setTitle("ACORD 130 - Workers Compensation Application")
    c.setProducer(metadata["producer"])
    c.setCreator(metadata["creator"])
    c.setLineWidth(0.7)
    for fn, args in ((_page1, (m, prem, defect)), (_page2, (m, prem, defect)),
                     (_page3, (m, defect)), (_page4, (m, defect))):
        c.setLineWidth(0.7)
        fn(c, *args)
        c.showPage()
    c.save()
    out = legalpdf._fix_dates(buf.getvalue(), created=metadata.get("created"),
                              modified=metadata.get("modified"))
    return legalpdf._fix_id(out)
