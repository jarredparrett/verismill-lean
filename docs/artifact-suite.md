# Artifact Suite API

`ArtifactSuite` is the public collection boundary for products that need many
independently forgeable and measurable artifacts. It coordinates child
Experiments; it does not replace them.

## Lifecycle

```text
create suite
  -> create or link independent Experiments
  -> build, independently approve, and measure each child
  -> select one exact Candidate per member
  -> derive collection qualification
  -> attest the immutable collection
```

`create_experiment()` creates a normal Experiment beneath the portable suite
root. The caller uses the complete Experiment API to freeze research and a
rubric, register model receipts, record or emit Candidates, optionally apply
human review, record independent agent approval when used, and run blind
measurement. `select_member()` freezes its exact current
Candidate and Artifact Attestation into the collection.

`link_experiment()` accepts an existing verified Experiment. It snapshots only
the Experiment state, hash-chained bus, and content-addressed objects into a
relative child directory, reopens that copy, and selects the requested
Candidate. Absolute source paths are not part of the Suite Member contract.

For a selected child that is awaiting blind judgment,
`measure_member()` delegates to the child
`Experiment.run_absolute_blind_measurement()` and selects the resulting exact
Artifact Attestation. Provider identity, resolved model, prompts, inputs, raw
outputs, usage, and independent judge contexts remain child Experiment
evidence.

Public blind execution requires either a persisted human approval or a typed,
receipt-backed independent agent approval for the exact child Candidate and
its frozen rubric. Both appear as distinct fields in the Artifact Attestation;
human evidence is not synthesized when an agent authorizes measurement. An
agent approver must use the `approval_reviewer` role and a fresh principal and
context relative to the child's builder, fixer, and development judges.

## Qualification

A Suite Attestation reports only the artifact-realism evidence class and member
counts:

- `accepted` only when every member has accepted Experiment standing;
- `not_accepted` when any member completed measurement without passing;
- `measurement_required` when any member is unselected or awaiting judgment;
- `development_only` when all members are selected but at least one has no
  formal measurement.

The suite never averages or compares member scores. Different artifacts may
use different rubric versions and dimensions, and those numbers remain
namespaced to their Experiments. Artifact-realism acceptance is not human-play
standing or public-release qualification.

## Verification and replay

`verify()` re-hashes the suite bus, opens and verifies every child Experiment,
checks each selected child state and bus against its frozen Member Attestation,
re-materializes the Artifact Attestation through the child public facade, and
recomputes the Suite Attestation. Mutation in any child invalidates the suite.

`replay()` returns the suite membership events and each authoritative child
Experiment event stream. `artifact_results()` succeeds only for a verified
suite and materializes the locked artifacts through each child
`artifact_result()` method.

Calling `attest()` seals the collection. Additions, replacement, or fresh
measurements require a child Artifact Suite; unchanged members may later be
carried forward only when their exact Experiment, Candidate, and attestations
remain verified.

## Worked child revision

This is the complete collection-level flow. `night_log` and `telegram` are
ordinary child `Experiment` objects; the builder and provider implementations
remain application adapters.

```python
from verismill import (
    ArtifactSuite, ModelConfig, PanelExecutionPolicy,
)

suite = ArtifactSuite.create(
    "runs/observatory-v1",
    suite_id="observatory_v1",
    request="Winter Observatory evidence packet",
)
night_log = suite.create_experiment(
    "night_log", request="Forge the 1937 observatory night log"
)
# Freeze sourced research/rubric, then use public Experiment methods:
# night_log.freeze_preparation(...)
# builder_ref = night_log.invoke_agent(builder_backend, builder_task)
# candidate = night_log.emit_candidate(..., builder_run=builder_ref, ...)
# development_ref = night_log.invoke_agent(development_backend, development_task)
# night_log.record_development_round(..., decision="select")
# Human approval remains available:
# night_log.record_human_review(..., decision="approve")
# Or authorize with a separate agent receipt:
approval_task = night_log.agent_approval_task(model=approval_model)
approval_run = night_log.invoke_agent(approval_backend, approval_task)
night_log.record_agent_approval(
    candidate=candidate,
    reviewer_run=approval_run,
)

models = [
    ModelConfig(provider="provider-a", model="judge-a"),
    ModelConfig(provider="provider-b", model="judge-b"),
    ModelConfig(provider="provider-c", model="judge-c"),
]
suite.measure_member(
    "night_log",
    class_name="observatory_night_log_1937",
    persona="astronomical archive conservator",
    models=models,
    backends=[judge_a, judge_b, judge_c],
)

# A separately built and measured Experiment can join through the same public
# result boundary; no Mattermill or private judge import is needed here.
suite.link_experiment("telegram", measured_telegram)
v1 = suite.attest()
assert suite.verify()["ok"]

# Canon changes invalidate only impacted artifacts. Exact unchanged bytes and
# member-attestation hashes carry forward; the telegram starts before a new
# Candidate and therefore has no inherited evaluation or standing.
child = suite.revise(
    "runs/observatory-v2",
    suite_id="observatory_v2",
    impacts={"telegram": "the canonical disappearance time changed"},
)
assert child.state["members"]["night_log"]["attestation"] == \
    suite.state["members"]["night_log"]["attestation"]

telegram = child.experiment("telegram")
# Build a child Candidate, development-select it, then preserve human direction.
telegram.record_human_review(
    candidate=telegram_candidate,
    reviewer_id="creator-42",
    decision="approve",
    feedback=[],
)
child.measure_member(
    "telegram",
    class_name="observatory_telegram_1937",
    persona="postal-telegraph historian",
    models=models,
    backends=[judge_a2, judge_b2, judge_c2],
    policy=PanelExecutionPolicy(
        max_workers=3, max_attempts=2, max_calls=5,
        max_total_tokens=120_000,
    ),
)
v2 = child.attest()

assert child.verify()["ok"]
events = child.replay()       # suite bus plus both child Experiment buses
artifacts = child.artifact_results()
assert v2["parent"]["attestation"] == v1["attestation_hash"]
```

The same policy can be supplied directly to a child's
`run_absolute_blind_measurement()`. The execution receipt is linked into the
evaluation, and relocation or mutation breaks `verify()`.
