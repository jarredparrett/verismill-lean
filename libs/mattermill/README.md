# mattermill

**Deterministic, seeded rendering of realistic business and legal documents
— with defect-delta hooks for verifiable-fault injection.**

mattermill renders *document classes* — the things a person asks for by name:
an ACORD 126 or 130, a 1642 bill of sale engrossed on a membrane, a 1987
marital settlement typed on pleading paper, a coordinated Massachusetts
estate file, a 1997 New Jersey deed, a
multi-instrument diligence production, independently forgeable 1937
private-observatory evidence objects, or an 1878 New Jersey birth return. It renders them
**byte-identically for a given seed**, so a pipeline can regenerate, diff, and
verify every byte.

The companion **lens** reads back what was emitted, so one library defines
both sides of "what counts as a feature" — the emitter and the verifier can
never drift.

## Why it exists

Synthetic-document pipelines (RL environments, agent evals, extraction-tool
fixtures) need artifacts that are (a) realistic, (b) internally consistent,
and (c) reproducible. Faker gives you data; mattermill gives you the
*documents*, with **defect-delta hooks**: a worksheet row that stops footing,
a charge under a pricing program the state does not have, a chronology that
contradicts itself — each a deliberate, keyed fault a verifier can score an
agent against. Consistency by construction; defects by explicit delta.

## Install

```bash
pip install -e .                 # library
pip install -e ".[dev]"          # + pytest
pip install -c constraints.txt . # byte-reproducible builds (exact pins)
```

## Asking for a document

The registry is the front door. A caller who knows only a class name gets a
correct artifact — the facade owns the metadata, so nobody hand-assembles a
producer/creator/created triple that has to be forensically consistent with
the era the document claims:

```python
from mattermill import registry

registry.list_classes()          # static capability catalog
pdf, manifest = registry.emit("bill_of_sale", seed=1642,
                              pins={"vessel_name": "Hopewell", "share": 8})
```

```bash
python -m mattermill.cli classes
python -m mattermill.cli emit --class bill_of_sale --seed 1642 --out bill.pdf \
    --pin vessel_name=Hopewell --pin share=8
python -m mattermill.cli lens --file bill.pdf
```

The manifest is the reproduction recipe — class, version, pins, seed, sha256 —
and it carries the ground truth of anything `defect=` planted, so an artifact
can be used as a scorable fixture. Experiment rubrics, model receipts, scores,
and standing belong to the user's verismill data store; they are not package
metadata and are not copied into emitted manifests.

## The classes, and what each is made of

