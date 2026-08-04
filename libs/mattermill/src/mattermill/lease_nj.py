"""lease_nj: a New Jersey / Hoboken management-company residential lease, seeded.

A contemporary born-digital lease as a property manager's system would export
it — for a fictional, caller-replaceable Hoboken building.
PDF shipped in 1993, so this is a vector file, not a scan.

A lease is a GOVERNED FILL. The prose layout is half the contract; the law
controlling what may be written into it is the other half, and it is the half
that decides whether the first reader who rents in Hoboken believes it. Two
jurisdictions STACK here and both are gates in code:

- **New Jersey**, sourced from the DCA and the statutes:
  - Rent Security Deposit Act, N.J.S.A. 46:8-19 et seq. — deposit at most one
    and one-half times one month's rent, held in trust; a building of ten or
    more units invests it in an insured money-market fund/account rather than a
    plain interest-bearing account, and the tenant gets written notice of the
    institution, account type, rate and amount within thirty days. Deposit is
    COMPUTED from the rent, never sampled beside it.
  - the disclosure battery the Truth in Renting guide (p.6) enumerates: lead
    paint (pre-1978 only), the Truth in Renting statement itself, the flood
    risk notice (N.J.S.A. 46:8-50 / P.L.2023 c.93), window guards, bed bugs,
    domestic-violence termination — and the rule that late-fee and attorney-fee
    recovery must be EXPRESSLY stated to be recoverable (Community Realty v.
    Harris, 155 N.J. 212 (1998)).

- **Hoboken**, sourced from Municipal Code Ch. 155 (ecode360 HO0741):
  - § 155-5 caps a renewal increase at the LESSER of 5% or the CPI differential.
    The new rent is derived from the prior rent and that capped percentage,
    rounded to the nearest dollar (§ 155-4).
  - § 155-4 requires a disclosure statement served on the tenant: the right to
    a legal rent calculation, the two-year bar, the registration on file, and
    an acknowledgement of the Truth-in-Renting Act. Its base-rent recital is
    coupled to the building's age — the Oct 1, 1985 base rent for a building
    that existed then, or the first rent charged after Oct 1, 1985 for a newer
    one (§ 155-4.D).

The municipality is the second gate: Hoboken's rent-control world is the only
one sourced, so a lease asked for in another New Jersey municipality raises
rather than rendering Hoboken's caps under another town's name.

The guard list (what the sources proved must be ABSENT) is enforced in code and
asserted directly: a deposit over the 1.5-month cap, a renewal increase over
min(5%, CPI), a lead disclosure on a post-1978 building (or its absence on a
pre-1978 one), a flood notice answering "No" in flood-exposed Hoboken, a pet
deposit on a disability assistance animal, a waiver of the tenant's right to a
legal rent calculation, an invented NJ-Realtors form edition mark.

Not sourced, therefore not invented: the FEMA flood-zone designation for the
fictional unit. The flood notice uses the modeled Hoboken risk context without
printing a zone code that would invite a lookup it cannot survive; no
NJ-Realtors form edition number is stamped because that form was not read.

Fictional parties, high entropy by construction: tenant names, the signing
leasing agent, the deposit institution and the account tail are drawn from
large combinatorial spaces so repeated generation never reuses a small pool
that would itself become a tell. The building and its landlord entity are
caller-supplied canon (a lease for one building has one landlord); the people
and the money vary.
"""

from __future__ import annotations

import datetime as _dt
import io
import random

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from . import legalpdf

PAGE_W, PAGE_H = letter

# ---------------------------------------------------------------------------
# The sourced worlds. Hoboken's rent-control world is a dict because the
# MUNICIPALITY is a gate: another New Jersey town has its own ordinance (or
# none), and none of Hoboken's arithmetic transfers.
# ---------------------------------------------------------------------------

NJ = {
    "state_name": "NEW JERSEY",
    # Rent Security Deposit Act, N.J.S.A. 46:8-19
    "deposit_cap_months": 1.5,
    "deposit_interest_penalty_pct": 7,          # 46:8-19, failure remedy
    "deposit_notice_days": 30,                  # 46:8-19 subsec. c(1)
    "large_building_units": 10,                 # 46:8-19 subsec. a threshold
    # DCA Landlord-Tenant Information Service, quoted by Hoboken § 155-4
    "dca_address": "P.O. Box 805, Trenton, New Jersey 08625",
    # Flood: N.J.S.A. 46:8-50 / P.L. 2023 c.93, effective March 20, 2024
    "flood_law_effective": _dt.date(2024, 3, 20),
    "lead_paint_cutoff_year": 1978,             # federal 24 CFR 35 / 40 CFR 745
    "senior_grace_business_days": 5,            # N.J.S.A. 2A:42-6.1
}

HOBOKEN = {
    "municipality": "Hoboken",
    "county": "Hudson",
    "code_id": "HO0741",                        # ecode360
    "chapter": "Chapter 155",
    "base_rent_date": "October 1, 1985",        # § 155-4
    "increase_cap_pct": 5.0,                    # § 155-5 — the lesser of this or CPI
    "legal_rent_calc_bar_years": 2,             # § 155-4.B two-year bar
    "registration_office":
        "Rent Leveling and Stabilization Office, 124 Grand Street, "
        "Hoboken, New Jersey 07030",           # § 155-30
    # the amended-section marks a real reader recognises
    "increase_section": "§ 155-5",
    "disclosure_section": "§ 155-4",
}

# The only municipal rent-control world sourced. A gate, not a label.
_SOURCED_MUNICIPALITIES = {"Hoboken": HOBOKEN}

