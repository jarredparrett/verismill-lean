---
name: forge-document
description: Produce a document that survives expert scrutiny, from a plain request — "I need a 1642 bill of sale for a ship", "make me a real-looking ACORD 126", "generate a 1987 master services agreement". Triages whether the class already exists, forces a real reference to be sourced before any code is written, defines a testable contract, builds the emitter, then measures realism in a blind round and reports standing honestly. Use as the entry point for any "make me a document that looks real" request; it dispatches to source-template, add-emitter, and climb-round.
---

# Forge a document

The request arrives as one sentence and implies a lifecycle: **triage → classify
→ source → define → build → measure → report.** This skill owns the routing and
the two decisions that are always made wrong when skipped — what the artifact
physically *is*, and whether it has been sourced enough to build.

Read `AGENTS.md` first if you have not this session. The invariants there are
what the capability tests exist to protect.

## Experiment framework (current path)

For a user-facing experiment, create and drive a persisted experiment rather
than writing round files by hand. Omit the path to create it in the operator's
data directory, then use the printed path. The CLI is the durable state machine:

```bash
verismill init --request "..." --id <experiment-id>
verismill prepare <experiment-dir> --research <json> --rubric <json> --requirements <json>
verismill source <experiment-dir> --name <name> --file <pdf>
verismill emit <experiment-dir> --class <class> --builder-run <receipt> --explanation <json>
verismill development <experiment-dir> --candidate <ref> --judge-run <receipt> --findings <json> --score <json> --decision continue
verismill submit <experiment-dir> --candidate <ref>
verismill judge <experiment-dir> --mode absolute --judge-run <receipt>
verismill continue <experiment-dir>
verismill report <experiment-dir> --out <report.md>
verismill verify <experiment-dir>
```

Every transition, artifact, model receipt, rubric revision, tell, repair, and
score belongs in the experiment store. Use `status`, `verify`, and
`replay`/`rerun` to resume or reproduce it. Different models are ordinary
provider-neutral builder or judge receipts; record provider, model, role,
prompt hash, and exact input/output hashes while keeping the rubric fixed for
a comparable round.

Treat the frozen preparation bundle as the experiment's source of truth.

**Never skip to step 4.** A document authored from memory reads as directionally
correct and fails a real look. `worked-example-1642.md`
is the full trace of one of these requests, including the round it failed and why.

## 0. Does the class already exist?

```bash
verismill status <experiment-dir> --json
verismill classes
rg "CLASSES|def emit" libs/mattermill/src/mattermill/registry.py
ls libs/mattermill/src/mattermill/
```

If it exists, **emit — do not rebuild.** A second emitter for an existing class
is how versions fork and how a fixed tell comes back. Sample with pins, render,
capture, and go to step 7.

If it exists but the request needs something it cannot express, that is not a
new class — it is a new pin or a new requirement on the existing one.

## 1. Classify the request — this is what picks the sourcing mode

Three kinds, and the kind decides what "sourced" means:

| Kind | Example | What must be sourced |
|---|---|---|
| **Standard form in current use** | ACORD 126, UCC-1, a 1099 | the blank form itself, at the right edition — **and, if the fill is governed, the rule that governs it** |
| **Period or historical instrument** | a 1642 bill of sale, an 1890 bill of lading | the **words** (a published transcription) *and* the **object** (a photographic facsimile) |
| **Fictional-world document** | a court order in an invented matter | no exemplar of the whole — but every standard structure inside it still needs one |

If the request names a **place** — "in Minnesota", "a New Jersey certificate" —
the place is a second contract, not an adjective. A national form filled on the
wrong jurisdiction's rules passes a glance and fails the first reader who works
there. Source the jurisdiction separately, and make it a gate in code.

Say out loud which kind you are in. Naming it is what stops sourcing from
looking optional.

Then answer the question the date is hiding: **what is this artifact
physically?** If the represented era predates the format, it is a photograph of
an object, not a document — and substrate, format, hand, execution and wear all
become part of the contract. PDF shipped in 1993. Make this call now; finding it
in step 4 means rebuilding everything.

## 2. The sourcing gate

**No code before a source.** Go to `source-template` and come back with a
contract.

