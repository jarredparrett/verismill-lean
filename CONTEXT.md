# Verismill Experiment Context

Verismill preserves trustworthy evidence for agent-operated realism climbs.
Its language separates an artifact's independent measurement from a product's
selection of several measured artifacts.

## Language

**Experiment**:
The authoritative, independently replayable climb lineage for one artifact.
_Avoid_: Run, job, suite member

**Artifact Suite**:
An immutable selected collection of independently measured Experiments. It
aggregates qualification state without owning or blending member measurements.
_Avoid_: Batch experiment, packet experiment

**Suite Member**:
A stable identity that binds one Artifact Suite position to one exact
Experiment revision and Candidate.
_Avoid_: File, document slot

**Artifact Attestation**:
The Experiment's claim about exact artifact bytes, emitter provenance,
measurement status, and supported standing.
_Avoid_: Score, certificate

**Suite Attestation**:
A content-addressed claim over every selected Suite Member and the collection's
artifact-realism qualification. It never converts unlike rubric scores into one
average.
_Avoid_: Combined score, release standing

**Carry-forward**:
Reuse of an unchanged Suite Member whose exact Experiment, Candidate, and
Artifact Attestation remain verified in a child Artifact Suite.
_Avoid_: Skip, cached score

**Measurement Authorization**:
First-order evidence permitting the public blind panel to run for one exact
Candidate and frozen rubric. It is either a Human Approval or an Independent
Agent Approval; the evidence types remain distinct in storage and attestation.
_Avoid_: Sign-off note, blended approval

**Independent Agent Approval**:
A typed, content-addressed authorization backed by an `approval_reviewer`
AgentRun that saw the exact Candidate, artifact, and frozen rubric. Its agent
principal and context are independent from builders, fixers, and development
judges.
_Avoid_: Human review, development selection, blind score
