# Experiment API

`Experiment` is the durable public object for the complete verismill process:

```text
request -> research and frozen rubric -> development hill climb
        -> fresh blind judgment -> repeat
```

It does not choose an LLM provider. Provider adapters implement `AgentBackend`;
the experiment persists provider-neutral `AgentRun` receipts containing the
role, model revision, prompt hash, inputs, raw response, parsed result, tools,
and usage. `AgentTask.prompt_hash()` covers the role, instructions, and response
schema; `AgentTask.input_hashes()` covers the exact input bytes. `invoke_agent()`
rejects a backend receipt that does not match either contract.

## Minimal lifecycle

```python
from verismill import AgentRun, Experiment, ModelConfig, experiments_root

exp = Experiment.create(
    experiments_root() / "lease_nj",
    request="A management-company residential lease for Hoboken, New Jersey",
    experiment_id="lease_nj",
)

exp.freeze_preparation(
    research={
        "sources": [{
            "id": "nj-law",
            "kind": "statutory_prescription",
            "provenance": {"publisher": "New Jersey Legislature"},
        }],
        "coverage": {"procedural_correctness": "sourced",
                     "forensic_authenticity": "open"},
    },
    rubric={
        "version": "1.0",
        "scorer": "absolute-v0.2",
        "dimensions": [{
            "id": "procedural_correctness",
            "description": "The lease follows the governing procedure.",
            "anchors": {"0": "wrong jurisdiction", "100": "source-faithful"},
        }],
        "acceptance": {"rules": [
            {"metric": "overall_min", "operator": ">=", "value": 80},
        ]},
    },
    requirements=[{
        "id": "lease.deposit-cap",
        "property": "security deposit is within the statutory cap",
        "failure": "displayed deposit exceeds the computed cap",
    }],
)
```

The rubric's `scorer` is part of the frozen instrument. `absolute-v0.2`
produces aggregate metrics such as `overall_min`, `overall_mean`,
`discrimination_accuracy`, and `coverage_ok`; `pairwise-v1` produces
`synth_vs_real_accuracy`, `real_vs_real_pick_rate`, and `trials_scored`.
Preparation rejects acceptance metrics the selected scorer cannot produce.

Register a builder receipt, then either persist bytes directly with
`record_candidate()` or render a mattermill class with `emit_candidate()`.
Development rounds use `record_development_round()`. When a candidate is
selected, call `submit_for_blind_judgment()`, register fresh `blind_judge`
receipts, and record the evaluation.

Quoted and image-region tells are recorded with `record_tell()`. It delegates
to the existing evidence-of-k `Atlas`, then captures the resulting atlas as an
immutable experiment object; builders do not receive the raw atlas in their
role view. A harvest can only `assert_repair()`. After a fresh blind evaluation
does not re-raise the tell, `resolve_repair()` ties resolution to that exact
evaluation and candidate.

The lower-level pairwise and absolute scorers are exposed through
`record_pairwise_blind_evaluation()` and
`record_absolute_blind_evaluation()`.
`absolute_judge_tasks()` builds one isolated task per configured model using
the existing glance/deep-read protocol and complementary judge lenses;
`invoke_agent()` accepts any `AgentBackend` and persists the returned receipt.

## State machine

```text
requested -> preparing -> rubric_frozen -> climbing
          -> awaiting_blind_judgment -> accepted
                                     -> judged -> climbing
                                               -> preparing (new revision)
```

Invalid transitions raise. A rubric replacement is not a repair;
`revise()` archives the prior instrument and starts a numbered revision.

## Persistence guarantees

- **Resume:** `Experiment.open(path)` reads the last durable state.
- **Replay:** `replay()` returns the recorded event history without invoking
  agents.
- **Verify:** `verify()` checks every reachable object hash, the bus chain, and
  that published standing derives from an accepted evaluation.
- **Rerun:** `rerun(destination, from_phase="development" | "evaluation")`
  creates a fresh attempt with the same frozen inputs. An evaluation rerun
  retains the candidate but no prior agent contexts.

An LLM response is not claimed to be deterministic. Its original result is
replayable because the raw response is persisted; invoking the model again is
a new evaluation attempt linked to the original bundle.

## User-owned state and standing

`experiments_root()` resolves beneath the platform's per-user application-data
directory. `verismill home` prints that directory, and `VERISMILL_HOME`
overrides it. This keeps mutable experiments out of clones and wheels while
still allowing an explicit path for a shared or temporary store.

The mattermill catalog and emitted manifests contain static reproduction data,
not experiment standing. `verismill classes` discovers experiment bundles,
verifies them, and derives a class's local standing from an accepted blind
evaluation of a candidate recorded through `emit_candidate()` for the installed
mattermill version. Generic byte candidates cannot claim a registered class.
Invalid bundles are reported; accepted evidence for a different version is
historical rather than current.

## Model experiments

Changing a builder model creates another candidate arm under the same frozen
instrument. Changing the final judge panel creates a new measurement series.
Record immutable provider revisions where available; when a provider exposes
only a mutable alias, retain both the requested alias and the best resolved
identity and report the limitation.

Freshness is enforced by `agent_id` and `context_id`, not by model family. The
same model can therefore fill separate roles in clean contexts, while a model
ensemble can be used to measure correlated judge bias.

## Views

`view(role)` returns only information permitted to that role:

- builders receive the frozen rubric, requirements, candidate, and development
  feedback, but no final evaluation;
- blind judges receive the rubric and opaque trial packet, but no provenance,
  atlas, development history, or answer key;
- users receive progress, research coverage, scores, limitations, and next
  actions;
- auditors receive the complete record after the experiment.

`write_report()` produces the human interface: objective, research coverage,
rubric, causal findings, development decisions, blind results, conclusion, and
next action. The object store and bus are its receipts, not the interface a
reader must decipher.

## CLI

```bash
verismill init --id lease_nj \
  --request "A management-company residential lease for Hoboken"
EXP="$(verismill home)/experiments/lease_nj"
verismill source "$EXP" \
  --name governing-form --file blank-form.pdf
verismill prepare "$EXP" \
  --research research.json --rubric rubric.json \
  --requirements requirements.json
verismill emit "$EXP" --class lease_nj --seed 221 \
  --builder-run sha256:... --explanation candidate-explanation.json
verismill submit "$EXP" --candidate sha256:...
verismill agent-run "$EXP" --file blind-judge-1.json
verismill judge "$EXP" --mode absolute \
  --judge-run sha256:...
verismill status "$EXP"
verismill verify "$EXP"
verismill report "$EXP"
verismill classes
verismill rerun "$EXP" /tmp/lease-rerun --from evaluation
```
