"""diligence: multi-instrument diligence packets as bates-numbered productions.

What distinguishes a packet from a long filing (`longdoc`) is that its pages
came from DIFFERENT ORGANIZATIONS. A real production set is visually
heterogeneous — a law firm's memorandum, a London surveyor's report, a
veterinarian's certificate and a corporate secretary's resolution do not share
a typeface, a date format, or a sense of what a heading is. Uniform styling
across tabs is the single loudest tell that a packet was generated rather than
assembled, so per-source visual identity is a capability here, not decoration.

The other half is cross-INSTRUMENT coherence. One sampled fact must answer
every field it touches even when those fields sit in documents written by
parties who never spoke: the specimen roster drives the surveyor's schedule,
the veterinarian's certificate and the licence exhibit; the recommendation
register drives which recommendations counsel and the board describe as open;
the incident drives the report, the loss-experience section and the board's
recitals. Nothing is restated — it is recomputed.

## The canon instance: a private biological reserve, 1993

The realism thesis is structural and deliberately unstated: **nobody approved
the park.** Seven professionals each certified something materially narrower
than a reader assumes, and the packet is the record of that narrowing —

- the veterinarian certifies containment *as presently housed, at present body
  mass*, having observed the apex enclosure from outside it;
- the surveyor does not decline the risk, he *sublimits* it, and warrants
  cover on compliance he then records as outstanding;
- counsel opines on regulatory exposure and expressly declines to opine on
  containment adequacy — and advises against the minors, in writing;
- the board authorises a limited-invitee weekend inspection, expressly not an
  opening, and reserves that decision to a further resolution.

Read any instrument alone and it is responsible. Read the scope limitations
against each other and the gap between them is the park.

Period discipline (represented 1993, digitised later): MIRENEM is the ministry
of the day — MINAE (1995) and SINAC (1998) are anachronisms; Ley de
Conservación de la Vida Silvestre 7317 (1992) is in force; the Convention on
Biological Diversity is signed at Rio (June 1992) but not yet in force
(December 1993) and not yet ratified by Costa Rica (1994), which is precisely
what supplies the urgency to open before the regime binds.

Delivery is a scan, and for a packet the reason is not the format's age: a
diligence production is photocopied, bates-stamped paper, digitised later. The
bates numbers and the scan tell the same story.

## v0.2 — the insurance transaction as the narrative spine (round 6)

The round-6 external review's verdict: v0.1 was a diligence binder WITH an
insurance report inside it, not the underwriting file THROUGH which the risk
was presented, priced, restricted and conditionally insured. v0.2 adds the
placement record (tabs 8–11): the broker's first advice and statement of
values (whose declared total is DERIVED from its components), a placing slip
with the programme in sections and a subscription table that oversubscribes
on written lines and signs down to exactly 100%, the lead underwriter's
retained file note (risk-quality grades, PML/MFL, a subjectivity register
whose statuses are COMPUTED from facts other tabs already state, and the
broker's answers with the underwriter's marginal annotations), and the
special-acceptance trail — the request to waive the minors and certification
subjectivities, the lead's refusal, and the priced, restricted exception
endorsement under which the inspection actually proceeds. The park can still
happen; the file now shows precisely how little of it the market accepted.

Period mechanics matter here: in 1993 a breach of warranty DISCHARGES
underwriters from liability from the date of breach (Marine Insurance Act
1906 s.33(3) regime) — suspension-until-cure is an Insurance Act 2015
anachronism. And markings are party-appropriate per tab: privilege belongs to
counsel's memorandum alone; a surveyor's report is a confidential survey
report for underwriting purposes; the lead's file note is not addressed to
the assured at all.
"""

from __future__ import annotations

import datetime as _dt
import io
import random

from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as rl_canvas

from . import assets, scan

PAGE_W, PAGE_H = letter
LEFT, RIGHT = 72.0, 540.0
TOP_Y, BOTTOM_Y = 716.0, 92.0
USABLE = RIGHT - LEFT


# ---------------------------------------------------------------------------
# Canon — caller-supplied world facts. Only texture is sampled.
#
# The canon is DATA, not code: pass your own to sample_packet(rng,
# canon=...). The default below is an invented operator, shipped so the
# emitter runs out of the box.
# ---------------------------------------------------------------------------

DEFAULT_CANON = {
    "company": "HELICON LIFE SYSTEMS, INCORPORATED",
    "company_short": "Helicon",
    "bates_prefix": "HELICON-DIL-",   # production numbering follows
                                      # the producing party
    "subsidiary": "Helicon Marítima, S.A.",
    "hq": ["480 Oyster Point Boulevard",
           "South San Francisco, California 94080"],
    "island": "Isla Ventana",
    "island_desc": "an island situated approximately 140 miles west of the "
                   "Pacific coast of the Republic of Costa Rica",
    "park": "the Ventana Reserve",
    "chairman": "AUGUST W. LINDQVIST",
    "chairman_title": "Chairman and Chief Executive Officer",
    "counsel_firm": "COWAN, SWAIN & ROSS",
    "counsel_name": "DONALD GENNARO",
    "counsel_city": "San Francisco, California",
    "geneticist": "MIRA A. SOLBERG, Ph.D.",
    "geneticist_title": "Chief Geneticist",
    "warden": "THOMAS OYELARAN",
    "warden_title": "Reserve Warden, Isla Ventana",
    "vet": "GERALD R. HARDING, D.V.M.",
    "vet_title": "Reserve Veterinary Officer",
    "engineer": "RAY ARNOLD",
    "engineer_title": "Chief Engineer",
    "experts": [
        ("ALICE N. FERREIRA, Ph.D.", "Vertebrate zoology",
         "Department of Zoology, Cascade Institute of Natural History, Oregon"),
        ("EVAN R. HOLLIS, Ph.D.", "Plant pathology",
         "Department of Botany, Cascade Institute of Natural History, Oregon"),
        ("NADIA KRISTOFF, Ph.D.", "Mathematics; non-linear dynamics",
         "Department of Mathematics, Fairhaven University"),
    ],
    "minors": [("ALEXIS MURPHY", 12), ("TIMOTHY MURPHY", 9)],
    "minors_relation": "grandchildren of the Chairman",
    "ministry": "Ministerio de Recursos Naturales, Energía y Minas (MIRENEM)",
    # -- the placement (fictional market; see the spec's open sourcing gaps —
    # real syndicate NUMBERS invite lookup, so following markets are named
    # stamps without numbers) -----------------------------------------------
    "broker": "HARROWGATE, PIKE & FENNER LTD.",
    "broker_desc": "Lloyd's Brokers",
    "broker_addr": ["Minster Court, Mincing Lane", "London EC3R 7AA"],
    "broker_partner": "J. G. PIKE",
    "lead_uw": "E. R. CASTLETON",
    "lead_uw_initials": "E.R.C.",
}

_CANON_KEYS = frozenset(DEFAULT_CANON)

# Following markets, in slip order after the lead. Names only — no syndicate
# numbers (spec: open sourcing gap; a real number invites lookup).
FOLLOWING_MARKETS = [
    "Anstruther & Vane, Syndicate at Lloyd's",
    "Kelsall Marine & General, Syndicate at Lloyd's",
    "Mercantile & Colonial Assurance Company Limited",
    "Hollandia Reinsurance N.V. (London Branch)",
    "Bermuda Atlantic Casualty Limited",
]

# Line conditions a following market may scratch onto its stamp. Two Nones:
# most followers simply follow. Assigned by seeded sample in sample_packet.
_LINE_CONDITIONS = [
    None,
    None,
    "Excluding Class IV liability in toto.",
    "Property and business interruption sections only. NIL Sections V and VI.",
    "To follow the Leading Underwriter upon all endorsements save any "
    "additional premium exceeding USD 50,000.",
]

# Statement-of-values conventional components: (item, low, high, basis).
# Values are SAMPLED; the declared total is COMPUTED from them (plus the
# specimen schedule), never the other way round.
_SOV_ITEMS = [
    ("Visitor centre and administration buildings", 14.0, 22.0,
     "Replacement cost"),
    ("Laboratory and hatchery building and fit-out", 19.0, 28.0,
     "Replacement cost"),
    ("Control, communications and security systems", 12.0, 18.0,
     "Replacement cost"),
    ("Power generation and distribution", 9.0, 15.0, "Replacement cost"),
    ("Paddocks, perimeter barriers and roads", 24.0, 36.0,
     "Replacement cost"),
    ("Marine, aviation and transport equipment", 6.0, 10.0,
     "Depreciated value"),
    ("Research equipment and conventional inventory", 7.0, 12.0,
     "Replacement cost"),
    ("Data, cultures and genetic media (media only)", 5.0, 9.0,
     "Reproduction cost of media"),
]

# Agreed value per head by containment class ($m). The basis an underwriter
# will actually ask about: these are AGREED settlement values, not expected
# revenue and not the value of the library (which is expressly not insured —
# see the licence, clause 6, and the note to the statement of values).
_AGREED_VALUE_BY_CLASS = {"IV": (2.0, 3.5), "III": (1.2, 2.0),
                          "II": (0.8, 1.6), "I": (0.4, 0.9)}

# Species: mass and behaviour are canon-anchored facts. Containment class is
# DERIVED from them (see _containment_class) — never sampled, because the
# whole point of the classification is that it follows from the animal.
SPECIES = [
    # (name, adult mass kg, predator, pack-hunting)
    ("Tyrannosaurus rex", 7000, True, False),
    ("Velociraptor", 90, True, True),
    ("Dilophosaurus", 400, True, False),
    ("Triceratops", 9000, False, False),
    ("Brachiosaurus", 35000, False, False),
    ("Gallimimus", 440, False, False),
    ("Parasaurolophus", 2500, False, False),
]


def _containment_class(mass_kg: int, predator: bool, pack: bool) -> str:
    """Class follows from the animal, not from its size alone.

    This rule is the reason the register is worth reading: mass alone puts
    Velociraptor two classes below Tyrannosaurus, and the pack term is what
    pulls it back up to apex. A classification that ignored behaviour would
    under-rate the enclosure that actually failed.
    """
    if predator and (mass_kg >= 500 or pack):
        return "IV"
    if predator:
        return "III"
    if mass_kg >= 5000:
        return "II"
    return "I"


# ---------------------------------------------------------------------------
# Sampler
# ---------------------------------------------------------------------------

def _sample_subscription(rng: random.Random) -> list[dict]:
    """Written lines. The lead writes 20%; followers are sampled until the
    slip oversubscribes (a placement nobody oversubscribes reads as a
    placement nobody wanted). Line conditions are drawn from a fixed pool —
    two followers simply follow. Signed lines are computed, not sampled."""
    while True:
        written = [rng.choice([7.5, 10.0, 12.5, 15.0, 17.5, 20.0])
                   for _ in FOLLOWING_MARKETS]
        if 105.0 <= 20.0 + sum(written) <= 120.0:
            break
    conds = rng.sample(_LINE_CONDITIONS, len(FOLLOWING_MARKETS))
    lines = [{"market": "Chelmsford Underwriting Agencies Ltd. — "
                        "Leading Underwriter",
              "written": 20.0, "lead": True, "condition": None}]
    for name, w, cond in zip(FOLLOWING_MARKETS, written, conds):
        lines.append({"market": name, "written": w, "lead": False,
                      "condition": cond})
    return lines


def sample_packet(rng: random.Random, *, canon: dict | None = None) -> dict:
    """Seeded texture around a caller-supplied canon. Every date derives by
    offset from a single anchor, so the chronology cannot invert; every
    derived figure is computed at render time from the facts below, never
    stored here. `canon` supplies the world — see DEFAULT_CANON for the
    required keys; an incomplete one fails here rather than rendering a blank
    where an operator's name belongs."""
    canon = dict(DEFAULT_CANON if canon is None else canon)
    missing = _CANON_KEYS - set(canon)
    if missing:
        raise ValueError(f"canon missing required keys: {sorted(missing)}")
    anchor = _dt.date(1993, 5, 1) + _dt.timedelta(days=rng.randint(0, 26))

    roster = []
    for name, mass, predator, pack in SPECIES:
        count = (rng.randint(2, 4) if predator and pack else
                 rng.randint(1, 2) if predator else rng.randint(3, 9))
        cls = _containment_class(mass, predator, pack)
        roster.append({
            "species": name,
            "count": count,
            "adult_mass_kg": mass,
            "predator": predator,
            "pack": pack,
            "class": cls,
            "paddock": f"P-{rng.randint(2, 19):02d}",
            "agreed_value_mm": round(
                rng.uniform(*_AGREED_VALUE_BY_CLASS[cls]), 1),
        })

    # The register. Status is a sampled FACT (what the surveyor found); which
    # recommendations counsel and the board call open is computed from it.
    recs = [
        (1, "A", "Park systems depend upon a single integrated supervisory "
                 "control system. No independent local isolation exists at "
                 "perimeter or paddock barriers.", "Open"),
        (2, "A", "Transfer of Class IV specimens undertaken without the "
                 "three-handler minimum required by the operator's own "
                 "standing instruction.", "Closed"),
        (3, "A", "Standby generation restores barrier circuits only upon "
                 "restart of the main plant. Barrier circuits are not on "
                 "uninterruptible supply.", "Open"),
        (4, "A", "Class IV containment is rated to specimen mass recorded at "
                 "last examination. Specimens continue to gain mass. No "
                 "provision for periodic re-rating.", "Open"),
        (5, "B", "Casualty evacuation depends upon a single vessel and is "
                 "weather-dependent. No all-weather evacuation capability.",
         "Open"),
        (6, "B", "Specimen inventory is reconciled by count against expected "
                 "population, not by individual tag. A count-based census "
                 "cannot detect an unexpected increase.", "Open"),
        (7, "B", "Barrier breach alarms are not annunciated at a "
                 "continuously manned point outside the control room.",
         "Open"),
        (8, "C", "Chemical immobilisation stocks held at one location only.",
         "Closed"),
    ]
    recommendations = [
        {"no": n, "priority": p, "text": t, "status": s,
         "due": _fmt_uk(anchor + _dt.timedelta(days=rng.randint(60, 120)))}
        for n, p, t, s in recs
    ]

    # -- chronology: one anchor, fixed offsets, and the placement dates sit
    # BETWEEN the events they respond to by construction: first advice
    # follows the incident, the Q&A and the revised slip follow the survey,
    # the memorandum describes terms already set, and the special-acceptance
    # correspondence follows the board and precedes the visit.
    survey_date = anchor + _dt.timedelta(days=rng.randint(8, 16))
    board_date = anchor + _dt.timedelta(days=rng.randint(29, 33))

    return {
        **canon,
        "roster": roster,
        "recommendations": recommendations,
        "incident_date": anchor,
        "advice_date": anchor + _dt.timedelta(days=rng.randint(1, 3)),
        "survey_date": survey_date,
        "qa_date": survey_date + _dt.timedelta(days=rng.randint(4, 6)),
        "slip_date": survey_date + _dt.timedelta(days=rng.randint(7, 9)),
        "memo_date": anchor + _dt.timedelta(days=rng.randint(26, 28)),
        "board_date": board_date,
        "request_date": board_date + _dt.timedelta(days=1),
        "endt_date": board_date + _dt.timedelta(days=rng.randint(2, 3)),
        "visit_date": anchor + _dt.timedelta(days=rng.randint(37, 45)),
        "digitised": _dt.date(2016 + rng.randint(0, 5),
                              rng.randint(1, 12), rng.randint(1, 28)),
        # -- the incident --------------------------------------------------
        "incident": {
            "report_no": f"IN-93-{rng.randint(114, 189)}",
            "time": f"{rng.randint(19, 23)}{rng.choice(['05', '20', '40'])}",
            "location": "Paddock 11 holding pen, transfer race",
            "worker_role": "Gate keeper, animal handling section",
            "service_years": rng.randint(2, 6),
            "classification": "Fatality — animal handling",
            "handlers_present": 2,
            "handlers_required": 3,
        },
        # -- insurance: the placement --------------------------------------
        # Chelmsford is the LEAD, not a sole carrier: the risk is presented
        # by the broker and subscribed across a (fictional) London market.
        "carrier": "CHELMSFORD UNDERWRITING AGENCIES LIMITED",
        "carrier_addr": ["Fenchurch Buildings", "London EC3M 5AD"],
        "surveyor_firm": "HOLBEACH RISK ENGINEERING",
        "surveyor": "A. J. FENWICK, C.Eng., M.I.Mech.E.",
        "policy_no": f"CUA/{rng.randint(70, 94)}/{rng.randint(2000, 4999)}",
        "broker_ref": f"HPF/{rng.randint(4100, 9899)}/93",
        "endt_no": rng.randint(5, 9),
        "each_occurrence_mm": rng.choice([10.0, 15.0, 20.0]),
        "animal_sublimit_pct": rng.choice([0.25, 0.30, 0.40]),
        "class_iv_sublimit_pct": rng.choice([0.08, 0.10, 0.125]),
        "retention_k": rng.choice([250, 500, 750]),
        # -- rating inputs, one per section of the programme ---------------
        "rate_per_mille": round(rng.uniform(6.5, 11.5), 2),
        "mb_rate_per_mille": round(rng.uniform(9.0, 14.0), 2),
        "bi_premium_k": rng.randrange(480, 700, 20),
        "bi_sum_mm": rng.choice([10.0, 12.5, 15.0]),
        "liability_premium_k": rng.randrange(780, 960, 10),
        "specimen_rate_per_mille": round(rng.uniform(38.0, 52.0), 1),
        "el_premium_k": rng.randrange(180, 250, 10),
        "property_ded_k": rng.choice([1000, 1500, 2500]),
        "ap_inspection_k": rng.randrange(150, 225, 5),
        "inspection_retention_mm": rng.choice([1.5, 2.0, 2.5]),
        "brokerage_pct": rng.choice([10.0, 12.5, 15.0]),
        # -- statement of values: components sampled, total derived --------
        "sov_conventional": [
            (item, round(rng.uniform(lo, hi), 1), basis)
            for item, lo, hi, basis in _SOV_ITEMS
        ],
        # -- subscription: written lines sampled to oversubscribe; signed
        # lines are COMPUTED (sign-down to exactly 100%) in compute_coverage
        "subscription": _sample_subscription(rng),
        # -- loss-estimation inputs (survey section 8) ---------------------
        "pml_control_pct": round(rng.uniform(0.28, 0.36), 3),
        "pml_storm_pct": round(rng.uniform(0.18, 0.26), 3),
        "site_headcount": rng.randint(90, 140),
        # -- corporate -----------------------------------------------------
        "resolution_no": f"93-{rng.randint(11, 29)}",
        "directors_total": rng.choice([7, 9]),
        "secretary": rng.choice(["MARGARET T. ELLIS", "HOWARD B. LINDSTROM"]),
        "dissenting_director": rng.choice(["A. R. VASQUEZ", "P. J. OKONKWO",
                                           "S. M. BRENNAN"]),
        "concession_no": f"{rng.randint(1200, 4800)}-{rng.randint(84, 89)}",
        "bates_prefix": canon["bates_prefix"],
        "scan_seed": rng.randint(1, 9999),
    }


