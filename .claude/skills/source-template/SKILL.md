---
name: source-template
description: Ingest a real-world reference so an emitter can be built against it rather than from memory — a blank standard form, a published transcription of a historical instrument, or a photographic facsimile of a physical original. Fetch or register the source, record provenance and its distance from the target, extract the template or material contract, and curate capability-test markers. Use before building any emitter for a document that exists in the world, when the user supplies a real form ("here's the template"), or when a review flags a form edition, registry code, layout, substrate, or hand as wrong.
---

# Source a reference

The reference artifact is the load-bearing input. A from-memory layout of a
standard form reads as directionally correct and fails expert review — wrong
section inventory, wrong edition, invented blocks. This skill turns a real
artifact into a testable contract.

Read `AGENTS.md` first if you have not this session.

## 0. Which kind of source does this artifact need?

Sourcing is not one thing. Three modes, and most artifacts need more than one:

| Mode | Source | What it fixes | What it cannot fix |
|---|---|---|---|
| **A. Blank form** | the issuer's PDF, right edition | layout, section inventory, edition marks | how a filled one is filled |
| **B. Published transcription** | a scholarly edition printing the instrument verbatim | clause anatomy, orthography, formulas | anything about the object |
| **C. Photographic facsimile** | an image of a real physical original | substrate, format, hand, execution, wear | the words, if the image is unreadable |
| **D. Statutory or manual prescription** | the law, rule or rating manual the form exists to satisfy | the field inventory, the arithmetic, what may and may not appear | the object, and the layout |

Mode D is the one people do not think to look for. For a document created by a
rule — a statutory return, a regulated application, anything a bureau publishes
a manual for — **the rule is a stronger source for the contract than a specimen
would be**, because it is what the blank was printed to satisfy. The 1878 New
Jersey birth build cleared a sourcing gate on section 2 of the registry act
after no facsimile could be obtained. The Minnesota ACORD 130 build got its
classification rule, its premium order, and its guard list from MWCIA's manuals
when the form alone would have given layout and nothing else.

Mode D also yields the thing no other mode does: **a list of what must be
absent.** A manual that publishes which programs exist in a jurisdiction has
thereby published which of the form's preprinted rows must stay empty there.

Two rules decide your modes:

1. **If the artifact renders as a scan of a physical object, mode C is not
   optional.** An era predating the format (PDF shipped 1993) forces this.
2. **Enumerate the dimensions the artifact will be judged on, and give each one a
   source.** An unsourced dimension is not a smaller risk than a wrong one —
   round 8 shipped a bill of sale sourced in mode B only. `cross_field` scored
   78; `forensic_authenticity` scored **5**.

Record the **distance from target** for every source — years, jurisdiction,
instrument family. Distance is a fact you write down, not a thing you hide. A
1536 instrument is a legitimate source for a 1642 build if the gap is stated and
the era-specific parts are calibrated separately.

## 1. Mode A — get the blank form

**Operator-supplied** (they pasted a path) — register it as-is:

```bash
PYTHONPATH=src python -m verismill.source \
    --name acord126 --file "~/Downloads/Acord126 GL.pdf"
```

**Sourced yourself** — search for an authoritative blank copy, get a direct
PDF URL, then:

```bash
PYTHONPATH=src python -m verismill.source \
    --name acord125 --url "https://example.org/acord-125.pdf"
```

Prefer issuer, regulator, or government sources over aggregators. Landing
pages usually are not the PDF; find the direct file link. The tool rejects
non-PDF payloads (an HTML error page saved as `.pdf` is a common trap).

Either path writes `.foundry/reference/<name>/`:
`source.pdf` (gitignored), `provenance.json` (origin, sha256, byte count,
retrieval date), and `contract.json` (per-page text lines + proposed
markers).

## 2. Read the artifact yourself

Rasterize and **look at every page** before trusting the text extraction:

```python
import pypdfium2 as pdfium
doc = pdfium.PdfDocument(".foundry/reference/<name>/source.pdf")
for i, page in enumerate(doc):
    page.render(scale=2.0).to_pil().save(f"/tmp/ref_p{i}.png")
```

Note what the extraction cannot tell you: the grid anatomy, which labels sit
in box corners, checkbox placement, column splits, and — critically — the
**section inventory**, including sections you assumed were there and are not.
Record the edition mark exactly (`ACORD 126 (2009/08)`).

If the form carries a wordmark or seal you need, crop it at high scale, trim
to the content bbox, and commit it under
`libs/mattermill/src/mattermill/data/` with a package-data entry.

