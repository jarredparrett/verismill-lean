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


@dataclass(frozen=True)
class PanelExecutionPolicy:
    """Bounded provider-call policy for one blind panel.

    Calls may finish in any wall-clock order.  Verismill always persists arms
    and attempts in their assigned task order so scheduling cannot change the
    experiment record.
    """

    max_attempts: int = 1
    max_workers: int | None = None
    max_calls: int | None = None
    max_total_tokens: int | None = None

    def __post_init__(self) -> None:
        for name in ("max_attempts", "max_workers", "max_calls", "max_total_tokens"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool)
                                      or value < 1):
                raise ValueError(f"{name} must be a positive integer")

    def to_dict(self) -> dict[str, int | None]:
        return {
            "max_attempts": self.max_attempts,
            "max_workers": self.max_workers,
            "max_calls": self.max_calls,
            "max_total_tokens": self.max_total_tokens,
        }


class PanelExecutionError(RuntimeError):
    """A bounded panel stopped without producing a score."""

    def __init__(self, message: str, *, execution_ref: str):
        super().__init__(message)
        self.execution_ref = execution_ref


ROLE_VISIBLE_FIELDS: dict[str, frozenset[str]] = {
    "researcher": frozenset({"id", "revision", "request", "phase", "research",
                             "references"}),
    "builder": frozenset({"id", "revision", "request", "phase", "rubric",
                          "requirements", "current_candidate", "development",
                          "development_standing", "human_reviews"}),
    "fixer": frozenset({"id", "revision", "request", "phase", "rubric",
                        "requirements", "current_candidate", "development",
                        "development_standing", "human_reviews"}),
    "development_judge": frozenset({"id", "revision", "request", "phase", "rubric",
                                    "current_candidate"}),
    "blind_judge": frozenset({"phase", "rubric", "current_candidate",
                              "trial_packet"}),
    "approval_reviewer": frozenset({"id", "revision", "request", "phase",
                                     "rubric", "current_candidate"}),
    "auditor": frozenset({"*"}),
    "user": frozenset({"id", "revision", "request", "phase", "research_summary",
                       "rubric", "requirements", "current_candidate", "candidates", "development",
                       "evaluations", "atlas_summary", "standing", "measurement",
                       "development_standing", "human_reviews", "agent_approvals",
                       "next_actions"}),
}


def scoped_view(value: dict, role: str) -> dict:
    try:
        visible = ROLE_VISIBLE_FIELDS[role]
    except KeyError as exc:
        raise ValueError(f"unknown view role: {role!r}") from exc
    if "*" in visible:
        return dict(value)
    return {key: item for key, item in value.items() if key in visible}