# -- derived values: computed, never stored ---------------------------------


def _signed_lines(subscription: list[dict]) -> list[float]:
    """Sign the slip down to exactly 100%. The lead's signed line equals its
    written line; followers scale to the remaining 80% in quarter-point
    steps, the residual distributed by largest remainder. Computed, never
    sampled — the tower must stack by construction."""
    lead_w = subscription[0]["written"]
    followers = [s["written"] for s in subscription[1:]]
    target = 100.0 - lead_w
    raw = [w * target / sum(followers) for w in followers]
    quarters = [int(r * 4) / 4 for r in raw]
    residual = round((target - sum(quarters)) * 4)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - quarters[i],
                   reverse=True)
    for i in range(residual):
        quarters[order[i % len(order)]] += 0.25
    return [lead_w] + quarters


def compute_coverage(m: dict) -> dict:
    """The programme, in sections. Every figure below follows from the
    sampled inputs: the declared total is the SUM of the statement-of-values
    components and the specimen schedule; each section's premium follows
    from its own rating base; the slip's signed lines foot to 100%. A
    schedule whose totals were drawn independently of their components is
    how you ship a tower that does not stack."""
    each = m["each_occurrence_mm"]
    animal = round(each * m["animal_sublimit_pct"], 2)
    class_iv = round(each * m["class_iv_sublimit_pct"], 2)
    aggregate = round(each * 2, 2)

    # -- statement of values: total derived from components ----------------
    conventional_mm = round(sum(v for _, v, _ in m["sov_conventional"]), 1)
    specimen_mm = round(sum(r["count"] * r["agreed_value_mm"]
                            for r in m["roster"]), 1)
    declared_mm = round(conventional_mm + specimen_mm, 1)

    # -- per-section premiums, footing to the annual total -----------------
    sov = dict((item, v) for item, v, _ in m["sov_conventional"])
    mb_base_mm = round(
        sov["Control, communications and security systems"]
        + sov["Power generation and distribution"], 1)
    premium_property = round(conventional_mm * 1000 * m["rate_per_mille"], 2)
    premium_mb = round(mb_base_mm * 1000 * m["mb_rate_per_mille"], 2)
    premium_bi = float(m["bi_premium_k"] * 1000)
    premium_liab = float(m["liability_premium_k"] * 1000)
    premium_specimen = round(specimen_mm * 1000
                             * m["specimen_rate_per_mille"], 2)
    premium_el = float(m["el_premium_k"] * 1000)
    sections = [
        ("I", "Industrial all risks (conventional property)",
         premium_property),
        ("II", "Machinery breakdown and electronic equipment", premium_mb),
        ("III", "Business interruption (standing charges only)", premium_bi),
        ("IV", "Public liability", premium_liab),
        ("V", "Specimen mortality, escape and recapture expense",
         premium_specimen),
        ("VI", "Employers' liability (excess of local admitted cover)",
         premium_el),
    ]
    annual_premium = round(sum(p for _, _, p in sections), 2)
    ap_inspection = float(m["ap_inspection_k"] * 1000)

    # -- loss estimation (survey section 8) --------------------------------
    pml_control_mm = round(conventional_mm * m["pml_control_pct"], 1)
    pml_fire_mm = round(
        sov["Control, communications and security systems"]
        + sov["Power generation and distribution"]
        + sov["Laboratory and hatchery building and fit-out"], 1)
    pml_storm_mm = round(conventional_mm * m["pml_storm_pct"], 1)

    return {
        "each_occurrence_mm": each,
        "aggregate_mm": aggregate,
        "animal_sublimit_mm": animal,
        "class_iv_sublimit_mm": class_iv,
        "retention_k": m["retention_k"],
        "retention_usd": m["retention_k"] * 1000,
        "layers": [
            ("Public liability — each occurrence", each),
            ("Public liability — aggregate", aggregate),
            ("Sub-limit: bodily injury arising from contact with or escape "
             "of any specimen", animal),
            ("Sub-limit: bodily injury arising from Class IV specimens", class_iv),
        ],
        "conventional_mm": conventional_mm,
        "specimen_mm": specimen_mm,
        "declared_mm": declared_mm,
        "mb_base_mm": mb_base_mm,
        "premium": premium_property,
        "sections": sections,
        "annual_premium": annual_premium,
        "ap_inspection": ap_inspection,
        "signed": _signed_lines(m["subscription"]),
        "written_total": round(sum(s["written"] for s in m["subscription"]), 2),
        "pml_control_mm": pml_control_mm,
        "pml_fire_mm": pml_fire_mm,
        "pml_storm_mm": pml_storm_mm,
    }


def subjectivity_register(m: dict) -> list[dict]:
    """The lead's subjectivity register. Statuses are COMPUTED from facts
    other instruments already state — the register cannot say satisfied
    while the board's resolution, the survey register or counsel's
    memorandum say otherwise, because it reads from the same variables."""
    open_a = open_recommendations(m, "A")
    rec6_open = any(r["no"] == 6 and r["status"] == "Open"
                    for r in m["recommendations"])
    minors = " and ".join(n.title() for n, _ in m["minors"])
    vet_expiry = m["survey_date"] + _dt.timedelta(days=90)
    return [
        {"no": 1, "text": "No admission of the public and no sale of any "
                          "admission prior to re-survey and Underwriters' "
                          "written agreement.",
         "evidence": f"Board resolution {m['resolution_no']}, resolution 5",
         "status": "Satisfied"},
        {"no": 2, "text": "No person under the age of majority upon the "
                          "island.",
         "evidence": f"Board resolution {m['resolution_no']}, resolution 6 "
                     f"permits {minors}",
         "status": "NOT SATISFIED"},
        {"no": 3, "text": "Recommendations rated A closed and closure "
                          "certified in writing by Holbeach Risk "
                          "Engineering.",
         "evidence": ("Management advice only; recommendations "
                      + _serial([r["no"] for r in open_a]) + " open"
                      if open_a else
                      "Surveyor's certificate of closure supplied"),
         "status": "NOT SATISFIED" if open_a else "Satisfied"},
        {"no": 4, "text": "Current veterinary certificate of containment "
                          "adequacy.",
         "evidence": f"Harding certificate of {_fmt_uk(m['survey_date'])}; "
                     f"expressly limited to recorded body masses",
         "status": f"Satisfied to {_fmt_uk(vet_expiry)}"},
        {"no": 5, "text": "Opinion of local counsel upon the Assured's "
                          "obligations under the concession.",
         "evidence": "Outstanding; counsel's memorandum records separate "
                     "advice not yet received",
         "status": "NOT SATISFIED"},
        {"no": 6, "text": "Specimen census verified by individual "
                          "identification.",
         "evidence": "Reconciliation by count against expected population "
                     "only (survey recommendation 6)",
         "status": "NOT SATISFIED" if rec6_open else "Satisfied"},
        {"no": 7, "text": "Control room manned by not fewer than two "
                          "persons at all times.",
         "evidence": "Survey records ordinary operation by one person",
         "status": "NOT SATISFIED"},
    ]


def open_recommendations(m: dict, priority: str | None = None) -> list[dict]:
    """Which recommendations are open — computed from the register so counsel
    and the board cannot drift from the surveyor."""
    return [r for r in m["recommendations"]
            if r["status"] == "Open" and (priority is None
                                          or r["priority"] == priority)]


def total_specimens(m: dict) -> int:
    return sum(r["count"] for r in m["roster"])


# -- date formatting is per-source texture ----------------------------------

_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def _fmt_us(d: _dt.date) -> str:
    return f"{_MONTHS[d.month - 1]} {d.day}, {d.year}"


def _fmt_uk(d: _dt.date) -> str:
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def _fmt_num(d: _dt.date) -> str:
    return f"{d.day:02d}/{d.month:02d}/{str(d.year)[2:]}"


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------

# Per-source typographic identity. A packet whose tabs share a font reads as
# one author's work — which is exactly what it must not be.
SOURCES = {
    "lawfirm":  {"body": ("Times-Roman", 11), "bold": ("Times-Bold", 11),
                 "lead": 14.6, "head": ("Times-Bold", 11)},
    "insurer":  {"body": ("Helvetica", 9), "bold": ("Helvetica-Bold", 9),
                 "lead": 12.2, "head": ("Helvetica-Bold", 9.5)},
    "vet":      {"body": ("Times-Roman", 11), "bold": ("Times-Bold", 11),
                 "lead": 15.0, "head": ("Times-Bold", 11.5)},
    "operator": {"body": ("Courier", 9.5), "bold": ("Courier-Bold", 9.5),
                 "lead": 12.6, "head": ("Courier-Bold", 9.5)},
    "corp":     {"body": ("Times-Roman", 11.5), "bold": ("Times-Bold", 11.5),
                 "lead": 15.4, "head": ("Times-Bold", 12)},
    "fineprint": {"body": ("Times-Roman", 8.2), "bold": ("Times-Bold", 8.2),
                  "lead": 10.0, "head": ("Times-Bold", 9)},
    "broker":   {"body": ("Helvetica", 9.8), "bold": ("Helvetica-Bold", 9.8),
                 "lead": 13.2, "head": ("Helvetica-Bold", 10.2)},
    "slip":     {"body": ("Courier", 9.0), "bold": ("Courier-Bold", 9.0),
                 "lead": 11.8, "head": ("Courier-Bold", 9.5)},
}


class _C:
    """Line accumulator. Emits style-tagged lines; the renderer paginates."""

    def __init__(self):
        self.lines: list[dict] = []
        self.src = "corp"

    def source(self, name):
        self.src = name
        return self

    @property
    def _s(self):
        return SOURCES[self.src]

    def raw(self, **kw):
        if kw.get("lead") is None:
            kw["lead"] = self._s["lead"]
        self.lines.append(kw)

    def t(self, text="", *, bold=False, align="l", indent=0.0, font=None,
          lead=None):
        self.raw(t=text, font=font or (self._s["bold"] if bold
                                       else self._s["body"]),
                 align=align, indent=indent, lead=lead)

    def head(self, text, *, align="l"):
        self.space(6)
        self.raw(t=text, font=self._s["head"], align=align, indent=0.0)
        self.space(3)

    def para(self, text, *, indent=0.0, first=0.0, bold=False, lead=None,
             align="l", after=5.0):
        font = self._s["bold"] if bold else self._s["body"]
        for i, ln in enumerate(_wrap(text, font, USABLE - indent - first)):
            self.raw(t=ln, font=font, align=align,
                     indent=indent + (first if i == 0 else 0), lead=lead)
        if after:
            self.space(after)

    def numbered(self, n, text, *, width=26.0, after=6.0):
        """Hanging-indent numbered paragraph — the shape legal prose has."""
        font = self._s["body"]
        for i, ln in enumerate(_wrap(text, font, USABLE - width)):
            if i == 0:
                self.raw(t=n, font=font, indent=0.0, hang=(width, ln))
            else:
                self.raw(t=ln, font=font, indent=width)
        if after:
            self.space(after)

    def space(self, pts=8.0):
        self.raw(space=pts)

    def rule(self, *, width=0.8, x1=LEFT, x2=RIGHT, pad=5.0):
        self.raw(rule=(x1, x2, width), lead=pad)

    def newpage(self):
        self.raw(newpage=True)

    def sig(self, key, name, *, w=150.0, h=42.0):
        self.raw(sig=(key, name), lead=h)

    def row(self, cells, widths, *, bold=False, font=None, lead=None,
            aligns=None):
        self.raw(row=cells, widths=widths, aligns=aligns,
                 font=font or (self._s["bold"] if bold else self._s["body"]),
                 lead=lead)

    def stamp(self, lines):
        self.raw(stamp=lines)