# ---------------------------------------------------------------------------
# High-entropy fictional name spaces. FIRST x LAST is ~2,400 combinations, so
# a hundred generated leases reuse essentially nothing — the low-entropy pool
# (nj_birth's ten surnames) is exactly the tell this avoids.
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "Marcus", "Priya", "Daniel", "Aisha", "Nathaniel", "Sofia", "Elena",
    "Jordan", "Camille", "Devon", "Isabella", "Rohan", "Grace", "Malik",
    "Vivian", "Theodore", "Naomi", "Lucas", "Yuki", "Adrian", "Farah",
    "Gabriel", "Simone", "Wei", "Katherine", "Omar", "Nadia", "Julian",
    "Rosa", "Emeka", "Hannah", "Sebastian", "Leila", "Andre", "Clara",
    "Tobias", "Amara", "Vincent", "Delia", "Rafael", "Ingrid", "Damon",
    "Talia", "Everett", "Mireille", "Kwame", "Beatrice", "Soren", "Anjali",
    "Callum",
]
LAST_NAMES = [
    "Okonkwo", "Delgado", "Ferrante", "Nakamura", "Whitfield", "Abadi",
    "Costa", "Blackwood", "Mensah", "Petrov", "Sandoval", "Larkin",
    "Chaudhry", "Vasquez", "Holloway", "Kearney", "Osei", "Marchetti",
    "Sundaram", "Novak", "Ellison", "Rahimi", "Cardoza", "Bergstrom",
    "Adeyemi", "Quinlan", "Voss", "Castellano", "Emerson", "Bhatt",
    "Lindqvist", "Serrano", "Ashford", "Nguyen", "Trujillo", "Fairbanks",
    "Okoro", "Delacroix", "Winslow", "Habib", "Prieto", "Carrington",
    "Amaral", "Yoon", "Kellerman", "Solano", "Redgrave", "Nasser",
    "Beaumont", "Iqbal",
]
# A FICTIONAL e-signature platform. A real one (DocuSign, Adobe Sign) is a
# trademark; stamping it on a fabricated executed lease would be brand
# impersonation, so the platform is invented like the managing agent and bank.
ESIGN_PLATFORM = "Riverline eSign"

DEFAULT_CANON = {
    "building_name": "Loom House",
    "street": "47 Loomwright Mews",
    "unit": "4C",
    "municipality": "Hoboken",
    "county": "Hudson",
    "state": "NEW JERSEY",
    "zip": "07030",
    "units": 128,                               # a large building -> 46:8-19(a)
    "landlord_entity": "Loomwright Mews Owner, LLC",
    "managing_agent": "Riverglass Residential Management, LLC",
    "managing_agent_addr": ["47 Loomwright Mews, Suite 100",
                            "Hoboken, New Jersey 07030"],
}
_CANON_KEYS = frozenset(DEFAULT_CANON)

_PIN_KEYS = {"lease_type", "monthly_rent", "prior_rent", "cpi_pct",
             "deposit_months", "building_year", "rent_controlled",
             "term_start", "pets", "seniors"}


# ---------------------------------------------------------------------------
# Derived values — computed from their inputs, stored nowhere as a free draw.
# ---------------------------------------------------------------------------

def deposit_amount(monthly_rent: float, months: float) -> float:
    """Rent Security Deposit Act, 46:8-19: the deposit follows from the rent.
    Capped at one and one-half months so the emitter cannot render an unlawful
    figure; the cap is the law, not a preference."""
    if months > NJ["deposit_cap_months"]:
        raise ValueError(
            f"security deposit of {months} months exceeds the New Jersey cap of "
            f"{NJ['deposit_cap_months']} months' rent (N.J.S.A. 46:8-19).")
    return round(monthly_rent * months, 2)


def capped_increase_pct(cpi_pct: float, *, municipality: str = "Hoboken") -> float:
    """Hoboken § 155-5: the renewal increase is the LESSER of 5% or the CPI
    differential. A larger number is void by the ordinance's own terms."""
    return round(min(_SOURCED_MUNICIPALITIES[municipality]["increase_cap_pct"],
                     cpi_pct), 2)


def renewed_rent(prior_rent: float, cpi_pct: float,
                 *, municipality: str = "Hoboken") -> int:
    """The new legal rent: prior rent lifted by the capped percentage and
    rounded to the nearest dollar (§ 155-4, 'rounded up or down to the nearest
    dollar')."""
    pct = capped_increase_pct(cpi_pct, municipality=municipality)
    return int(round(prior_rent * (1 + pct / 100)))


def term_end(start: _dt.date, months: int = 12) -> _dt.date:
    """A twelve-month term ends the day before its anniversary."""
    if months != 12:
        raise ValueError("only a 12-month term is modelled")
    try:
        anniv = start.replace(year=start.year + 1)
    except ValueError:                          # Feb 29 start
        anniv = start.replace(year=start.year + 1, day=28)
    return anniv - _dt.timedelta(days=1)


# ---------------------------------------------------------------------------
# Sampled model — coherent by construction
# ---------------------------------------------------------------------------

