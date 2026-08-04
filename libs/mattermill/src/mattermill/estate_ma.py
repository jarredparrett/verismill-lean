"""Seeded Massachusetts estate-planning and contested-probate packets.

The class renders a coordinated production set rather than one long document:
will, revocable-trust restatement, funding instruments, intent memorandum,
capacity evidence, execution notes, inventory, formal-probate petition,
objection, and settlement/no-contest analysis. Caller canon supplies the world;
the emitter supplies only deterministic texture.
"""

from __future__ import annotations

import datetime as _dt
import io
import random

from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as rl_canvas

from . import assets, legalpdf


PAGE_W, PAGE_H = letter
LEFT, RIGHT = 68.0, 544.0
TOP, BOTTOM = 724.0, 66.0
USABLE = RIGHT - LEFT


DEFAULT_CANON = {
    "decedent": "Edward Vale",
    "beneficiary": "Maya Serrano",
    "attorney": "Peter Halden",
    "attorney_assistant": "Ellen Shaw",
    "independent_fiduciary": "Marian Holt",
    "estate_counsel": "Eleanor Pike",
    "beneficiary_counsel": "Thomas Carver",
    "company_secretary": "Dana Mercer",
    "company": "Vale House Press, Inc.",
    "company_short": "Vale House Press",
    "home_address": "17 Orchard Rise",
    "municipality": "Marlowe",
    "state": "Massachusetts",
    "county": "Norfolk",
    "postal_code": "02090",
    "trust_name": "The Edward Vale Revocable Trust",
    "trust_original_date": "2012-06-14",
    "execution_date": "2019-11-01",
    "death_date": "2019-11-08",
    "petition_date": "2019-12-16",
    "settlement_date": "2020-04-10",
    "age": 85,
    "marital_status": "widower",
    "liquid_assets": 60000000,
    "company_shares": 1000,
    "company_share_class": "Common Stock",
    "copyright_scope": (
        "all copyrights and renewal, termination, royalty, and enforcement "
        "interests owned by Edward Vale in every published and unpublished "
        "literary work in the Vale House Press catalog"
    ),
    "copyright_catalog": [
        {"title": "The Last Cipher", "year": 1984},
        {"title": "The Ivory Knife", "year": 1989},
        {"title": "Midnight at Blackwood", "year": 1994},
        {"title": "A Killing in the Orchard", "year": 2001},
        {"title": "The Glass Stair", "year": 2008},
        {"title": "The Hollow Key", "year": 2016},
    ],
    "family": [
        {"name": "Clara Vale North", "relationship": "daughter",
         "heir_at_law": True},
        {"name": "Martin Vale", "relationship": "son",
         "heir_at_law": True},
        {"name": "Julian Vale", "relationship": "predeceased son",
         "heir_at_law": False},
        {"name": "Nora Vale", "relationship": "granddaughter and issue of "
         "predeceased Julian Vale", "heir_at_law": True},
        {"name": "Adrian North", "relationship": "grandson through living "
         "daughter Clara", "heir_at_law": False},
        {"name": "Thomas Vale", "relationship": "grandson through living "
         "son Martin", "heir_at_law": False},
        {"name": "Leah Vale", "relationship": "widow of predeceased son "
         "Julian", "heir_at_law": False},
    ],
}

_CANON_KEYS = frozenset(DEFAULT_CANON)

_WITNESS_PAIRS = [
    ("Helen Ortiz", "Samuel Greer"),
    ("Irene Kwan", "Philip Morse"),
    ("Dana Lowell", "Marcus Bell"),
]
_NOTARIES = ["Rachel Imes", "Victor Chen", "Andrea Foley"]
_PHYSICIANS = ["Evelyn Moore, M.D.", "Nathan Cole, M.D.",
               "Priya Shah, M.D."]
_OBJECTOR_COUNSEL = ["Barron & Pike LLP", "Lowell, Dane & Frost LLP",
                     "Carver and Holt LLP"]


def _date(value: str) -> _dt.date:
    return _dt.date.fromisoformat(value)


def _fmt(value: str | _dt.date) -> str:
    d = _date(value) if isinstance(value, str) else value
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def _add_months(value: _dt.date, months: int) -> _dt.date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, (_dt.date(year + (month == 12), month % 12 + 1, 1)
                          - _dt.timedelta(days=1)).day)
    return _dt.date(year, month, day)


def _money(value: int | float) -> str:
    return f"${value:,.0f}"


def _stable_hash(text: str) -> int:
    value = 0
    for char in text:
        value = (value * 131 + ord(char)) % 1000003
    return value


def sample_estate(rng: random.Random, *, canon: dict | None = None,
                  pins: dict | None = None) -> dict:
    """Sample document texture around a complete caller-supplied world."""
    canon = dict(DEFAULT_CANON if canon is None else canon)
    missing = _CANON_KEYS - set(canon)
    if missing:
        raise ValueError(f"canon missing required keys: {sorted(missing)}")
    pins = dict(pins or {})

    execution = _date(canon["execution_date"])
    death = _date(canon["death_date"])
    petition = _date(canon["petition_date"])
    settlement = _date(canon["settlement_date"])
    if not execution < death <= petition <= settlement:
        raise ValueError("canon dates must satisfy execution < death <= petition <= settlement")
    if death.year != 2019:
        raise ValueError("estate_packet_ma currently sources the 2019 Massachusetts world")
    if canon["company_shares"] <= 0 or canon["liquid_assets"] <= 0:
        raise ValueError("company shares and liquid assets must be positive")
    if not any(person.get("heir_at_law") for person in canon["family"]):
        raise ValueError("canon must identify at least one heir at law")

    witness_1, witness_2 = rng.choice(_WITNESS_PAIRS)
    probate_cash = int(round(canon["liquid_assets"] * rng.uniform(.045, .075), -3))
    model = {
        **canon,
        "pins": pins,
        "witness_1": witness_1,
        "witness_2": witness_2,
        "notary": rng.choice(_NOTARIES),
        "physician": rng.choice(_PHYSICIANS),
        "objector_counsel": rng.choice(_OBJECTOR_COUNSEL),
        "house_value": int(round(rng.uniform(6_500_000, 10_500_000), -4)),
        "company_value": int(round(rng.uniform(85_000_000, 145_000_000), -5)),
        "copyright_value": int(round(rng.uniform(24_000_000, 48_000_000), -5)),
        "personal_effects": int(round(rng.uniform(900_000, 2_400_000), -4)),
        "royalties_receivable": int(round(rng.uniform(700_000, 1_800_000), -4)),
        "probate_cash": probate_cash,
        "settlement_fraction": rng.choice([0.02, 0.025, 0.03]),
        "notary_expiry": execution.replace(year=execution.year + 4),
        "instruction_date": execution - _dt.timedelta(days=24),
        "review_date": execution - _dt.timedelta(days=10),
        "draft_date": execution - _dt.timedelta(days=4),
        "objection_date": petition + _dt.timedelta(days=3),
        "assembly_date": settlement + _dt.timedelta(days=1),
        "signature_salt": rng.randint(1000, 9999),
        "bates_prefix": pins.get("bates_prefix", "ESTATE-"),
    }
    return model