def _wrap(text: str, font, width: float) -> list[str]:
    name, size = font
    out, line = [], ""
    for word in text.split():
        cand = (line + " " + word) if line else word
        if pdfmetrics.stringWidth(cand, name, size) > width and line:
            out.append(line)
            line = word
        else:
            line = cand
    if line:
        out.append(line)
    return out or [""]


def _letterhead(c: _C, *, name, addr, right=None, rule=True, sub=None):
    c.t(name, bold=True, align="c")
    if sub:
        c.t(sub, align="c", font=(c._s["body"][0], c._s["body"][1] - 0.5))
    for ln in addr:
        c.t(ln, align="c", font=(c._s["body"][0], c._s["body"][1] - 1))
    if right:
        for ln in right:
            c.t(ln, align="r", font=(c._s["body"][0], c._s["body"][1] - 1))
    if rule:
        c.rule()
    c.space(6)


# -- the instruments ---------------------------------------------------------

def _tab_memorandum(c: _C, m: dict, cov: dict) -> None:
    c.source("lawfirm")
    _letterhead(c, name=m["counsel_firm"],
                addr=["ATTORNEYS AT LAW",
                      f"One Market Plaza, {m['counsel_city']} 94105"])
    c.t("PRIVILEGED AND CONFIDENTIAL", bold=True, align="c")
    c.t("ATTORNEY WORK PRODUCT — PREPARED IN ANTICIPATION OF LITIGATION",
        align="c", font=("Times-Roman", 9.5))
    c.space(10)
    for label, value in (
            ("TO:", "The Board of Directors, "
                    "International Genetic Technologies, Inc."),
            ("FROM:", f"{m['counsel_name'].title()}"),
            ("DATE:", _fmt_us(m["memo_date"])),
            ("RE:", f"{m['island']} — regulatory characterisation, liability "
                    f"exposure, and conditions to limited operations")):
        c.raw(t=label, font=("Times-Bold", 11), indent=0.0,
              hang=(62.0, value))
    c.rule()
    c.space(4)

    c.head("I.  QUESTION PRESENTED")
    c.para("Whether the Company may permit a limited inspection of the "
           f"{m['island']} facility by named outside experts, prior to any "
           "public opening, without incurring exposure materially greater "
           "than that already assumed; and upon what conditions.")
    c.head("II.  SHORT ANSWER")
    c.para("Yes, upon the conditions stated in Part VII. The exposure "
           "presented by a limited inspection under written release is of a "
           "different order from that presented by public admission, "
           "principally because the invitee class is small, individually "
           "identified, professionally sophisticated, and capable of giving "
           "an informed release. That conclusion does not extend to public "
           "opening, upon which we express no view, and it is subject "
           "throughout to the limitations in Part VIII, which are not "
           "formal.")

    c.head("III.  FACTS AND POSTURE")
    c.para(f"On {_fmt_us(m['incident_date'])} an employee of the Company's "
           f"animal handling section sustained fatal injuries during a "
           f"transfer operation at {m['incident']['location']}. The matter "
           f"is the subject of the Company's internal report "
           f"{m['incident']['report_no']} (Tab 4). Following notification, "
           f"underwriters instructed a survey of the facility, carried out "
           f"on {_fmt_us(m['survey_date'])} (Tab 2). Cover remains in force, "
           f"but is now written subject to warranty of compliance with the "
           f"surveyor's A-rated recommendations, and the exposure arising "
           f"from Class IV specimens is sub-limited to "
           f"${cov['class_iv_sublimit_mm']:.2f} million, being a fraction of "
           f"the each-occurrence limit.")
    c.para("Underwriters have further required, as a condition of continued "
           "cover on present terms, that the containment and operating "
           "systems be reviewed by independent persons of standing who are "
           "not employees of the Company, and that the review be documented. "
           "The inspection proposed is the Company's response to that "
           "requirement. It is important that the Board appreciate the "
           "inspection is not a marketing exercise: it exists because "
           "underwriters asked for it, and its written product will be "
           "disclosable.")

    c.head("IV.  REGULATORY CHARACTERISATION")
    c.para("A.  No existing wildlife category governs the specimens.",
           bold=True)
    c.para("The Convention on International Trade in Endangered Species "
           "regulates trade in listed taxa. The specimens are not listed, "
           "and could not be: the Convention's appendices enumerate species "
           "presently existing in the wild, and the specimens are neither "
           "presently existing in the wild nor, in the ordinary sense, "
           "members of an enumerated taxon. The same difficulty attends the "
           "Endangered Species Act.")
    c.para(f"Costa Rican law is to like effect. La Ley de Conservación de la "
           f"Vida Silvestre, No. 7317, regulates the wild fauna of the "
           f"Republic — fauna silvestre — and the licensing of those who "
           f"take, hold or exhibit it. The specimens were not taken from the "
           f"wild of the Republic or of anywhere else. We have taken the "
           f"view, and have so advised {m['ministry']}, that the specimens "
           f"fall to be treated as biological material produced in a "
           f"laboratory rather than as fauna silvestre, and the Ministry has "
           f"not to date asserted a contrary position. We emphasise that "
           f"the Ministry's silence is not an approval and should not be "
           f"described as one in any document circulated to investors.")
    c.para("The Animal Welfare Act, 7 U.S.C. §2131 et seq., and the "
           "licensing regime administered thereunder, do not reach a "
           "facility situated outside the United States and not exhibiting "
           "within it.")
    c.para("B.  The facility is not a public accommodation.", bold=True)
    c.para(f"The facility is operated as a private biological research "
           f"station upon land held under concession No. "
           f"{m['concession_no']} from the Republic. No person is admitted "
           f"otherwise than as an invitee of the Company under written "
           f"terms. This characterisation is the foundation of the release "
           f"at Tab 6 and of much of the analysis in Part VI; it will not "
           f"survive public admission on sold tickets, and the Board should "
           f"understand that the opening of the facility to the public "
           f"changes the legal position more fundamentally than it changes "
           f"the operational one.")
    c.para("C.  The regime now forming.", bold=True)
    c.para("The Convention on Biological Diversity was opened for signature "
           "at Rio de Janeiro in June 1992 and has been signed by the "
           "Republic. It is not in force, and the Republic has not "
           "ratified. When it is and has, the Convention's provisions "
           "respecting access to genetic resources and the sovereign rights "
           "of States over them will require the Company's arrangements to "
           "be revisited, and we think it likely that the Republic will "
           "assert an interest in material derived from within its "
           "territory. Nothing in this memorandum should be read as advice "
           "to accelerate any decision in order to precede that regime; we "
           "note only that the present position is unlikely to be "
           "permanent.")

    c.head("V.  INSURANCE POSITION")
    c.para(f"The programme is placed through the Company's brokers, "
           f"{m['broker'].title()}, under policy {m['policy_no']}, and is "
           f"subscribed by a market of which "
           f"{m['carrier'].title()} is the leading underwriter. It is "
           f"written in sections; the liability section carries limits of "
           f"${cov['each_occurrence_mm']:.2f} million each occurrence and "
           f"${cov['aggregate_mm']:.2f} million in the aggregate, subject to "
           f"a retention of ${cov['retention_usd']:,} each and every loss. "
           f"Two sub-limits materially qualify that cover: "
           f"${cov['animal_sublimit_mm']:.2f} million in respect of bodily "
           f"injury arising from contact with or escape of any specimen, and "
           f"${cov['class_iv_sublimit_mm']:.2f} million in respect of Class "
           f"IV specimens. The Board should read those figures as the "
           f"underwriters' view of the risk rather than as a limitation of "
           f"it: the exposure above the sub-limit has not been transferred "
           f"and rests with the Company.")
    _open_a = open_recommendations(m, "A")
    c.para("Cover is further warranted upon compliance with the surveyor's "
           "A-rated recommendations within ninety days of survey. "
           + (f"Recommendation{'s' if len(_open_a) != 1 else ''} "
              f"{_serial([r['no'] for r in _open_a])} "
              f"{'remain' if len(_open_a) != 1 else 'remains'} open at the "
              f"date of this memorandum. "
              if _open_a else "No A-rated recommendation is open at the date "
                              "of this memorandum. ")
           + "The effect of a breach of warranty under the law governing "
             "the policy is not to pause the cover but to discharge "
             "underwriters from liability from the date of the breach, in "
             "respect of the very exposures the sub-limits address; cover "
             "once lost in that manner is restored only by endorsement, at "
             "underwriters' option and price. We regard closure of those "
             "items as the single most valuable step available to the "
             "Company, and more valuable than the inspection.")

    c.head("VI.  EXPOSURE ANALYSIS")
    c.para("The distinction between the proposed inspection and public "
           "opening is not one of degree. Four differences are material.")
    for n, text in enumerate([
        "The invitee class is closed, named in advance, and small. Each "
        "invitee can be given the specific disclosure at Tab 6 and can be "
        "shown to have received it. A ticketed member of the public cannot, "
        "and a release printed upon a ticket is worth very little in any "
        "jurisdiction we have considered.",
        "The invitees are professionally sophisticated in the relevant "
        "sense. Two are natural scientists and one a mathematician retained "
        "for his views on the stability of complex systems. A release given "
        "by such a person, having been shown the paddocks, is materially "
        "stronger than one given by a visitor who has been shown a film.",
        "The duration is short and the movements are supervised and "
        "recorded, which bears directly upon the foreseeability of any "
        "particular injury and upon the Company's ability to demonstrate "
        "what was and was not represented.",
        "No consideration passes for admission. The invitees are not "
        "purchasers, and the implied terms that attend a contract for "
        "admission to a place of entertainment do not arise.",
    ], start=1):
        c.numbered(f"{n}.", text)
    c.para("Against those matters must be set the following. The exposure "
           "is not capped by the release. A release is a defence, not a bar; "
           "it will not exclude a claim founded upon gross negligence or "
           "upon the concealment of a known defect, and the open A-rated "
           "recommendations at Tab 2 are, in our view, the most likely "
           "foundation for a plea of that kind. A plaintiff who obtains the "
           "surveyor's report in discovery will read recommendations "
           + _serial([r["no"] for r in _open_a]) +
           " as notice, and the Company's answer must be that they were "
           "closed, not that they were understood.")

    c.head("VII.  CONDITIONS TO PROCEED")
    for n, text in enumerate([
        "That every person set foot upon the island only after execution of "
        "the acknowledgement and release at Tab 6, in the presence of a "
        "witness, and that no release be executed on the island.",
        "That the A-rated recommendations at Tab 2 be closed, and closure "
        "certified by the surveyor, before any inspection party arrives; "
        "alternatively, that the inspection be confined to those areas "
        "unaffected by the open items.",
        "That the Board authorise the inspection only, and that the "
        "authorisation state on its face that it is not an authorisation to "
        "open the facility to the public.",
        "That no person under the age of majority be present upon the "
        "island during the inspection.",
        "That the veterinary certification at Tab 3 be re-executed within "
        "seven days of the arrival of the inspection party, the present "
        "certificate being expressly limited to the body masses recorded "
        "when it was given.",
        "That a written record be kept of every representation made to the "
        "invitees as to the safety of any enclosure, and that no such "
        "representation be made otherwise than by a person authorised in "
        "writing.",
    ], start=1):
        c.numbered(f"{n}.", text)

    c.head("VIII.  RESERVATIONS AND LIMITATIONS")
    c.para("This memorandum is subject to the following, which we ask the "
           "Board to read with the same attention as the conclusion.")
    minor_names = ", ".join(n.title() for n, _ in m["minors"])
    for n, text in enumerate([
        "We express no opinion upon the adequacy of any containment system. "
        "We are lawyers. We have not inspected the barriers, we are not "
        "competent to evaluate them, and nothing in Part VI should be read "
        "as suggesting that we regard them as sufficient. Our analysis "
        "assumes containment performs as the surveyor and the veterinary "
        "officer describe, and no further.",
        "We express no opinion upon the sufficiency of the corrective "
        "measures recorded in report " + m["incident"]["report_no"] +
        ", nor upon whether the cause identified in that report is the whole "
        "of the cause.",
        "We have advised, and repeat, that a pre-injury release executed by "
        "a parent or guardian on behalf of a minor is unenforceable in the "
        "majority of United States jurisdictions which have considered it, "
        "and that its enforceability under the law of the Republic is "
        "untested. A release executed on behalf of " + minor_names +
        " should be assumed to be of no effect. Condition 4 of Part VII "
        "follows from this and is not a matter upon which we are able to be "
        "flexible. We are instructed that the Chairman intends otherwise.",
        "We have not advised upon, and express no view respecting, the "
        "Company's obligations to the Republic under the concession, which "
        "are the subject of separate advice from local counsel not yet "
        "received.",
        "This memorandum is given to the Board in confidence for the purpose "
        "of its deliberations upon the inspection. It is not to be "
        "circulated to prospective investors, to underwriters, or to any "
        "person outside the Company, and it may not be relied upon by any "
        "such person. It states our advice as at its date upon the facts "
        "reported to us by the Company, which we have not verified.",
    ], start=1):
        c.numbered(f"{n}.", text)
    c.space(14)
    c.t("Respectfully submitted,")
    c.space(4)
    c.sig("gennaro", "Donald Gennaro")
    c.t(m["counsel_name"].title())
    c.t(f"For and on behalf of {m['counsel_firm'].title()}")


