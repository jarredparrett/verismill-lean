"""The registry and the emit facade — one request in, an artifact out.

Before this module a caller had to know which emitter module to import, how
to build a `random.Random`, and how to hand-assemble a metadata dict whose
producer, creator and `created` date were forensically consistent with the
era the document claims. Seven emitters each set their own metadata, which is
seven places for the same mistake.

    from mattermill import registry
    pdf, manifest = registry.emit("bill_of_sale", pins={"vessel_name": "Unity"})

The facade owns two things the caller should never have to:

1. **Metadata, era-correctly.** A document whose era predates PDF (1993) is a
   scan, so its metadata describes the *scanner* and its `created` is the
   digitisation date — never the date the document claims. A modern form
   carries its own date. Profiles are drawn from the same seeded rng, so the
   choice is reproducible.
2. **Provenance.** Every emit returns a manifest — class, version, pins, seed,
   sha256 — which is the reproduction recipe. Same manifest in, same bytes
   out, on any machine, offline.

Realism standing is deliberately absent. It belongs to the user's verified
verismill experiments, whose research, rubric, models, and acceptance rules
cannot be represented honestly by a package-level constant.

Registered here are *document classes* — things a person asks for by name.
Shared PDF, scan, asset, and inspection machinery stays out of the catalog;
it supports classes but is not itself a user-requestable document.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Callable

from . import (__version__, acord, acord130, bill_of_sale, deed_nj, diligence,
               estate_ma, lease_nj, nj_birth, observatory, vintage)

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
LAW_OFFICE = [
    ("Adobe Acrobat Pro DC 19.021", "Microsoft Word 2016"),
    ("Adobe PDF Library 15.0", "Microsoft Word for Mac 16.30"),
    ("PDF-XChange 8.0", "Worldox Document Manager"),
]


@dataclass(frozen=True)
class DocumentClass:
    name: str
    summary: str
    module: str
    era: str
    substrate: str                 # what the artifact physically IS
    pins: dict[str, str]
    sample: Callable[..., dict]
    render: Callable[..., bytes]
    profiles: list = field(default_factory=list)
    capture_window: tuple[int, int] = (2015, 2021)
    takes_pins: bool = False
    takes_canon: bool = False
    public_facts: Callable[[dict], dict] | None = None

    def describe(self) -> dict:
        return {"name": self.name, "summary": self.summary,
                "module": self.module, "era": self.era,
                "substrate": self.substrate, "pins": dict(self.pins),
                "mattermill": __version__}


CLASSES: dict[str, DocumentClass] = {}


def register(cls: DocumentClass) -> DocumentClass:
    CLASSES[cls.name] = cls
    return cls


# ---------------------------------------------------------------------------
# The static catalog. Measurements live in user-owned experiment bundles.
# ---------------------------------------------------------------------------

register(DocumentClass(
    name="acord126",
    summary="ACORD 126 commercial general liability section — a filled "
            "application as a broker's system would export it.",
    module="mattermill.acord",
    era="contemporary",
    substrate="born-digital vector PDF",
    pins={"insured": "the named insured (str); sampled if omitted"},
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
    sample=diligence.sample_packet, render=diligence.render_packet,
    profiles=SHEETFED, capture_window=(2015, 2020), takes_canon=True,
))

register(DocumentClass(
    name="observatory_packet_1937",
    summary="A noncanonical review binder composing the independently "
            "forgeable 1937 private-observatory evidence objects.",
    module="mattermill.observatory",
    era="1937",
    substrate="scan of a mixed handwritten and typewritten observatory file",
    pins={},
    sample=observatory.sample_packet, render=observatory.render_packet,
    profiles=PLANETARY, capture_window=(2016, 2021),
    takes_canon=True, public_facts=observatory.public_display_facts,
))

for _artifact_id, _class_name, _page_index in observatory.ARTIFACT_SPECS:
    register(DocumentClass(
        name=_class_name,
        summary=("One independently forgeable 1937 private-observatory "
                 f"object: {observatory.PAGE_MARKERS[_page_index].lower()}."),
        module="mattermill.observatory",
        era="1937",
        substrate="scan of one handwritten or typewritten observatory object",
        pins={},
        sample=observatory.sample_packet,
        render=partial(observatory.render_artifact, artifact_id=_artifact_id),
        profiles=PLANETARY,
        capture_window=(2016, 2021),
        takes_canon=True,
        public_facts=partial(
            observatory.public_artifact_facts, artifact_id=_artifact_id),
    ))

register(DocumentClass(
    name="msa_1987",
    summary="A 1987 California marital settlement agreement carrying an "
            "extraordinary custody arrangement, typed on pleading paper.",
    module="mattermill.vintage",
    era="1987",
    substrate="scan of a typewritten original",
    pins={},
    sample=vintage.sample_msa, render=vintage.render_msa,
    profiles=SHEETFED, capture_window=(2016, 2021), takes_canon=True,
))

register(DocumentClass(
    name="estate_packet_ma",
    summary="A coordinated 2019 Massachusetts estate-planning and contested-"
            "probate packet: will, funded revocable trust, capacity and "
            "execution evidence, inventory, tax/liquidity plan, formal filing "
            "set, objection, and settlement.",
    module="mattermill.estate_ma",
    era="contemporary (2019)",
    substrate="searchable law-office production assembled from mixed originals",
    pins={"bates_prefix": "production prefix; defaults to ESTATE-"},
    sample=estate_ma.sample_estate, render=estate_ma.render_estate,
    profiles=LAW_OFFICE, capture_window=(2020, 2020),
    takes_pins=True, takes_canon=True,
))

register(DocumentClass(
    name="lease_nj",
    summary="A New Jersey / Hoboken management-company residential lease at a "
            "fictional, caller-replaceable address — a governed "
            "fill on the Rent Security Deposit Act, the NJ disclosure battery, "
            "and Hoboken Rent Control (Ch. 155), as a property manager's system "
            "would export it.",
    module="mattermill.lease_nj",
    era="contemporary",
    substrate="born-digital vector PDF",
    pins={"lease_type": "new | renewal",
          "monthly_rent": "int/float; sampled if omitted",
          "prior_rent": "renewal only — the rent the § 155-5 cap lifts from",
          "cpi_pct": "renewal only — CPI differential; the cap is min(5%, this)",
          "deposit_months": "float <= 1.5 (N.J.S.A. 46:8-19); deposit is derived",
          "building_year": "int — drives lead disclosure and the § 155-4 recital",
          "rent_controlled": "bool", "term_start": "ISO date",
          "pets": "bool", "seniors": "bool"},
    sample=lease_nj.sample_lease, render=lease_nj.render_lease,
    profiles=OFFICE, capture_window=(2024, 2026),
    takes_pins=True, takes_canon=True,
))

register(DocumentClass(
    name="deed_nj_1997",
    summary="A 1997 Madison, New Jersey residential bargain-and-sale deed "
            "with covenant against grantor's acts, as a county scan.",
    module="mattermill.deed_nj",
    era="1997",
    substrate="scan of an executed paper deed package",
    pins={"execution_date": "ISO date in 1997",
          "consideration": "whole-dollar transfer consideration",
          "grantor_married": "bool — grantor capacity",
          "new_construction": "bool — period RTF exemption",
          "partial_exemption": "none | senior | blind | disabled"},
    sample=deed_nj.sample_deed, render=deed_nj.render_deed,
    profiles=SHEETFED, capture_window=(2010, 2016),
    takes_pins=True, takes_canon=True,
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
    sample=nj_birth.sample_birth, render=nj_birth.render_birth,
    profiles=PLANETARY, capture_window=(2014, 2020),
    takes_pins=True, takes_canon=True,
))


# ---------------------------------------------------------------------------
# The facade
# ---------------------------------------------------------------------------

def list_classes() -> list[dict]:
    """Static capabilities for every requestable class, sorted by name."""
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
        "canon": dict(canon) if canon is not None else None,
        "metadata": meta,
        "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "ground_truth": [defect] if defect else [],
    }
    if cls.public_facts is not None:
        manifest["display_facts"] = cls.public_facts(model, defect=defect)
    return data, manifest