def sample_lease(rng: random.Random, *, pins: dict | None = None,
                 canon: dict | None = None) -> dict:
    """One lease, coherent by construction. The rent decides the deposit; the
    building's age decides the lead disclosure and the base-rent recital; the
    unit count decides how the deposit is invested; a renewal's prior rent and
    CPI decide the new rent through the § 155-5 cap. Nothing two fields must
    agree on is drawn twice."""
    pins = dict(pins or {})
    bad = set(pins) - _PIN_KEYS
    if bad:
        raise ValueError(f"unknown pins: {sorted(bad)}")
    cn = dict(DEFAULT_CANON if canon is None else canon)
    missing = _CANON_KEYS - set(cn)
    if missing:
        raise ValueError(f"canon missing required keys: {sorted(missing)}")

    # -- the jurisdiction gates --------------------------------------------
    if cn["state"].upper() not in ("NEW JERSEY", "NJ"):
        raise ValueError(
            f"no landlord-tenant world sourced for {cn['state']!r}. This "
            f"emitter is New Jersey only; another state's security-deposit "
            f"limits, disclosures and rent regulation are its own law and none "
            f"of it transfers.")
    muni = cn["municipality"]
    if muni not in _SOURCED_MUNICIPALITIES:
        raise ValueError(
            f"no municipal rent-control world sourced for {muni!r}. Hoboken's "
            f"Chapter 155 is the only one sourced (ecode360 HO0741); its base "
            f"rent, its 5%/CPI cap and its § 155-4 disclosure statement do not "
            f"transfer to another municipality. Source the town before "
            f"rendering a lease that claims to comply with it.")
    ho = _SOURCED_MUNICIPALITIES[muni]

    units = int(cn["units"])
    large_building = units >= NJ["large_building_units"]
    rent_controlled = bool(pins.get("rent_controlled", True))

    # -- building age: drives the lead disclosure AND the § 155-4 recital ---
    building_year = int(pins.get("building_year", rng.randint(1905, 2008)))
    pre_1978 = building_year < NJ["lead_paint_cutoff_year"]
    existed_at_base = building_year <= 1985

    # -- rent and, from it, the deposit ------------------------------------
    lease_type = pins.get("lease_type", rng.choice(["new", "renewal", "renewal"]))
    if lease_type not in ("new", "renewal"):
        raise ValueError("lease_type must be 'new' or 'renewal'")
    if lease_type == "renewal":
        prior_rent = float(pins.get("prior_rent", rng.randint(240, 460) * 10))
        cpi_pct = float(pins.get("cpi_pct", round(rng.uniform(1.4, 6.2), 1)))
        increase_pct = capped_increase_pct(cpi_pct, municipality=muni)
        monthly_rent = float(pins.get("monthly_rent",
                                      renewed_rent(prior_rent, cpi_pct,
                                                   municipality=muni)))
    else:
        prior_rent = cpi_pct = increase_pct = None
        monthly_rent = float(pins.get("monthly_rent", rng.randint(255, 475) * 10))

    deposit_months = float(pins.get("deposit_months",
                                    rng.choice([1.0, 1.5, 1.5, 1.5])))
    deposit = deposit_amount(monthly_rent, deposit_months)

    # -- the deposit's investment PATH, by unit count (46:8-19 a vs b). The
    # institution, account number and rate belong in the SEPARATE 30-day
    # statutory notice, not the lease body: a fabricated bank name and account
    # number embedded here are unverifiable identifiers that invite a lookup
    # they fail (invariant 7, and round-1 external_verifiability tell).
    account_type = ("insured money market account" if large_building
                    else "interest-bearing account")

    # -- term ---------------------------------------------------------------
    start = pins.get("term_start")
    if start is None:
        start = _dt.date(rng.randint(2024, 2026), rng.randint(1, 12),
                         rng.choice([1, 15]))
    elif isinstance(start, str):
        start = _dt.date.fromisoformat(start)
    end = term_end(start, 12)

    # -- fictional people, high entropy ------------------------------------
    def _person() -> str:
        return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"

    tenants = [_person()]
    if rng.random() < 0.4:                      # a co-tenant, sometimes
        second = _person()
        while second == tenants[0]:
            second = _person()
        tenants.append(second)
    leasing_agent = _person()                   # the human who signs for the LLC

    # -- fees ---------------------------------------------------------------
    late_fee = rng.choice([50, 75, 100, 125])
    late_after_day = rng.choice([5, 6, 10])
    pets_allowed = bool(pins.get("pets", rng.random() < 0.45))

    # -- flood: Hoboken is flood-exposed; the notice says so on the
    #    landlord's actual knowledge, without asserting a FEMA zone code ----
    flood_in_hazard_area = "Yes"                # broadly true of Hoboken
    flood_history = rng.choice(["Yes", "Unknown", "Unknown"])

    # -- e-signature envelope: ONE execution convention for the whole
    #    instrument. Round-2 disqualifiers fired because the lease mixed
    #    wet-ink scrawls, typeset initials and blank initial slots; an e-signed
    #    document adopts one typeset signature everywhere, fills every slot, and
    #    carries a certificate of completion. The envelope/signature IDs are
    #    internal to the platform and resolve to nothing public, so they are not
    #    lookup-inviting identifiers (unlike a registry code).
    sign_h, sign_m = rng.randint(9, 16), rng.randint(0, 55)
    roster = [(t, "Tenant") for t in tenants] + \
             [(leasing_agent, f"Authorized Agent, {cn['managing_agent']}")]
    signers = []
    for i, (nm, role) in enumerate(roster):
        mm = (sign_m + i * 6) % 60
        hh = sign_h + (sign_m + i * 6) // 60
        signers.append({
            "name": nm, "role": role, "id": _guid(rng), "ip": _ip(rng),
            "signed_at": f"{start.strftime('%B')} {start.day}, {start.year} "
                         f"at {hh:02d}:{mm:02d} ET"})
    esign = {"envelope_id": _guid(rng), "platform": ESIGN_PLATFORM,
             "signers": signers}

    return {
        **cn,
        "municipality_world": ho,
        "large_building": large_building,
        "rent_controlled": rent_controlled,
        "building_year": building_year,
        "pre_1978": pre_1978,
        "existed_at_base": existed_at_base,
        "lease_type": lease_type,
        "monthly_rent": monthly_rent,
        "prior_rent": prior_rent,
        "cpi_pct": cpi_pct,
        "increase_pct": increase_pct,
        "annual_rent": monthly_rent * 12,
        "deposit_months": deposit_months,
        "security_deposit": deposit,
        "deposit_account_type": account_type,
        "term_start": start,
        "term_end": end,
        "tenants": tenants,
        "leasing_agent": leasing_agent,
        "late_fee": late_fee,
        "late_after_day": late_after_day,
        "pets_allowed": pets_allowed,
        "flood_in_hazard_area": flood_in_hazard_area,
        "flood_history": flood_history,
        "esign": esign,
        "sig_seed": rng.randrange(1 << 30),
    }


def _guid(rng: random.Random) -> str:
    """A platform-style envelope/signature id from the caller's seed (never the
    uuid module — that would break seed -> byte identity, invariant 1). It IS a
    conformant RFC-4122 version-4 UUID: real e-sign platforms emit v4, and a
    round-3 forensic judge caught that random hex dressed as a GUID has the
    wrong version/variant nibbles."""
    h = list("%032x" % rng.getrandbits(128))
    h[12] = "4"                                  # version 4
    h[16] = rng.choice("89ab")                   # variant 10xx
    s = "".join(h)
    return f"{s[:8]}-{s[8:12]}-{s[12:16]}-{s[16:20]}-{s[20:32]}".upper()


def _ip(rng: random.Random) -> str:
    return (f"{rng.choice([24, 71, 73, 98, 108, 172])}.{rng.randint(0, 255)}."
            f"{rng.randint(0, 255)}.{rng.randint(1, 254)}")


def _person_initials(name: str) -> str:
    return "".join(w[0] for w in name.split()[:2]).upper()


# ---------------------------------------------------------------------------
# The document, in clause order. DOC_MARKERS is the Mode B contract: the
# strings a capability test asserts appear, in order, across the flow.
# ---------------------------------------------------------------------------

