"""mattermill: deterministic PDF document classes for verismill experiments.

Each class samples a coherent model from caller-supplied canon and a seeded
random generator, then renders byte-identical PDF bytes for the same inputs.
Explicit defect hooks create scorable deltas without ambient inconsistency.
"""


__version__ = "0.16.0"

from . import acord, acord130, assets, bill_of_sale, deed_nj, diligence, estate_ma, legalpdf, lease_nj, lens, nj_birth, registry, scan, vintage  # noqa: F401
