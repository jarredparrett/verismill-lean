"""docforge: seeded document forge + lens (foundry platform, pinned).

The forge renders realistic binary artifacts — PDFs with full metadata models
and bates stamps, xlsx with LIVE formulas and calc chains, eml with threaded
quoting — and the lens inspects them. One tool defines both sides so "what
counts as a bates stamp" is consistent between the builder that emits a
feature and the gate that verifies it.

Hard rules:
- seeded everywhere. Every forge function takes an explicit rng/seed-derived
  inputs; no wall clocks, no os.urandom. Same inputs → byte-identical bytes.
- the library is the source of truth; the CLI is a thin wrapper for agents.
"""


__version__ = "0.13.3"

from . import acord, acord130, assets, bill_of_sale, diligence, legalpdf, lease_nj, lens, nj_birth, registry, scan, vintage  # noqa: F401
