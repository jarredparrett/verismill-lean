"""The registry and the emit facade — one request in, an artifact out.

Before this module a caller had to know which emitter module to import, how
to build a `random.Random`, and how to hand-assemble a metadata dict whose
producer, creator and `created` date were forensically consistent with the
era the document claims. Seven emitters each set their own metadata, which is
seven places for the same mistake.

    from mattermill import registry
    pdf, manifest = registry.emit("bill_of_sale", pins={"vessel_name": "Unity"})

The facade owns three things the caller should never have to:

1. **Metadata, era-correctly.** A document whose era predates PDF (1993) is a
   scan, so its metadata describes the *scanner* and its `created` is the
   digitisation date — never the date the document claims. A modern form
   carries its own date. Profiles are drawn from the same seeded rng, so the
   choice is reproducible.
2. **Provenance.** Every emit returns a manifest — class, version, pins, seed,
   sha256 — which is the reproduction recipe. Same manifest in, same bytes
   out, on any machine, offline.
3. **Standing, stated.** `list_classes()` reports the round that judged each
   class and what it scored. A class that has never been judged says so. This
   is the only honest answer to "is it realistic?", and it is why the registry
   is the right place to ask.

Registered here are *document classes* — things a person asks for by name.
The primitives they are built from (`pdf`, `xlsx`, `eml`, `longdoc`,
`invoice`, `ledger`) stay importable and out of the registry: they are how
you build a class, not a thing anyone requests.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any, Callable

from . import (__version__, acord, acord130, bill_of_sale, diligence, nj_birth,
               vintage)

# ---------------------------------------------------------------------------
# Metadata profiles — how the artifact was captured, by era.
#
# Invariant 6 (period honesty) lives here now: a scan-class artifact was
# digitised on a real machine at a real time, and the metadata says so. The
# planetary/overhead profiles matter for anything that cannot be fed through
# a sheetfed scanner — round 8 lost forensic authenticity on exactly that.
# ---------------------------------------------------------------------------

SHEETFED = [
    ("Canon DR-C240 / Adobe Paper Capture", "Canon DR-C240"),
    ("Xerox WorkCentre 7855 / Adobe Paper Capture", "Xerox WorkCentre 7855"),
    ("Fujitsu fi-7160 / ABBYY FineReader", "Fujitsu fi-7160"),
]
PLANETARY = [                      # overhead capture: bound, fragile, oversize
    ("Zeutschel OS 12002 / Adobe Paper Capture", "Zeutschel OS 12002"),
    ("i2S CopiBook HD / Adobe Paper Capture", "i2S CopiBook HD"),
    ("Bookeye 4 V1A / ABBYY FineReader", "Bookeye 4 V1A"),
]
OFFICE = [                         # born-digital: the document IS the file
    ("Acrobat Distiller 8.3.1 (Windows)", "AMS360 Form Library"),
    ("Adobe PDF Library 15.0", "Adobe LiveCycle Designer ES4"),
    ("PDF-XChange (xcpro40.dll v4.0.0195.0000)", "Applied Epic Forms"),
]


@dataclass(frozen=True)
class DocumentClass:
    name: str
    summary: str
    module: str
    era: str
    substrate: str                 # what the artifact physically IS
    pins: dict[str, str]
    standing: dict[str, Any]
    sample: Callable[..., dict]
    render: Callable[..., bytes]
    profiles: list = field(default_factory=list)
    capture_window: tuple[int, int] = (2015, 2021)
    takes_pins: bool = False
    takes_canon: bool = False

    def describe(self) -> dict:
        return {"name": self.name, "summary": self.summary,
                "module": self.module, "era": self.era,
                "substrate": self.substrate, "pins": dict(self.pins),
                "standing": dict(self.standing),
                "mattermill": __version__}


CLASSES: dict[str, DocumentClass] = {}


def register(cls: DocumentClass) -> DocumentClass:
    CLASSES[cls.name] = cls
    return cls


# ---------------------------------------------------------------------------
# The catalog. `standing` is the class's realism claim and nothing more: the
# round that judged it, how, and what it scored. Never edit a score here that
# a round did not produce — the foundry ledger is the evidence, this is the
# label on the tin.
# ---------------------------------------------------------------------------

register(DocumentClass(
    name="acord126",
    summary="ACORD 126 commercial general liability section — a filled "
            "application as a broker's system would export it.",
    module="mattermill.acord",
    era="contemporary",
    substrate="born-digital vector PDF",
    pins={"insured": "the named insured (str); sampled if omitted"},
    standing={"rung": "external review", "round": 4, "mode": "external "
              "commercial-lines underwriter review", "score": 62,
              "dimensions": {"financial_operational": 96,
                             "cross_field_consistency": 43},
              "open": ["registry identifiers (NAIC, class codes) unsourced — "
                       "they will not survive lookup"]},
    sample=acord.sample_126, render=acord.render_126,
    profiles=OFFICE, capture_window=(2026, 2026),
))

register(DocumentClass(
    name="acord130",
    summary="ACORD 130 workers compensation application for a Minnesota "
            "gasoline station — filled on MWCIA's rating rules, as an agency "
            "management system would export it.",
    module="mattermill.acord130",
    era="contemporary",
    substrate="born-digital vector PDF",
    pins={"state": "MN only — the rating world is a gate, not a label",
          "market": "voluntary | assigned_risk",
          "full_service": "bool — pumps gas or services cars, which forces 8380",
          "gasoline_share": "float 0-1, share of total receipts (the 90% test)",
          "food_service_share": "float 0-1 (the 50% test)",
          "car_wash": "bool", "el_limits": "(accident, disease policy, disease each)",
          "annual_payroll": "int, station staff before officer remuneration",
          "year": "int"},
    standing={"rung": "unreviewed", "round": None,
              "mode": "never judged", "score": None, "dimensions": {},
              "open": ["never judged. The 2017/05 layout and the Minnesota "
                       "rating rules are both sourced, but no blind round has "
                       "measured whether that adds up to an artifact an "
                       "underwriter believes",
                       "voluntary carrier rate pages are not public, so rates "
                       "are derived from MWCIA's assigned-risk schedule by a "
                       "sampled multiplier rather than filed values",
                       "NAIC company code and National Producer Number are "
                       "left blank on purpose — unsourced identifiers that "
                       "would invite lookup",
                       "only Appendix A Table 1 (Type A carriers) of the "
                       "premium discount table was transcribed, through "
                       "$30,645 of standard premium; beyond it the emitter "
                       "raises rather than guessing",
                       "one location, one state. Multi-state risks need the "
                       "second page-2 sheet the form provides for, and each "
                       "added state needs its own rating world sourced"]},
    sample=acord130.sample_130, render=acord130.render_130,
    profiles=OFFICE, capture_window=(2026, 2026),
    takes_pins=True, takes_canon=True,
))

register(DocumentClass(
    name="bill_of_sale",
    summary="A 1642 English bill of sale of a share in a vessel, engrossed on "
            "a membrane and delivered as a modern digitisation.",
    module="mattermill.bill_of_sale",
    era="1642",
    substrate="scan of a manuscript membrane (recto + dorse)",
    pins={"vessel_name": "str", "tuns": "int", "share": "int denominator",
          "price_pounds": "int", "former": "bool — carries a superseded name",
          "sale_month": "int 1-12", "sale_day": "int",
          "salutation": "bool — deed-poll form B rather than 'This bill made'"},
    standing={"rung": "blind pairwise", "round": 9,
              "mode": "blind pairwise + paired absolute, k=3, manuscripts "
                      "specialist, against a 1613 English bargain-and-sale",
              "score": 43,
              "real_counterpart_score": 94,
              "discrimination_accuracy": 1.0,
              "dimensions": {"financial_operational": 68,
                             "cross_field_consistency": 72,
                             "drafting_realism": 61,
                             "procedural_correctness": 47,
                             "external_verifiability": 40,
                             "visual_formatting": 25,
                             "transaction_provenance": 21,
                             "forensic_authenticity": 10},
              "open": ["all 3 judges identified it as synthetic at 0.97-0.99; "
                       "the objective is judge accuracy at chance (0.5) and it "
                       "is at 1.0",
                       "forensic_authenticity 10 against the real exemplar's 97 "
                       "— the dominant remaining gap. The hand is set type, not "
                       "a secretary hand; the seal is a flat disc on a tag that "
                       "passes through no plica",
                       "declares itself a bill (deed poll, cut plain) but "
                       "carries an indented head copied from an INDENTURE "
                       "exemplar — a feature implemented without checking it "
                       "belonged to this instrument class",
                       "the defeasance voids the bill rather than the "
                       "obligation, so the seller performing destroys the "
                       "buyer's title",
                       "text is fully expanded with no abbreviations or "
                       "suspensions — a 19th-century transcription convention "
                       "inherited from the textual source"]},
    sample=bill_of_sale.sample_bill, render=bill_of_sale.render_bill,
    profiles=PLANETARY, capture_window=(2016, 2021), takes_pins=True,
))

register(DocumentClass(
    name="underwriting_file",
    summary="A pre-opening diligence packet for a hazardous private reserve, "
            "as a broker's placement submission and the lead underwriter's "
            "working file.",
    module="mattermill.diligence",
    era="1993",
    substrate="scan of a production set",
    pins={},
    standing={"rung": "external review", "round": 6, "mode": "external "
              "London-market underwriter review", "score": 61,
              "dimensions": {}, "open": [
                  "market-practice reference data unsourced",
                  "following markets are named without syndicate numbers on "
                  "purpose — a real number invites lookup"]},
    sample=diligence.sample_packet, render=diligence.render_packet,
    profiles=SHEETFED, capture_window=(2015, 2020), takes_canon=True,
))

register(DocumentClass(
    name="msa_1987",
    summary="A 1987 California marital settlement agreement carrying an "
            "extraordinary custody arrangement, typed on pleading paper.",
    module="mattermill.vintage",
    era="1987",
    substrate="scan of a typewritten original",
    pins={},
    standing={"rung": "external review", "round": 5, "mode": "external "
              "family-law review", "score": None, "dimensions": {},
              "open": ["reviewed qualitatively; no numeric score recorded"]},
    sample=vintage.sample_msa, render=vintage.render_msa,
    profiles=SHEETFED, capture_window=(2016, 2021), takes_canon=True,
))

register(DocumentClass(
    name="nj_birth",
    summary="A New Jersey return of a birth, 1878-1900 — the printed blank a "
            "town assessor or city clerk filled and forwarded, as a scan.",
    module="mattermill.nj_birth",
    era="1878-1900",
    substrate="scan of a filled printed blank",
    pins={"year": "int 1878-1899", "surname": "str", "sex": "Male | Female",
          "named": "bool — 'its name, if it be named'",
          "attendant": "physician | midwife | none",
          "special_return": "bool — the assessor filled the blank himself",
          "return_lag_days": "int, the statute allows thirty"},
    standing={"rung": "unreviewed", "round": None,
              "mode": "never judged", "score": None, "dimensions": {},
              "open": ["THE OBJECT IS NOT SOURCED. The field inventory comes "
                       "from section 2 of the registry act, but no facsimile "
                       "of the 1878-1900 blank was obtainable (microfilm, "
                       "in-person only), so sheet size, rule work, layout and "
                       "the printer's imprint are invented",
                       "expect visual_formatting and forensic_authenticity to "
                       "score badly — round 8 measured this exact shape "
                       "(sourced words, unsourced object) at 5",
                       "entries are set in an italic face, not a clerk's hand",
                       "coverage was poor in this era: at least 100,000 New "
                       "Jersey births before 1920 went unrecorded, so a "
                       "confident return for an arbitrary person is itself a "
                       "claim"]},
    sample=nj_birth.sample_birth, render=nj_birth.render_birth,
    profiles=PLANETARY, capture_window=(2014, 2020),
    takes_pins=True, takes_canon=True,
))


# ---------------------------------------------------------------------------
# The facade
# ---------------------------------------------------------------------------

def list_classes() -> list[dict]:
    """Every class a caller can request, with its standing. Sorted by name so
    the answer is stable."""
    return [CLASSES[n].describe() for n in sorted(CLASSES)]


def _metadata(cls: DocumentClass, rng: random.Random) -> dict:
    """Era-correct capture metadata, drawn from the caller's seed.

    `created` is when the artifact came into existence as a FILE — the
    digitisation for a scan, the export for a born-digital form. It is never
    the date the document claims, which is a forensic tell rather than a
    nicety (a 1642 deed with a 1642 CreationDate advertises the forgery)."""
    producer, creator = rng.choice(cls.profiles)
    lo, hi = cls.capture_window
    year = rng.randint(lo, hi)
    return {"producer": producer, "creator": creator,
            "created": (f"{year}-{rng.randint(1, 12):02d}-"
                        f"{rng.randint(1, 28):02d} "
                        f"{rng.randint(8, 18):02d}:{rng.randint(0, 59):02d}:"
                        f"{rng.randint(0, 59):02d}"),
            "modified": None}


def emit(name: str, *, pins: dict | None = None, seed: int = 0,
         canon: dict | None = None, defect: dict | None = None,
         metadata: dict | None = None) -> tuple[bytes, dict]:
    """Render one artifact of class `name`.

    Returns `(bytes, manifest)`. The manifest is the reproduction recipe:
    replaying the same class, version, pins, canon and seed produces the same
    bytes, offline, on any machine.

    `defect` plants a fault — exactly one displayed value changes while
    everything computed around it stays honest — so the artifact can be used
    as a scorable fixture. The manifest records it as ground truth.
    """
    if name not in CLASSES:
        raise KeyError(f"unknown document class {name!r}; "
                       f"available: {sorted(CLASSES)}")
    cls = CLASSES[name]

    # One rng, threaded: the model, the metadata profile and any scan texture
    # all draw from it, so the whole artifact is a function of the seed.
    rng = random.Random(seed)

    kwargs: dict[str, Any] = {}
    if pins:
        if not cls.takes_pins:
            raise TypeError(f"{name} takes no pins; got {sorted(pins)}")
        kwargs["pins"] = dict(pins)
    if canon is not None:
        if not cls.takes_canon:
            raise TypeError(f"{name} takes no canon")
        kwargs["canon"] = canon

    model = cls.sample(rng, **kwargs)
    meta = dict(metadata) if metadata else _metadata(cls, rng)
    data = cls.render(model, metadata=meta, defect=defect)

    manifest = {
        "class": name,
        "mattermill": __version__,
        "module": cls.module,
        "seed": seed,
        "pins": dict(pins) if pins else {},
        "canon": "caller-supplied" if canon is not None else "default",
        "metadata": meta,
        "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "ground_truth": [defect] if defect else [],
        "standing": dict(cls.standing),
    }
    return data, manifest
