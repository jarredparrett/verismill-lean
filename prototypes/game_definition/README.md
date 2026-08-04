# PROTOTYPE — smallest human-readable game definition

This throwaway prototype asks one question:

> What is the smallest concrete game definition that can express canonical
> truth, character knowledge, beliefs, objectives, evidence dependencies,
> reveal rules, and resolution without embedding runtime or document-rendering
> concerns?

The YAML file is the object under review. The terminal inspector exists only
to pressure-test its author/seat information boundary and references. It does
not persist a session, execute commands, render artifacts, or propose a
production API.

Human direction is explicit in the editable definition: premise, experience
targets, realism requirements, content boundaries, and required outcomes.
Human observations, reviewer provenance, and approval receipts deliberately
remain outside this definition; those bind to Candidate lineage in the
experiment layer and may direct a later Draft without rewriting reviewed state.

Run it from the repository root:

```bash
.venv/bin/python prototypes/game_definition/prototype.py
```

Useful keys are shown in the terminal. For a non-interactive integrity check:

```bash
.venv/bin/python prototypes/game_definition/prototype.py --check
```