def _tab_survey(c: _C, m: dict, cov: dict) -> None:
    c.source("insurer")
    _letterhead(c, name=m["surveyor_firm"],
                addr=["Consulting Engineers to the Insurance Market",
                      "Billiter Street, London EC3M 2RY"],
                sub="INCORPORATING THE SPECIAL RISKS PRACTICE")
    c.t("SURVEY REPORT — SPECIAL RISKS", bold=True, align="c")
    c.space(8)
    w = [122.0, 346.0]
    for k, v in (("Report reference", f"HRE/{m['policy_no'].split('/')[-1]}/SR"),
                 ("Prepared for", f"{m['carrier'].title()}, "
                                  f"{', '.join(m['carrier_addr'])}"),
                 ("Policy", m["policy_no"]),
                 ("Insured", f"{m['company'].title()}"),
                 ("Risk situated", f"{m['island']}, Republic of Costa Rica"),
                 ("Date of survey", _fmt_uk(m["survey_date"])),
                 ("Surveyor", m["surveyor"].title()),
                 ("Occupancy", "Private biological research station; "
                               "captive specimen holding")):
        c.row([k, v], w, aligns=["l", "l"])
    c.rule()

    c.head("1.  SCOPE AND BASIS OF SURVEY")
    c.para("This survey was instructed by underwriters following "
           f"notification of a fatal accident at the risk on "
           f"{_fmt_uk(m['incident_date'])}. The writer attended the risk on "
           f"{_fmt_uk(m['survey_date'])} and was accompanied throughout by "
           f"the game warden and the chief engineer. The survey is a survey "
           f"of the risk as presented for insurance. It is not a "
           f"certification of safety, and it is not addressed to the "
           f"insured. Recommendations are made for underwriting purposes.")
    c.para("The writer was not permitted access to the interior of the "
           "Class IV holding areas and did not enter them. Observations "
           "respecting those areas were made from service walkways and from "
           "the control room, and, as respects specimen condition, are "
           "founded upon the veterinary officer's records rather than upon "
           "the writer's own examination.")

    c.head("2.  RISK DESCRIPTION")
    c.para(f"The risk comprises {m['island_desc']}, developed as a research "
           f"station with visitor accommodation, a laboratory and hatchery "
           f"building, a central control facility, a power plant with "
           f"standby generation, a service harbour and a helipad. Specimen "
           f"holding is distributed among enclosed paddocks connected by a "
           f"service road. Barriers are of three kinds: electrified fencing "
           f"energised from the main plant, dry moats, and concrete-walled "
           f"holding pens for transfer and veterinary work.")
    c.para(f"Total specimen population at the date of survey was "
           f"{total_specimens(m)}, held as scheduled at section 3. The "
           f"population is stated by the insured. The writer's observations "
           f"respecting the method by which it is verified are at "
           f"recommendation 6.")

    c.head("3.  SCHEDULE OF SPECIMENS")
    sw = [150.0, 40.0, 74.0, 44.0, 56.0, 104.0]
    c.row(["Species", "No.", "Adult mass", "Class", "Paddock", "Barrier"],
          sw, bold=True)
    c.rule(width=0.5, pad=3.0)
    for r in m["roster"]:
        barrier = ("Electrified fence + moat" if r["class"] in ("IV", "III")
                   else "Electrified fence" if r["class"] == "II"
                   else "Fence")
        c.row([r["species"], str(r["count"]), f"{r['adult_mass_kg']:,} kg",
               r["class"], r["paddock"], barrier], sw,
              aligns=["l", "r", "r", "c", "l", "l"])
    c.rule(width=0.5, pad=3.0)
    c.row(["Total specimens", str(total_specimens(m)), "", "", "", ""], sw,
          bold=True, aligns=["l", "r", "r", "c", "l", "l"])
    c.space(6)
    c.para("Classification is that of the insured's own standing "
           "instruction, which grades by mass and by behaviour. The writer "
           "draws underwriters' attention to the classification of "
           "Velociraptor, which at a recorded adult mass of "
           f"{[r for r in m['roster'] if r['species'] == 'Velociraptor'][0]['adult_mass_kg']} "
           "kg is graded Class IV upon the behavioural limb alone. The "
           "writer considers that grading correct and, if anything, "
           "conservative in the wrong direction: the animals are "
           "co-ordinated, they test the barriers systematically and at "
           "different points, and the handlers' accounts of this are "
           "consistent with one another and with the writer's own "
           "observation.")

    c.head("4.  PROTECTION AND UTILITIES")
    c.para("Barrier energisation, paddock gates, service doors, the "
           "telephone system, closed-circuit television and the perimeter "
           "alarms are all functions of a single integrated supervisory "
           "control system operated from the central control facility. The "
           "writer was informed that the system is ordinarily operated by "
           "one person. There is no manual means of energising or isolating "
           "a barrier at the barrier itself; all such operations are "
           "performed from the control room. This is the most significant "
           "single feature of the risk and is the subject of recommendation "
           "1.")
    c.para("Standby generation is provided and is adequate in capacity. It "
           "is not, however, arranged to restore barrier circuits "
           "independently: upon loss of the main plant the barrier circuits "
           "are dead until the main plant is restarted, restart being a "
           "manual operation performed from the plant room. No "
           "uninterruptible supply serves the barrier circuits. See "
           "recommendation 3.")

    c.head("5.  LOSS EXPERIENCE")
    inc = m["incident"]
    c.para(f"One fatality, {_fmt_uk(m['incident_date'])}, during transfer of "
           f"a Class IV specimen from a transport unit to the holding pen at "
           f"{inc['location']}. The insured's report is numbered "
           f"{inc['report_no']}. The writer has read the report and "
           f"discussed it with the game warden.")
    c.para(f"The immediate cause is recorded as the release of the "
           f"transport unit gate while a handler remained within the "
           f"transfer race. The insured's standing instruction requires "
           f"{inc['handlers_required']} handlers upon any Class IV transfer; "
           f"{inc['handlers_present']} were present. The writer accepts that "
           f"the corrective action taken meets the immediate cause. The "
           f"writer does not accept that the immediate cause is the whole of "
           f"the cause: a procedure whose observance depends upon the "
           f"judgement of the men performing it, at night, at the end of a "
           f"shift, is a procedure which will be departed from again, and "
           f"the engineering answer — an interlock preventing release of the "
           f"gate while the race is occupied — has not been provided.")

    c.head("6.  RECOMMENDATIONS")
    c.para("Recommendations rated A are the subject of warranty. Compliance "
           "is required within ninety days of the date of survey.")
    c.space(4)
    rw = [26.0, 34.0, 262.0, 46.0, 100.0]
    c.row(["No.", "Rating", "Recommendation", "Status", "Target"], rw,
          bold=True)
    c.rule(width=0.5, pad=3.0)
    for r in m["recommendations"]:
        body = _wrap(r["text"], c._s["body"], rw[2] - 6)
        for i, ln in enumerate(body):
            c.row([str(r["no"]) if i == 0 else "",
                   r["priority"] if i == 0 else "",
                   ln,
                   r["status"] if i == 0 else "",
                   r["due"] if i == 0 else ""], rw,
                  aligns=["c", "c", "l", "l", "l"])
        c.space(3)
    c.rule(width=0.5, pad=3.0)
    n_open_a = len(open_recommendations(m, "A"))
    c.para(f"A-rated recommendations outstanding at the date of this report: "
           f"{n_open_a} of "
           f"{len([r for r in m['recommendations'] if r['priority'] == 'A'])}.",
           bold=True)

    c.head("7.  SCHEDULE OF COVER AS RATED — LIABILITY SECTION")
    lw = [352.0, 116.0]
    for label, val in cov["layers"]:
        body = _wrap(label, c._s["body"], lw[0] - 6)
        for i, ln in enumerate(body):
            c.row([ln, f"USD {val:,.2f} m" if i == len(body) - 1 else ""],
                  lw, aligns=["l", "r"])
    c.rule(width=0.5, pad=3.0)
    c.row(["Retention each and every loss",
           f"USD {cov['retention_usd']:,}"], lw, aligns=["l", "r"])
    c.row(["Declared values — conventional property (per statement of "
           "values)", f"USD {cov['conventional_mm']:,.1f} m"], lw,
          aligns=["l", "r"])
    c.row(["Declared values — specimens at agreed values",
           f"USD {cov['specimen_mm']:,.1f} m"], lw, aligns=["l", "r"])
    c.row(["Total declared values", f"USD {cov['declared_mm']:,.1f} m"], lw,
          bold=True, aligns=["l", "r"])
    c.space(6)
    c.para(f"The programme is written in sections and each section is rated "
           f"upon its own base; the premium in sections is stated upon the "
           f"slip. The writer's rating basis for Section I is "
           f"{m['rate_per_mille']:.2f} per mille upon conventional declared "
           f"values of USD {cov['conventional_mm']:,.1f} million, producing "
           f"USD {cov['premium']:,.2f}. Specimen values are agreed values "
           f"for settlement purposes and are rated separately; they are "
           f"neither production cost nor expected revenue, and no value is "
           f"declared in respect of the genetic library, which is not "
           f"insured under this programme.")

    c.head("8.  ESTIMATED MAXIMUM LOSS")
    c.para("Estimates below are for the conventional property account and "
           "are stated against the declared conventional values. They "
           "assume the barriers hold. That assumption is examined, and not "
           "endorsed, at section 4.")
    ew = [286.0, 92.0, 90.0]
    c.row(["Scenario", "Property PML", "Basis"], ew, bold=True)
    c.rule(width=0.5, pad=3.0)
    for label, val, basis in (
            ("Failure of the integrated supervisory control system with "
             "consequential damage during recapture or destruction of "
             "specimens", cov["pml_control_mm"],
             f"{m['pml_control_pct'] * 100:.1f}% of values"),
            ("Fire at the main power plant extending to the control "
             "facility and laboratory, with loss of laboratory "
             "refrigeration", cov["pml_fire_mm"], "Summed values at risk"),
            ("Severe tropical storm; marine access unavailable; extended "
             "isolation of the risk", cov["pml_storm_mm"],
             f"{m['pml_storm_pct'] * 100:.1f}% of values")):
        body = _wrap(label, c._s["body"], ew[0] - 6)
        for i, ln in enumerate(body):
            c.row([ln, f"USD {val:,.1f} m" if i == 0 else "",
                   basis if i == 0 else ""], ew, aligns=["l", "r", "l"])
        c.space(3)
    c.rule(width=0.5, pad=3.0)
    c.para(f"Maximum foreseeable loss, conventional property: total loss of "
           f"the declared conventional values, USD "
           f"{cov['conventional_mm']:,.1f} million. The liability account "
           f"is not susceptible of the same treatment: the writer records, "
           f"and asks underwriters to note, that the liability maximum "
           f"foreseeable loss is not capable of dependable numerical "
           f"estimation, because the population exposed following an escape "
           f"is not bounded by the insured premises.")

    c.space(4)
    c.para("WARRANTY. It is warranted that the recommendations rated A "
           "herein shall be complied with within ninety days of the date of "
           "survey and that compliance shall be certified in writing by "
           "Holbeach Risk Engineering. In the event of breach, underwriters "
           "are discharged from liability in respect of loss arising on or "
           "after the date of breach under the liability and specimen "
           "sections, without prejudice to liability for loss arising "
           "before that date. Reinstatement of cover following breach is by "
           "written endorsement only.", bold=True)
    c.para("The writer is not instructed to advise whether the risk should "
           "be written and does not do so. The writer observes only that "
           "the sub-limits at which underwriters have written it are, in the "
           "writer's opinion, the correct order for a risk of this kind "
           "where the liability exposure resists estimation.")
    c.space(10)
    c.sig("fenwick", "A J Fenwick")
    c.t(m["surveyor"].title())
    c.t(f"for {m['surveyor_firm'].title()}")
    c.t(_fmt_uk(m["survey_date"] + _dt.timedelta(days=3)))


def _tab_vet(c: _C, m: dict, cov: dict) -> None:
    c.source("vet")
    _letterhead(c, name="OFFICE OF THE PARK VETERINARY OFFICER",
                addr=[f"{m['park']} — {m['island']}",
                      "Republic of Costa Rica"])
    c.t("CERTIFICATE OF CONTAINMENT ADEQUACY", bold=True, align="c")
    c.t("(Specimens in captivity — periodic certification)", align="c",
        font=("Times-Italic", 10))
    c.space(12)
    exam_start = m["survey_date"] - _dt.timedelta(days=4)
    c.para(f"I, {m['vet'].title()}, {m['vet_title']}, having conducted "
           f"examinations and observations at the paddocks and holding "
           f"facilities of {m['park']} on the days "
           f"{_fmt_us(exam_start)} through {_fmt_us(m['survey_date'])}, "
           f"CERTIFY as follows.")
    c.space(4)
    c.numbered("1.", "That the specimens scheduled below are, as presently "
                     "housed and at the body masses recorded below, "
                     "contained by barriers adequate to prevent their "
                     "egress from the enclosures in which they are held.")
    c.numbered("2.", "That the specimens are in a condition of health "
                     "consistent with continued captivity and exhibit no "
                     "sign of disease requiring isolation.")
    c.numbered("3.", "That the enclosures provide the space, shelter, water "
                     "and substrate appropriate to each species so far as "
                     "these are presently understood.")
    c.space(6)
    sw = [176.0, 42.0, 84.0, 50.0, 116.0]
    c.row(["Species", "No.", "Mass at exam.", "Class", "Basis of examination"],
          sw, bold=True)
    c.rule(width=0.5, pad=3.0)
    for r in m["roster"]:
        basis = ("Observed from service walkway" if r["class"] == "IV"
                 else "Direct examination" if r["class"] in ("I", "II")
                 else "Direct examination under sedation")
        c.row([r["species"], str(r["count"]), f"{r['adult_mass_kg']:,} kg",
               r["class"], basis], sw,
              aligns=["l", "r", "r", "c", "l"])
    c.rule(width=0.5, pad=3.0)
    c.row(["Total", str(total_specimens(m)), "", "", ""], sw, bold=True,
          aligns=["l", "r", "r", "c", "l"])

    c.head("LIMITATIONS UPON THIS CERTIFICATE")
    c.para("This certificate is given subject to the following limitations, "
           "which are part of it and are not to be separated from it.")
    class_iv = [r["species"] for r in m["roster"] if r["class"] == "IV"]
    c.numbered("(a)", "It speaks as at the dates of examination and to the "
                      "body masses there recorded. The specimens are "
                      "immature and continue to gain mass. A barrier "
                      "adequate to an animal of a given mass is not thereby "
                      "adequate to the same animal six months later, and "
                      "this certificate should not be relied upon beyond "
                      "ninety days from its date.")
    c.numbered("(b)", "The Class IV specimens — " + _serial(class_iv) +
                      " — were not examined at close quarters. Safe "
                      "approach to these animals is not presently possible "
                      "with the facilities available to me. My observations "
                      "of their condition were made from the service "
                      "walkway and from photographic record, and my "
                      "statements as to their mass are estimates derived "
                      "from feed conversion and from photogrammetry, not "
                      "from weighing.")
    c.numbered("(c)", "I certify the adequacy of barriers to contain the "
                      "specimens. I do not certify, and am not competent to "
                      "certify, the adequacy of the systems by which those "
                      "barriers are energised, monitored or controlled, "
                      "which are matters of engineering.")
    c.numbered("(d)", "I am informed that reliance is placed in part upon a "
                      "nutritional dependency engineered into the specimens "
                      "as a measure of biological containment. I have not "
                      "been provided with data sufficient to evaluate that "
                      "measure and I have not taken it into account in "
                      "giving this certificate. Nothing herein should be "
                      "read as my endorsement of it.")
    c.numbered("(e)", "I hold no view upon whether the facility should "
                      "receive visitors. I have not been asked for one.")
    c.space(14)
    c.t(f"Given at {m['island']} this "
        f"{_ordinal(m['survey_date'].day)} day of "
        f"{_MONTHS[m['survey_date'].month - 1]}, {m['survey_date'].year}.")
    c.space(6)
    c.sig("harding", "Gerald R Harding")
    c.t(m["vet"].title())
    c.t(m["vet_title"])