def compute_assets(model: dict) -> dict:
    """Compute every inventory bucket and total from the sampled facts."""
    trust_cash = model["liquid_assets"] - model["probate_cash"]
    trust_rows = [
        ("Residence", model["house_value"]),
        ("Publishing-company stock", model["company_value"]),
        ("Author-owned catalog copyrights", model["copyright_value"]),
        ("Cash and marketable investments", trust_cash),
    ]
    probate_rows = [
        ("Cash and marketable investments", model["probate_cash"]),
        ("Tangible personal property", model["personal_effects"]),
        ("Accrued author royalties", model["royalties_receivable"]),
    ]
    trust_total = sum(value for _, value in trust_rows)
    probate_total = sum(value for _, value in probate_rows)
    gross = trust_total + probate_total
    settlement_offer = int(round(
        model["liquid_assets"] * model["settlement_fraction"], -3))
    reserve = int(round(gross * .018, -3))
    return {
        "trust_cash": trust_cash,
        "trust_rows": trust_rows,
        "probate_rows": probate_rows,
        "trust_total": trust_total,
        "probate_total": probate_total,
        "gross_total": gross,
        "settlement_offer": settlement_offer,
        "administration_reserve": reserve,
    }


def compute_tax_projection(model: dict) -> dict:
    """Derive a conservative planning reserve from the one asset model.

    This is a liquidity memorandum, not a filed return. The federal estimate
    uses the 2019 $11.4 million exclusion and 40 percent top-rate equivalent;
    the Massachusetts amount is a deliberately conservative 16 percent
    planning reserve pending preparation of Form M-706.
    """
    assets = compute_assets(model)
    taxable = max(0, assets["gross_total"] - assets["administration_reserve"])
    federal = int(round(max(0, taxable - 11_400_000) * .40, -3))
    massachusetts = int(round(max(0, taxable - 1_000_000) * .16, -3))
    income_tax = int(round(assets["gross_total"] * .01, -3))
    total = federal + massachusetts + assets["administration_reserve"] + income_tax
    shortfall = max(0, total - model["liquid_assets"])
    closely_held_ratio = model["company_value"] / assets["gross_total"]
    return {
        "taxable_estate": taxable,
        "federal_estate_tax": federal,
        "massachusetts_estate_tax_reserve": massachusetts,
        "income_tax_reserve": income_tax,
        "total_reserve": total,
        "liquid_assets": model["liquid_assets"],
        "liquidity_shortfall": shortfall,
        "closely_held_ratio": closely_held_ratio,
        "section_6166_candidate": closely_held_ratio > .35,
    }


STYLES = {
    "cover": {"body": ("Times-Roman", 11), "bold": ("Times-Bold", 11),
              "head": ("Times-Bold", 12), "lead": 15},
    "instrument": {"body": ("Times-Roman", 10.5),
                   "bold": ("Times-Bold", 10.5),
                   "head": ("Times-Bold", 11.5), "lead": 14.2},
    "medical": {"body": ("Helvetica", 10),
                "bold": ("Helvetica-Bold", 10),
                "head": ("Helvetica-Bold", 11), "lead": 13.5},
    "notes": {"body": ("Courier", 8.8), "bold": ("Courier-Bold", 8.8),
              "head": ("Courier-Bold", 9.4), "lead": 11.5},
    "court": {"body": ("Times-Roman", 9.5), "bold": ("Times-Bold", 9.5),
              "head": ("Times-Bold", 10.5), "lead": 12.4},
    "letter": {"body": ("Times-Roman", 10.5),
               "bold": ("Times-Bold", 10.5),
               "head": ("Times-Bold", 11.5), "lead": 14.2},
}


def _wrap(text: str, font: tuple[str, float], width: float) -> list[str]:
    name, size = font
    lines: list[str] = []
    current = ""
    for word in str(text).split():
        candidate = f"{current} {word}" if current else word
        if current and pdfmetrics.stringWidth(candidate, name, size) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


class _Composer:
    def __init__(self):
        self.lines: list[dict] = []
        self.style = "instrument"
        self.document = "File index"

    @property
    def s(self):
        return STYLES[self.style]

    def source(self, style: str):
        self.style = style

    def new_document(self, number: int, title: str, style: str = "instrument"):
        self.lines.append({"newpage": True, "document": title,
                           "document_no": number})
        self.style = style
        self.document = title

    def text(self, text: str = "", *, bold: bool = False, align: str = "l",
             indent: float = 0, font: tuple[str, float] | None = None,
             lead: float | None = None):
        self.lines.append({"text": text,
                           "font": font or (self.s["bold"] if bold else self.s["body"]),
                           "align": align, "indent": indent,
                           "lead": lead or self.s["lead"]})

    def para(self, text: str, *, bold: bool = False, indent: float = 0,
             after: float = 6, font: tuple[str, float] | None = None):
        selected = font or (self.s["bold"] if bold else self.s["body"])
        for line in _wrap(text, selected, USABLE - indent):
            self.text(line, indent=indent, font=selected)
        if after:
            self.space(after)

    def numbered(self, label: str, text: str, *, after: float = 6):
        width = 28.0
        lines = _wrap(text, self.s["body"], USABLE - width)
        self.lines.append({"hang": (label, lines[0]), "font": self.s["body"],
                           "width": width, "lead": self.s["lead"]})
        for line in lines[1:]:
            self.text(line, indent=width)
        self.space(after)

    def heading(self, text: str, *, align: str = "l"):
        self.space(7)
        self.text(text, bold=True, align=align, font=self.s["head"])
        self.space(3)

    def title(self, text: str, subtitle: str | None = None):
        self.text(text, bold=True, align="c", font=(self.s["head"][0], 14))
        if subtitle:
            self.text(subtitle, align="c")
        self.space(12)

    def space(self, points: float = 8):
        self.lines.append({"space": points, "lead": points})

    def rule(self):
        self.lines.append({"rule": True, "lead": 7})

    def ensure(self, height: float):
        self.lines.append({"ensure": height, "lead": 0})

    def row(self, cells: list[str], widths: list[float], *, bold: bool = False,
            aligns: list[str] | None = None, font: tuple[str, float] | None = None):
        self.lines.append({"row": cells, "widths": widths,
                           "font": font or (self.s["bold"] if bold else self.s["body"]),
                           "aligns": aligns or ["l"] * len(cells),
                           "lead": self.s["lead"]})

    def signature(self, name: str, role: str, key: str):
        self.lines.append({"signature": (name, role, key), "lead": 66})

    def notary_seal(self, name: str, expiry: _dt.date):
        self.lines.append({"notary_seal": (name, _fmt(expiry)), "lead": 82})


def _named_family(model: dict, *, include_predeceased: bool = False) -> list[dict]:
    return [p for p in model["family"]
            if include_predeceased
            or not p["relationship"].lower().startswith("predeceased")]


def _heirs(model: dict) -> list[dict]:
    return [p for p in model["family"] if p.get("heir_at_law")]


def _cover(c: _Composer, m: dict) -> None:
    c.source("cover")
    c.text("ESTATE PLANNING AND CONTESTED PROBATE FILE", bold=True,
           align="c", font=("Times-Bold", 16))
    c.text(f"Estate of {m['decedent']}", align="c", font=("Times-Roman", 14))
    c.text(f"{m['county']} County, {m['state']}", align="c")
    c.space(12)
    c.text("CONFIDENTIAL - ATTORNEY FILE", bold=True, align="c")
    c.rule()
    c.para("Production copy assembled from executed planning instruments, "
           "contemporaneous professional records, fiduciary schedules, and "
           "post-death contested-probate drafts. Instrument dates are the "
           "dates represented on each document; the PDF assembly occurred "
           f"on {_fmt(m['assembly_date'])}.")
    c.heading("INDEX OF DOCUMENTS", align="c")
    for i, title in enumerate(DOCUMENT_TITLES, 1):
        c.row([str(i), title], [32, USABLE - 32])
    c.space(10)
    c.para("Core disposition: after payment of enforceable claims, expenses, "
           "and taxes, the residence, publishing-company equity, author-owned "
           f"copyrights, liquid property, and residue pass to {m['beneficiary']}. "
           "The intent memorandum is evidentiary only; the operative result "
           "rests on the executed will, trust restatement, and assignments.")


