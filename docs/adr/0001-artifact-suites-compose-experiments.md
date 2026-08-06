# Artifact Suites compose independent Experiments

An Artifact Suite indexes exact independently replayable Experiments rather
than introducing a packet-level experiment or blended score. This preserves
per-artifact scaling and rubric lineage while giving downstream products one
portable collection attestation; the cost is that suite orchestration must
explicitly coordinate and verify every child Experiment.