def _tab_incident(c: _C, m: dict, cov: dict) -> None:
    inc = m["incident"]
    c.source("operator")
    _letterhead(c, name=m["company"],
                addr=[f"{m['island'].upper()} SITE — SAFETY OFFICE"],
                sub="REPORT OF SERIOUS INJURY OR DEATH")
    fw = [148.0, 320.0]
    for k, v in (("REPORT NUMBER", inc["report_no"]),
                 ("DATE OF OCCURRENCE", _fmt_num(m["incident_date"])),
                 ("TIME (24 HR)", inc["time"]),
                 ("LOCATION", inc["location"]),
                 ("CLASSIFICATION", inc["classification"].upper()),
                 ("PERSON INJURED", f"EMPLOYEE NO. "
                                    f"{_stable_hash(inc['report_no']) % 9000 + 1000}"
                                    f" — NAME WITHHELD PENDING NOTIFICATION"),
                 ("POSITION", inc["worker_role"].upper()),
                 ("LENGTH OF SERVICE", f"{inc['service_years']} YEARS"),
                 ("REPORTED BY", f"{m['warden']} — {m['warden_title'].upper()}"),
                 ("DISTRIBUTION", "CHAIRMAN / GENERAL COUNSEL / UNDERWRITERS")):
        c.row([k, v], fw, aligns=["l", "l"])
    c.rule()

    c.head("1.  DESCRIPTION OF OCCURRENCE")
    c.para(f"At approximately {inc['time']} hours on "
           f"{_fmt_num(m['incident_date'])} a transport unit containing one "
           f"Class IV specimen was positioned at the transfer race of the "
           f"{inc['location']} for transfer into the holding pen. The "
           f"transfer party consisted of {inc['handlers_present']} handlers "
           f"and the undersigned. The standing instruction for transfer of "
           f"Class IV specimens requires {inc['handlers_required']} "
           f"handlers.")
    c.para("The transport unit was raised to the race gate and the gate "
           "seal was made. The deceased took position on the unit to "
           "release the gate. The specimen struck the gate from within "
           "before the seal was confirmed. The unit was displaced from the "
           "race and the deceased was drawn against the aperture. The "
           "remaining handlers applied restraint and I discharged a "
           "cartridge into the specimen without effect at that range. The "
           "specimen returned into the unit on its own account after "
           "approximately forty seconds and the gate was closed.")
    c.para("The deceased was recovered and conveyed to the medical station. "
           "Death was pronounced at the station. The specimen was not "
           "destroyed and is presently held in the pen at Paddock 11.")

    c.head("2.  IMMEDIATE CAUSE")
    c.para("Release of the transport unit gate while a person remained upon "
           "the unit and within reach of the aperture, the gate seal not "
           "having been confirmed.")

    c.head("3.  CONTRIBUTING FACTORS")
    for n, t in enumerate([
        f"Transfer undertaken with {inc['handlers_present']} handlers "
        f"against a standing instruction requiring "
        f"{inc['handlers_required']}. The transfer was undertaken at the "
        f"end of a shift and was not deferred.",
        "No mechanical interlock prevents release of the transport gate "
        "while the race is occupied. The sequence depends entirely upon the "
        "observance of the men performing it.",
        "The race is lit by portable lamp. Fixed lighting at the transfer "
        "position has been requisitioned and not supplied.",
        "The specimen had been confined in the transport unit for a period "
        "in excess of that contemplated by the transfer procedure owing to "
        "the late arrival of the vessel.",
    ], start=1):
        c.numbered(f"{n}.", t)

    c.head("4.  CORRECTIVE ACTION")
    aw = [268.0, 108.0, 92.0]
    c.row(["ACTION", "RESPONSIBLE", "STATUS"], aw, bold=True)
    c.rule(width=0.5, pad=3.0)
    actions = [
        ("Standing instruction reissued; three-handler minimum on all Class "
         "IV transfers, no exception, transfer to be deferred if not met",
         m["warden"].split()[-1], "COMPLETE"),
        ("Mechanical interlock at transport gate — design and installation",
         m["engineer"].split()[-1], "REQUISITIONED"),
        ("Fixed lighting at transfer position", m["engineer"].split()[-1],
         "REQUISITIONED"),
        ("Transfer operations prohibited outside daylight hours pending "
         "lighting", m["warden"].split()[-1], "COMPLETE"),
        ("Notification to underwriters", "GENERAL COUNSEL", "COMPLETE"),
    ]
    for act, who, status in actions:
        body = _wrap(act, c._s["body"], aw[0] - 6)
        for i, ln in enumerate(body):
            c.row([ln, who if i == 0 else "", status if i == 0 else ""], aw,
                  aligns=["l", "l", "l"])
        c.space(2)
    c.rule(width=0.5, pad=3.0)
    c.space(8)
    c.para("THE UNDERSIGNED RECORDS THAT HE ADVISED AGAINST THE ACQUISITION "
           "OF FURTHER CLASS IV SPECIMENS ON 3 OCCASIONS PRIOR TO THIS "
           "OCCURRENCE AND REPEATS THAT ADVICE.", bold=True)
    c.space(12)
    c.sig("muldoon", "Robert Muldoon")
    c.t(m["warden"])
    c.t(m["warden_title"].upper())
    c.t(f"DATED {_fmt_num(m['incident_date'] + _dt.timedelta(days=2))}")


def _tab_licence(c: _C, m: dict, cov: dict) -> None:
    c.source("corp")
    c.t("GENETIC MATERIAL OWNERSHIP AND LICENCE AGREEMENT", bold=True,
        align="c")
    c.space(10)
    lic = m["subsidiary"]
    c.para(f"THIS AGREEMENT is made as of {_fmt_us(m['memo_date'])} between "
           f"{m['company'].title()}, a Delaware corporation having its "
           f"principal place of business at {', '.join(m['hq'])} (the "
           f"\"Proprietor\"), and {lic}, a sociedad anónima organised under "
           f"the laws of the Republic of Costa Rica (the \"Operator\").")
    c.head("RECITALS")
    c.para("A.  The Proprietor has developed and holds a library of genetic "
           "material, together with the processes, protocols and data by "
           "which viable organisms are produced from it (together, the "
           "\"Library\").")
    c.para(f"B.  The Operator holds concession No. {m['concession_no']} from "
           f"the Republic in respect of {m['island']} and operates thereon a "
           f"private biological research station.")
    c.para("C.  The Library is the principal asset of the Proprietor. The "
           "specimens are an application of the Library and are not the "
           "Library. The parties intend that the distinction be preserved in "
           "every respect, including upon insolvency, and that no interest "
           "in the Library pass by reason of the possession, exhibition, "
           "injury or death of any specimen.")
    c.head("AGREEMENT")
    for n, text in enumerate([
        "OWNERSHIP. The Library, and all intellectual property in it, "
        "belongs to the Proprietor absolutely. The Operator acquires no "
        "right in the Library other than the licence granted by clause 2, "
        "and acknowledges that its possession of specimens does not confer "
        "and has never conferred any right in the material from which they "
        "were produced.",
        "GRANT. The Proprietor grants the Operator a non-exclusive, "
        "non-transferable, revocable licence to hold, maintain and exhibit "
        "specimens produced from the Library at the concession area, for the "
        "term of the concession, and for no other purpose and at no other "
        "place.",
        "RESTRICTIONS. The Operator shall not, and shall procure that no "
        "person shall: (a) remove viable genetic material from the "
        "concession area; (b) permit any specimen to be transported off the "
        "concession area otherwise than in accordance with the Proprietor's "
        "written protocol; (c) permit any third party to sample, biopsy or "
        "take tissue from any specimen; or (d) breed, or permit the "
        "breeding of, any specimen.",
        "POPULATION CONTROL. The Proprietor represents that the specimens "
        "are produced as a single sex and that reproduction in the "
        "concession area is thereby precluded. The Operator shall "
        "nevertheless maintain a census of the specimen population and "
        "shall report any variance to the Proprietor forthwith.",
        "BIOLOGICAL CONTAINMENT. The Proprietor represents that the "
        "specimens are engineered to lack the capacity to synthesise a "
        "necessary amino acid and are dependent upon supplementation "
        "administered by the Operator. The Operator shall not rely upon this "
        "dependency as a substitute for physical containment, and the "
        "Proprietor gives no warranty that the dependency will operate as a "
        "control upon any specimen at large.",
        "SECURITY. The Proprietor has granted to the collateral agent for "
        "the holders of its senior notes a first-priority security interest "
        "in the Library, perfected by filing. The parties acknowledge that "
        "the value securing the notes is the Library and not the concession, "
        "the station or the specimens, and that the destruction or loss of "
        "every specimen would not impair that security. The Operator shall "
        "do nothing to prejudice the security interest and shall permit the "
        "collateral agent access to the Library upon demand.",
        "CONFIDENTIALITY. The Operator shall keep the Library and all "
        "protocols confidential and shall procure that every person having "
        "access executes an obligation of confidence in the Proprietor's "
        "form. The Operator shall report to the Proprietor forthwith any "
        "approach made to its personnel by any competitor of the Proprietor "
        "in respect of the Library.",
        "TERMINATION. The Proprietor may terminate the licence forthwith "
        "upon any breach of clause 3, upon any variance reported under "
        "clause 4 which is not explained to the Proprietor's satisfaction "
        "within thirty days, or upon the concession ceasing to be held. Upon "
        "termination the Operator shall deliver up all material derived from "
        "the Library and shall dispose of the specimens as the Proprietor "
        "directs.",
        "GOVERNING LAW. This Agreement is governed by the laws of the State "
        "of California, save that clause 2 and the Operator's obligations "
        "under the concession are governed by the laws of the Republic of "
        "Costa Rica.",
    ], start=1):
        c.numbered(f"{n}.", text)
    c.space(12)
    c.t("EXECUTED as of the date first written above.")
    c.space(10)
    lw = [234.0, 234.0]
    c.row(["For the Proprietor:", "For the Operator:"], lw, bold=True)
    c.space(30)
    c.row(["_" * 30, "_" * 30], lw)
    c.row([m["geneticist"].title(), m["chairman"].title()], lw)
    c.row([m["geneticist_title"], m["chairman_title"]], lw)
    c.space(10)
    c.head("SCHEDULE 1 — SPECIMENS PRODUCED FROM THE LIBRARY")
    sw = [232.0, 60.0, 88.0, 88.0]
    c.row(["Species", "No.", "Class", "Paddock"], sw, bold=True)
    c.rule(width=0.5, pad=3.0)
    for r in m["roster"]:
        c.row([r["species"], str(r["count"]), r["class"], r["paddock"]], sw,
              aligns=["l", "r", "c", "l"])
    c.rule(width=0.5, pad=3.0)
    c.row(["Total specimens licensed", str(total_specimens(m)), "", ""], sw,
          bold=True, aligns=["l", "r", "c", "l"])


def _tab_release(c: _C, m: dict, cov: dict) -> None:
    c.source("fineprint")
    c.t("ACKNOWLEDGEMENT OF RISK, ASSUMPTION OF RISK,", bold=True, align="c",
        font=("Times-Bold", 11))
    c.t("WAIVER AND RELEASE OF LIABILITY", bold=True, align="c",
        font=("Times-Bold", 11))
    c.t("INVITEE TO A PRIVATE BIOLOGICAL RESEARCH FACILITY", align="c",
        font=("Times-Roman", 9))
    c.space(8)
    c.para("READ THIS DOCUMENT BEFORE SIGNING IT. IT AFFECTS YOUR LEGAL "
           "RIGHTS AND THE RIGHTS OF YOUR ESTATE AND YOUR FAMILY. IT IS NOT "
           "A FORMALITY. IF YOU DO NOT UNDERSTAND IT, DO NOT SIGN IT UNTIL "
           "YOU HAVE TAKEN YOUR OWN LEGAL ADVICE, WHICH THE COMPANY WILL PAY "
           "FOR IF YOU ASK.", bold=True)
    c.space(4)
    c.head("1.  STATUS OF THE UNDERSIGNED")
    c.para(f"The undersigned is admitted to {m['island']} as an invitee of "
           f"{m['company'].title()} for the purpose of inspecting the "
           f"facility and reporting upon it. The facility is a private "
           f"biological research station. It is not open to the public, no "
           f"admission is sold, and the undersigned is not a customer, "
           f"patron or member of the public. The undersigned pays nothing "
           f"and buys nothing.")
    c.head("2.  THE NATURE OF THE RISK")
    c.para("The undersigned acknowledges having been informed, and "
           "understanding, each of the following.")
    class_iv = [r["species"] for r in m["roster"] if r["class"] == "IV"]
    for lbl, text in [
        ("(a)", "The facility holds living animals of great size and "
                "strength, including animals which are predatory and which "
                "are capable of causing death to a human being rapidly and "
                "without warning."),
        ("(b)", "The animals designated Class IV — " + _serial(class_iv) +
                " — are held behind barriers which the Company believes "
                "adequate but which have not been tested by any authority "
                "independent of the Company, there being no authority which "
                "certifies barriers of this kind."),
        ("(c)", "There is no body of experience concerning these animals. "
                "Their behaviour is not predictable from the behaviour of "
                "any animal presently living. No person, including the "
                "Company, is able to state what they will do."),
        ("(d)", "A person has been killed at the facility by an animal "
                "within the last ninety days. The undersigned has been "
                "offered, and has had the opportunity to read, the "
                "Company's report of that occurrence."),
        ("(e)", "Barriers depend upon electrical power and upon a computer "
                "control system, and the Company's insurance surveyor has "
                "made recommendations concerning both which are not yet "
                "complied with. The undersigned has been offered, and has "
                "had the opportunity to read, the surveyor's "
                "recommendations."),
        ("(f)", "The facility is remote. Evacuation to a hospital depends "
                "upon weather and upon a single vessel and may not be "
                "possible for many hours. There is no surgical facility "
                "upon the island."),
    ]:
        c.numbered(lbl, text, width=22.0)
    c.head("3.  ASSUMPTION OF RISK")
    c.para("Knowing the matters set out in clause 2, the undersigned "
           "voluntarily assumes all risk of bodily injury, death, and loss "
           "of or damage to property arising from presence at the facility, "
           "whether or not caused by the negligence of the Company or of any "
           "of its officers, employees or agents.")
    c.head("4.  RELEASE")
    c.para("The undersigned releases and discharges the Company, its "
           "officers, employees, agents and insurers from all claims, "
           "demands and causes of action arising from bodily injury, death "
           "or property loss sustained at the facility, and covenants not to "
           "sue upon any of them. This release does not extend to injury "
           "caused by the wilful misconduct of the Company, and does not "
           "extend to any matter which cannot lawfully be released.")
    c.head("5.  NO REPRESENTATION OF SAFETY")
    c.para("The Company has made no representation that the facility is "
           "safe. The undersigned has not relied upon any statement of any "
           "person as to the safety of any enclosure, and acknowledges that "
           "no employee of the Company is authorised to make one.")
    c.head("6.  CONFIDENTIALITY")
    c.para("The undersigned shall keep confidential everything observed at "
           "the facility, save that nothing in this clause prevents the "
           "undersigned from stating an opinion to the Company, to its "
           "underwriters, or to any court or authority requiring it. The "
           "undersigned is not asked to withhold an adverse conclusion and "
           "the Company acknowledges that the value of the inspection "
           "depends upon the freedom of the undersigned to reach one.")
    c.head("7.  GOVERNING LAW")
    c.para("This document is governed by the laws of the Republic of Costa "
           "Rica. The undersigned submits to the courts of the Republic. "
           "The undersigned has been advised that the enforceability of a "
           "document of this kind is not certain in every jurisdiction.")
    c.space(10)
    c.t(f"Executed at ______________________ on the ____ day of "
        f"{_MONTHS[m['visit_date'].month - 1]}, {m['visit_date'].year}.")
    c.space(10)
    ew = [178.0, 178.0, 112.0]
    c.row(["SIGNATURE OF INVITEE", "PRINTED NAME AND DISCIPLINE", "WITNESS"],
          ew, bold=True)
    c.space(6)
    for name, discipline, _ in m["experts"]:
        c.row(["_" * 26, name.title(), "_" * 16], ew)
        c.row(["", discipline, ""], ew,
              font=("Times-Italic", 7.6))
        c.space(8)
    c.space(4)
    c.rule(width=0.5)
    c.para("FOR COMPLETION ONLY WHERE THE INVITEE IS UNDER THE AGE OF "
           "MAJORITY. The undersigned parent or guardian executes this "
           "document on behalf of the minor named and on the undersigned's "
           "own behalf. THE COMPANY'S COUNSEL HAS ADVISED THAT THIS BLOCK IS "
           "OF DOUBTFUL EFFECT AND THAT A RELEASE GIVEN ON BEHALF OF A MINOR "
           "MAY BE UNENFORCEABLE. IT IS COMPLETED AT THE DIRECTION OF THE "
           "CHAIRMAN.", bold=True)
    c.space(8)
    for name, age in m["minors"]:
        c.row(["_" * 26, f"{name.title()}, aged {age}", "_" * 16], ew)
        c.space(8)


