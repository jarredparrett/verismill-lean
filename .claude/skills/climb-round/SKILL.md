---
name: climb-round
description: Run one L1 realism round on verismill artifacts — judge blind (or harvest an external review), record tells to the atlas, fix content coherence, revise the instrument when the rubric missed something, and log the round to the bus. Use when the user asks to run a round, judge the artifacts, harvest a review, or "climb" realism. Also use when a human pastes in an expert review of a generated document.
---

# Run an L1 climb round

A round measures, then improves, then records — in that order. Skipping the
measurement makes the next round unreadable.

Read `AGENTS.md` first if you have not this session; the invariants below
assume it.

## 0. Decide which kind of round

**Internal round** — you assemble blind trials and invoke judge subagents.
Use when there are real reference artifacts to compare against, or you want
a pairwise discrimination score.

**Harvest round** — a human supplies an external expert review of an
artifact. Rounds 2, 4, and 5 were all this kind, and they found more than
internal pairwise judging did. Skip to step 3.

**First round on a new class** — there is no real counterpart to pair against
yet, so the round is **absolute review only**: `k=3` judges, each given the
artifact alone plus a brief, scoring every rubric dimension. Lay it out as
`.foundry/rounds/<class>_abs_r<n>/trials/J{1,2,3}/{brief.md,document.pdf}` with
verdicts beside it — that is the shape round 8 used. Pairwise becomes available
the moment a genuine exemplar of the same instrument family is sourced, and it
is a strictly better measurement; take it as soon as you can.

Absolute review still yields a discrimination signal: if every judge names the
artifact synthetic at high confidence, that is the finding, and the dimension
scores tell you where the sourcing debt is.

## 1. Assemble blind trials (internal only)

```python
from verismill.climb import judges
key = judges.assemble_trial(trial_root, real_src=..., synth_src=..., rng=...)
```

The module copies sampled files into `trial_trees/<id>/{left,right}/` and
returns the answer key. **The key never enters a judge's context.** Trial
trees are gitignored; keep them out of commits.

## 2. Invoke blind judges (internal only)

Launch judge subagents — one per trial, `k=3` independent judges per
artifact for corroboration. Build the prompt from the spec's judge protocol
(`judges.protocol` in `.foundry/spec.yaml`), which is authoritative
for persona, modes, dimensions, and verdict schema. As of round 4 it
requires:

- the **domain persona** matching the artifact (`domain_personas`) — an
  insurance form gets a commercial-lines underwriter, not a bankruptcy lawyer
- **both modes**: pairwise discrimination *and* absolute domain review
- all seven rubric dimensions, including `cross_field_consistency` and
  `external_verifiability`
- deep-read instructions for the artifact classes in
  `deep_read_required_for` (compute the dates, recompute the totals, compare
  every related answer pair across pages)

Judges return JSON only. Score with `judges.parse_verdict` /
`judges.score_batch`. Capture each trial on the bus — the event's input
hashes are the exact bytes the judge saw, and the full verdict rides along —
then feed the orchestrator:

```python
import hashlib
sha = lambda p: "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()

for trial_id, verdict in verdicts.items():
    tdir = trial_root / trial_id
    bus.emit("L1", "judge", "judge_trial", spec_version=...,
             inputs={str(p.relative_to(tdir)): sha(p)
                     for p in sorted(tdir.rglob("*")) if p.is_file()},
             verdicts={"trial_id": trial_id, **verdict})
orch.on_judge_batch(keys=keys, verdicts=verdicts, spec_version=...)
```

Hash the **exact files the judge saw**, not the artifact you meant to show
them. That is the whole value of the event: it is what lets a later reader
confirm a score was earned on the bytes you claim, and an event with empty
inputs records that something happened without recording to what.

Persist raw verdicts to `<round_dir>/verdicts/<trial_id>.json` with answer
keys beside them in `answer_keys/`.

The acceptance rule is monotone toward chance (0.5): a revision is accepted
only if judge accuracy drops below the checkpoint best by more than the CI
margin.

## 3. Harvest tells into the atlas

Every finding becomes a tell with its **quoted span** — the quote is the
evidence, and a tell without one cannot be verified or regression-probed
later.