def _will(c: _Composer, m: dict, defect: dict) -> None:
    c.new_document(1, DOCUMENT_TITLES[0])
    c.title("LAST WILL AND TESTAMENT", f"OF {m['decedent'].upper()}")
    date_display = defect.get("will_execution_date", _fmt(m["execution_date"]))
    c.para(f"I, {m['decedent']}, of {m['municipality']}, {m['county']} County, "
           f"{m['state']}, declare this instrument, signed on {date_display}, "
           "to be my Last Will and Testament and revoke all prior wills and "
           "codicils.")
    c.heading("ARTICLE I - FAMILY AND INTENTIONAL EXCLUSIONS")
    c.para(f"I am a {m['marital_status']}. I have identified the persons who "
           "would be the natural objects of my bounty. Except for any right "
           "expressly created by this Will or by the trust identified below, "
           "I intentionally make no provision for any member of my family, "
           "including descendants and their spouses. This omission is "
           "intentional and is not the result of mistake or lack of knowledge.")
    c.heading("ARTICLE II - PERSONAL REPRESENTATIVE")
    c.para(f"I nominate {m['independent_fiduciary']} as Personal Representative, to serve "
           "without sureties to the fullest extent permitted by law. If that "
           "nominee cannot serve, the court may appoint a disinterested "
           "professional fiduciary. My Personal Representative may retain "
           "property, settle claims, employ advisers, operate a closely held "
           "business, and make tax elections as applicable law permits.")
    c.heading("ARTICLE III - PAYMENT AND TAX APPORTIONMENT")
    c.para("My Personal Representative shall pay legally enforceable debts, "
           "funeral and administration expenses, and taxes attributable to "
           "property passing under this Will. No fiduciary shall distribute "
           "property needed for a reasonable administration reserve.")
    c.heading("ARTICLE IV - POUR-OVER RESIDUE")
    c.para(f"I give all the residue of my probate estate to the then-serving "
           f"trustee of {m['trust_name']}, originally dated "
           f"{_fmt(m['trust_original_date'])}, as amended and completely "
           "restated on the date of this Will, to be added to and administered "
           "under that trust. This devise is intended as a testamentary "
           "addition under G. L. c. 190B, section 2-511.")
    c.heading("ARTICLE V - PENALTY FOR CONTEST")
    c.para("To the extent enforceable, an interested person who directly "
           "contests this Will or institutes a proceeding to defeat its "
           "dispositive plan shall forfeit any benefit otherwise provided "
           "to that person under this Will. This clause does not purport to "
           "eliminate standing or the court's jurisdiction.")
    c.ensure(280)
    c.heading("EXECUTION AND ATTESTATION")
    c.para(f"I sign this Will willingly on {_fmt(m['execution_date'])} as my "
           "free and voluntary act, being eighteen years of age or older, of "
           "sound mind, and under no constraint or undue influence.")
    c.signature(m["decedent"], "Testator", "testator-will")
    c.para("Each witness signs in the testator's presence and hearing after "
           "observing the testator sign or acknowledge the Will.")
    c.signature(m["witness_1"], "Witness", "witness-1-will")
    c.signature(m["witness_2"], "Witness", "witness-2-will")
    c.ensure(500)
    c.heading("SELF-PROVING AFFIDAVIT")
    c.para(f"Commonwealth of {m['state']}; {m['county']}, ss.")
    c.para(f"{m['decedent']}, the testator, being first duly sworn, declares "
           "that he signed and executed this instrument as his Will, signed "
           "it willingly as his free and voluntary act, is eighteen years "
           "of age or older and of sound mind, and is under no constraint or "
           "undue influence. The witnesses, being first duly sworn, declare "
           "that the testator signed or acknowledged the Will and that each "
           "signed in the testator's presence and hearing, and that to the "
           "best of each witness's knowledge the testator met those conditions.")
    c.signature(m["decedent"], "Testator", "testator-affidavit")
    c.signature(m["witness_1"], "Witness", "witness-1-affidavit")
    c.signature(m["witness_2"], "Witness", "witness-2-affidavit")
    c.para(f"Subscribed, sworn to, and acknowledged before me on "
           f"{_fmt(m['execution_date'])}.")
    c.signature(m["notary"],
                f"Notary Public; commission expires {_fmt(m['notary_expiry'])}",
                "notary-will")
    c.notary_seal(m["notary"], m["notary_expiry"])


def _trust(c: _Composer, m: dict, defect: dict) -> None:
    beneficiary = defect.get("trust_beneficiary", m["beneficiary"])
    c.new_document(2, DOCUMENT_TITLES[1])
    c.title("COMPLETE RESTATEMENT OF REVOCABLE TRUST", m["trust_name"])
    c.para(f"This Complete Restatement is made on {_fmt(m['execution_date'])} "
           f"by {m['decedent']}, as Settlor and Trustee. It replaces every "
           f"prior dispositive provision of the trust originally dated "
           f"{_fmt(m['trust_original_date'])}.")
    c.heading("ARTICLE 1 - AMENDMENT METHOD AND REVOCABILITY")
    c.para("The trust instrument permits the Settlor to amend or revoke by a "
           "signed writing delivered to the Trustee. The Settlor signs this "
           "writing and, as Trustee, acknowledges delivery and acceptance. "
           "During the Settlor's lifetime the trust remains revocable and "
           "the Settlor may withdraw property. At death it becomes irrevocable.")
    c.heading("ARTICLE 2 - LIFETIME ADMINISTRATION")
    c.para("During the Settlor's lifetime the Trustee shall distribute income "
           "and principal as the Settlor directs. No remainder beneficiary "
           "has a present right to control administration while the trust is "
           "revocable.")
    c.heading("ARTICLE 3 - SUCCESSOR TRUSTEE")
    c.para(f"At the Settlor's death, {m['independent_fiduciary']} shall serve as successor "
           "Trustee. The successor shall act independently of every "
           "beneficiary, may retain the publishing business, and shall keep "
           "separate records for probate, trust, and company property.")
    c.heading("ARTICLE 4 - ADMINISTRATION AT DEATH")
    c.para("The successor Trustee may reserve for enforceable claims, expenses, "
           "and taxes and may make funds available to the Personal "
           "Representative if the probate estate is insufficient. Company "
           "assets are not trust assets merely because the trust owns stock.")
    c.heading("ARTICLE 5 - DISTRIBUTION")
    c.para(f"After completing or adequately providing for administration, the "
           f"Trustee shall distribute all remaining trust property outright "
           f"to {beneficiary}, if living. The distribution includes the "
           f"residence at {m['home_address']}, all trust-owned shares of "
           f"{m['company']}, all author-owned copyrights assigned to the trust, "
           "and the residue. No family member is a remainder beneficiary.")
    c.heading("ARTICLE 6 - INTENTIONAL EXCLUSION AND CONTEST")
    c.para("The Settlor intentionally excludes the persons who would otherwise "
           "expect to benefit. To the extent enforceable under applicable "
           "law, a beneficiary who contests this Restatement forfeits any "
           "benefit provided by it. The clause does not create a benefit for "
           "a person otherwise excluded and does not bar access to a court.")
    c.heading("ARTICLE 7 - GOVERNING LAW AND SEVERABILITY")
    c.para(f"The law of {m['state']} governs. Invalid language is severed only "
           "to the extent necessary, without enlarging an excluded person's "
           "interest.")
    c.ensure(170)
    c.signature(m["decedent"], "Settlor and Trustee", "testator-trust")
    c.para(f"The foregoing signed Restatement was delivered to and accepted "
           f"by the Trustee on {_fmt(m['execution_date'])}.")
    c.signature(m["decedent"], "Trustee, acknowledging delivery", "trustee-accept")
    c.para(f"Acknowledged before me on {_fmt(m['execution_date'])}.")
    c.signature(m["notary"],
                f"Notary Public; commission expires {_fmt(m['notary_expiry'])}",
                "notary-trust")
    c.notary_seal(m["notary"], m["notary_expiry"])