def _tab_resolution(c: _C, m: dict, cov: dict) -> None:
    c.source("corp")
    c.t(m["company"], bold=True, align="c")
    c.t("(a Delaware corporation)", align="c", font=("Times-Roman", 10))
    c.space(6)
    c.t("RESOLUTION OF THE BOARD OF DIRECTORS", bold=True, align="c")
    c.t(f"No. {m['resolution_no']}", align="c")
    c.space(4)
    c.t(f"Adopted at a special meeting held {_fmt_us(m['board_date'])}",
        align="c", font=("Times-Roman", 10))
    c.rule()
    c.space(6)
    inc = m["incident"]
    open_a = open_recommendations(m, "A")
    c.head("RECITALS")
    for lbl, text in [
        ("WHEREAS,", f"on {_fmt_us(m['incident_date'])} an employee of the "
                     f"Corporation sustained fatal injuries at the "
                     f"{m['island']} facility, the occurrence being the "
                     f"subject of report {inc['report_no']}, which has been "
                     f"circulated to and read by each director;"),
        ("WHEREAS,", f"underwriters instructed a survey of the facility, "
                     f"carried out {_fmt_us(m['survey_date'])}, and have "
                     f"continued cover subject to warranty of compliance "
                     f"with the recommendations therein rated A, of which "
                     f"{_serial([r['no'] for r in open_a]) or 'none'} "
                     f"{'remain' if len(open_a) != 1 else 'remains'} "
                     f"outstanding at the date hereof;"),
        ("WHEREAS,", f"underwriters have required as a condition of "
                     f"continued cover that the containment and operating "
                     f"systems of the facility be reviewed and reported "
                     f"upon by independent persons of standing who are not "
                     f"employees of the Corporation;"),
        ("WHEREAS,", f"the Board has received and considered the "
                     f"memorandum of {m['counsel_firm'].title()} dated "
                     f"{_fmt_us(m['memo_date'])}, together with the "
                     f"conditions and the reservations therein stated;"),
        ("WHEREAS,", "the Board is mindful that the Corporation's "
                     "obligations to the holders of its senior notes are "
                     "secured upon the genetic library and not upon the "
                     "facility, and that the continuation of the facility "
                     "is accordingly a matter of commercial judgement and "
                     "not of necessity;"),
    ]:
        c.para(f"{lbl} {text}")
    c.head("RESOLUTIONS")
    for n, text in enumerate([
        f"That a limited inspection of the {m['island']} facility be and is "
        f"hereby authorised, to commence {_fmt_us(m['visit_date'])} and to "
        f"conclude not later than seventy-two hours thereafter.",
        "That the persons authorised to attend as inspecting experts are: "
        + "; ".join(f"{n.title()} ({d})" for n, d, _ in m["experts"]) +
        "; together with such officers and employees of the Corporation as "
        "the Chairman shall direct, and one representative of the holders "
        "of the senior notes.",
        "That no person be permitted upon the island otherwise than after "
        "execution, off the island and before a witness, of the "
        "acknowledgement and release in the form approved by counsel and "
        "annexed to these resolutions.",
        f"That the officers be and are hereby directed to procure closure "
        f"of the outstanding A-rated recommendations "
        f"({_serial([r['no'] for r in open_a]) or 'none outstanding'}) and "
        f"certification of that closure by the surveyor, and to report "
        f"compliance to this Board before the commencement of the "
        f"inspection.",
        "THAT NOTHING IN THESE RESOLUTIONS AUTHORISES THE OPENING OF THE "
        "FACILITY TO THE PUBLIC, THE SALE OF ANY ADMISSION, OR THE "
        "ANNOUNCEMENT OF ANY OPENING DATE. The decision to open is reserved "
        "to this Board and shall be the subject of a further resolution "
        "taken upon the written report of the inspecting experts and upon "
        "further advice of counsel.",
        f"That the {m['minors_relation']}, namely "
        + " and ".join(f"{n.title()} (aged {a})" for n, a in m["minors"]) +
        ", be permitted to accompany the Chairman for the duration of the "
        "inspection, subject to execution of the release on their behalf "
        "and to their remaining in the company of a designated employee at "
        "all times.",
        "That the Chairman be and is hereby authorised to do all things "
        "necessary to give effect to these resolutions.",
    ], start=1):
        c.numbered(f"{n}.", text)
    c.head("RECORD OF VOTE")
    c.para(f"Resolutions 1 to 5 and 7 were adopted by the unanimous vote of "
           f"the {m['directors_total']} directors present.")
    c.para(f"Resolution 6 was adopted by a vote of {m['directors_total'] - 1} "
           f"to 1, Director {m['dissenting_director']} dissenting. Director "
           f"{m['dissenting_director']} required that the following be "
           f"recorded: that counsel has advised in writing that a release "
           f"executed on behalf of a minor is of doubtful effect and has "
           f"recommended that no person under the age of majority be present "
           f"upon the island; that the Board has resolved contrary to that "
           f"advice; and that the dissenting director wishes that dissent "
           f"noted in respect of that resolution only.")
    c.para("The Chairman stated for the record that he accepted "
           "responsibility for resolution 6 and that the facility had been "
           "built for children.")
    c.space(14)
    c.t("CERTIFICATE OF THE SECRETARY", bold=True)
    c.space(4)
    c.para(f"I certify that I am the duly elected Secretary of "
           f"{m['company'].title()}; that the foregoing is a true and "
           f"correct copy of resolutions duly adopted at a special meeting "
           f"of the Board of Directors held {_fmt_us(m['board_date'])}, at "
           f"which a quorum was present and acting throughout; and that the "
           f"same have not been amended or rescinded and remain in full "
           f"force and effect.")
    c.space(10)
    c.sig("secretary", m["secretary"].title())
    c.t(m["secretary"].title())
    c.t("Secretary")


def _tab_broker(c: _C, m: dict, cov: dict) -> None:
    """Tab 8 — the broker's presentation: first advice of the loss, the
    risk-information schedule, and the statement of values whose total the
    programme is rated against."""
    c.source("broker")
    _letterhead(c, name=m["broker"],
                addr=[m["broker_desc"], ", ".join(m["broker_addr"])])
    c.t("FIRST ADVICE OF MATERIAL ALTERATION AND REQUEST FOR CONTINUATION",
        bold=True, align="c")
    c.space(8)
    w = [116.0, 352.0]
    for k, v in (("To", f"{m['lead_uw'].title()}, Esq., "
                        f"{m['carrier'].title()}, "
                        f"{', '.join(m['carrier_addr'])}"),
                 ("Our reference", m["broker_ref"]),
                 ("Policy", m["policy_no"]),
                 ("Assured", m["company"].title()),
                 ("Date", _fmt_uk(m["advice_date"]))):
        c.row([k, v], w, aligns=["l", "l"])
    c.rule()
    c.para("Dear Sirs,")
    c.para(f"We refer to the above risk and advise underwriters of a "
           f"material alteration following a fatal handling incident at the "
           f"risk on {_fmt_uk(m['incident_date'])}. The Assured's internal "
           f"report is in preparation and will be supplied. We request "
           f"continuation of the existing cover and underwriters' agreement "
           f"to a limited inspection of the risk by named scientific "
           f"advisers, subject to such revised terms and conditions as "
           f"underwriters may require.")
    c.para("It is right that we state the unfavourable matters plainly "
           "rather than leave them to survey. The incident was fatal. The "
           "operator's own standing instruction as to handling strength was "
           "not observed on the night. The specimen population continues to "
           "gain mass against barrier ratings fixed at earlier "
           "examinations. The facility has no operating history as a "
           "visitor attraction and no public admission is proposed to "
           "underwriters at this time.")
    c.para("Against those matters: the risk is an island situated far from "
           "any population, access to it is entirely within the Assured's "
           "control, the invitee population is small and named, capital "
           "investment and protective staffing are substantial, and the "
           "Assured has accepted the principle of independent inspection.")
    c.para("Documents supplied herewith or to follow: the Assured's report "
           "of the incident; the veterinary officer's certificate of "
           "containment adequacy; the statement of values annexed; and the "
           "survey report which underwriters have instructed. Material "
           "information outstanding: the opinion of local counsel upon the "
           "concession, and verification of the specimen census, upon both "
           "of which we will revert.")
    c.para("We should be pleased to attend upon you with the Assured's "
           "risk manager at your convenience.")
    c.space(6)
    c.t("Yours faithfully,")
    c.space(4)
    c.sig("broker", "J G Pike")
    c.t(m["broker_partner"].title())
    c.t(f"for {m['broker'].title()}")

    c.raw(newpage=True)
    _letterhead(c, name=m["broker"],
                addr=[m["broker_desc"], ", ".join(m["broker_addr"])])
    c.t("RISK INFORMATION SCHEDULE", bold=True, align="c")
    c.space(8)
    rw = [176.0, 292.0]
    for k, v in (
            ("Assured", f"{m['company'].title()} and subsidiary "
                        f"{m['subsidiary']}"),
            ("Occupancy", "Private biological research station; captive "
                          "specimen holding; no public admission"),
            ("Situation", f"{m['island']}, {m['island_desc']}"),
            ("Tenure", f"Concession No. {m['concession_no']} from the "
                       f"Republic of Costa Rica"),
            ("Site personnel", f"{m['site_headcount']} persons at the date "
                               f"of this schedule"),
            ("Specimen population", f"{total_specimens(m)}, per the "
                                    f"schedule to the statement of values"),
            ("Loss record", f"One fatality, {_fmt_uk(m['incident_date'])} "
                            f"(animal handling); nil other losses advised"),
            ("Risk management", f"{m['warden'].title()} (game warden); "
                                f"{m['engineer'].title()} (chief engineer); "
                                f"{m['vet'].title()} (veterinary officer)"),
            ("Protections", "Electrified barriers energised from main "
                            "plant; standby generation; central "
                            "supervisory control; perimeter alarms"),
            ("Access", "By sea (service harbour) and by helicopter "
                       "(helipad); no other access")):
        body = _wrap(v, c._s["body"], rw[1] - 6)
        for i, ln in enumerate(body):
            c.row([k if i == 0 else "", ln], rw, aligns=["l", "l"])
        c.space(2)
    c.rule()

    c.t("STATEMENT OF VALUES", bold=True, align="c")
    c.t(f"As at {_fmt_uk(m['slip_date'])} — supplied for underwriting "
        f"purposes", align="c", font=("Helvetica-Oblique", 8.5))
    c.space(8)
    sw = [252.0, 78.0, 138.0]
    c.row(["Item", "Value", "Basis"], sw, bold=True)
    c.rule(width=0.5, pad=3.0)
    for item, value, basis in m["sov_conventional"]:
        body = _wrap(item, c._s["body"], sw[0] - 6)
        for i, ln in enumerate(body):
            c.row([ln, f"USD {value:,.1f} m" if i == 0 else "",
                   basis if i == 0 else ""], sw, aligns=["l", "r", "l"])
    c.row(["Specimens at agreed values (schedule below)",
           f"USD {cov['specimen_mm']:,.1f} m", "Agreed value"], sw,
          aligns=["l", "r", "l"])
    c.rule(width=0.5, pad=3.0)
    c.row(["TOTAL DECLARED VALUES", f"USD {cov['declared_mm']:,.1f} m", ""],
          sw, bold=True, aligns=["l", "r", "l"])
    c.space(8)
    c.t("SCHEDULE OF SPECIMENS AT AGREED VALUES", bold=True)
    c.space(4)
    aw = [176.0, 42.0, 92.0, 76.0, 82.0]
    c.row(["Species", "No.", "Agreed value each", "Class", "Line total"],
          aw, bold=True)
    c.rule(width=0.5, pad=3.0)
    for r in m["roster"]:
        c.row([r["species"], str(r["count"]),
               f"USD {r['agreed_value_mm']:,.1f} m", r["class"],
               f"USD {r['count'] * r['agreed_value_mm']:,.1f} m"], aw,
              aligns=["l", "r", "r", "c", "r"])
    c.rule(width=0.5, pad=3.0)
    c.row(["Total specimens at agreed values", str(total_specimens(m)), "",
           "", f"USD {cov['specimen_mm']:,.1f} m"], aw, bold=True,
          aligns=["l", "r", "r", "c", "r"])
    c.space(6)
    c.para("Notes. Agreed values are for settlement purposes only and are "
           "neither production cost nor anticipated revenue. No value is "
           "declared, and no cover is requested, in respect of the genetic "
           "library or any intellectual property, which are excluded from "
           "the programme in their entirety. Business interruption is "
           "proposed upon standing charges and increased cost of working "
           "only, the facility having no operating revenue history.")


