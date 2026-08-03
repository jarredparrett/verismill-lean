---
name: add-emitter
description: Add a document type or rendering capability to the mattermill library via the L2 meta-build lifecycle — spec requirements first, then a coherent-by-construction sampler, renderer, defect hooks, one capability test per requirement, version bump, and a demo. Use when the user asks for a new document type, form, or artifact class ("can we make an X", "add a Y emitter"), or when a climb round finds a tell class no current tool can fix.
---

# Add an emitter (the L2 meta-build lifecycle)

The order matters: **requirements before code.** The spec is what makes a
capability testable, and writing it first is what keeps the toolsmith honest
about what "done" means.

Read `AGENTS.md` first if you have not this session.

## 1. Is a real reference artifact involved?

If the thing you are building exists in the world — a standard form, a
regulated filing, an industry export format — **stop and run
`source-template` first.** Do not author it from memory. This is the most
expensive lesson in the repo: our first ACORD 126 was a plausible-looking
invention that carried two sections belonging to a different form, and it
failed a real look immediately.

Fictional-world documents (a court order for an invented matter, a ledger for
a synthetic company) need no reference — but standard *structures* they
contain still do.

## 2. Enter the requirements in the spec

Add a `tools:` entry in `.foundry/spec.yaml`, with a meta-build note
saying **why** the tool was admitted — the tell class it answers, or the
domain it opens. Name one requirement per property a test can check:

```yaml
  - name: acord
    version: "0.2.1"
    status: active
    # Meta-build note: <why this exists; what review or tell class drove it>
    requirements:
      - acord.126-2009-08-template-contract   # layout faithful to the reference
      - acord.premium-foots                   # arithmetic by construction
      - acord.cross-field-consistency         # semantic coupling
      - acord.defect-delta-hooks
      - seeded.everywhere
```

Requirements are properties, not features: "premium foots", not "renders a
rating table". If you cannot state how a test would fail, it is not a
requirement yet.

## 3. Write the sampler — coherence by construction

`sample_<thing>(rng, **canon)` returns the complete model. Rules:

- **One `rng`**, threaded from the caller. Nothing else generates randomness.
- **Never sample a derived value.** Totals, subtotals, and cross-references
  are computed from their inputs in a `compute_*` helper at render time.
- **Couple related facts.** If two fields could contradict each other, they
  read from the same variable. Draw the *fact* ("leases equipment to
  others"), then let every field it touches follow from it. Independent
  draws are how cross-field contradictions get shipped.
- **Fix canon, sample texture.** For a canon-constrained artifact (a document
  from a known matter), the immutable facts are **caller-supplied data**, not
  code: `sample_x(rng, *, canon=None)` takes a world, ships a generic default
  so the emitter runs out of the box, and validates that every required key is
  present rather than rendering a blank where a name belongs. Sample only the
  surrounding detail, inside canon-consistent windows. See
  `vintage.DEFAULT_CANON` — and note every place name in the instrument
  derives from it, so a replacement canon relocates the whole document
  coherently. Never weld a world into an emitter: it makes the module
  unusable by anyone else and puts someone else's facts in your source tree.

## 4. Write the renderer

`render_<thing>(model, *, metadata, defect=None) -> bytes`.

- Layout constants at module scope; for a sourced form, transcribe the
  contract into a `PAGE_MARKERS`-style structure the test can assert against.
- Finish through the shared forensic tail — `legalpdf._fix_dates(...)` then
  `legalpdf._fix_id(...)` — so metadata chronology and the xref stay correct.
  `metadata["created"]` is the date the document *claims*, never render time.
- If the represented era predates the format, render a scan, not a vector
  file (`vintage` shows the pattern: typed page → rasterize → seeded scan
  artifacts → re-embed with an invisible OCR layer).

## 5. Defect hooks

A `defect` dict where each key alters exactly one displayed value while
everything around it stays honest:

```python
defect={"premium_row": (0, 99_999)}   # one row unfoots; the total stays true
defect={"premium_total": n}           # the total mis-adds; components stay true
```

Prefer hooks that break a *relationship* an expert checks (a footing, a
hierarchy, a chronology) over hooks that insert obvious garbage.

## 6. One capability test per requirement

In `libs/mattermill/tests/test_<thing>.py`, each test's docstring names its
requirement:

```python
def test_premium_foots(model):
    """acord.premium-foots: schedule premiums = exposure/1,000 x rate."""
```

Cover, at minimum: layout/contract fidelity, every coherence property,
cross-field coupling, determinism (`sample` twice equal, `render` twice
byte-identical), each defect hook breaking only its target, and metadata
chronology. Add **guard tests** for mistakes you have ruled out — asserting
the *absence* of a wrong-form section or an anachronistic citation.

## 7. Wire, version, demo, commit

```bash
# export the module
#   libs/mattermill/src/mattermill/__init__.py  -> add to the import line
# bump: pyproject.toml, __init__.py __version__, README compatibility line
# add package data (fonts/logos) to [tool.setuptools.package-data]
pip install -e libs/mattermill
python -m pytest libs/mattermill/tests/ -q && python -m pytest tests/ -q
```

Generate a demo into `.foundry/artifacts/`, then **look at the rendered
pages** — rasterize them and read them. Do not ship a document you have only
tested by string match; every layout collision this repo has shipped passed
its string assertions.

```bash
python -m mattermill.cli emit --class <name> --seed <n> \
    --out .foundry/artifacts/<name>.pdf
```

The CLI writes the sidecar manifest beside the artifact — class, version,
pins, seed, sha256, and the ground truth of anything `defect=` planted. That
manifest is the reproduction recipe, which is why the bytes never need to be
committed. Record the build on the bus:

```python
from verismill import trace
bus = trace.TraceBus(".foundry/bus.jsonl")
bus.emit("L0", "builder", "build", spec_version=...,
         outputs={"artifact": "<sha256 from the manifest>"},
         verdicts={"class": "<name>", "seed": <n>, "mattermill": "<version>"})
```

Update the mattermill README usage block, and register the class in
`registry.py` at rung `unreviewed` — a class that has never been judged says
so. Commit the code; the demo and the bus stay in `.foundry/`.

## 8. Report back

State what the emitter guarantees by construction, what the defect hooks
break, and — honestly — the known limitations, especially any value that
looks verifiable but is not (unverified codes, invented identifiers,
superseded editions). Record those in the spec's meta-build note as open
sourcing targets so the next round can close them instead of rediscovering
them.
