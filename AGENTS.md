# Working in verismill

Three things live here and nothing else:

```
prompt    .claude/skills/    the lifecycle you run
climber   src/verismill/     trace (the bus) + climb (atlas, judges, orchestrator)
result    libs/mattermill/   seeded document classes
```

verismill is **agent-operated and human-triggered.** There is no autonomous
runner: a person asks for a round or an addition, you perform it using the
libraries here, and the bus records what happened. The repeating workflows are
packaged as skills — prefer them over improvising:

| Skill | Use when |
|---|---|
| `forge-document` | **the front door** — a plain request for a document ("I need a 1642 bill of sale for a ship"); triages and routes the three below |
| `source-template` | a real-world form, transcription, or facsimile must drive the work |
| `add-emitter` | adding a document type or capability to mattermill |
| `climb-round` | running a round: judge the current artifacts, harvest tells, fix, re-measure |

**Environment.** A fresh clone has no installed packages: install both
distributions editable into the project venv before doing anything —
`pip install -e . -e libs/mattermill` (plus `pytest`). Everything must then
run offline (invariant 5).

## `.foundry/` — your state, and it is not repo content

The climb's state is gitignored. You write it; a clone never carries it.
Create what you need, when you need it:

```
.foundry/
  spec.yaml          what this foundry is climbing: requirements, rubric, open findings
  atlas.json         every tell, with its quote        → climb.atlas.Atlas
  bus.jsonl          hash-chained record of every round → trace.TraceBus
  reference/         sourced blanks and facsimiles, with provenance
  rounds/<n>/        briefs, answer keys, verdicts, scores
  artifacts/         emitted documents
```

Two rules about writing it:

- **`atlas.json`** — append via `climb.atlas.Atlas.record(...)`, which dedupes
  on (class, normalized quote) and counts *distinct* trials. Don't hand-roll
  the JSON; one loud trial is not corroboration, and only the class enforces
  that.
- **`bus.jsonl`** — append-only hash chain via `trace.TraceBus.emit(...)`.
  Never edit or reorder: `TraceBus.verify()` must stay true, and it is the
  only reason a later reader should believe a score you report.

A tell's `path` is the **artifact path** the quote lives in — never a section
name ("caption", "ordered ¶11"). A section name orphans the observation from
the thing it was observed on.

## The invariants

These are what capability tests exist to protect. Breaking one is a defect
even when the output looks right.

**1. Seeded everywhere.** Same seed in → byte-identical bytes out. No
`time.time()`, no unseeded `random`, no `uuid`, no builtin `hash()` (it is
randomized per interpreter process, so it passes same-process byte-identity
tests and still breaks reproducibility across runs — found twice in shipped
code; derive display values from strings with a stable digest like
`diligence._stable_hash`), no dict iteration order that depends on insertion
by an unseeded path. reportlab canvases are built with `invariant=1`; PDF
`/ID` is a content hash (`legalpdf._fix_id`). If you add randomness, thread
the caller's `rng` through — never create your own.
`tests/test_determinism_lint.py` reads the source for this, because a
same-process test cannot catch it.

**2. Coherence by construction, not by checking.** Derived values are
computed from their inputs at render time and stored nowhere. A total that is
sampled independently of its components is a bug even if it happens to add
up. This extends past arithmetic to *semantics*: one underlying fact must
answer every field it touches. If two questions can contradict each other,
they must read from the same sampled variable. An external underwriter scored
an ACORD 126 arithmetic 96 and cross-field consistency 43 — the arithmetic
was never the problem.

**3. Defects are explicit deltas.** A `defect=` hook alters exactly one
displayed value; everything computed around it stays honest. That is what
makes a planted fault findable and provable rather than ambient noise.

**4. One capability test per requirement.** The test docstring names the
requirement it protects (`"""acord.premium-foots: ..."""`). A requirement you
accept in `.foundry/spec.yaml` without landing a test is a requirement you
have not actually accepted.

**5. No network in the render path.** `mattermill` and everything it imports
must work offline. Reference acquisition is **authoring-time only**, done by
`source-template`: its outputs land in `.foundry/reference/` and are read as
files, never fetched at render time.

**6. Forensic and period honesty.** Metadata describes the document the
artifact claims to be: represented dates, not render time; `ModDate` equals
`CreationDate` for a flattened export (never the epoch placeholder); the xref
is rebuilt after any byte-level edit (`legalpdf._rebuild_xref`). If an era
predates the format, the artifact is a *scan* of the original, not a vector
file — see `mattermill.vintage`. A round lost forensic authenticity because a
1642 membrane carried a sheetfed office scanner's producer string.

**7. Reference artifacts are load-bearing.** Never author a standard form,
registry code, or citation from memory and call it faithful. Source the real
thing (`source-template`), extract the contract, build against it. An ACORD
126 invented from memory looked convincing and carried two sections that
belong on a different form. The dimension you did not source is the dimension
that scores 5.

## Role blindness

Blindness here is **discipline, not mechanism** — nothing enforces it at
runtime, so say which role you are acting in when a session spans several.

- A **builder** working ahead of a blind round must not read the atlas, the
  answer keys, or prior scores. Work from requirements only. Knowing which
  tell you are fixing is how the measurement gets contaminated.
- Findings reach the builder as **requirements, never as answers**: *"fields
  that can contradict each other must read from one variable"*, not *"the
  underwriter noticed page 2 says yes and page 3 says no."*
- A **harvest round is inherently unblinded** — the same session records an
  external review's tells and then fixes them. That is not a violation; it is
  why **a harvest never claims a score.** The acceptance evidence for a
  harvest's fixes is the next blind round, judged by agents who were not the
  fixer. A harvest moves the code, not the rung.
- A **judge** sees only the trial trees and the cover story — never
  provenance, never the repo. `judges.COVER_STORY` deliberately does not name
  the domain; naming it tells a judge what to be suspicious of.

## Before you commit

```bash
python -m pytest tests/ -q && python -m pytest libs/mattermill/tests/ -q
```

Both green, always. Then:

- **Changed an emitter?** Bump `mattermill` version in `pyproject.toml`,
  `__init__.py`, and the README Status line.
- **Changed a class's standing?** It lives in `registry.py` and nowhere else,
  so the claim a caller sees and the claim in the README stay one object.
  State the round and the score; never an adjective.
- **Ran a round?** The measurement goes in `.foundry/`, which is not
  committed — so the commit message is where the reasoning survives. Say what
  the review found, what changed because of it, and what is still open.

Never commit a fix without its measurement, or a measurement without saying
what instrument produced it.
