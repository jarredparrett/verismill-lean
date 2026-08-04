# Worked example: "I need a 1642 bill of sale for a ship"

> Historical trace: this predates the persisted experiment framework. Preserve
> its sourcing and realism lessons, but execute new work through
> `init/prepare/agent-run/emit/development/submit/judge/continue`.

The complete trace that produced `.foundry/artifacts/bill_of_sale_1642.pdf`. Read it
for the shape of the process, and for the one lesson that cost a whole round:
**the dimension you did not source is the dimension that scores 5.**

Two sourcing passes, one build, one blind round, one rebuild. The second
sourcing pass would never have happened if the round had not been run blind.

---

## 1. Classify — and find the inference hiding in the date

A period instrument. Both halves need sourcing: the words *and* the object.

The load-bearing inference is not about bills of sale at all. PDF shipped in
1993. Nothing made in 1642 can be a vector file, so the artifact is not a
document — it is **a photograph of an object**, and every physical decision
(substrate, format, hand, execution, wear) is now part of the contract.

Make that call in step 1. It determines what you must source, what the renderer
has to do, and what the tests assert. Discovering it in step 4 means rebuilding.

## 2. Source the words

*Select Pleas in the Court of Admiralty*, vol. I, ed. R. G. Marsden (Selden
Society vol. 6, London, 1894), no. 15 (1536) — a complete bill of sale of half
a ship, from HCA File 4. 754,323 bytes of OCR text, sha256 recorded, file
gitignored.

106 years earlier than the target: the closest *complete* instrument of the
exact type available in full text. Distance from target is a fact you record,
not a thing you hide.

Two calibration corpora for the decade the target actually sits in:

- *Records of the colony and plantation of New-Haven, 1638–1649* — 1640s
  orthography and vessel vocabulary
- *Records of the governor and company of the Massachusetts Bay*, vol. I —
  ship-share transaction language ("the 1/8 pt of the sd shipp")

And one discipline sourced as a rule rather than a corpus: England dated by
regnal year and started the legal year on 25 March until 1752. Charles I
acceded 27 March 1625, so 18 Charles I runs 27 Mar 1642 – 26 Mar 1643, and a
date of 1 Jan – 24 Mar 1642 is 17 Charles I, legal year 1641.

**What this fixed:** the ten-clause anatomy in order, period orthography, the
penal-bond defeasance structure, the dating regime.

**What it could not fix:** anything whatsoever about the object. A transcription
prints words. It does not tell you the skin is landscape.

## 3. Define

`contract.json` — the clause contract, in order, with the load-bearing formulas
quoted exactly from the source, plus a **guard list** of things the source
proved do *not* belong (no notary, no *Anno Domini*, no printed-form furniture,
no "Signed, sealed").

The frozen experiment requirements — six properties a test can fail:
`billofsale.clause-contract`, `.regnal-dating`, `.couplings`,
`.manuscript-scan`, `.defect-delta-hooks`, `seeded.everywhere`.

## 4. Build

Coherence by construction: the vessel's whole value is `tuns × rate`, the
consideration is a share of that value, the penal bond is twice the
consideration. One sampled share answers the bargain, the warranty, and the
receipt. Pentecost is the computed Julian movable feast, not a sampled one.

Scan-class render: engross the manuscript → rasterize → seeded scan artifacts →
re-embed as JPEG with an invisible render-mode-3 OCR layer, metadata dated at
**digitization** (1993 or later), `ModDate == CreationDate`.

One capability test per requirement, plus guard tests for the ruled-out classes.

## 5. Measure — round 8, blind, absolute mode, k=3

Three judges, domain persona, no provenance, no repo. All three picked
synthetic, at 0.95 / 0.97 / 0.95 confidence.

