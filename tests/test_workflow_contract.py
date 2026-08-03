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