DOC_MARKERS = [
    "RESIDENTIAL LEASE AGREEMENT",
    "1. PARTIES", "2. PREMISES", "3. TERM", "4. RENT",
    "5. LATE CHARGE", "6. ATTORNEY", "7. SECURITY DEPOSIT",
    "one and one-half", "Within thirty (30) days",
    "8. UTILITIES", "9. SUBLETTING AND ASSIGNMENT", "10. KEYS",
    "11. RENTER'S INSURANCE", "12. PETS",
    "13. LANDLORD'S RIGHT OF ENTRY", "16. DEFAULT AND REMEDIES",
    "17. HOLDOVER", "19. RULES AND REGULATIONS", "23. GOVERNING LAW",
    "IN WITNESS WHEREOF", "Signed electronically by:",
    # addenda / disclosures
    "HOBOKEN RENT CONTROL", "DISCLOSURE STATEMENT",
    "legal rent calculation", "two (2) years",
    "FLOOD RISK", "National Flood Insurance Program",
    "TRUTH IN RENTING", "P.O. Box 805",
    "WINDOW GUARD", "BED BUG", "DOMESTIC VIOLENCE",
    "RULES AND REGULATIONS OF THE BUILDING",
    # e-sign certificate of completion (one execution convention, sealed)
    "CERTIFICATE OF COMPLETION", "Uniform Electronic Transactions Act",
]


def _money(v) -> str:
    return f"${v:,.2f}" if isinstance(v, float) else f"${v:,}"


def _date(d: _dt.date) -> str:
    return d.strftime("%B ") + f"{d.day}, {d.year}"


def _tenants_str(tenants: list[str]) -> str:
    if len(tenants) == 1:
        return tenants[0]
    return " and ".join(tenants)