| dimension | score |
|---|---|
| cross_field_consistency | 78 |
| drafting_realism | 55 |
| external_verifiability | 42 |
| procedural_correctness | 18 |
| financial_operational | 15 |
| transaction_provenance | 10 |
| visual_formatting | 8 |
| **forensic_authenticity** | **5** |

Read the *shape*, not the average. The dimension backed by a real source scored
78. The dimension backed by nothing scored 5. That is not a bug in the renderer;
it is sourcing debt, arriving on schedule.

Fourteen tells recorded. The six corroborated by all three judges:

- `forensic.scan` — "uniform digital italic typeface: every recurring glyph is
  identical"; no pen-pressure variation, no secretary hand
- `forensic.substrate` — "bright white and pristine"; US Letter, no parchment
  tone, no folds, no chain lines, no deckle
- `forensic.metadata` — "Canon DR-C240 / Adobe Paper Capture"; a sheetfed office
  scanner cannot have fed a 1642 skin
- `procedural.execution` — the text executes by mark, yet fluent cursive
  signatures appear
- `procedural.execution` — witnesses are anonymous scrawls aligned to no named
  party
- `coherence.money` — £430 for one eighth of an 8-tun shallop implies a £3,440
  whole vessel, off by an order of magnitude for the period

## 6. Source the object — the step the process was missing

This is the pass that had to be *added* to the lifecycle. Round 8 proved the
sourcing step was only half done.

Deed of bargain and sale, Henry Walker to William Shakespeare and trustees, of
the Blackfriars gatehouse, 10 March 1613 (Old Style). World Digital Library item
11289, mirrored on Wikimedia Commons; public domain; 2 pages, recto and dorse.

29 years from the target, same polity, same instrument family, same execution
regime — and the only source that speaks to the object rather than the words.

Recorded in `contract.json` as `visual_material_contract`, in three parts:

1. **observed** — landscape membrane; scalloped chirograph head; two scripts and
   a cadel initial; a plica carrying a ruled name panel, a threaded tag and
   pendent wax; a dorse with show-through, witness subscriptions and a sideways
   docket; staining that stops at the skin edge; text that fills the skin
2. **implemented_in_0_8_0**
3. **observed_but_NOT_implemented** — the secretary hand; the Latin sealing
   memorandum (visible but not transcribed, therefore not invented); prick marks
   and ruling; the counterpart

Category 3 is the one people skip. Writing it down is what stops the next
builder from inventing what you could see but could not read.

## 7. Rebuild against the object

Landscape membrane sized to its own line count. Scalloped head. Plica with a
ruled name panel and a pendent seal on a threaded tag hanging below the skin's
foot. Dorse with mirrored show-through, witness hands, and a docket rotated
along the fold. Cadel initial. Per-word jitter and sub-degree baseline
rotation. Substrate mottling clipped to the skin path so nothing bleeds onto
the platen.

And the metadata tell fixed at the level it lives: `Zeutschel OS 12002` — a
planetary overhead scanner, which is what actually digitizes a membrane.

## 8. What is not claimed

**Round 8's scores stand.** The rebuild was measured and repaired inside one
session, which is a harvest, and a harvest claims no score. The acceptance
evidence is round 9 — judged blind, by agents that were not the fixer, and now
pairwise for the first time, because a real exemplar finally exists to pair
against.

Still open, and recorded as such: the secretary hand (the italic serif is a
known approximation); the Latin memorandum; prick marks and ruling; the
counterpart; a maritime bill specifically; and a colour full-resolution
facsimile with a scale bar, since parchment tone is currently inferred from a
grayscale-friendly image.

---

## The four things this example is here to teach

1. **Decide what the artifact physically is before you write code.** "A 1642
   document" is a photograph, not a PDF.
2. **Source every dimension you intend to be judged on.** Words and object are
   two sources, not one.
3. **Run the round blind before you believe anything.** The build looked
   finished. It scored 5 on forensics.
4. **Separate measuring from fixing.** The session that repairs a tell cannot be
   the session that scores the repair.
