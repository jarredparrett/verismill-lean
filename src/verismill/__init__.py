"""verismill — persistent experiments for climbing synthetic documents.

    prompt   .agents/skills/   the lifecycle an agent runs
    climber  this package      experiment facade + trace bus + atlas + judges
    result   mattermill        seeded document classes

The low-level atlas, judge harness, source tooling, and trace bus remain
available.  :class:`Experiment` is the public lifecycle and persistence facade.
"""

from .agents import AgentBackend, AgentTask
from .experiment import Experiment
from .catalog import class_catalog, derive_local_standings, experiments_root, user_data_root
from .schema import AgentRun, ModelConfig, Phase

__all__ = ["AgentBackend", "AgentRun", "AgentTask", "Experiment", "ModelConfig",
           "Phase", "class_catalog", "derive_local_standings", "experiments_root",
           "user_data_root"]

__version__ = "0.7.0"