def compose_lease(m: dict, defect: dict | None = None) -> dict:
    """Every displayed value, with defect deltas applied at the point of
    display so the model stays honest. Returns {articles, disclosures} where
    each is a list the renderer lays out in order."""
    d = defect or {}
    ho = m["municipality_world"]
    rent = m["monthly_rent"]
    deposit = d.get("security_deposit", m["security_deposit"])
    end = m["term_end"]
    if "term_end" in d:
        end = _dt.date.fromisoformat(d["term_end"])
    flood_area = d.get("flood_answer", m["flood_in_hazard_area"])

    addr = f"{m['unit']} at {m['building_name']}, {m['street']}, " \
           f"{m['municipality']}, {m['state'].title()} {m['zip']}"
    landlord = f"{m['landlord_entity']}, by and through its managing agent " \
               f"{m['managing_agent']}"
    tenants = _tenants_str(m["tenants"])

    articles = []

    articles.append(("1. PARTIES", [
        f"This Residential Lease Agreement (the \"Lease\") is made as of "
        f"{_date(m['term_start'])} between {landlord} (\"Landlord\"), whose "
        f"address for notice is {m['managing_agent_addr'][0]}, "
        f"{m['managing_agent_addr'][1]}, and {tenants} (\"Tenant\"). Each party "
        f"represents that the person signing this Lease is at least eighteen "
        f"(18) years of age and legally competent to enter into this Lease.",
    ]))

    articles.append(("2. PREMISES", [
        f"Landlord leases to Tenant, and Tenant rents from Landlord, the "
        f"residential dwelling unit known as Apartment {addr} (the "
        f"\"Premises\"), together with the fixtures and appliances therein, for "
        f"use solely as a private residence for Tenant and Tenant's immediate "
        f"family and for no other purpose.",
    ]))

    articles.append(("3. TERM", [
        f"The term of this Lease is twelve (12) months, commencing on "
        f"{_date(m['term_start'])} and ending at 11:59 p.m. on {_date(end)} "
        f"(the \"Term\"), unless sooner terminated or renewed as provided "
        f"herein or by law.",
    ]))

    rent_paras = [
        f"Tenant shall pay Landlord rent of {_money(rent)} per month, payable "
        f"in advance on the first (1st) day of each month, without demand, "
        f"deduction or setoff, at the office of the managing agent or at such "
        f"other place as Landlord may designate in writing. The total rent for "
        f"the Term is {_money(m['annual_rent'])}.",
    ]
    if m["lease_type"] == "renewal":
        shown_incr = d.get("increase_pct", m["increase_pct"])
        rent_paras.append(
            f"This Lease renews a prior tenancy at the Premises. The prior "
            f"monthly rent was {_money(float(m['prior_rent']))}. The rent stated "
            f"above reflects an increase of {shown_incr:.2f}%, which does "
            f"not exceed the lesser of five percent (5%) or the applicable "
            f"Consumer Price Index differential permitted under {ho['increase_section']} "
            f"of the {m['municipality']} Rent Control Ordinance, rounded to the "
            f"nearest dollar.")
    articles.append(("4. RENT", rent_paras))

    grace = NJ["senior_grace_business_days"]
    articles.append(("5. LATE CHARGE", [
        f"If any installment of rent is not received by the "
        f"{_ordinal(m['late_after_day'])} day of the month, Tenant shall pay a "
        f"late charge of {_money(m['late_fee'])}, which the parties agree shall "
        f"be deemed additional rent and recoverable as rent in any proceeding "
        f"for possession or for a money judgment. A Tenant who is a senior "
        f"citizen or a recipient of Social Security benefits shall be allowed a "
        f"grace period of five ({grace}) business days before any late charge "
        f"is imposed (N.J.S.A. 2A:42-6.1). A charge of $25.00 shall apply to "
        f"any dishonored check (N.J.S.A. 2A:32A-1).",
    ]))

    articles.append(("6. ATTORNEY'S FEES", [
        "In the event Landlord commences any action to enforce this Lease or "
        "to recover possession of the Premises, Tenant shall pay Landlord's "
        "reasonable attorney's fees and court costs actually incurred, which "
        "the parties expressly agree shall be recoverable as additional rent.",
        "<b>NOTICE: If the Tenant is successful in any action or summary "
        "proceeding arising out of this Lease, the Tenant shall recover "
        "attorney's fees or expenses, or both, from the Landlord to the same "
        "extent that the Landlord is entitled to recover attorney's fees or "
        "expenses, or both, under this Lease (N.J.S.A. 2A:18-61.66 and "
        "2A:18-61.67).</b>",
    ]))

    # -- security deposit: computed, and invested by unit count ------------
    invest = (
        f"Because the building contains ten (10) or more dwelling units, "
        f"Landlord shall invest the deposit in an insured money market fund or "
        f"account as required by N.J.S.A. 46:8-19(a)."
        if m["large_building"] else
        f"Landlord shall deposit the security in an interest-bearing account "
        f"as required by N.J.S.A. 46:8-19(b).")
    articles.append(("7. SECURITY DEPOSIT", [
        f"Tenant has deposited {_money(deposit)} with Landlord as security for "
        f"the faithful performance of this Lease. This sum does not exceed one "
        f"and one-half (1.5) times one month's rent, the maximum permitted by "
        f"the Rent Security Deposit Act, N.J.S.A. 46:8-19 et seq. The deposit "
        f"is held in trust, shall not be commingled with Landlord's own funds, "
        f"and remains the property of Tenant. {invest}",
        f"Within thirty (30) days of receipt of the deposit, and again at each "
        f"annual interest payment, Landlord shall furnish Tenant with the "
        f"written notice required by N.J.S.A. 46:8-19(c), stating the name and "
        f"address of the banking institution, the type of account, the current "
        f"rate of interest, and the amount of the deposit. Interest earned "
        f"belongs to Tenant and shall be paid to Tenant or credited toward rent "
        f"on each anniversary of the Term.",
    ]))

    articles.append(("8. UTILITIES", [
        "Tenant shall pay for electricity and cooking gas serving the Premises, "
        "and shall place such accounts in Tenant's name as of the commencement "
        "of the Term. Landlord shall furnish heat, hot water, and water and "
        "sewer service. Tenant shall not permit any utility to be discontinued.",
    ]))

    articles.append(("9. SUBLETTING AND ASSIGNMENT", [
        "Tenant shall not sublet the Premises or assign this Lease, in whole or "
        "in part, without the prior written consent of Landlord, which consent "
        "shall not be unreasonably withheld. Any purported sublet or assignment "
        "without such consent is void.",
    ]))

    articles.append(("10. KEYS", [
        "Landlord has furnished Tenant with keys to the Premises and the "
        "building entrances. Tenant shall provide Landlord with a duplicate of "
        "any lock Tenant is permitted to install and shall return all keys upon "
        "surrender of the Premises. Tenant shall not add or change any lock "
        "without Landlord's prior written consent.",
    ]))

    articles.append(("11. RENTER'S INSURANCE", [
        "Tenant shall obtain and maintain, at Tenant's expense, renter's "
        "(tenant's contents) insurance with personal liability coverage of not "
        "less than $100,000 for the Term, and shall provide Landlord with "
        "evidence of such coverage upon request. Landlord's insurance does not "
        "cover Tenant's personal property.",
    ]))

    pet_txt = (
        "Tenant may keep the household pet(s) disclosed to and approved by "
        "Landlord in writing, subject to the Rules and Regulations. "
        if m["pets_allowed"] else
        "No dog, cat, or other animal shall be kept in the Premises without "
        "Landlord's prior written consent. ")
    articles.append(("12. PETS", [
        pet_txt +
        "This provision does not apply to a service or assistance animal "
        "required by a person with a disability, for which no pet fee or pet "
        "deposit shall be charged (N.J.S.A. 10:5-29.2).",
    ]))

    articles.append(("13. LANDLORD'S RIGHT OF ENTRY", [
        "Landlord and its agents may enter the Premises upon reasonable notice "
        "(except in an emergency, when no notice is required) to inspect, make "
        "repairs or improvements, supply services, or show the Premises to "
        "prospective tenants, purchasers, or lenders. Landlord shall conduct "
        "any such entry so as to minimize interference with Tenant's use.",
    ]))

    articles.append(("14. MAINTENANCE AND CONDITION", [
        "Tenant shall keep the Premises clean and in good condition, shall not "
        "commit waste or permit any nuisance, and shall be responsible for "
        "damage caused by Tenant, Tenant's household, or Tenant's guests, "
        "ordinary wear and tear excepted. Landlord shall maintain the building "
        "structure, systems, and common areas in accordance with the New Jersey "
        "Hotel and Multiple Dwelling Law and applicable housing codes.",
    ]))

    articles.append(("15. FIRE, CASUALTY AND CONDEMNATION", [
        "If the Premises are rendered untenantable by fire or other casualty "
        "not caused by Tenant, rent shall abate proportionately until the "
        "Premises are restored, and either party may terminate this Lease if "
        "the Premises cannot reasonably be restored within ninety (90) days. If "
        "all or a material part of the Premises is taken by condemnation or "
        "eminent domain, this Lease terminates as of the date of taking, and the "
        "entire condemnation award belongs to Landlord.",
    ]))

    articles.append(("16. DEFAULT AND REMEDIES", [
        "If Tenant fails to pay rent when due, or breaches any other covenant of "
        "this Lease, Landlord may pursue any remedy available under the New "
        "Jersey Anti-Eviction Act, N.J.S.A. 2A:18-61.1 et seq., including a "
        "summary proceeding for possession, only upon the notice that Act "
        "requires. Rent is due independent of any claim Tenant may assert, "
        "except as the implied warranty of habitability and applicable law "
        "provide. No waiver of a default is a waiver of any later default, and "
        "acceptance of rent with knowledge of a default is not a waiver of it.",
    ]))

    articles.append(("17. HOLDOVER", [
        "If Tenant remains in possession after the end of the Term without a "
        "renewal, Tenant becomes a month-to-month tenant subject to all the "
        "terms of this Lease, at the rent then in effect as adjusted by any "
        "increase the Rent Control Ordinance permits, until either party "
        "terminates the tenancy on the notice required by law. This provision "
        "does not waive Landlord's rights under the Anti-Eviction Act.",
    ]))

    articles.append(("18. QUIET ENJOYMENT", [
        "So long as Tenant performs the covenants of this Lease, Tenant shall "
        "have quiet enjoyment of the Premises without interference by Landlord, "
        "subject to the terms of this Lease and to the rights of the holder of "
        "any mortgage on the building.",
    ]))

    articles.append(("19. RULES AND REGULATIONS", [
        "Tenant has received and agrees to comply with the Rules and "
        "Regulations of the Building attached as Exhibit A, which Landlord may "
        "amend from time to time upon reasonable notice. The Rules and "
        "Regulations are incorporated into and made part of this Lease.",
    ]))

    articles.append(("20. NOTICES", [
        f"All notices under this Lease shall be in writing and delivered "
        f"personally or by certified mail: to Landlord at "
        f"{m['managing_agent_addr'][0]}, {m['managing_agent_addr'][1]}, and to "
        f"Tenant at the Premises. Notice is effective on personal delivery or "
        f"three (3) days after mailing.",
    ]))

    articles.append(("21. SUBORDINATION AND ESTOPPEL", [
        "This Lease is subordinate to any mortgage now or later placed on the "
        "building and to any renewal or replacement of it. Tenant shall, within "
        "ten (10) days of request, execute an estoppel certificate stating the "
        "status of this Lease and the rent and deposit paid.",
    ]))

    articles.append(("22. ENTIRE AGREEMENT; SEVERABILITY", [
        "This Lease, together with the disclosures and Exhibit A attached, is "
        "the entire agreement between the parties and supersedes all prior "
        "understandings. It may be amended only in a writing signed by both "
        "parties. If any provision is held unenforceable, the remaining "
        "provisions remain in effect.",
    ]))

    articles.append(("23. GOVERNING LAW", [
        f"This Lease is governed by the laws of the State of New Jersey and by "
        f"the {m['municipality']} Rent Control Ordinance, {ho['chapter']} of "
        f"the {m['municipality']} Municipal Code. Any provision of this Lease "
        f"that conflicts with those laws is void to the extent of the conflict, "
        f"and the remainder of the Lease remains in effect.",
    ]))

    # -- disclosures / addenda, each its own page-ish section --------------
    disclosures = []
    disclosures.append(_hoboken_disclosure(m))
    disclosures.append(_flood_notice(m, flood_area))
    if m["pre_1978"]:
        disclosures.append(_lead_disclosure(m))
    disclosures.append(_truth_in_renting(m))
    disclosures.append(_window_guard(m))
    disclosures.append(_bed_bug(m))
    disclosures.append(_domestic_violence(m))
    disclosures.append(_rules(m))

    return {"articles": articles, "disclosures": disclosures,
            "landlord": landlord, "tenants": m["tenants"],
            "leasing_agent": m["leasing_agent"], "premises": addr,
            "signed_date": _date(m["term_start"])}


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _hoboken_disclosure(m: dict) -> tuple:
    ho = m["municipality_world"]
    base = (f"the base rent level received by the Landlord as of "
            f"{ho['base_rent_date']}" if m["existed_at_base"] else
            f"the first legal rent charged for this dwelling unit after "
            f"{ho['base_rent_date']}")
    return ("HOBOKEN RENT CONTROL DISCLOSURE STATEMENT", [
        f"This dwelling unit is subject to the {m['municipality']} Rent Control "
        f"Ordinance, {ho['chapter']}. This Disclosure Statement is furnished "
        f"pursuant to {ho['disclosure_section']} of the Ordinance and is to be "
        f"signed and dated by the Tenant and filed by the Landlord with the "
        f"Rent Regulation Officer.",
        f"LEGAL RENT. The rent for this unit is controlled at {base}, as "
        f"adjusted by the increases the Ordinance permits. Tenant has the right "
        f"to request a legal rent calculation from the Rent Regulation Officer "
        f"to determine the legal base rent for this unit.",
        f"TWO-YEAR BAR. A failure to request a legal rent calculation within "
        f"two (2) years of service of this Disclosure Statement will result in "
        f"a bar of any refund or credit of an excess or overpayment of rent.",
        f"REGISTRATION. A copy of the Landlord's current rent registration "
        f"statement is on file with the {ho['registration_office']} and is "
        f"available to Tenant upon request.",
        f"TRUTH IN RENTING. Landlord advises Tenant of the Truth-in-Renting "
        f"Act, N.J.S.A. 46:8-43 et seq., and of the statement prepared "
        f"thereunder, which may be obtained from the New Jersey Department of "
        f"Community Affairs, Division of Codes and Standards, Landlord-Tenant "
        f"Information Service, {NJ['dca_address']}.",
    ])