## 2b. Mode B — a published transcription

For instruments that survive as text in scholarly editions rather than as
downloadable forms. Pull the full text, hash it, gitignore the bytes, and record
provenance with the edition, editor, volume, and the heading the instrument is
printed under — a citation someone else can follow to the same page.

Then add **calibration sources**: period-adjacent corpora that fix the decade
the transcription does not. The 1642 build sourced its clause anatomy from a
1536 instrument and its 1640s orthography and ship-share vocabulary from two
colonial record series printed from the exact decade. Calibration sources are
recorded separately from the exemplar, because they license different claims.

Some disciplines source as a **rule** rather than a corpus — dating regimes,
currency, measures, honorifics. Record the rule with its authority and compute
it in code; never sample what a calendar determines.

Quote load-bearing formulas **exactly** and note OCR damage where you found it.
Then build the clause contract in order, and a **guard list** of what the source
proved does not belong (the 1642 contract forbids a notary, *Anno Domini*, and
printed-form furniture).

## 2c. Mode C — a photographic facsimile

Mandatory for any scan-class artifact. Prefer a library, archive, or museum
digitisation with clear rights; record the item identifier, page inventory
(recto/dorse), rights status, sha256, and distance from target.

**Look at every page at full scale**, then write a `visual_material_contract`
into `contract.json` in three parts:

- **observed** — everything the image tells you about the object: dimensions and
  orientation, edge treatment, ruling, scripts and their number, execution
  furniture (seals, tags, plicae, panels), what is on the reverse, how staining
  and wear distribute, how the text fills the surface
- **implemented_in_<version>** — what the emitter actually does
- **observed_but_NOT_implemented** — what you could see and chose not to build

The third list is the one people skip, and it is the one that stops the next
builder inventing what you could see but could not read. If a feature is visible
but illegible — a memorandum in a hand you cannot transcribe — it goes here, not
into the renderer.

Note what the facsimile still cannot tell you (colour, true scale, tone under a
grayscale-optimised scan) and record it as `not_yet_sourced`.

## 2d. Mode D — the rule the document exists to satisfy

Find the instrument that governs: the statute and its section, the bureau's
manual, the regulator's order. Pull it, hash it, gitignore the bytes, and record
provenance with the edition or printing date and the exact rule numbers you
read.

Then extract three things:

- **the field inventory** — what the rule requires the document to contain, in
  the rule's own terms
- **the arithmetic** — any order of operations the rule fixes, quoted. Where the
  rule says a figure *excludes* something, that exclusion is a test
- **the guard list** — what the rule proves does not belong here, especially
  where a national form prints a row that this jurisdiction has no program for

A form used across jurisdictions is really two contracts: the sheet, and the
place. Sourcing the sheet and inventing the place produces a document that
passes a glance and fails the first reader who works there. When the place is
sourced, make it a **gate in code** — refuse the jurisdictions you have not
sourced rather than letting one jurisdiction's arithmetic render under
another's name.

Never cite a source for work it did not do. A file in the reference directory
earns its provenance entry by being **read and used**, not by being downloaded
and plausibly titled.

## 3. Curate the markers (mode A)

`contract.json` carries `proposed_markers` — a heuristic (form-number and
pagination marks, then caps section lines longest-first). They are proposals,
not a verdict. Curate into the emitter's `PAGE_MARKERS`, keeping strings
that are:

- **structural** (section headers, column headings, footer marks), not
  filled values
- **long enough** not to collide inside a content stream
- **page-ordered**, so the test can assert page sequence

Text extraction merges same-baseline runs, so a footer may arrive as one long
line — assert the substring you actually care about.

## 4. Hand off

Go to `add-emitter` with the contract in hand. Each mode hands off a different
kind of test:

- **A** — the markers become the layout-fidelity test; the sections you found
  become the structure to build
- **B** — the clause anatomy becomes an ordered-marker test; the formulas become
  exact-string assertions; the calibration corpora set the orthography
- **C** — the material contract becomes assertions about the *object*: page
  geometry, orientation, page count, image-vs-vector, which era the metadata may
  claim

And in every mode, a **guard test** for what the reference proved does *not*
belong here.

## 5. When you cannot source it

Say so plainly and record it in the spec's meta-build note as an open
sourcing target — never invent the value. This applies especially to things
that *invite* verification: registry identifiers (NAIC codes, bar numbers),
classification codes, form editions, regulator names, statutory citations. A
realistic-looking identifier that fails lookup is a worse tell than an
obviously fictional one, because it advertises that it should resolve.