The evidence for how hard this rule is: round 8 built a 1642 bill of sale from a
sourced *text* and nothing else. It scored `cross_field_consistency` **78** — and
`forensic_authenticity` **5**, `visual_formatting` **8**. Three blind judges
called it synthetic at 0.95 confidence. Nothing was wrong with the renderer.

> **The dimension you did not source is the dimension that scores 5.**

So enumerate the dimensions this artifact will be judged on *before* sourcing,
and make sure each has a source behind it. A transcription fixes words and fixes
nothing about the object. A blank form fixes layout and fixes nothing about how
a filled one is filled.

If a dimension cannot be sourced right now, say so plainly and record it as an
open sourcing target in the spec's meta-build note. Never invent a value that
invites lookup — a registry code, a form edition, a statutory citation. An
identifier that fails verification is a worse tell than an obviously fictional
one, because it advertises that it should resolve.

## 3. Define

The contract is what makes realism testable rather than arguable. It carries:

- the structural anatomy in order, with load-bearing strings quoted **exactly**
  from the source
- a **guard list** — what the source proved does *not* belong here
- for a scan-class artifact, a **material contract** in three parts: what you
  observed, what you implemented, and what you observed and deliberately did not
  implement

That third part is the one people skip, and it is the one that stops the next
builder from inventing what you could see but could not read.

Then enter requirements in the experiment's preparation bundle — one per
property a test can fail, with a note saying why the tool was admitted. If you
cannot state how a test would fail, it is not a requirement.

## 4. Build

Go to `add-emitter`. Coherence by construction, one `rng` threaded from the
caller, never sample a derived value, defect hooks that alter exactly one
displayed value, one capability test per requirement.

**Look at the rendered pages.** Rasterize and read them. A document that has only
been tested by string match has never been seen.

## 5. Measure — blind, and not by you

Go to `climb-round`. For a brand-new class the first round is **absolute review**
— `k=3` independent judges, the domain persona that matches the artifact, no
provenance, no repo access. Pairwise discrimination becomes available only once
a real counterpart exists to pair against, which for a period instrument means
after the facsimile is sourced.

You built it, so you do not judge it. If the same session measures and repairs,
that is a **harvest** — legitimate, often the most productive kind of round, and
it **claims no score**. The acceptance evidence is the next blind round, judged
by agents that were not the fixer.

## 6. Fix at the level the tell lives

- a wrong or incoherent value → fix the **sampler** so it cannot recur; do not
  patch the output
- present in one emitter → check every other one; the round-4 metadata tells
  were single fixes that repaired artifacts nobody had reviewed
- no current tool can fix it → that is an L2 trigger: it becomes a spec
  requirement and goes back to `add-emitter`
- needs real-world data → back to `source-template`, or record it as open

## 7. Report standing, never success

Answer "is it realistic?" with a measurement, not an adjective:

> `bill_of_sale` 0.8.0 — round 8, absolute review, k=3. cross_field 78,
> forensic 5. Rebuilt against a 1613 facsimile since; that rebuild is a harvest
> and is **unscored** pending round 9. Known approximation: the hand is an
> italic serif where a secretary hand belongs.

State what the emitter guarantees by construction, what the defect hooks break,
and what remains open with what it would take to close it. Read measurements
from the active verified experiment or `verismill classes`, never from package
metadata. If no accepted local experiment exists for the installed emitter
version, say `no local standing available` rather than implying otherwise.

---

## Environment

A fresh clone has nothing installed:

```bash
pip install -e . -e libs/mattermill && pip install pytest
```

Everything after that runs offline. Reference acquisition is authoring-time
only — its outputs are persisted, content-addressed experiment objects, never
runtime fetches.

Before committing code: both suites green, the version bumped if an emitter
changed, and the candidate regenerated with its sidecar manifest. Experiment
state remains in the operator's data directory and must verify cleanly. Preserve
the round reasoning in the commit message: never a fix without its measurement,
or a measurement without saying what instrument produced it. A repository
change discovered by the experiment must be pushed on a `codex/` branch and
published as a ready pull request (or added to the open pull request that
already owns the scope); returning with an unpushed local repair is not a
completed forge.