```python
from verismill.climb.atlas import Atlas
a = Atlas(".foundry/atlas.json")
a.record(tell_class="coherence.cross_field",
         quote="p2 Q6 'Y' leases wheel loader vs p3 Q5 'N' machinery rented",
         path="acord126_gl_section.pdf",
         rationale="same fact answered oppositely on different pages",
         trial_id="acord126_external_review_1",
         round_no=4)
a.save()
```

`path` is the **artifact file the quote lives in** (e.g.
`acord126_gl_section.pdf`), never a section name ("caption", "ordered ¶11")
— the dataset joiner matches tells to artifacts by path, and a section name
orphans the observation. Use `trial_id` consistently — corroboration counts
**distinct trials**, so reusing one id across a batch silently suppresses
promotion. Name
`tell_class` in the existing taxonomy where one fits (`coherence.*`,
`domain.*`, `drafting.*`, `forensic.*`, `reference.*`, `procedural.*`);
invent a new class only for a genuinely new failure mode.

## 4. Fix content — at the level the tell actually lives

Ask where the fix belongs before writing it:

- **Instance/model** — a wrong value or an incoherent pair. Fix the sampler
  so the fault *cannot* recur: couple the fields (invariant 2), don't patch
  the output.
- **Library-wide** — if one emitter has it, do the others? The round-4
  ModDate and xref tells were single fixes in `legalpdf` that repaired every
  emitter, including artifacts nobody had reviewed.
- **Unfixable by current tools** — stop. That is an L2 trigger: the tell
  becomes a spec requirement and goes to `add-emitter`.
- **Needs real-world data** (registry codes, form editions, regulator
  names) — that is `source-template`. If you cannot source it now, record it
  as an open sourcing target in the spec rather than inventing a value.

Add or extend a capability test for each fix, and a guard test for classes
you have now ruled out (`test_not_a_125` exists because v1 carried the wrong
form's sections).

## 5. Revise the instrument if it missed something

If an external review found a class our own rubric had no dimension for, the
**instrument is the finding** — content fixes alone leave you blind next
round. Update `judges.protocol` in the spec: add the dimension, extend
`deep_read_required_for`, add a domain persona. Record it as a proposal
event. Round 4 added two dimensions this way; round 2 added the absolute
review mode.

## 6. Log the round and commit

```python
from verismill.trace import TraceBus
tr = TraceBus(".foundry/bus.jsonl", session_id=<your session id>)
tr.emit("L1", "judge", "judge_batch", spec_version="0.1.0+r2",
        verdicts={"kind": "external_expert_review", "score": 62,
                  "dimensions": {...}, "note": "..."})
tr.emit("L2", "spec_author", "proposal", spec_version="0.1.0+r2",
        verdicts={"kind": "instrument_revision", "note": "..."})
assert TraceBus.verify(".foundry/bus.jsonl")
```

Then: both suites green, bump the library version if an emitter changed, and
commit.

**The measurement itself is not committable** — it lives in `.foundry/`,
which is gitignored. So the commit message is the only place the round's
reasoning survives a clone. Write it accordingly: what the review found, what
changed because of it, what is still open. A commit that says "fix cross-field
bug" and omits that three judges caught it at 0.97 has thrown away the
finding and kept only the patch.

## Standing — what a class is allowed to claim

Realism is not an adjective a builder applies. It is a rung, and a class states
which one it is on:

| Rung | Earned by |
|---|---|
| `unreviewed` | merged, capability tests green, never judged |
| `absolute r<n>` | one blind absolute round, `k=3`, dimension scores published |
| `pairwise r<n>` | blind pairwise discrimination against a real counterpart |
| `harvest-repaired, unscored` | tells fixed since the last round — **claims nothing** |

A harvest moves the code, not the rung. The rung only moves when agents that
were not the fixer judge the result. Report the class as its rung plus its open
approximations, never as "realistic".

## Report back

Give the user the dimension scores, what moved and why, what you fixed at
which level, and — explicitly — what you left open and what it would take to
close (usually reference data). Do not claim a score improvement you have
not measured; if the round was a harvest, say the next measurement is
pending.