def _flood_notice(m: dict, area_answer: str) -> tuple:
    return ("FLOOD RISK NOTICE", [
        "This notice is provided under N.J.S.A. 46:8-50. The answers below are "
        "given to the best of Landlord's actual knowledge.",
        f"Is the dwelling unit or the building located in a FEMA Special Flood "
        f"Hazard Area or Moderate Risk Flood Hazard Area? {area_answer}.",
        f"Has the dwelling unit or building experienced flood damage, water "
        f"seepage, or pooled water due to a natural flood event? "
        f"{m['flood_history']}.",
        "Flood insurance may be available to renters through the Federal "
        "Emergency Management Agency's National Flood Insurance Program to "
        "cover Tenant's personal property against flood loss. Tenant's renter's "
        "insurance policy may not cover losses due to flooding. Tenant is "
        "encouraged to obtain flood insurance for personal property.",
        "If Landlord fails to make the disclosures required by this section and "
        "Tenant later becomes aware that the Premises are in a Special or "
        "Moderate Risk Flood Hazard Area, Tenant may terminate this Lease.",
    ])


def _lead_disclosure(m: dict) -> tuple:
    li = _person_initials(m["leasing_agent"])   # landlord agent initials
    ti = _person_initials(m["tenants"][0])      # tenant initials
    ini = lambda x: f'<font face="Times-Italic">[{x}]</font>'
    return ("LEAD-BASED PAINT DISCLOSURE", [
        f"This building was constructed in {m['building_year']}. This "
        f"disclosure is required by the federal Residential Lead-Based Paint "
        f"Hazard Reduction Act, 42 U.S.C. 4852d, and its implementing "
        f"regulations at 40 C.F.R. Part 745, as well as N.J.A.C. 5:10-6.6.",
        "<b>WARNING STATEMENT:</b> Housing built before 1978 may contain "
        "lead-based paint. Lead from paint, paint chips, and dust can pose "
        "health hazards if not managed properly. Lead exposure is especially "
        "harmful to young children and pregnant women.",
        f"LESSOR'S DISCLOSURE (Landlord's initials): (a) Landlord has no "
        f"knowledge of lead-based paint or lead-based paint hazards in the "
        f"Premises. {ini(li)}   (b) Landlord has no reports or records "
        f"pertaining to lead-based paint or lead-based paint hazards in the "
        f"Premises. {ini(li)}",
        f"LESSEE'S ACKNOWLEDGMENT (Tenant's initials): Tenant has received "
        f"copies of any information listed above and the EPA-approved pamphlet "
        f"\"Protect Your Family From Lead in Your Home.\" {ini(ti)}",
    ])


