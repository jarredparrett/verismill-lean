"""Validated, human-readable contracts for a verismill experiment.

The schema is deliberately stdlib-only.  Experiment records must remain
readable and verifiable long after a particular agent SDK has disappeared.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import copy
from enum import StrEnum
import re
from typing import Any


SCHEMA_VERSION = "1.0"
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
DEFAULT_SCORER = "absolute-v0.3"
ABSOLUTE_V02_DIMENSIONS = (
    "drafting_realism",
    "procedural_correctness",
    "cross_field_consistency",
    "financial_operational",
    "external_verifiability",
    "visual_formatting",
    "forensic_authenticity",
)
SCORER_METRICS = {
    "absolute-v0.2": frozenset({
        "k", "overall_min", "overall_mean", "coherence_profile",
        "synthetic_calls", "discrimination_accuracy", "coverage_ok",
    }),
    "absolute-v0.3": frozenset({
        "k", "overall_min", "overall_mean", "coherence_profile",
        "synthetic_calls", "discrimination_accuracy", "coverage_ok",
    }),
    "pairwise-v1": frozenset({
        "synth_vs_real_accuracy", "real_vs_real_pick_rate", "trials_scored",
    }),
}


class Phase(StrEnum):
    REQUESTED = "requested"
    PREPARING = "preparing"
    RUBRIC_FROZEN = "rubric_frozen"
    CLIMBING = "climbing"
    AWAITING_BLIND_JUDGMENT = "awaiting_blind_judgment"
    JUDGED = "judged"
    ACCEPTED = "accepted"


TRANSITIONS: dict[Phase, frozenset[Phase]] = {
    Phase.REQUESTED: frozenset({Phase.PREPARING}),
    Phase.PREPARING: frozenset({Phase.RUBRIC_FROZEN}),
    Phase.RUBRIC_FROZEN: frozenset({Phase.CLIMBING}),
    Phase.CLIMBING: frozenset({Phase.AWAITING_BLIND_JUDGMENT}),
    Phase.AWAITING_BLIND_JUDGMENT: frozenset({
        Phase.CLIMBING, Phase.JUDGED, Phase.ACCEPTED,
    }),
    Phase.JUDGED: frozenset({Phase.CLIMBING, Phase.PREPARING}),
    Phase.ACCEPTED: frozenset({Phase.PREPARING}),
}


AGENT_ROLES = frozenset({
    "researcher", "builder", "fixer", "development_judge", "blind_judge",
    "auditor",
})


def require_keys(value: dict, keys: set[str], label: str) -> None:
    missing = keys - set(value)
    if missing:
        raise ValueError(f"{label} missing keys: {sorted(missing)}")


def validate_research(value: dict) -> None:
    require_keys(value, {"sources", "coverage"}, "research")
    if not isinstance(value["sources"], list) or not isinstance(value["coverage"], dict):
        raise ValueError("research sources must be a list and coverage a mapping")
    for i, source in enumerate(value["sources"]):
        if not isinstance(source, dict):
            raise ValueError(f"research source {i} must be an object")
        require_keys(source, {"id", "kind", "provenance"}, f"research source {i}")


def normalize_rubric(value: dict) -> dict:
    """Copy a new rubric and select the domain-driven scorer by default."""
    normalized = copy.deepcopy(value)
    normalized["scorer"] = value.get("scorer", DEFAULT_SCORER)
    for dimension in normalized.get("dimensions", []):
        if isinstance(dimension, dict):
            dimension.setdefault("applicability", "required")
    if normalized["scorer"].startswith("absolute-"):
        acceptance = normalized.get("acceptance")
        if isinstance(acceptance, dict) and isinstance(acceptance.get("rules"), list):
            if not any(rule.get("metric") == "coverage_ok"
                       for rule in acceptance["rules"] if isinstance(rule, dict)):
                acceptance["rules"].append(
                    {"metric": "coverage_ok", "operator": "==", "value": True}
                )
    return normalized


def validate_rubric(value: dict) -> None:
    require_keys(value, {"version", "dimensions", "acceptance"}, "rubric")
    scorer = value.get("scorer", DEFAULT_SCORER)
    if scorer not in SCORER_METRICS:
        raise ValueError(f"unsupported rubric scorer: {scorer!r}")
    if not isinstance(value["dimensions"], list) or not value["dimensions"]:
        raise ValueError("rubric dimensions must be a non-empty list")
    seen: set[str] = set()
    for i, dimension in enumerate(value["dimensions"]):
        if not isinstance(dimension, dict):
            raise ValueError(f"rubric dimension {i} must be an object")
        require_keys(dimension, {"id", "description", "anchors"},
                     f"rubric dimension {i}")
        if dimension["id"] in seen:
            raise ValueError(f"duplicate rubric dimension: {dimension['id']}")
        seen.add(dimension["id"])
        if not isinstance(dimension["anchors"], dict) or not dimension["anchors"]:
            raise ValueError(f"rubric dimension {dimension['id']} needs score anchors")
        applicability = dimension.get("applicability", "required")
        if applicability not in {"required", "not_applicable"}:
            raise ValueError(
                f"rubric dimension {dimension['id']} applicability must be "
                "required or not_applicable"
            )
        if applicability == "not_applicable" and not str(
                dimension.get("applicability_reason", "")).strip():
            raise ValueError(
                f"rubric dimension {dimension['id']} needs an applicability_reason"
            )
    applicable = {
        dimension["id"] for dimension in value["dimensions"]
        if dimension.get("applicability", "required") == "required"
    }
    if not applicable:
        raise ValueError("rubric requires at least one applicable dimension")
    if scorer == "absolute-v0.2":
        declared = tuple(dimension["id"] for dimension in value["dimensions"])
        if declared != ABSOLUTE_V02_DIMENSIONS:
            raise ValueError(
                "absolute-v0.2 is a fixed legacy instrument; rubric dimensions "
                f"must exactly match {ABSOLUTE_V02_DIMENSIONS!r}; use "
                "absolute-v0.3 for a domain rubric"
            )
        if applicable != set(ABSOLUTE_V02_DIMENSIONS):
            raise ValueError("absolute-v0.2 dimensions cannot be not_applicable")
    acceptance = value["acceptance"]
    if not isinstance(acceptance, dict) or not isinstance(acceptance.get("rules"), list) \
            or not acceptance["rules"]:
        raise ValueError("rubric acceptance.rules must be a non-empty list")
    for i, rule in enumerate(acceptance["rules"]):
        require_keys(rule, {"metric", "operator", "value"}, f"acceptance rule {i}")
        if rule["metric"] not in SCORER_METRICS[scorer]:
            raise ValueError(
                f"metric {rule['metric']!r} is not produced by {scorer}")
        if rule["operator"] not in {">=", ">", "<=", "<", "=="}:
            raise ValueError(f"unsupported acceptance operator: {rule['operator']!r}")
    if scorer.startswith("absolute-"):
        strict_overall = any(
            rule["metric"] == "overall_min" and rule["operator"] in {">=", ">"}
            and isinstance(rule["value"], (int, float)) and rule["value"] >= 80
            for rule in acceptance["rules"]
        )
        strict_coverage = any(
            rule["metric"] == "coverage_ok" and rule["operator"] == "=="
            and rule["value"] is True
            for rule in acceptance["rules"]
        )
        if not strict_overall:
            raise ValueError("absolute release standing requires overall_min >= 80")
        if not strict_coverage:
            raise ValueError("absolute release standing requires coverage_ok == true")
    dimension_requirements = acceptance.get("dimension_requirements", [])
    if not isinstance(dimension_requirements, list):
        raise ValueError("acceptance.dimension_requirements must be a list")
    required_dimensions: set[str] = set()
    for i, requirement in enumerate(dimension_requirements):
        if not isinstance(requirement, dict):
            raise ValueError(f"dimension requirement {i} must be an object")
        require_keys(requirement, {"dimension", "operator", "value"},
                     f"dimension requirement {i}")
        dimension_id = requirement["dimension"]
        if dimension_id not in applicable:
            raise ValueError(
                f"dimension requirement names non-applicable dimension {dimension_id!r}"
            )
        if dimension_id in required_dimensions:
            raise ValueError(f"duplicate dimension requirement: {dimension_id}")
        required_dimensions.add(dimension_id)
        if requirement["operator"] not in {">=", ">", "<=", "<", "=="}:
            raise ValueError(
                f"unsupported dimension operator: {requirement['operator']!r}"
            )


def validate_requirements(value: list[dict]) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError("requirements must be a non-empty list")
    for i, requirement in enumerate(value):
        if not isinstance(requirement, dict):
            raise ValueError(f"requirement {i} must be an object")
        require_keys(requirement, {"id", "property", "failure"}, f"requirement {i}")


@dataclass(frozen=True)
class ModelConfig:
    """The effective model configuration, not merely a mutable alias."""

    provider: str
    model: str
    resolved_model: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    tools: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.model.strip():
            raise ValueError("model provider and model are required")

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "resolved_model": self.resolved_model,
            "parameters": self.parameters,
            "tools": list(self.tools),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "ModelConfig":
        require_keys(value, {"provider", "model"}, "model config")
        return cls(provider=value["provider"], model=value["model"],
                   resolved_model=value.get("resolved_model"),
                   parameters=dict(value.get("parameters", {})),
                   tools=tuple(value.get("tools", ())))


@dataclass(frozen=True)
class AgentRun:
    """A persisted invocation receipt shared by all agent backends."""

    run_id: str
    agent_id: str
    context_id: str
    role: str
    model: ModelConfig
    prompt_hash: str
    input_hashes: dict[str, str]
    raw_response: str
    parsed_output: dict[str, Any]
    usage: dict[str, Any] = field(default_factory=dict)
    tool_trace: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.role not in AGENT_ROLES:
            raise ValueError(f"unknown agent role: {self.role!r}")
        for name in ("run_id", "agent_id", "context_id", "prompt_hash"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"agent run {name} is required")
        if not _SHA256.fullmatch(self.prompt_hash):
            raise ValueError("agent run prompt_hash must be sha256 plus 64 lowercase hex digits")
        if not isinstance(self.raw_response, str) or not self.raw_response.strip():
            raise ValueError("agent run raw_response must preserve the provider response")
        if not isinstance(self.parsed_output, dict):
            raise ValueError("agent run parsed_output must be a mapping")
        if not isinstance(self.usage, dict):
            raise ValueError("agent run usage must be a mapping")
        if not isinstance(self.tool_trace, tuple) or any(
                not isinstance(item, dict) for item in self.tool_trace):
            raise ValueError("agent run tool_trace must be a tuple of mappings")
        if not isinstance(self.input_hashes, dict):
            raise ValueError("agent run input_hashes must be a mapping")
        for label, digest in self.input_hashes.items():
            if not str(label).strip() or not isinstance(digest, str) \
                    or not _SHA256.fullmatch(digest):
                raise ValueError(f"invalid input hash for {label!r}")
        if self.role in {"builder", "fixer", "development_judge", "blind_judge"} \
                and not self.input_hashes:
            raise ValueError(f"{self.role} receipts must hash the exact inputs seen")

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "context_id": self.context_id,
            "role": self.role,
            "model": self.model.to_dict(),
            "prompt_hash": self.prompt_hash,
            "input_hashes": dict(self.input_hashes),
            "raw_response": self.raw_response,
            "parsed_output": self.parsed_output,
            "usage": self.usage,
            "tool_trace": list(self.tool_trace),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "AgentRun":
        require_keys(value, {"run_id", "agent_id", "context_id", "role", "model",
                             "prompt_hash", "input_hashes", "raw_response",
                             "parsed_output"}, "agent run")
        return cls(run_id=value["run_id"], agent_id=value["agent_id"],
                   context_id=value["context_id"], role=value["role"],
                   model=ModelConfig.from_dict(value["model"]),
                   prompt_hash=value["prompt_hash"],
                   input_hashes=dict(value["input_hashes"]),
                   raw_response=value["raw_response"],
                   parsed_output=dict(value["parsed_output"]),
                   usage=dict(value.get("usage", {})),
                   tool_trace=tuple(value.get("tool_trace", ())))


def transition_allowed(current: Phase, target: Phase) -> bool:
    return target in TRANSITIONS[current]