def _funding(c: _Composer, m: dict, defect: dict) -> None:
    shares = defect.get("assigned_shares", m["company_shares"])
    c.new_document(3, DOCUMENT_TITLES[2])
    c.title("PUBLISHING-COMPANY STOCK SCHEDULE",
            "AND ASSIGNMENT OF STOCK AND COPYRIGHTS")
    c.heading("SCHEDULE A - UNCERTIFICATED EQUITY POSITION")
    c.row(["Issuer", m["company"]], [120, USABLE - 120], bold=True)
    c.row(["Class", m["company_share_class"]], [120, USABLE - 120])
    c.row(["Shares issued", f"{m['company_shares']:,}"], [120, USABLE - 120])
    c.row(["Shares owned", f"{m['company_shares']:,}"], [120, USABLE - 120])
    c.row(["Ownership", "100 percent"], [120, USABLE - 120])
    c.row(["Ledger account", "BLW-TRUST-001 (internal issuer record)"],
          [120, USABLE - 120])
    c.row(["Evidence", "Uncertificated position on issuer stock ledger"],
          [120, USABLE - 120])
    c.heading("ASSIGNMENT OF STOCK")
    c.para(f"For estate-planning purposes, {m['decedent']} assigns and transfers "
           f"to himself as Trustee of {m['trust_name']} all right, title, and "
           f"interest in {shares:,} shares of {m['company_share_class']} of "
           f"{m['company']}, constituting the entire issued and outstanding "
           "equity position. The transfer is effective on delivery of this signed "
           "instrument and the issuer's acceptance below.")
    c.heading("ISSUER STOCK-LEDGER EXTRACT")
    widths = [112, 116, 82, 76, 90]
    c.row(["Effective date", "Registered owner", "Class", "Shares", "Status"],
          widths, bold=True)
    c.row([_fmt(m["execution_date"]), m["decedent"],
           m["company_share_class"], f"({shares:,})", "CANCELLED"], widths)
    c.row([_fmt(m["execution_date"]), m["trust_name"],
           m["company_share_class"], f"{shares:,}", "OPEN"], widths)
    c.para(f"I certify that the issuer's uncertificated stock ledger was updated "
           f"on {_fmt(m['execution_date'])}, that the former individual position "
           "was cancelled, and that the trust is the registered holder of the "
           "entire issued position.")
    c.signature(m["company_secretary"], f"Secretary, {m['company']}",
                "company-secretary")
    c.heading("SCHEDULE B - AUTHOR-OWNED COPYRIGHTS")
    c.para(m["copyright_scope"] + ". This category includes registered and "
           "unregistered works, manuscripts, reserved rights, accrued and "
           "future royalties, claims and causes of action, and proceeds. It "
           "does not include copyrights already owned by the corporation; "
           "those remain company assets reflected only in the stock value.")
    c.row(["Work", "Pub.", "Record status", "Transferred interest"],
          [180, 48, 105, 143], bold=True)
    for work in m["copyright_catalog"]:
        c.row([work["title"], str(work["year"]), "Audit pending",
               "Author-owned copyright"], [180, 48, 105, 143])
    c.para("Registration and chain-of-title identifiers remain subject to the "
           "catalog audit. This schedule identifies each transferred work without "
           "asserting an unverified Copyright Office registration number. Publishing "
           "agreements remain company assets; the author's underlying copyrights, "
           "reserved rights, and net royalty interests are transferred here.")
    c.heading("ASSIGNMENT OF COPYRIGHTS")
    c.para(f"{m['decedent']} hereby assigns to himself as Trustee all right, "
           "title, and interest described in Schedule B. This signed writing "
           "is intended as an instrument of conveyance under 17 U.S.C. "
           "section 204(a). The Trustee may record this instrument and execute "
           "further confirmations without changing the beneficial disposition.")
    c.ensure(180)
    c.signature(m["decedent"], "Assignor and Trustee", "testator-assignment")
    c.para(f"Acknowledged before me on {_fmt(m['execution_date'])}.")
    c.signature(m["notary"],
                f"Notary Public; commission expires {_fmt(m['notary_expiry'])}",
                "notary-assignment")
    c.notary_seal(m["notary"], m["notary_expiry"])


def _memorandum(c: _Composer, m: dict) -> None:
    c.new_document(4, DOCUMENT_TITLES[3])
    c.title("MEMORANDUM OF INTENT", "Intentional exclusion of family members")
    c.para(f"I, {m['decedent']}, write this statement at my own request on "
           f"{_fmt(m['execution_date'])}. Some may be surprised by the choice "
           "I have made. I take no pleasure in the exclusions. Their purpose "
           "is not to sow greater discord in my family. I ask that the result "
           "be accepted without bitterness because I believe it is best.")
    c.para(f"I have considered my family, including "
           + ", ".join(p["name"] for p in _named_family(m))
           + ". I intentionally provide no share to any of them. The omission "
           "is not an oversight. I have separately concluded financial support "
           "and business roles that had prevented adult family members from "
           "building lives independent of me.")
    c.para(f"I leave my beneficial estate to {m['beneficiary']} because of my "
           "independent judgment about character, stewardship, and need. She "
           "did not request, prepare, witness, or know the terms of the "
           "instruments when I signed them.")
    c.para("THIS MEMORANDUM IS NOT A WILL, CODICIL, TRUST AMENDMENT, DEED, OR "
           "ASSIGNMENT. It creates no transfer and has no independent dispositive "
           "effect. My signed "
           "Will, Trust Restatement, and assignments alone control.", bold=True)
    c.ensure(90)
    c.signature(m["decedent"], "Declarant", "testator-memorandum")
    c.text(f"Witnessed by {m['attorney']} on {_fmt(m['execution_date'])}.")


def _capacity(c: _Composer, m: dict) -> None:
    c.new_document(5, DOCUMENT_TITLES[4], "medical")
    c.text("HARBOR INTERNAL MEDICINE", bold=True, align="c",
           font=("Helvetica-Bold", 13))
    c.text("CONFIDENTIAL CLINICAL CORRESPONDENCE",
           align="c", font=("Helvetica", 8.5))
    c.rule()
    c.text(_fmt(m["execution_date"]))
    c.space(8)
    c.text(f"To: {m['attorney']}")
    c.text(f"Re: {m['decedent']} - contemporaneous capacity observations")
    c.space(10)
    c.para(f"At {m['decedent']}'s written request, I performed a limited clinical "
           "assessment and met with him alone this "
           "morning. I explained that my role was clinical and that I was not "
           "giving a legal opinion on testamentary capacity or undue influence.")
    c.para(f"He was awake, alert, and oriented to person, place, date, and "
           f"purpose. He accurately stated his age as {m['age']}, described "
           "his residence and publishing business, identified his children and "
           "grandchildren by relationship, and gave a coherent account of the "
           "approximate nature and extent of his property. Immediate recall, "
           "delayed recall, attention, naming, and clock planning were intact "
           "on bedside screening. No delirium, intoxication, or acute mood or "
           "psychotic process was apparent.")
    c.para(f"He stated, without prompting, that he intended to remove family "
           f"members from his estate plan and benefit {m['beneficiary']}. He "
           "understood that the change would provoke a contest and described "
           "reasons tied to long-standing family and business decisions. I saw "
           "no other person direct his responses.")
    c.para("These observations describe one encounter. They do not determine "
           "legal capacity, validate an instrument, exclude subtle cognitive "
           "impairment, or prove the absence of influence outside my presence.")
    c.space(12)
    c.signature(m["physician"], "Attending physician", "physician")