def _tab_slip(c: _C, m: dict, cov: dict) -> None:
    """Tab 9 — the placing slip, revised terms following survey. The
    programme in sections, the subjectivities, and the subscription table:
    written lines oversubscribe; signed lines sign down to exactly 100%."""
    c.source("slip")
    c.t("PLACING SLIP — REVISED TERMS FOLLOWING SURVEY", bold=True,
        align="c")
    c.t(f"Broker: {m['broker'].title()} — Reference {m['broker_ref']}",
        align="c")
    c.space(8)
    lw = [128.0, 340.0]

    def field(label, value):
        body = _wrap(value, c._s["body"], lw[1] - 6)
        for i, ln in enumerate(body):
            c.row([label if i == 0 else "", ln], lw, aligns=["l", "l"],
                  bold=(i == 0))
        c.space(3)

    field("POLICY NO.", m["policy_no"])
    field("ASSURED", f"{m['company'].title()} and {m['subsidiary']}, "
                     f"each for their respective rights and interests.")
    field("PERIOD", f"Continuation of the current policy year; revised "
                    f"terms herein attaching {_fmt_uk(m['slip_date'])}.")
    field("SITUATION", f"{m['island']}, Republic of Costa Rica.")
    field("INTEREST", "The programme in sections as follows.")
    c.space(2)
    sec_specs = {
        "I": f"Buildings, plant and conventional contents per statement of "
             f"values. Sum insured USD {cov['conventional_mm']:,.1f} m. "
             f"Deductible USD {m['property_ded_k'] * 1000:,} each and "
             f"every loss.",
        "II": f"Machinery breakdown and electronic equipment upon control, "
              f"communications, security and power plant. Base USD "
              f"{cov['mb_base_mm']:,.1f} m. Excluding loss caused by "
              f"deliberate shutdown, programming error, or any defect "
              f"notified and not made good.",
        "III": f"Business interruption: standing charges and increased "
               f"cost of working only. Sum insured USD "
               f"{m['bi_sum_mm']:,.1f} m. Prospective gate receipts, "
               f"licensing and merchandising income and unearned investor "
               f"returns EXCLUDED, the risk having no operating history.",
        "IV": f"Public liability. USD {cov['each_occurrence_mm']:,.2f} m "
              f"each occurrence; USD {cov['aggregate_mm']:,.2f} m "
              f"aggregate. Specimen contact/escape sub-limit USD "
              f"{cov['animal_sublimit_mm']:,.2f} m; Class IV sub-limit USD "
              f"{cov['class_iv_sublimit_mm']:,.2f} m, defence costs "
              f"inclusive. Retention USD {cov['retention_usd']:,} each and "
              f"every loss. Named adult invitees only; no public "
              f"admission; no person under the age of majority.",
        "V": f"Specimen mortality, escape and recapture expense at agreed "
             f"values per schedule, total USD {cov['specimen_mm']:,.1f} m. "
             f"Covering death by listed external peril, humane destruction "
             f"ordered following insured injury, and recapture expense. "
             f"EXCLUDING natural mortality, failure to thrive, "
             f"unexplained disappearance, unauthorised breeding, escape "
             f"caused by failure to maintain barriers, and loss of "
             f"scientific or commercial value.",
        "VI": "Employers' liability excess of local admitted cover, USD "
              "5.00 m any one occurrence.",
    }
    for roman, name, _p in cov["sections"]:
        field(f"SECTION {roman}", f"{name}. {sec_specs[roman]}")
    field("WARRANTY", f"Warranted recommendations rated A in survey report "
                      f"HRE/{m['policy_no'].split('/')[-1]}/SR completed "
                      f"within ninety days of survey and compliance "
                      f"certified in writing by Holbeach Risk Engineering. "
                      f"Breach discharges Underwriters from liability for "
                      f"loss arising on or after the date of breach under "
                      f"Sections IV and V, without prejudice to liability "
                      f"arising before that date. Reinstatement by written "
                      f"endorsement only.")
    field("LAW", "This insurance is subject to English law and practice. "
                 "London market wordings to apply.")
    c.space(3)
    c.t("SUBJECT TO:", bold=True)
    c.space(2)
    for s in subjectivity_register(m):
        c.numbered(f"{s['no']}.", s["text"], width=22.0, after=3.0)
    c.numbered(f"{len(subjectivity_register(m)) + 1}.",
               "No known loss or circumstance at attachment of the revised "
               "terms other than as advised in the broker's first advice.",
               width=22.0, after=3.0)
    c.space(4)

    c.t("PREMIUM (IN SECTIONS):", bold=True)
    c.space(2)
    pw = [318.0, 150.0]
    for roman, name, prem in cov["sections"]:
        c.row([f"Section {roman} — {name}", f"USD {prem:,.2f}"], pw,
              aligns=["l", "r"])
    c.rule(width=0.5, pad=3.0)
    c.row(["ANNUAL PREMIUM", f"USD {cov['annual_premium']:,.2f}"], pw,
          bold=True, aligns=["l", "r"])
    c.row([f"Additional premium — inspection period (see Endorsement No. "
           f"{m['endt_no']})", f"USD {cov['ap_inspection']:,.2f}"], pw,
          aligns=["l", "r"])
    c.row(["TOTAL INCLUSIVE OF ADDITIONAL PREMIUM",
           f"USD {cov['annual_premium'] + cov['ap_inspection']:,.2f}"], pw,
          bold=True, aligns=["l", "r"])
    c.space(4)
    field("BROKERAGE", f"{m['brokerage_pct']:.1f} per cent.")
    c.space(4)

    c.t("SUBSCRIPTION:", bold=True)
    c.space(2)
    sw = [252.0, 72.0, 72.0, 72.0]
    c.row(["Market", "Written", "Signed", "Ref."], sw, bold=True)
    c.rule(width=0.5, pad=3.0)
    override = m.get("_signed_override")
    for s, signed in zip(m["subscription"], cov["signed"]):
        shown = signed
        if override and override[0] in s["market"]:
            shown = override[1]
        ref = (m["policy_no"].split("/")[-1] if s["lead"]
               else f"L{_stable_hash(s['market']) % 900 + 100}")
        c.row([s["market"], f"{s['written']:.2f}%", f"{shown:.2f}%", ref],
              sw, aligns=["l", "r", "r", "r"])
        if s["condition"]:
            body = _wrap("— " + s["condition"], ("Courier-Oblique", 8.0),
                         sw[0] + sw[1] - 6)
            for ln in body:
                c.row([ln, "", "", ""], sw, font=("Courier-Oblique", 8.0))
    c.rule(width=0.5, pad=3.0)
    c.row(["TOTALS", f"{cov['written_total']:.2f}%",
           f"{sum(cov['signed']):.2f}%", ""], sw, bold=True,
          aligns=["l", "r", "r", "r"])
    c.space(4)
    c.para(f"Written lines signed down to 100 per cent by the broker "
           f"{_fmt_uk(m['slip_date'])}. Lead terms set by "
           f"{m['lead_uw_initials']} for the Leading Underwriter; "
           f"following lines subject to their respective conditions as "
           f"noted against each stamp.")


# The broker's answers to the lead's written enquiries, with the marginal
# annotations retained on the lead's file copy. Fixed canon: each exchange
# coheres with a fact another instrument states (recommendation 6, the
# barrier power finding, the licence's population-control clause, and
# resolution 6 on the minors).
_UW_ENQUIRIES = [
    ("How is the specimen census independently verified?",
     "Production records are reconciled against the expected population "
     "daily. Individual physical tagging has not been implemented.",
     "Not a census. Reconciliation to model. Recommendation 6 stands."),
    ("Can the perimeter and paddock barriers remain energised following "
     "total loss of the central control facility?",
     "Standby generation is available and adequate in capacity; restart of "
     "the main plant is a manual operation performed from the plant room.",
     "Answer does not address loss of CONTROLS. Refer engineer. "
     "Recommendations 1 and 3 stand."),
    ("Have any specimens reproduced otherwise than through the authorised "
     "hatchery process?",
     "No such reproduction has been observed.",
     "Asked whether POSSIBLE, not whether observed. Not answered. Census "
     "subjectivity stands."),
    ("Why is the presence of minors necessary to an engineering and "
     "scientific inspection?",
     "The Chairman regards their presence as material to evaluation of the "
     "visitor experience.",
     "Decline."),
]


def _tab_uwfile(c: _C, m: dict, cov: dict) -> None:
    """Tab 10 — the lead underwriter's retained file note. Not addressed to
    the assured; the grades, the loss estimation, the subjectivity register
    and the annotated Q&A are what the decision actually rested on."""
    c.source("insurer")
    _letterhead(c, name=m["carrier"],
                addr=[", ".join(m["carrier_addr"])],
                sub="UNDERWRITING FILE NOTE — NOT FOR RELEASE")
    w = [122.0, 346.0]
    for k, v in (("Risk", f"{m['company'].title()} — {m['island']}"),
                 ("Policy", m["policy_no"]),
                 ("Broker", f"{m['broker'].title()} — {m['broker_ref']}"),
                 ("Prepared by", f"{m['lead_uw'].title()} (lead)"),
                 ("Date", _fmt_uk(m["slip_date"]))):
        c.row([k, v], w, aligns=["l", "l"])
    c.rule()

    c.head("1.  RISK QUALITY")
    gw = [234.0, 234.0]
    for left, right in (
            ("Management", "Below average"),
            ("Engineering controls", "Below average"),
            ("Fire protection", "Average"),
            ("Natural hazards", "Uncertain"),
            ("Business interruption exposure", "Severe"),
            ("Liability severity", "Not quantifiable"),
            ("Loss experience", "Adverse"),
            ("Information quality", "Incomplete"),
            ("Moral hazard / governance", "Material concern")):
        c.row([left, right], gw, aligns=["l", "l"])
    c.space(6)
    c.para("For the risk: isolation; access wholly within the assured's "
           "control; a closed and named invitee population; no public "
           "operation; substantial capital investment; professional "
           "veterinary staffing; redundant generating capacity; a named "
           "inspection panel of standing.")
    c.para("Against it: a fatal loss; an unresolved mechanical interlock; "
           "every protective system dependent upon one control facility "
           "operated by one man; barriers without independent power; no "
           "individual animal census; growing specimen mass against fixed "
           "barrier ratings; inadequate casualty evacuation; management "
           "pressure to admit minors against its own counsel's written "
           "advice; and no credible maximum-loss estimate for the "
           "liability account.")

    c.head("2.  LOSS ESTIMATION")
    c.para(f"Property estimates per survey section 8: control-system "
           f"failure USD {cov['pml_control_mm']:,.1f} m; power plant fire "
           f"USD {cov['pml_fire_mm']:,.1f} m; storm USD "
           f"{cov['pml_storm_mm']:,.1f} m; conventional MFL USD "
           f"{cov['conventional_mm']:,.1f} m. The liability MFL is not "
           f"susceptible of dependable numerical estimation: the exposed "
           f"population following an escape is not bounded by the insured "
           f"premises. Price what can be priced; exclude what cannot; "
           f"retain nothing silently.")

    c.head("3.  BROKER'S ANSWERS TO ENQUIRIES, WITH FILE ANNOTATIONS")
    for n, (q, a, note) in enumerate(_UW_ENQUIRIES, start=1):
        c.para(f"Q{n}. {q}", bold=True)
        c.para(f"A{n}. {a}")
        c.para(f"[Noted on file, {m['lead_uw_initials']}]: {note}",
               bold=True)
    override = m.get("_subjectivity_override")

    c.head("4.  SUBJECTIVITY REGISTER")
    sw = [172.0, 178.0, 118.0]
    c.row(["Subjectivity", "Evidence supplied", "Lead decision"], sw,
          bold=True)
    c.rule(width=0.5, pad=3.0)
    for s in subjectivity_register(m):
        status = s["status"]
        if override and override[0] == s["no"]:
            status = override[1]
        cells = [_wrap(f"{s['no']}. {s['text']}", c._s["body"], sw[0] - 6),
                 _wrap(s["evidence"], c._s["body"], sw[1] - 6),
                 _wrap(status, c._s["body"], sw[2] - 6)]
        for i in range(max(len(col) for col in cells)):
            c.row([col[i] if i < len(col) else "" for col in cells], sw,
                  aligns=["l", "l", "l"])
        c.space(3)
    c.rule(width=0.5, pad=3.0)

    c.head("5.  DECISION")
    c.para("Continue Sections I and II on the revised terms. Section III "
           "restricted to standing charges: no prospective revenue until "
           "the risk has one. Section IV restricted to named adult "
           "invitees; public-opening exposure declined; the Class IV "
           "sub-limit stands and the exposure above it remains the "
           "assured's. No cover to attach in respect of the proposed "
           "inspection until every subjectivity has been satisfied in "
           "writing or expressly excepted by endorsement at additional "
           "premium. The assured's request concerning the minors is "
           "refused as presented; see the special-acceptance "
           "correspondence.")
    c.space(10)
    c.sig("leaduw", "E R Castleton")
    c.t(f"{m['lead_uw'].title()} — for the Leading Underwriter")
    c.t(_fmt_uk(m["slip_date"]))


def _tab_special(c: _C, m: dict, cov: dict) -> None:
    """Tab 11 — the special-acceptance trail: the broker's request, the
    lead's refusal-and-exception, and the endorsement under which the
    inspection actually proceeds. The market did not waive; it priced."""
    c.source("broker")
    _letterhead(c, name=m["broker"],
                addr=[m["broker_desc"], ", ".join(m["broker_addr"])])
    c.t("REQUEST FOR SPECIAL ACCEPTANCE OF INSPECTION RISK", bold=True,
        align="c")
    c.space(8)
    w = [116.0, 352.0]
    for k, v in (("To", f"{m['lead_uw'].title()}, Esq., "
                        f"{m['carrier'].title()}"),
                 ("Our reference", m["broker_ref"]),
                 ("Policy", m["policy_no"]),
                 ("Date", _fmt_uk(m["request_date"]))):
        c.row([k, v], w, aligns=["l", "l"])
    c.rule()
    minors = " and ".join(n.title() for n, _ in m["minors"])
    c.para("Dear Sirs,")
    c.para(f"The Assured requests that underwriters waive, solely for the "
           f"inspection to commence {_fmt_uk(m['visit_date'])}, the "
           f"outstanding subjectivities numbered 2 and 3 upon the slip — "
           f"the presence of persons under the age of majority, and final "
           f"engineering certification of the recommendations rated A. We "
           f"are instructed that the Chairman intends that his "
           f"grandchildren, {minors}, accompany the inspection party, and "
           f"that the certification of the outstanding recommendations "
           f"will follow rather than precede the inspection.")
    c.para("We put the request as instructed. Our advice to the Assured, "
           "which we repeat here so that the file is complete, was that "
           "underwriters would be unlikely to waive either item.")
    c.t("Yours faithfully,")
    c.space(4)
    c.sig("broker", "J G Pike")
    c.t(m["broker_partner"].title())

    c.raw(newpage=True)
    c.source("insurer")
    _letterhead(c, name=m["carrier"],
                addr=[", ".join(m["carrier_addr"])])
    c.t(f"To: {m['broker'].title()} — {m['broker_ref']}", bold=True)
    c.t(f"{_fmt_uk(m['endt_date'])}")
    c.space(6)
    c.para("Dear Sirs,")
    c.para(f"Underwriters do not waive the subjectivities, and nothing in "
           f"this letter is to be read as satisfaction of either of them. "
           f"However, in consideration of an additional premium of USD "
           f"{cov['ap_inspection']:,.2f} and upon the terms of Endorsement "
           f"No. {m['endt_no']} annexed, underwriters agree to provide "
           f"limited property and third-party liability cover for the "
           f"named inspection period only. The exclusions in the "
           f"endorsement are of its essence. The Assured should understand "
           f"— and we ask you to confirm in writing that the Assured has "
           f"been told — that the catastrophic liability exposure of the "
           f"inspection remains with the Assured.")
    c.t("Yours faithfully,")
    c.space(4)
    c.sig("leaduw", "E R Castleton")
    c.t(f"{m['lead_uw'].title()} — for the Leading Underwriter")

    c.raw(newpage=True)
    c.source("slip")
    c.t(f"ENDORSEMENT NO. {m['endt_no']} — SPECIAL ACCEPTANCE — "
        f"INSPECTION PERIOD", bold=True, align="c")
    c.t(f"Attaching to and forming part of Policy No. {m['policy_no']}",
        align="c")
    c.space(8)
    end = m["visit_date"] + _dt.timedelta(days=3)
    for n, text in enumerate([
        f"Period of this endorsement: from 00:01 hours "
        f"{_fmt_uk(m['visit_date'])} to 24:00 hours {_fmt_uk(end)}, local "
        f"standard time at the situation.",
        f"Additional premium: USD {cov['ap_inspection']:,.2f}, payable "
        f"upon attachment.",
        f"For the period of this endorsement the retention under Section "
        f"IV is increased to USD {m['inspection_retention_mm']:,.2f} "
        f"million each and every loss.",
        "Cover under Section IV extends only to the persons named in the "
        "schedule of invitees annexed to the Assured's board resolution "
        "and to the Assured's own personnel in attendance upon them.",
        f"EXCLUSION. No indemnity is provided under any Section in "
        f"respect of bodily injury to {minors}, or either of them, "
        f"arising from contact with, escape of, or attempted avoidance "
        f"of any Class III or Class IV specimen.",
        "Subjectivities 2 and 3 upon the slip are not waived and remain "
        "unsatisfied. This endorsement is a special acceptance for the "
        "period stated and is without prejudice to underwriters' rights "
        "in respect of any breach of warranty.",
        "All other terms, conditions, warranties and exclusions remain "
        "unaltered.",
    ], start=1):
        c.numbered(f"{n}.", text, after=5.0)
    c.space(8)
    c.t(f"Agreed for and on behalf of underwriters subscribing hereto, "
        f"{_fmt_uk(m['endt_date'])}.")
    c.space(4)
    c.sig("leaduw", "E R Castleton")
    c.t(f"{m['lead_uw'].title()} — Leading Underwriter")


