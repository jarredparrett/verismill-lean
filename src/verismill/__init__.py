"""verismill — a prompt, a hill climber, and a result.

    prompt   .claude/skills/   the lifecycle an agent runs
    climber  this package      trace (the bus) + climb (atlas, judges, orchestrator)
    result   mattermill        seeded document classes

The climb's own state — spec, atlas, bus, scores, references — is NOT repo
content. It lives in an untraced `.foundry/` the operating agent writes, so a
clone carries the instrument and none of one foundry's accumulated findings.
"""

__version__ = "0.2.0"