def _execution_notes(c: _Composer, m: dict) -> None:
    c.new_document(6, DOCUMENT_TITLES[5], "notes")
    c.title("CONFIDENTIAL ATTORNEY FILE NOTE", "EXECUTION CONFERENCE NOTES")
    c.text(f"Client: {m['decedent']}")
    c.text(f"Responsible attorney: {m['attorney']}")
    c.text(f"Assistant: {m['attorney_assistant']}")
    c.rule()
    entries = [
        (m["instruction_date"], "Client telephoned without beneficiary present; "
         "the beneficiary was not present for any instruction conference. "
         "Directed complete exclusion of family and outright benefit for named "
         "beneficiary. Asked attorney to determine instruments required."),
        (m["review_date"], "Met client alone. Reviewed marital status, descendants, "
         "predeceased child, residence, liquid assets, publishing equity, author-owned "
         "copyrights, taxes, creditors, and prior trust. Client described the natural "
         "objects of bounty and consequences of exclusion."),
        (m["draft_date"], "Read dispositive articles and funding assignments aloud. "
         "Client rejected a family trust and confirmed an outright distribution after "
         "administration. Confirmed stock and author copyrights require separate title "
         "work. Beneficiary received no draft and was not contacted."),
        (_date(m["execution_date"]), "Received physician's limited clinical letter. "
         "Met client alone again; client summarized plan from memory, identified "
         "property and family, and confirmed free choice. Witnesses and notary entered "
         "only after instructions were complete. Each instrument was signed in the "
         "required sequence. Original will sealed for custody; trust and assignment "
         "copies delivered to client as trustee."),
    ]
    for date, text in entries:
        c.heading(_fmt(date).upper())
        c.para(text)
    c.heading("CONFLICT AND PRIVILEGE")
    c.para("Firm has performed company and family-adjacent work. Confirmed in writing "
           "that the client for this planning engagement is the decedent alone; no "
           "family member or beneficiary is a client on the disposition. Advised that "
           "the file may become evidence after death and that fiduciary appointments "
           "may require separate litigation counsel. Client was advised that the "
           "drafting lawyer could become a fact witness and that appointment of "
           "independent fiduciary and separate post-death counsel would reduce role "
           "conflicts. Client selected that structure.")
    c.heading("CAPACITY AND INFLUENCE ASSESSMENT")
    c.para("Attorney's independent assessment: client understood the act, approximate "
           "property, natural objects of bounty, and chosen plan; maintained the same "
           "instructions over multiple meetings; supplied reasons; and was not "
           "subservient to the beneficiary, who did not participate.")
    c.signature(m["attorney"], "Attorney file note", "attorney-notes")


def _inventory(c: _Composer, m: dict, defect: dict) -> None:
    assets = compute_assets(m)
    displayed_total = defect.get("inventory_total", assets["gross_total"])
    c.new_document(7, DOCUMENT_TITLES[6], "court")
    c.title("CONSOLIDATED FIDUCIARY INVENTORY",
            f"Estate and trust of {m['decedent']} - values as of {_fmt(m['death_date'])}")
    c.para("Purpose: title map and preliminary administration values. Company "
           "balance-sheet assets are included only through the appraised stock value "
           "and are not listed again. Values are good-faith preliminary estimates, "
           "subject to qualified appraisal and tax-return positions.")
    widths = [250, 108, 108]
    c.row(["Asset", "Title bucket", "Value"], widths, bold=True,
          aligns=["l", "l", "r"])
    c.rule()
    for label, value in assets["trust_rows"]:
        c.row([label, "Revocable trust", _money(value)], widths,
              aligns=["l", "l", "r"])
    for label, value in assets["probate_rows"]:
        c.row([label, "Probate estate", _money(value)], widths,
              aligns=["l", "l", "r"])
    c.rule()
    c.row(["TRUST SUBTOTAL", "", _money(assets["trust_total"])], widths,
          bold=True, aligns=["l", "l", "r"])
    c.row(["PROBATE SUBTOTAL", "", _money(assets["probate_total"])], widths,
          bold=True, aligns=["l", "l", "r"])
    c.row(["CONSOLIDATED GROSS", "", _money(displayed_total)], widths,
          bold=True, aligns=["l", "l", "r"])
    c.space(10)
    c.heading("TITLE AND CONTROL NOTES")
    c.numbered("1.", f"Residence: {m['home_address']}, {m['municipality']}, "
               f"{m['state']} {m['postal_code']}; trust-titled before death.")
    c.numbered("2.", f"{m['company_shares']:,} shares of {m['company_share_class']} "
               f"of {m['company']} equal 100 percent of the issued equity. Company "
               "assets and liabilities are subsumed in the stock appraisal. The "
               "company valuation excludes author-owned copyrights and values only "
               "the publisher's contractual margin and operating enterprise.")
    c.numbered("3.", "Author copyrights were assigned separately and are not assumed "
               "to pass merely with the publishing-company stock. Their valuation "
               "uses author net-royalty cash flows after the publisher's share, so "
               "the same royalty stream is not counted in both appraisals.")
    c.numbered("4.", f"Preliminary administration reserve: "
               f"{_money(assets['administration_reserve'])}; reserve is a holdback, "
               "not an additional liability or asset.")
    c.ensure(90)
    c.para("I certify under the penalties of perjury that this preliminary inventory "
           "is complete and accurate to the best of my knowledge and belief.")
    c.signature(m["independent_fiduciary"], "Nominated Personal Representative",
                "fiduciary-inventory")