def _truth_in_renting(m: dict) -> tuple:
    return ("TRUTH IN RENTING ACKNOWLEDGMENT", [
        f"Because this building contains more than two dwelling units and is "
        f"not owner-occupied, Landlord is required to distribute the New Jersey "
        f"Truth in Renting statement (N.J.S.A. 46:8-44 to -46). Tenant "
        f"acknowledges receipt of the current edition of the Truth in Renting "
        f"statement, which describes the rights and responsibilities of tenants "
        f"and landlords in New Jersey and may be obtained from the Department "
        f"of Community Affairs at {NJ['dca_address']}.",
    ])


def _window_guard(m: dict) -> tuple:
    return ("WINDOW GUARD NOTICE", [
        "The owner (Landlord) is required by law to install window guards in "
        "the Premises if a child or children ten (10) years of age or younger "
        "reside there, upon the written request of the Tenant (N.J.A.C. "
        "5:10-27.1). Window guards are not required in a first-floor window or "
        "a window giving access to a fire escape.",
    ])


def _bed_bug(m: dict) -> tuple:
    return ("BED BUG NOTICE", [
        "Landlord and Tenant each have responsibilities for the control of bed "
        "bugs in multiple dwellings (N.J.A.C. 5:10-10.2). Tenant shall promptly "
        "notify Landlord in writing of any suspected bed bug infestation and "
        "shall cooperate with inspection and treatment. Landlord shall arrange "
        "for the inspection and treatment of the Premises by a qualified "
        "exterminator.",
    ])


def _domestic_violence(m: dict) -> tuple:
    return ("DOMESTIC VIOLENCE LEASE TERMINATION", [
        "A Tenant who is a victim of domestic violence, or whose child is a "
        "victim, may terminate this Lease upon written notice to Landlord "
        "certifying that the Tenant or child faces an imminent threat of "
        "serious physical harm, together with the documentation required by "
        "N.J.S.A. 46:8-9.6 to -9.7. The Tenant is then liable only for rent "
        "owed through the termination date plus not more than one month's rent.",
    ])


def _rules(m: dict) -> tuple:
    return ("EXHIBIT A — RULES AND REGULATIONS OF THE BUILDING", [
        "1. Quiet enjoyment. Tenant shall not make or permit noise that "
        "disturbs other residents between 10:00 p.m. and 8:00 a.m.",
        "2. Common areas. Hallways, stairs, lobby, and the roof deck shall not "
        "be obstructed and shall be used only for their intended purposes.",
        "3. Refuse and recycling. Refuse and recyclables shall be sorted and "
        "deposited only in the designated areas, in accordance with City of "
        "Hoboken collection rules.",
        "4. Alterations. Tenant shall not paint, wallpaper, or make structural "
        "alterations without Landlord's prior written consent.",
        "5. Deliveries and moving. Move-in and move-out shall be scheduled with "
        "the managing agent and shall use the service entrance and elevator.",
        "6. Building systems. Tenant shall not tamper with heating, sprinkler, "
        "fire-alarm, or intercom systems, and shall report any malfunction to "
        "the managing agent promptly.",
    ])


# ---------------------------------------------------------------------------
# Rendering — born-digital vector PDF, finished through the shared forensic
# tail so the metadata chronology and xref stay correct.
# ---------------------------------------------------------------------------

_TITLE = ParagraphStyle("t", fontName="Times-Bold", fontSize=13.5,
                        alignment=TA_CENTER, leading=17, spaceAfter=4)
_SUBTITLE = ParagraphStyle("st", fontName="Times-Roman", fontSize=9.5,
                           alignment=TA_CENTER, leading=12, spaceAfter=14)
_H = ParagraphStyle("h", fontName="Times-Bold", fontSize=10.5, leading=13,
                    spaceBefore=11, spaceAfter=4)
_BODY = ParagraphStyle("b", fontName="Times-Roman", fontSize=10, leading=13.5,
                       alignment=TA_JUSTIFY, spaceAfter=7)
# The flood notice statute requires not less than 12-point type.
_FLOOD = ParagraphStyle("f", parent=_BODY, fontSize=12, leading=15.5)
_SIG = ParagraphStyle("s", fontName="Times-Roman", fontSize=10, leading=22)
# The adopted e-signature: the signer's actual NAME set in an italic face —
# legible and name-specific, the opposite of the round-2 name-agnostic scrawl.
_ESIGN_NAME = ParagraphStyle("en", fontName="Times-Italic", fontSize=17,
                             leading=20, textColor=colors.HexColor("#12203c"))
_ESIGN_META = ParagraphStyle("em", fontName="Helvetica", fontSize=7,
                             leading=9, textColor=colors.HexColor("#5a5a5a"))
_CERT_H = ParagraphStyle("ch", fontName="Helvetica-Bold", fontSize=11,
                         leading=14, spaceAfter=6)
_CERT = ParagraphStyle("c", fontName="Helvetica", fontSize=8.5, leading=12,
                       spaceAfter=5)


