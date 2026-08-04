from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_measured_repairs_are_published_as_pull_requests():
    """workflow.measured-repair-pr: experiment-driven code repairs cannot
    end as unpushed workstation state."""
    agents = (ROOT / "AGENTS.md").read_text()
    climb = (ROOT / ".agents/skills/climb-round/SKILL.md").read_text()
    forge = (ROOT / ".agents/skills/forge-document/SKILL.md").read_text()

    for raw_contract in (agents, climb, forge):
        contract = " ".join(raw_contract.split())
        assert "ready pull request" in contract
        assert "open pull request" in contract
    assert "A harvest remains unscored" in agents
    assert "fresh blind evidence" in climb


def test_blind_measurement_is_integrated_into_forge_completion():
    """workflow.integrated-blind-measurement: selection must seal and continue
    through blind measurement without requiring another user request."""
    agents = (ROOT / "AGENTS.md").read_text()
    climb = (ROOT / ".agents/skills/climb-round/SKILL.md").read_text()
    forge = (ROOT / ".agents/skills/forge-document/SKILL.md").read_text()
    emitter = " ".join(
        (ROOT / ".agents/skills/add-emitter/SKILL.md").read_text().split())
    readme = (ROOT / "README.md").read_text()

    assert "Blind measurement is part of the build" in agents
    assert "automatically seals" in agents
    assert "Do not pause for a separate user request" in climb
    assert "Do not stop or hand back after development selection" in forge
    assert "blind measurement is part of the emitter build" in emitter
    assert "continues through measurement without requiring another user prompt" in readme