def _tax_liquidity(c: _Composer, m: dict) -> None:
    assets = compute_assets(m)
    tax = compute_tax_projection(m)
    c.new_document(8, DOCUMENT_TITLES[7], "medical")
    c.text("FIDUCIARY TAX GROUP", bold=True, align="c",
           font=("Helvetica-Bold", 14))
    c.text("PRELIMINARY ESTATE-TAX AND LIQUIDITY MEMORANDUM", bold=True,
           align="c")
    c.rule()
    c.text(f"Estate of {m['decedent']}")
    c.text(f"Prepared for {m['independent_fiduciary']}, nominated fiduciary")
    c.text(f"Planning date: {_fmt(m['settlement_date'])}")
    c.heading("PURPOSE AND LIMITATIONS")
    c.para("This memorandum is a conservative administration projection, not a "
           "filed Form 706 or Massachusetts Form M-706. Values, deductions, prior "
           "taxable gifts, portability, credits, and elections remain subject to "
           "appraisal, records, and return preparation. No distribution may rely on "
           "this estimate without the fiduciary's updated tax advice.")
    c.heading("PRELIMINARY RESERVE")
    widths = [315, 151]
    rows = [
        ("Consolidated gross estate", assets["gross_total"]),
        ("Less preliminary administration reserve",
         assets["administration_reserve"]),
        ("Planning taxable estate", tax["taxable_estate"]),
        ("Federal estate-tax estimate; 2019 $11.4m exclusion",
         tax["federal_estate_tax"]),
        ("Massachusetts estate-tax reserve; M-706 pending",
         tax["massachusetts_estate_tax_reserve"]),
        ("Estate/trust income-tax reserve", tax["income_tax_reserve"]),
        ("Administration expense reserve", assets["administration_reserve"]),
        ("TOTAL TAX AND ADMINISTRATION RESERVE", tax["total_reserve"]),
        ("Liquid cash and marketable investments", tax["liquid_assets"]),
        ("PROJECTED LIQUIDITY SHORTFALL", tax["liquidity_shortfall"]),
    ]
    for label, value in rows:
        c.row([label, _money(value)], widths,
              bold=label.startswith(("TOTAL", "PROJECTED")), aligns=["l", "r"])
    c.heading("FILING AND PAYMENT CALENDAR")
    due = _add_months(_date(m["death_date"]), 9)
    c.numbered("1.", f"Federal Form 706 return and estate-tax payment are due "
               f"{_fmt(due)}, nine months after death, subject to a timely extension "
               "of the return and separate payment-relief rules.")
    c.numbered("2.", "Massachusetts Form M-706 is required because the 2019 gross "
               "estate exceeds the $1,000,000 filing threshold. Obtain the estate-tax "
               "release before recording or distributing Massachusetts real estate.")
    c.numbered("3.", "Prepare fiduciary income-tax returns and reserve for post-death "
               "royalties, interest, gains, and income in respect of a decedent.")
    c.heading("LIQUIDITY PLAN")
    ratio = tax["closely_held_ratio"]
    c.para(f"The publishing-company interest is {ratio:.1%} of the preliminary gross "
           "estate. Counsel and the return preparer should test eligibility for the "
           "closely held business installment election under I.R.C. section 6166; "
           "this memorandum does not assume the election will be allowed.")
    c.para("Until eligibility is confirmed, the fiduciary shall preserve liquid "
           "assets, obtain a secured credit facility against marketable assets, "
           "request a lawful company dividend or redemption only after solvency and "
           "fiduciary review, and defer the family settlement payment. The residence, "
           "company voting control, and catalog copyrights are not designated for "
           "sale. Any borrowing or business distribution must be documented as an "
           "administration transaction, not a beneficiary preference.")
    c.ensure(90)
    c.signature(m["estate_counsel"], "Estate counsel; preliminary planning review",
                "tax-counsel")


def _petition(c: _Composer, m: dict) -> None:
    assets = compute_assets(m)
    c.new_document(9, DOCUMENT_TITLES[8], "court")
    c.text("COMMONWEALTH OF MASSACHUSETTS", bold=True, align="c")
    c.text("THE TRIAL COURT", bold=True, align="c")
    c.text("PROBATE AND FAMILY COURT", bold=True, align="c")
    c.space(8)
    c.row([f"{m['county']} Division", "Docket No. TO BE ASSIGNED BY COURT"],
          [230, 246], bold=True)
    c.rule()
    c.title("MPC 160 - PETITION FOR FORMAL PROBATE OF A WILL",
            "and formal appointment of a Personal Representative")
    c.para("Pursuant to G. L. c. 190B, section 3-402, the Petitioner requests "
           "formal probate of the original Will, determination of heirs, formal "
           "appointment of the nominated Personal Representative, and supervised "
           "administration because written objections are anticipated.")
    c.heading("1. DECEDENT")
    c.row(["Name", m["decedent"]], [120, 356])
    c.row(["Date of death", _fmt(m["death_date"])], [120, 356])
    c.row(["Age", str(m["age"])], [120, 356])
    c.row(["Domicile", f"{m['home_address']}, {m['municipality']}, "
           f"{m['state']} {m['postal_code']}"], [120, 356])
    c.row(["Marital status", m["marital_status"].title()], [120, 356])
    c.heading("2. PETITIONER AND PRIORITY")
    c.para(f"Petitioner {m['independent_fiduciary']} is the Personal Representative "
           "nominated in the offered Will. Service shall be made through estate "
           f"counsel {m['estate_counsel']} at the address endorsed on the signed "
           "court-filed original.")
    c.heading("3. WILL AND VENUE")
    c.para(f"The original Will dated {_fmt(m['execution_date'])} accompanies the "
           "petition and has not been informally probated. Venue lies in this "
           "Division because the decedent was domiciled in the county at death. "
           "A certified death certificate and the companion forms listed below "
           "accompany the filing; no court-issued citation or docket number existed "
           "when this production copy was assembled.")
    c.heading("4. HEIRS AT LAW")
    for person in _heirs(m):
        c.row([person["name"], person["relationship"]], [190, 286])
    c.heading("5. DEVISEE")
    c.row([m["beneficiary"], "Sole beneficial recipient through pour-over trust"],
          [190, 286])
    c.heading("6. ESTIMATED ESTATE")
    c.row(["Probate personal property", _money(assets["probate_total"])],
          [240, 236], aligns=["l", "r"])
    c.row(["Trust/nonprobate property (not probate inventory)",
           _money(assets["trust_total"])], [300, 176], aligns=["l", "r"])
    c.heading("7. REQUESTED ORDERS")
    c.numbered("a.", "Admit the original Will to formal probate and determine heirs.")
    c.numbered("b.", f"Appoint {m['independent_fiduciary']} as Personal Representative under "
               "supervised administration, with bond without sureties if allowed.")
    c.numbered("c.", "Issue citation and schedule a case-management conference if "
               "an appearance or objection is filed.")
    c.ensure(150)
    c.para("Signed under the penalties of perjury. I certify that the statements "
           "made are true and complete to the best of my knowledge and belief.")
    c.signature(m["independent_fiduciary"],
                "Petitioner and nominated Personal Representative",
                "petitioner")
    c.signature(m["estate_counsel"], "Counsel for Petitioner", "petition-counsel")
    c.ensure(590)
    c.title("FORMAL-PROBATE COMPANION FILING SET",
            "Massachusetts Probate and Family Court")
    c.para("The following state-form components accompany or follow the MPC 160. "
           "Court-issued citation and decree are listed but are not created or "
           "pre-signed by the petitioner.")
    c.row(["Form", "Purpose", "File status"], [76, 260, 130], bold=True)
    filing_rows = [
        ("MPC 162", "Surviving Spouse, Children, Heirs at Law", "Completed schedule"),
        ("MPC 163", "Devisees", "Completed schedule"),
        ("MPC 280", "Petition for Supervised Administration", "Signed for filing"),
        ("MPC 801", "Bond", "Signed; amount for court"),
        ("MPC 470", "Military Affidavit", "Due before decree"),
        ("MPC 560", "Citation", "Court to issue"),
        ("MPC 755", "Decree and Order", "Court to issue"),
    ]
    for form, purpose, status in filing_rows:
        c.row([form, purpose, status], [76, 260, 130])
    c.heading("MPC 162 - HEIRS AT LAW")
    for person in _heirs(m):
        c.row([person["name"], person["relationship"]], [190, 276])
    c.heading("MPC 163 - DEVISEE")
    c.row([m["beneficiary"], "Beneficiary through the pour-over trust"], [190, 276])
    c.heading("MPC 280 - SUPERVISED ADMINISTRATION")
    c.para("Supervision is requested because objections place testamentary capacity, "
           "undue influence, execution, trust amendment, and title in dispute. No "
           "distribution, compromise, sale of the residence, or transfer of company "
           "control should occur without the orders required by supervised administration.")
    c.signature(m["independent_fiduciary"], "Petitioner - MPC 280", "mpc-280")
    c.heading("MPC 801 - BOND")
    c.para(f"Principal: {m['independent_fiduciary']}. Penal sum and surety status are "
           "left for the court's order. The principal undertakes faithful performance "
           "and accounting according to law.")
    c.signature(m["independent_fiduciary"], "Principal - MPC 801", "mpc-801")
    c.heading("ATTACHMENT CONTROL")
    c.para("Original Will: lodged with petition. Certified death certificate: attached. "
           "MPC 162, MPC 163, MPC 280, MPC 801: attached. MPC 470: required before "
           "decree. MPC 560 citation and MPC 755 decree: court-issued only. Docket "
           "number remains TO BE ASSIGNED BY COURT.")