# -- packet assembly ---------------------------------------------------------

# Tab sources are format templates resolved against the model, so the
# index and the dividers name whatever operator the canon supplies.
TABS = [
    ("1", "MEMORANDUM OF OUTSIDE COUNSEL — REGULATORY CHARACTERISATION, "
          "LIABILITY EXPOSURE AND CONDITIONS TO LIMITED OPERATIONS",
     "Cowan, Swain & Ross", _tab_memorandum),
    ("2", "INSURANCE SURVEY REPORT — SPECIAL RISKS, WITH RECOMMENDATION "
          "REGISTER AND SCHEDULE OF COVER",
     "Holbeach Risk Engineering", _tab_survey),
    ("3", "CERTIFICATE OF CONTAINMENT ADEQUACY",
     "Office of the Park Veterinary Officer", _tab_vet),
    ("4", "REPORT OF SERIOUS INJURY OR DEATH",
     "{company_short} — Safety Office",
     _tab_incident),
    ("5", "GENETIC MATERIAL OWNERSHIP AND LICENCE AGREEMENT",
     "{company_short} / {subsidiary}", _tab_licence),
    ("6", "ACKNOWLEDGEMENT OF RISK, ASSUMPTION OF RISK, WAIVER AND RELEASE",
     "{company_short} — form of invitee release", _tab_release),
    ("7", "RESOLUTION OF THE BOARD OF DIRECTORS",
     "{company_short} — Office of the Secretary", _tab_resolution),
    ("8", "BROKER'S FIRST ADVICE, RISK INFORMATION SCHEDULE AND STATEMENT "
          "OF VALUES",
     "Harrowgate, Pike & Fenner Ltd. — Lloyd's brokers", _tab_broker),
    ("9", "PLACING SLIP — REVISED TERMS, SUBJECTIVITIES AND SUBSCRIPTION",
     "Produced from the files of the Company's brokers", _tab_slip),
    ("10", "LEAD UNDERWRITER'S FILE NOTE — RISK ASSESSMENT, LOSS "
           "ESTIMATION AND SUBJECTIVITY REGISTER",
     "Chelmsford Underwriting Agencies — produced from the files of "
     "underwriters", _tab_uwfile),
    ("11", "SPECIAL ACCEPTANCE CORRESPONDENCE AND ENDORSEMENT — "
           "INSPECTION PERIOD",
     "Harrowgate, Pike & Fenner / Chelmsford Underwriting Agencies",
     _tab_special),
]

# Party-appropriate page legends, per tab. Privilege belongs to counsel's
# memorandum alone; everything else carries the marking its author's role
# implies. The round-6 review's point: a surveyor's report stamped
# "privileged" is a tell, because it was prepared FOR underwriters.
DEFAULT_LEGEND = "CONFIDENTIAL"
PAGE_LEGENDS = {
    "1": "PRIVILEGED AND CONFIDENTIAL — ATTORNEY WORK PRODUCT",
    "2": "CONFIDENTIAL SURVEY REPORT — FOR UNDERWRITING PURPOSES ONLY",
    "3": "CONFIDENTIAL",
    "4": "COMPANY CONFIDENTIAL",
    "5": "CONFIDENTIAL",
    "6": "CONFIDENTIAL",
    "7": "CONFIDENTIAL — MINUTE BOOK EXTRACT",
    "8": "BROKER'S CONFIDENTIAL PRESENTATION",
    "9": "FOR UNDERWRITING PURPOSES ONLY",
    "10": "LEAD UNDERWRITER FILE — NOT TO BE DISCLOSED TO THE ASSURED",
    "11": "WITHOUT PREJUDICE TO COVER",
}


def compose_packet(m: dict, defect: dict | None = None) -> list[dict]:
    """Compose every instrument. Returns the flat line list; pagination and
    bates are the renderer's job.

    Defects are applied here as explicit single-value deltas on a COPY of the
    model, so exactly one displayed value moves and everything computed around
    it stays honest.
    """
    m = _apply_defect(m, defect)
    cov = compute_coverage(m)
    c = _C()

    # -- cover sheet + index ------------------------------------------------
    c.source("corp")
    c.t(m["company"], bold=True, align="c")
    c.space(4)
    c.t("PRE-OPENING DILIGENCE PACKET", bold=True, align="c",
        font=("Times-Bold", 15))
    c.t(f"{m['park']} — {m['island']}, Republic of Costa Rica", align="c")
    c.space(10)
    c.t("CONFIDENTIAL", align="c", bold=True)
    c.t("ASSEMBLED AT THE REQUEST OF UNDERWRITERS AND OF COUNSEL",
        align="c", font=("Times-Roman", 10))
    c.rule()
    c.space(10)
    c.para(f"This packet comprises the documents identified in the index "
           f"below, assembled as at {_fmt_us(m['visit_date'])}. Each "
           f"instrument is the work of the party stated and is reproduced "
           f"as executed or as issued, under the confidentiality marking "
           f"its author applied. Tabs 8 to 11 comprise the placement "
           f"record and are reproduced from the files of the Company's "
           f"insurance brokers and, where so marked, of the leading "
           f"underwriter. The reader is directed to the scope and "
           f"limitation provisions of each instrument, which differ from "
           f"one another and which are not summarised here.")
    c.space(10)
    c.t("INDEX OF DOCUMENTS", bold=True, align="c")
    c.space(8)
    iw = [34.0, 300.0, 134.0]
    c.row(["Tab", "Document", "Bates"], iw, bold=True)
    c.rule(width=0.5, pad=3.0)
    for tab, title, source, _ in TABS:
        source = source.format(**m)
        body = _wrap(title, c._s["body"], iw[1] - 6)
        for i, ln in enumerate(body):
            # (BATES, tab) resolves on the second pass, once pagination is
            # known — the index cites where each tab actually begins.
            c.row([tab if i == 0 else "", ln,
                   (BATES, tab) if i == 0 else ""], iw)
        c.row(["", source, ""], iw, font=("Times-Italic", 9.5))
        c.space(5)
    c.rule(width=0.5, pad=3.0)

    for tab, title, source, fn in TABS:
        source = source.format(**m)
        c.raw(newpage=True, tab_id=tab,
              legend=PAGE_LEGENDS.get(tab, DEFAULT_LEGEND))
        _divider(c, tab, title, source)
        c.raw(newpage=True)
        fn(c, m, cov)
    return c.lines


BATES = "\x00bates"        # sentinel resolved at render time


def _divider(c: _C, tab: str, title: str, source: str) -> None:
    """The tab divider every assembled production carries."""
    c.source("corp")
    c.space(190)
    c.t(f"TAB {tab}", bold=True, align="c", font=("Times-Bold", 34))
    c.space(24)
    for ln in _wrap(title, ("Times-Roman", 13), USABLE - 90):
        c.t(ln, align="c", font=("Times-Roman", 13), lead=17)
    c.space(12)
    c.t(source, align="c", font=("Times-Italic", 10.5))


def _apply_defect(m: dict, defect: dict | None) -> dict:
    """Each hook alters exactly one displayed value. Everything computed
    around it stays honest — which is what makes the fault findable and
    provable rather than ambient noise."""
    if not defect:
        return m
    m = {**m, "roster": [dict(r) for r in m["roster"]],
         "recommendations": [dict(r) for r in m["recommendations"]],
         "incident": dict(m["incident"])}
    if "specimen_count" in defect:
        species, n = defect["specimen_count"]
        for r in m["roster"]:
            if r["species"] == species:
                r["count"] = n
    if "recommendation_status" in defect:
        no, status = defect["recommendation_status"]
        for r in m["recommendations"]:
            if r["no"] == no:
                r["status"] = status
    if "incident_date" in defect:
        m["incident_date"] = defect["incident_date"]
    if "class_iv_sublimit_pct" in defect:
        m["class_iv_sublimit_pct"] = defect["class_iv_sublimit_pct"]
    if "signed_line" in defect:
        # One displayed signed percentage on the slip moves; the totals row
        # stays the honest sum, so the subscription no longer foots.
        m["_signed_override"] = defect["signed_line"]
    if "subjectivity_status" in defect:
        # One displayed status in the lead's register moves; the board
        # resolution, the survey register and counsel's memorandum keep
        # stating the fact the register now contradicts.
        m["_subjectivity_override"] = defect["subjectivity_status"]
    return m


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_SIG_SEEDS = {"gennaro": 71, "fenwick": 72, "harding": 73, "muldoon": 74,
              "secretary": 75, "broker": 76, "leaduw": 77}


def _vector(lines: list[dict], m: dict, bates_map: dict | None = None):
    """Paginate and draw. Returns (pdf bytes, per-page OCR text runs,
    tab -> starting bates number).

    bates_map is empty on the first pass and filled on the second: column
    widths are fixed, so resolving the index cannot change pagination.
    """
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=letter, invariant=1)
    pages: list[list[tuple]] = []
    runs: list[tuple] = []
    bates_map = bates_map or {}
    tab_pages: dict[str, str] = {}
    page_no = 1
    y = TOP_Y
    legend = DEFAULT_LEGEND

    def frame():
        """Bates stamp and the CURRENT tab's confidentiality legend. Both go
        into `runs` as well as onto the page: a real OCR'd production is
        searchable BY bates number, which is most of why anyone OCRs one.
        The legend is per-tab (party-appropriate markings), set by the
        newpage line that opens each tab."""
        bates = f"{m['bates_prefix']}{page_no:06d}"
        c.setFont("Times-Roman", 8.5)
        c.drawRightString(RIGHT, 56.0, bates)
        runs.append((RIGHT - pdfmetrics.stringWidth(bates, "Times-Roman", 8.5),
                     56.0, bates, ("Times-Roman", 8.5)))
        c.setFont("Times-Roman", 8)
        c.drawString(LEFT, 56.0, legend)
        runs.append((LEFT, 56.0, legend, ("Times-Roman", 8)))

    def flush():
        nonlocal page_no, y, runs
        frame()
        c.showPage()
        pages.append(runs)
        runs = []
        page_no += 1
        y = TOP_Y

    def draw(text, font, x, align="l"):
        name, size = font
        c.setFont(name, size)
        if align == "c":
            c.drawCentredString((LEFT + RIGHT) / 2, y, text)
            runs.append(((LEFT + RIGHT) / 2 - pdfmetrics.stringWidth(
                text, name, size) / 2, y, text, font))
        elif align == "r":
            c.drawRightString(RIGHT, y, text)
            runs.append((RIGHT - pdfmetrics.stringWidth(text, name, size),
                         y, text, font))
        else:
            c.drawString(x, y, text)
            runs.append((x, y, text, font))

    for ln in lines:
        need = ln.get("lead", 12.0) + (ln.get("space", 0.0))
        if ln.get("newpage"):
            if runs or y < TOP_Y:
                flush()
            if ln.get("legend"):
                legend = ln["legend"]
            if ln.get("tab_id"):
                tab_pages[ln["tab_id"]] = f"{m['bates_prefix']}{page_no:06d}"
            continue
        if y - need < BOTTOM_Y:
            flush()
        if "space" in ln:
            y -= ln["space"]
            continue
        if "rule" in ln:
            x1, x2, lw = ln["rule"]
            c.setLineWidth(lw)
            # sit between the previous baseline and the next, never through
            # the row that follows
            c.line(x1, y + 8, x2, y + 8)
            y -= ln["lead"]
            continue
        if "sig" in ln:
            key, name = ln["sig"]
            png = assets.signature_png(_SIG_SEEDS.get(key, 70), name=name)
            ir = ImageReader(io.BytesIO(png))
            iw, ih = ir.getSize()
            h = 34.0
            c.drawImage(ir, LEFT + 4, y - h + 6, width=h * iw / ih, height=h,
                        mask="auto")
            y -= ln["lead"]
            continue
        if "row" in ln:
            x = LEFT
            aligns = ln.get("aligns") or ["l"] * len(ln["row"])
            for cell, cw, al in zip(ln["row"], ln["widths"], aligns):
                if isinstance(cell, tuple) and cell and cell[0] == BATES:
                    cell = bates_map.get(cell[1], "")
                if cell:
                    name, size = ln["font"]
                    c.setFont(name, size)
                    if al == "r":
                        c.drawRightString(x + cw - 6, y, str(cell))
                    elif al == "c":
                        c.drawCentredString(x + cw / 2, y, str(cell))
                    else:
                        c.drawString(x, y, str(cell))
                    runs.append((x, y, str(cell), ln["font"]))
                x += cw
            y -= ln["lead"]
            continue
        if "hang" in ln:
            width, rest = ln["hang"]
            draw(ln["t"], ln["font"], LEFT + ln.get("indent", 0.0))
            body = _wrap(rest, ln["font"], USABLE - width)
            for i, part in enumerate(body):
                if i:
                    y -= ln["lead"]
                    if y - ln["lead"] < BOTTOM_Y:
                        flush()
                c.setFont(*ln["font"])
                c.drawString(LEFT + width, y, part)
                runs.append((LEFT + width, y, part, ln["font"]))
            y -= ln["lead"]
            continue
        if ln.get("t") is not None:
            if ln["t"]:
                draw(ln["t"], ln["font"], LEFT + ln.get("indent", 0.0),
                     ln.get("align", "l"))
            y -= ln["lead"]
    if runs or y < TOP_Y:
        frame()
        c.showPage()
        pages.append(runs)
    c.save()
    return buf.getvalue(), pages, tab_pages


def render_packet(model: dict, *, metadata: dict, defect: dict | None = None,
                  scan_dpi: int = 130) -> bytes:
    """Render the packet as a bates-numbered production scan.

    `metadata` dates the DIGITISATION — a production set is paper first and
    images later, so the represented 1993 documents carry a PDF-era scan date
    and never claim a 1993 CreationDate.
    """
    rng = random.Random(model.get("scan_seed", 93))
    lines = compose_packet(model, defect)
    _, _, tab_pages = _vector(lines, model)          # pass 1: learn pagination
    vector, pages, _ = _vector(lines, model, tab_pages)   # pass 2: fill index

    def text_layer(idx, t):
        for x, y, text, font in pages[idx]:
            t.setFont(*font)
            t.setTextOrigin(x, y)
            t.textOut(text)

    return scan.rescan(vector, rng=rng, metadata=metadata,
                       text_layer=text_layer, dpi=scan_dpi)


# -- small helpers -----------------------------------------------------------

def _stable_hash(s: str) -> int:
    """Deterministic across processes, unlike builtin hash() (which is
    randomized per interpreter and would break seed -> byte identity)."""
    h = 0
    for ch in s:
        h = (h * 131 + ord(ch)) % 1000003
    return h


def _serial(items: list) -> str:
    """'1', '1 and 3', '1, 3 and 4' — the way a document lists numbers."""
    s = [str(i) for i in items]
    if not s:
        return ""
    if len(s) == 1:
        return s[0]
    return ", ".join(s[:-1]) + " and " + s[-1]


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"
