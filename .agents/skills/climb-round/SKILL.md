---
name: climb-round
description: Run one persisted L1 realism cycle in a verismill experiment — resume state, register model receipts, blind-judge a candidate, record quoted tells, repair or revise, emit again, and preserve acceptance evidence. Use when the user asks to judge, harvest, climb, continue, loop, rerun, or compare models, or pastes an expert review.
---

# Run a persisted climb round

Treat the experiment as the source of truth. A round is:

**measure → record tells → repair/revise → emit → blind-judge again**

Read `AGENTS.md` first. Preserve builder/judge blindness and every seeded,
coherence, reference, and forensic invariant.

## 1. Resume, do not reconstruct

```bash
verismill status <experiment-dir> --json
verismill verify <experiment-dir>
```

Follow the persisted phase. Use `verismill continue` only after a failed blind
evaluation has left the experiment `judged`. Use `rerun` for a distinct attempt
from a recorded boundary and `replay` to inspect history without invoking agents.

The store must retain research, requirements, frozen rubric and scorer,
references, pins, candidates, manifests, exact artifact hashes, agent receipts,
development attempts, tells, repairs, evaluations, standing, and the bus chain.
Do not infer experiment state from a PDF, README, or registry entry.

## 2. Choose the round kind

- **Absolute blind review:** candidate alone; `k=3` fresh judges, every rubric
  dimension, independent identities/contexts, and assigned
  arithmetic/procedural/forensic lenses.
- **Pairwise blind review:** use when a genuine comparable exemplar exists;
  keep answer keys outside judge context.
- **Harvest:** human/external review or unblinded fixing; record tells and assert
  repairs, but claim no score.

Use `Experiment.absolute_judge_tasks(...)` for isolated absolute tasks. For
pairwise trials, use `verismill.climb.judges.assemble_trial(...)` with hidden
keys stored outside the judge context.

## 3. Register every model invocation

Models are experimental factors, not hidden implementation details:

```bash
verismill agent-run <experiment-dir> --file <receipt.json>
```

Each provider-neutral receipt identifies role, provider/model/config, fresh
agent and context identity, prompt hash, exact input hashes, raw and parsed
output, and usage. Changing models is comparable only when candidate bytes,
rubric, persona, schema, and assigned lens stay fixed. Never reuse a
builder, fixer, development-judge, or prior blind-judge identity in a fresh
blind panel.

## 4. Persist the blind measurement

```bash
verismill submit <experiment-dir> --candidate <candidate-ref>
```

Register each judge receipt, then call
`Experiment.record_absolute_blind_evaluation(judge_runs=..., assigned_lenses=...)`
or `Experiment.record_pairwise_blind_evaluation(keys=..., judge_runs=...)`.
These parse receipts, score the panel, apply the frozen rubric's acceptance
rules, preserve exact evidence, and transition to `accepted` or `judged`.
The CLI exposes the same trusted scorers:

```bash
verismill judge <experiment-dir> --mode absolute \
  --judge-run <receipt-ref> --judge-run <receipt-ref> --judge-run <receipt-ref>
verismill judge <experiment-dir> --mode pairwise --keys <hidden-keys.json> \
  --judge-run <receipt-ref>
```

Never submit caller-authored score JSON; standings derive from parsed judge
receipts and an explicit scorer.

Never substitute an informal acceptance threshold after seeing results.

## 5. Record every adverse tell through the experiment

Every finding needs the artifact path and either an exact quote or image region:

```bash
verismill tell <experiment-dir> --class <taxonomy.class> \
  --path <artifact-path> --rationale "..." --trial-id <unique-trial> \
  --round <n> --quote "..."
```

Use distinct trial IDs. Reuse the experiment's existing class naming convention
when one fits; the framework does not currently enforce a global taxonomy.
Do not turn favorable observations into defects. Never hand-edit the atlas; its
API deduplicates evidence and counts distinct trials.

## 6. Repair at the tell's level

- Fix wrong or contradictory values in the sampler/model so recurrence is
  impossible.
- Fix shared metadata, scan, or PDF defects in the common library.
- Route missing renderer capability to `add-emitter`.
- Route unsourced editions, identifiers, rules, or physical features to
  `source-template`.
- When a review reveals a missing rubric dimension, revise/rerun while retaining
  the frozen prior revision for comparison.

Add one capability test per new requirement. After a harvest fix, call
`Experiment.assert_repair(...)` or:

```bash
verismill repair <experiment-dir> --class <taxonomy.class> --round <n> \
  --path <artifact-path> --quote "..."
```

A repair remains `repair_asserted`, not resolved, until a fresh blind round does
not reproduce it. After that round, resolve it against the exact evaluation:

```bash
verismill resolve-repair <experiment-dir> --evaluation <evaluation-ref> \
  --class <taxonomy.class> --path <artifact-path> --quote "..."
```

The command refuses an older evaluation, a different candidate, or a verdict
that re-raised the same quoted span or image page.

## 7. Emit and record development work

```bash
verismill emit <experiment-dir> --class <class> --builder-run <receipt-ref> \
  --explanation <json> --seed <n> --pins <pins.json>
verismill development <experiment-dir> --candidate <candidate-ref> \
  --judge-run <receipt-ref> --findings <json> --score <json> \
  --decision <select|reject|continue>
```

Inspect every rendered page before selection. Development scores guide the hill
climb but never substitute for blind acceptance.

## 8. Close the cycle

```bash
verismill report <experiment-dir> --out <report.md>
verismill verify <experiment-dir>
```

Run both test suites if code changed. Report the blind score distribution,
acceptance result, model panel, asserted repairs, unresolved tells, and sourcing
debt. Leave a failed round `judged` until the next explicit `continue`; preserve
an accepted candidate with its frozen evidence.

If the round changed repository code, it is not closed while the fix exists
only in the worktree. Commit with the experiment ID and measuring instrument,
push a `codex/` branch, and open a ready pull request—or update the open pull
request that already owns the scope. Link the PR in the operator report. A harvest PR reports
an asserted repair, never a score or resolved tell; fresh blind evidence is
still required.