def _objection(c: _Composer, m: dict) -> None:
    c.new_document(10, DOCUMENT_TITLES[9], "court")
    c.text("COMMONWEALTH OF MASSACHUSETTS", bold=True, align="c")
    c.text("PROBATE AND FAMILY COURT", bold=True, align="c")
    c.row([f"{m['county']} Division", "Related docket: TO BE ASSIGNED"],
          [230, 246], bold=True)
    c.rule()
    c.title("FAMILY OBJECTORS' OBJECTION AND REQUEST FOR SUPERVISION",
            f"Estate of {m['decedent']}")
    objectors = [p["name"] for p in _named_family(m)]
    c.para("Objectors " + ", ".join(objectors) + ", by proposed counsel "
           f"{m['objector_counsel']}, object to allowance of the offered Will, "
           "contest the validity and effect of the contemporaneous trust "
           "restatement and assignments, and request supervised administration, "
           "preservation of assets, targeted discovery, and an evidentiary hearing.")
    c.heading("STANDING")
    c.para("The heirs at law would take if the offered Will fails. Additional "
           "Objectors allege interests under earlier estate instruments. These "
           "allegations identify asserted standing; they do not establish the "
           "validity or terms of any prior instrument.")
    grounds = [
        "Testamentary capacity. The dispositive change was executed by an "
        "eighty-five-year-old testator shortly before death and radically departed "
        "from family expectations. Objectors request the drafting file, medical "
        "records, witnesses, and testimony concerning the testator's understanding.",
        "Undue influence and procurement. The sole beneficiary was a caregiver with "
        "access and a confidential relationship. Objectors allege opportunity, "
        "susceptibility, an unexpected disposition, and actual procurement on "
        "information and belief. They acknowledge that suspicion and opportunity "
        "alone do not prove coercion.",
        "Execution and amendment. Objectors demand strict proof of the Will's signing "
        "and attestation, the self-proving affidavit, the trust's amendment method, "
        "delivery to the Trustee, and the authenticity of stock and copyright "
        "assignments.",
        "Mistake, fraud, and ownership. Objectors request proof that the documents "
        "reflect the testator's instructions and that each scheduled asset was owned "
        "and validly transferred, including stock-ledger and copyright evidence.",
        "Forfeiture related to death. Objectors preserve a claim under G. L. c. 190B, "
        "section 2-803 only if evidence shows the beneficiary feloniously and "
        "intentionally killed the decedent. They do not allege that negligence or a "
        "medication error alone satisfies that standard.",
    ]
    c.heading("GROUNDS")
    for i, ground in enumerate(grounds, 1):
        c.numbered(f"{i}.", ground)
    c.heading("REQUEST FOR RELIEF")
    c.para("Objectors request that no contested distribution occur until the court "
           "determines validity; that the fiduciary preserve the residence, stock, "
           "copyrights, books, and electronic records; that the matter proceed under "
           "supervision; and that the court grant further appropriate relief.")
    c.ensure(100)
    c.signature(m["objector_counsel"], "Proposed counsel for Family Objectors",
                "objector-counsel")
    c.text(f"Dated: {_fmt(m['objection_date'])}")


def _settlement(c: _Composer, m: dict) -> None:
    assets = compute_assets(m)
    tax = compute_tax_projection(m)
    c.new_document(11, DOCUMENT_TITLES[10], "letter")
    c.text(f"{m['beneficiary_counsel'].upper()} | PRIVATE CLIENT GROUP",
           bold=True, align="c", font=("Helvetica-Bold", 12))
    c.text("WITHOUT PREJUDICE - FOR SETTLEMENT PURPOSES ONLY", bold=True,
           align="c")
    c.text("ATTORNEY WORK PRODUCT", align="c")
    c.rule()
    c.text(_fmt(m["settlement_date"]))
    c.text(f"To: {m['objector_counsel']}, proposed counsel for Family Objectors")
    c.text(f"Re: Estate and trust of {m['decedent']}")
    c.heading("PROPOSAL")
    c.para(f"Without admitting liability or invalidity, {m['beneficiary']} offers "
           f"an aggregate {_money(assets['settlement_offer'])} from liquid property "
           "in exchange for a single coordinated resolution. Payment is subordinate "
           f"to the {_money(tax['total_reserve'])} preliminary tax and administration "
           "reserve and requires written fiduciary approval. The offer expires "
           "fourteen days after delivery unless extended in a signed writing.")
    allocations = [("Living children", .50), ("Issue of predeceased child", .20),
                   ("Other participating family objectors", .30)]
    c.row(["Settlement group", "Share", "Amount"], [270, 72, 124], bold=True,
          aligns=["l", "r", "r"])
    for label, fraction in allocations:
        c.row([label, f"{fraction:.0%}",
               _money(assets["settlement_offer"] * fraction)],
              [270, 72, 124], aligns=["l", "r", "r"])
    c.heading("NON-NEGOTIABLE RETAINED OUTCOME")
    c.para(f"{m['beneficiary']} retains the residence at {m['home_address']}, "
           f"all {m['company_shares']:,} voting shares of {m['company']}, all "
           "author-owned catalog copyrights, governance and licensing control, "
           "and the residue. Settlement recipients receive cash only, not an "
           "inheritance under the governing instruments and not a business role.")
    c.heading("REQUIRED RELEASE TERMS")
    for i, term in enumerate([
        "dismissal with prejudice of probate and trust objections after payment;",
        "a release of will, trust, capacity, influence, title, accounting, copyright, "
        "company-control, and fiduciary claims through the effective date;",
        "withdrawal of notices that restrain distribution, subject to the court's "
        "approval and the fiduciary's administration reserve;",
        "no admission, confidentiality to the extent lawful, mutual non-disparagement, "
        "and separate tax responsibility; and",
        "execution by every claimant and counsel-confirmed authority for minors or "
        "represented interests, if any."
    ], 1):
        c.numbered(f"{i}.", term)
    c.heading("NO-CONTEST CLAUSE ANALYSIS")
    c.para("G. L. c. 190B, section 2-517 states that a will provision penalizing "
           "an interested person for contesting the will or instituting related "
           "estate proceedings is enforceable. The statute does not eliminate "
           "standing, prevent filing, or by its own text decide treatment of a "
           "separate trust clause. More importantly, a person who receives nothing "
           "under the challenged instruments has no gift to forfeit. The clause is "
           "therefore not the principal defense to this contest.")
    c.heading("MERITS AND RISK ANALYSIS")
    c.para("The defense rests on repeated independent instructions, a dispositive "
           "plan the client could explain, disinterested witnesses, complete "
           "execution, a limited contemporaneous clinical letter, beneficiary "
           "absence, separate stock and copyright assignments, and consistent "
           "asset titling. The caregiver relationship and radical exclusion supply "
           "litigation risk but do not alone prove coercion.")
    c.ensure(185)
    c.para("The slayer statute requires a felonious and intentional killing. The "
           "available record states that the beneficiary administered the correctly "
           "selected medication, another person switched labels, and the decedent "
           "caused his own death. On those facts the statutory forfeiture does not "
           "apply. A contrary adjudicated factual record would control.")
    c.para("The revocable-trust contest period and distribution rules require prompt "
           "notice and careful holdback. Settlement is offered to cap cost and delay, "
           "not because the no-contest clause guarantees dismissal.")
    c.ensure(95)
    c.signature(m["beneficiary_counsel"], f"Counsel for {m['beneficiary']}",
                "settlement-counsel")