```python
from mattermill import (acord, acord130, bill_of_sale, deed_nj, diligence,
                        estate_ma, lease_nj, nj_birth, observatory, vintage)
import random

# ACORD 126 (2009/08, Commercial General Liability Section) — template-
# faithful 4-page form: limits honor the aggregate hierarchy, the Schedule
# of Hazards foots (split Prem/Ops-Products rates), the PREMIUMS box sums it,
# every "Y" answer carries an explanation surfaced in REMARKS
m126 = acord.sample_126(random.Random(26))
form = acord.render_126(m126, metadata=...)
bad  = acord.render_126(m126, metadata=..., defect={"premium_row": (0, 99999)})

# ACORD 130 (2017/05, Workers Compensation Application) — the layout PLUS a
# sourced jurisdiction. Minnesota is rated by MWCIA, not NCCI, so the class
# code is DERIVED from what the station does (8380 full service, 8381
# self-service at 90%+ gasoline receipts, 8006 with a store below it), the
# premium build-up follows Minnesota's order, and the rows Minnesota has no
# program for — ARAP, Assigned Risk Surcharge, Catastrophe, CCPAP — stay
# empty. The state is a gate: an unsourced state raises.
m130 = acord130.sample_130(random.Random(130))
appl = acord130.render_130(m130, metadata=...)
bad  = acord130.render_130(m130, metadata=..., defect={"arap": 412})  # no ARAP in MN

# Manuscript-era instruments as scans of engrossed manuscripts (a 1642 bill
# of sale of a vessel: sourced clause anatomy, regnal-year/Lady Day dating,
# fractional ship shares coupled across bargain-warranty-receipt, seal + hand)
bill = bill_of_sale.sample_bill(random.Random(1642), pins={"share": 8})
bill_pdf = bill_of_sale.render_bill(bill, metadata=...)

# Typewritten-era agreements as period-honest scans (a 1987 document cannot
# be a vector PDF — pages are seeded JPEG scans, digitisation-era metadata,
# invisible OCR layer, era-correct citations)
msa = vintage.render_msa(vintage.sample_msa(random.Random(87)), metadata=...)

# Multi-instrument diligence PACKETS — N documents from N organisations bound
# as one bates-numbered production with a document index and tab dividers.
# Per-source visual identity and cross-INSTRUMENT coherence: one sampled fact
# answers fields in documents written by parties who never spoke.
pk = diligence.sample_packet(random.Random(93))
packet = diligence.render_packet(pk, metadata=...)                  # ~26pp scan

# A New Jersey return of a birth, 1878-1900 — the printed blank a township
# assessor or city clerk filled and forwarded, as a scan
birth = nj_birth.render_birth(nj_birth.sample_birth(random.Random(1884)),
                              metadata=...)

# A New Jersey / Hoboken management-company residential lease — a GOVERNED
# FILL. The deposit is computed from the rent and capped at 1.5 months
# (46:8-19); a >=10-unit building invests it in a money-market account; a
# renewal increase is held to the lesser of 5% or CPI (Hoboken § 155-5); the
# § 155-4 rent-control disclosure and the NJ disclosure battery (flood, lead
# iff pre-1978, truth-in-renting, window guards, bed bugs, DV) attach. Two
# gates: state and municipality — Hoboken's Ch. 155 is the only rent-control
# world sourced, so another town raises.
lease = lease_nj.render_lease(lease_nj.sample_lease(random.Random(221)),
                              metadata=...)
bad   = lease_nj.render_lease(m, metadata=...,
                              defect={"security_deposit": 5460.0})  # over the cap

# A 1997 Morris County bargain-and-sale deed package, rendered as a later
# county scan with an era-correct deed, acknowledgment, and RTF-1 statement.
deed = deed_nj.render_deed(deed_nj.sample_deed(random.Random(1997)),
                           metadata=...)

# A coordinated 2019 Massachusetts estate-planning and contested-probate
# production. One canon drives the will, restated revocable trust, signed
# stock/copyright assignments, nonoperative intent memorandum, capacity
# letter, execution notes, title-aware inventory, formal-probate petition,
# family objection, and settlement/no-contest analysis. This is a law-office
# assembly, not a representation that a court accepted or docketed anything.
estate = estate_ma.sample_estate(random.Random(85), canon=my_estate_canon,
                                pins={"bates_prefix": "EST-"})
estate_pdf = estate_ma.render_estate(estate, metadata=...)
bad = estate_ma.render_estate(estate, metadata=...,
                              defect={"assigned_shares": 900})

# Independently forge the 1937 private-observatory objects. A shared canon
# keeps facts coherent, but every call returns its own bytes, manifest, hash,
# and Verismill measurement lineage. A game composes accepted results later.
observatory_model = observatory.sample_packet(random.Random(19370117),
                                               canon=my_observatory_canon)
night_log = observatory.render_artifact(
    observatory_model, artifact_id="night_observing_log", metadata=...)
altered_correction = observatory.render_artifact(
    observatory_model, artifact_id="clock_correction", metadata=...,
    defect={"correction_sign": "reverse"})

# Or use the registry so each artifact receives a class-specific manifest:
night_log, night_log_manifest = registry.emit(
    "observatory_night_log_1937", seed=19370117,
    canon=my_observatory_canon)

# Time-service dependencies are forgeable too. The fictional local L-2 card
# carries a sourced solar/sidereal conversion and keeps the public library
# entry at minute precision rather than inventing sub-second handwriting.
gatehouse_card, gatehouse_manifest = registry.emit(
    "observatory_gatehouse_time_card_1937", seed=19370117,
    canon=my_observatory_canon)

# This is only an optional review/print composition, never the canonical
# measurement unit:
review_binder = observatory.render_packet(observatory_model, metadata=...)
```

Under them sit four shared primitives, and nothing else:

| Primitive | Owns |
|---|---|
| `legalpdf` | the page machinery, the content-hashed `/ID`, the xref rebuild |
| `scan` | period-honest scan emulation, opt-in archival-color capture, and the invisible Paper-Capture OCR layer |
| `assets` | seeded wet-ink signatures, varied working hands, and received/filed stamps |
| `lens` | reading a rendered PDF back — metadata, pages, bates stamps |

## The determinism contract

- Every renderer is pure: same inputs + same seed → byte-identical bytes.
  Tested across seed sweeps.
- reportlab builds use `Canvas(invariant=1)` plus a content-hash trailer
  `/ID` (reportlab randomizes it; ours is content-addressed).
- External generative models (image gen, LLMs) are **authoring-time only**:
  their outputs are committed as assets and sampled under seed control,
  never called at render time.

Canon-driven classes (`underwriting_file`, `msa_1987`, `nj_birth`, `acord130`,
`lease_nj`, `deed_nj_1997`, `estate_packet_ma`,
`observatory_packet_1937`) take a `canon=` world. The shipped default is
invented; supply your own and every place, party and production number in the
document follows from it.

Where a class is bound to a jurisdiction, the jurisdiction is a **gate, not a
label**. `acord130` ships one sourced rating world — Minnesota's, from MWCIA —
because a rating world is a jurisdiction's own arithmetic (which pricing
programs exist, which assessments apply, what makes a risk experience-rated)
and none of it transfers. Asking for another state raises rather than printing
Minnesota's algebra under a different heading.

## Status

0.25.0 — API is unstable before 1.0 and will move while the foundry's realism
climb drives new emitters. The library is
developed inside [verismill](https://github.com/jarredparrett/verismill-lean)
as its rendering platform; it has no verismill dependencies.

Tests: `python -m pytest tests/` from this directory.
