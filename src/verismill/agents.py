"""Provider-neutral agent tasks and role-scoped experiment views."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Protocol

from .schema import AGENT_ROLES, AgentRun, ModelConfig


@dataclass(frozen=True)
class AgentTask:
    role: str
    instructions: str
    inputs: dict[str, bytes]
    response_schema: dict[str, Any]
    model: ModelConfig

    def __post_init__(self) -> None:
        if self.role not in AGENT_ROLES:
            raise ValueError(f"unknown agent task role: {self.role!r}")
        if not self.instructions.strip():
            raise ValueError("agent task instructions are required")
        if not isinstance(self.inputs, dict) or any(
                not isinstance(name, str) or not name or not isinstance(value, bytes)
                for name, value in self.inputs.items()):
            raise ValueError("agent task inputs must map nonempty names to bytes")
        if not isinstance(self.response_schema, dict):
            raise ValueError("agent task response_schema must be a mapping")

    def prompt_hash(self) -> str:
        """Digest the complete provider-neutral prompt contract."""
        payload = json.dumps(
            {"role": self.role, "instructions": self.instructions,
             "response_schema": self.response_schema},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode()
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    def input_hashes(self) -> dict[str, str]:
        return {name: "sha256:" + hashlib.sha256(value).hexdigest()
                for name, value in sorted(self.inputs.items())}


class AgentBackend(Protocol):
    """Adapters invoke agents; verismill owns the durable task and receipt."""

    def invoke(self, task: AgentTask) -> AgentRun: ...


ROLE_VISIBLE_FIELDS: dict[str, frozenset[str]] = {
    "researcher": frozenset({"id", "revision", "request", "phase", "research",
                             "references"}),
    "builder": frozenset({"id", "revision", "request", "phase", "rubric",
                          "requirements", "current_candidate", "development"}),
    "fixer": frozenset({"id", "revision", "request", "phase", "rubric",
                        "requirements", "current_candidate", "development"}),
    "development_judge": frozenset({"id", "revision", "request", "phase", "rubric",
                                    "current_candidate"}),
    "blind_judge": frozenset({"phase", "rubric", "current_candidate",
                              "trial_packet"}),
    "auditor": frozenset({"*"}),
    "user": frozenset({"id", "revision", "request", "phase", "research_summary",
                       "rubric", "requirements", "current_candidate", "candidates", "development",
                       "evaluations", "atlas_summary", "standing", "next_actions"}),
}


def scoped_view(value: dict, role: str) -> dict:
    try:
        visible = ROLE_VISIBLE_FIELDS[role]
    except KeyError as exc:
        raise ValueError(f"unknown view role: {role!r}") from exc
    if "*" in visible:
        return dict(value)
    return {key: item for key, item in value.items() if key in visible}
