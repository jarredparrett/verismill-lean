# PROTOTYPE — minimal Game Release and seat projection

This throwaway prototype asks:

> What must one immutable Game Release contain so the same release can produce
> an authorized player-seat snapshot, a replayable session, and a complete
> physical export without consulting mutable authoring state?

The release is a self-contained bundle: `release.json` owns rules and content
references, while `materials/` contains the exact content-addressed bytes. The
pure model functions verify the bundle, replay append-only events, project one
seat, authorize material access, and derive a physical file tree. The terminal
shell only drives those functions in memory.

Run it from the repository root:

```bash
.venv/bin/python prototypes/game_release/prototype.py
```

Run the non-interactive boundary check with:

```bash
.venv/bin/python prototypes/game_release/prototype.py --check
```

This is not production code and its text files are not a claim of print-ready
artifact fidelity. It tests the release's data sufficiency and information
boundaries. It deliberately contains no Draft, model context, rendering
instructions for Mattermill, mutable standing, or human-review evidence.

Measurement standing is an append-only Release Attestation that references the
immutable Release ID. New human reviews, playtests, and blind panels can
therefore accumulate without changing the identity or bytes of the playable
release. A frozen attestation snapshot may accompany a distributed release,
but it is a sidecar rather than part of the release's content hash.