def _make_canvas(footer_title: str, initials: str):
    """A numbered canvas: a two-pass 'Page X of Y' footer, deterministic under
    invariant=1. Producer/creator (the management system's, not reportlab's
    default — an export string is metadata a reader checks) are set in a page
    callback during build, so they persist through the replay. `initials`
    stamps the executing tenant's initials on each page — an executed lease
    is initialed, and a blank initials block on a signed lease was the round-1
    forensic tell."""
    class _NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *a, **k):
            k["invariant"] = 1
            super().__init__(*a, **k)
            self._saved = []

        def showPage(self):
            self._saved.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved)
            for i, state in enumerate(self._saved, 1):
                self.__dict__.update(state)
                self._footer(i, total)
                super().showPage()
            super().save()

        def _footer(self, page: int, total: int):
            self.saveState()
            self.setStrokeGray(0.6)
            self.setLineWidth(0.5)
            self.line(0.9 * inch, 0.62 * inch, PAGE_W - 0.9 * inch, 0.62 * inch)
            self.setFont("Times-Roman", 8)
            self.setFillGray(0.35)
            self.drawString(0.9 * inch, 0.48 * inch, footer_title)
            self.drawCentredString(PAGE_W / 2, 0.48 * inch,
                                   f"Page {page} of {total}")
            self.drawRightString(PAGE_W - 0.9 * inch, 0.48 * inch,
                                 f"Tenant initials: {initials}")
            self.restoreState()
    return _NumberedCanvas


def _initials(tenants: list[str]) -> str:
    """The primary tenant's initials, e-sign style, for the per-page block."""
    return " / ".join("".join(w[0] for w in t.split()[:2]) for t in tenants)


def _esign_block(signer: dict) -> list:
    """One adopted e-signature, ONE convention for every party. A bordered
    stamp: 'Signed electronically by', the signer's name in an italic hand, and
    the platform's signature id / timestamp / IP. No wet-ink image, so there is
    no name-agnostic scrawl and no shared hand — the round-2 disqualifiers."""
    inner = [
        [Paragraph("Signed electronically by:", _ESIGN_META)],
        [Paragraph(signer["name"], _ESIGN_NAME)],
        [Paragraph(f"{signer['role']}<br/>Signature ID {signer['id']}<br/>"
                   f"Signed {signer['signed_at']} &nbsp;·&nbsp; "
                   f"IP {signer['ip']}", _ESIGN_META)],
    ]
    t = Table(inner, colWidths=[3.5 * inch])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9aa4b8")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f6fb")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    t.hAlign = "LEFT"
    return [t, Spacer(1, 12)]


def _certificate_flowables(esign: dict, title: str) -> list:
    """The certificate of completion — the audit trail a real e-signed document
    carries. Its presence is what makes the whole execution model consistent:
    one platform, every signer accounted for, sealed under NJ UETA."""
    out = [PageBreak(),
           Paragraph("CERTIFICATE OF COMPLETION", _CERT_H),
           Paragraph(f"Envelope ID: {esign['envelope_id']}", _CERT),
           Paragraph(f"Document: {title}", _CERT),
           Paragraph("Status: <b>Completed</b>", _CERT),
           Spacer(1, 6),
           Paragraph("<b>Signers</b>", _CERT)]
    for s in esign["signers"]:
        out.append(Paragraph(
            f"&nbsp;&nbsp;{s['name']} — {s['role']}<br/>"
            f"&nbsp;&nbsp;&nbsp;&nbsp;Signature ID {s['id']} &nbsp;·&nbsp; "
            f"Signed {s['signed_at']} &nbsp;·&nbsp; IP {s['ip']}", _CERT))
    out.append(Spacer(1, 8))
    out.append(Paragraph(
        f"This record was created and sealed by {esign['platform']} in "
        f"accordance with the New Jersey Uniform Electronic Transactions Act, "
        f"N.J.S.A. 12A:12-1 et seq. Under that Act an electronic signature has "
        f"the same legal effect as a handwritten signature. Each signer adopted "
        f"the signature shown above and consented to transact electronically.",
        _CERT))
    return out


def render_lease(model: dict, *, metadata: dict,
                 defect: dict | None = None) -> bytes:
    """Render the lease as a born-digital vector PDF."""
    comp = compose_lease(model, defect)
    title = (f"Residential Lease — {model['building_name']}, "
             f"Apt {model['unit']}")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.9 * inch, rightMargin=0.9 * inch,
        topMargin=0.85 * inch, bottomMargin=0.8 * inch, title=title)

    def _meta(canv, _doc):
        canv.setProducer(metadata["producer"])
        canv.setCreator(metadata["creator"])
        canv.setTitle(title)

    story: list = [
        Paragraph("RESIDENTIAL LEASE AGREEMENT", _TITLE),
        Paragraph(f"{model['building_name']} &nbsp;·&nbsp; {model['street']}, "
                  f"Apartment {model['unit']} &nbsp;·&nbsp; "
                  f"{model['municipality']}, New Jersey {model['zip']}", _SUBTITLE),
    ]
    for heading, paras in comp["articles"]:
        story.append(Paragraph(heading.replace("&", "&amp;"), _H))
        for p in paras:
            story.append(Paragraph(p.replace("&", "&amp;"), _BODY))

    # execution block — ONE convention (adopted e-signatures) for every party.
    esign = model["esign"]
    story.append(Paragraph("IN WITNESS WHEREOF, the parties have executed this "
                           "Lease as of the date first written above, adopting "
                           "the electronic signatures below.", _BODY))
    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>LANDLORD:</b> " + comp["landlord"], _BODY))
    agent = esign["signers"][-1]                 # roster puts the agent last
    story += _esign_block(agent)
    story.append(Paragraph("<b>TENANT(S):</b>", _BODY))
    for s in esign["signers"][:-1]:
        story += _esign_block(s)

    # disclosures / addenda — each acknowledged by the tenant's adopted
    # e-signature (name + date), same convention as the signature page.
    ack_names = " and ".join(comp["tenants"])
    for heading, paras in comp["disclosures"]:
        story.append(PageBreak())
        story.append(Paragraph(heading.replace("&", "&amp;"), _H))
        style = _FLOOD if heading == "FLOOD RISK NOTICE" else _BODY
        for p in paras:
            story.append(Paragraph(p.replace("&", "&amp;"), style))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            f'Acknowledged by Tenant: '
            f'<font face="Times-Italic">{ack_names}</font> '
            f'&nbsp;&nbsp;&nbsp; Date: {comp["signed_date"]}', _SIG))

    # certificate of completion — the audit trail that seals the e-sign model
    story += _certificate_flowables(esign, title)

    doc.build(story, onFirstPage=_meta, onLaterPages=_meta,
              canvasmaker=_make_canvas(title, _initials(comp["tenants"])))
    out = legalpdf._fix_dates(buf.getvalue(), created=metadata.get("created"),
                              modified=metadata.get("modified"))
    return legalpdf._fix_id(out)