DOCUMENT_TITLES = [
    "Last Will and Testament",
    "Complete Restatement of Revocable Trust",
    "Publishing-Company Stock Schedule and Assignment",
    "Memorandum of Intent Disinheriting Family",
    "Physician Capacity Letter",
    "Attorney Execution Notes",
    "Consolidated Estate and Trust Inventory",
    "Preliminary Estate-Tax and Liquidity Memorandum",
    "Petition for Formal Probate and Appointment",
    "Family Objection to Beneficiary's Inheritance",
    "Settlement Proposal and No-Contest-Clause Analysis",
]


def compose_estate(model: dict, defect: dict | None = None) -> list[dict]:
    """Compose the ten requested components plus a tax/liquidity memorandum."""
    defect = dict(defect or {})
    c = _Composer()
    _cover(c, model)
    _will(c, model, defect)
    _trust(c, model, defect)
    _funding(c, model, defect)
    _memorandum(c, model)
    _capacity(c, model)
    _execution_notes(c, model)
    _inventory(c, model, defect)
    _tax_liquidity(c, model)
    _petition(c, model)
    _objection(c, model)
    _settlement(c, model)
    return c.lines


def _fit_footer(text: str, *, width: float = 185.0,
                font: str = "Helvetica", size: float = 6.5) -> str:
    """Bound footer labels so title, page, and Bates zones cannot collide."""
    if pdfmetrics.stringWidth(text, font, size) <= width:
        return text
    suffix = "..."
    candidate = text
    while candidate and pdfmetrics.stringWidth(
            candidate.rstrip() + suffix, font, size) > width:
        candidate = candidate[:-1]
    return candidate.rstrip() + suffix


def _render_vector(lines: list[dict], model: dict, metadata: dict) -> bytes:
    buffer = io.BytesIO()
    canvas = rl_canvas.Canvas(buffer, pagesize=letter, invariant=1)
    canvas.setTitle(f"Estate file - {model['decedent']}")
    canvas.setAuthor(model["attorney"])
    canvas.setProducer(metadata["producer"])
    canvas.setCreator(metadata["creator"])
    page = 1
    y = TOP
    document = "File index"

    def footer():
        canvas.setFont("Helvetica", 6.5)
        canvas.drawString(LEFT, 38, _fit_footer(document))
        bates = f"{model['bates_prefix']}{page:06d}"
        canvas.drawRightString(RIGHT, 38, bates)
        canvas.drawCentredString(PAGE_W / 2, 38, f"Page {page}")

    def new_page():
        nonlocal page, y
        footer()
        canvas.showPage()
        page += 1
        y = TOP

    def draw_text(text: str, font: tuple[str, float], x: float, align: str):
        name, size = font
        canvas.setFont(name, size)
        if align == "c":
            canvas.drawCentredString((LEFT + RIGHT) / 2, y, text)
        elif align == "r":
            canvas.drawRightString(RIGHT, y, text)
        else:
            canvas.drawString(x, y, text)

    for line in lines:
        if line.get("newpage"):
            if y < TOP or page > 1:
                new_page()
            document = line["document"]
            continue
        if "ensure" in line:
            if y - line["ensure"] < BOTTOM:
                new_page()
            continue
        lead = line.get("lead", 14)
        if y - lead < BOTTOM:
            new_page()
        if "space" in line:
            y -= line["space"]
            continue
        if line.get("rule"):
            canvas.setLineWidth(.6)
            canvas.line(LEFT, y + 4, RIGHT, y + 4)
            y -= lead
            continue
        if "notary_seal" in line:
            name, expiry = line["notary_seal"]
            cx, cy = RIGHT - 68, y - 28
            canvas.saveState()
            canvas.setStrokeColorRGB(.24, .31, .45)
            canvas.setFillColorRGB(.24, .31, .45)
            canvas.setLineWidth(1.2)
            canvas.circle(cx, cy, 44, stroke=1, fill=0)
            canvas.circle(cx, cy, 38, stroke=1, fill=0)
            canvas.setFont("Helvetica-Bold", 6.5)
            canvas.drawCentredString(cx, cy + 20,
                                     "COMMONWEALTH OF MASSACHUSETTS")
            canvas.setFont("Helvetica-Bold", 8)
            canvas.drawCentredString(cx, cy + 3, "NOTARY PUBLIC")
            canvas.setFont("Helvetica", 6.5)
            canvas.drawCentredString(cx, cy - 10, name.upper())
            canvas.drawCentredString(cx, cy - 21, f"COMMISSION EXPIRES {expiry}")
            canvas.restoreState()
            y -= lead
            continue
        if "signature" in line:
            name, role, key = line["signature"]
            seed = (_stable_hash(name + key) + model["signature_salt"]) % 1000003
            image = assets.signature_png(seed, name=name)
            reader = ImageReader(io.BytesIO(image))
            width, height = reader.getSize()
            target_h = 31.0
            target_w = min(190.0, target_h * width / height)
            canvas.drawImage(reader, LEFT + 4, y - target_h + 8,
                             width=target_w, height=target_h, mask="auto")
            canvas.setLineWidth(.5)
            canvas.line(LEFT, y - 25, LEFT + 220, y - 25)
            canvas.setFont("Times-Roman", 9.5)
            canvas.drawString(LEFT, y - 38, name)
            canvas.setFont("Times-Italic", 8.5)
            canvas.drawString(LEFT, y - 50, role)
            y -= lead
            continue
        if "row" in line:
            x = LEFT
            name, size = line["font"]
            wrapped = [_wrap(str(cell), line["font"], width - 8)
                       if cell else [""]
                       for cell, width in zip(line["row"], line["widths"])]
            row_lead = size + 2.2
            row_height = max(len(parts) for parts in wrapped) * row_lead
            if y - row_height < BOTTOM:
                new_page()
            for parts, width, align in zip(wrapped, line["widths"],
                                           line["aligns"]):
                for index, cell in enumerate(parts):
                    canvas.setFont(name, size)
                    line_y = y - index * row_lead
                    if align == "r":
                        canvas.drawRightString(x + width - 4, line_y, cell)
                    elif align == "c":
                        canvas.drawCentredString(x + width / 2, line_y, cell)
                    else:
                        canvas.drawString(x + 2, line_y, cell)
                x += width
            y -= max(lead, row_height)
            continue
        if "hang" in line:
            label, body = line["hang"]
            width = line["width"]
            draw_text(label, line["font"], LEFT, "l")
            draw_text(body, line["font"], LEFT + width, "l")
            y -= lead
            continue
        if "text" in line:
            if line["text"]:
                draw_text(line["text"], line["font"],
                          LEFT + line.get("indent", 0), line.get("align", "l"))
            y -= lead
    footer()
    canvas.showPage()
    canvas.save()
    pdf = legalpdf._fix_dates(buffer.getvalue(), created=metadata.get("created"),
                              modified=metadata.get("modified"))
    return legalpdf._fix_id(pdf)


def render_estate(model: dict, *, metadata: dict,
                  defect: dict | None = None) -> bytes:
    """Render a deterministic, searchable law-office production packet."""
    return _render_vector(compose_estate(model, defect), model, metadata)
