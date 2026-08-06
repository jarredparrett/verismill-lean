"""Content-addressed storage used by experiment bundles."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


_OBJECT_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
_REF_KEYS = frozenset({
    "artifact", "manifest", "builder_run", "rubric", "requirements",
    "evaluation", "source", "provenance", "contract", "atlas",
    "research", "reference", "round", "report", "current_candidate",
    "parent_state", "state", "attestation", "member_attestation",
    "panel_execution",
    "parent_attestation",
    "human_review", "human_approval",
})
_REF_LIST_KEYS = frozenset({
    "agent_runs", "inherited_agent_runs", "references", "candidates", "development_rounds",
    "evaluations", "reports", "judge_runs", "prior_revisions",
    "panel_executions",
    "human_reviews",
})
_REF_MAP_KEYS = frozenset({"refs", "output_refs", "carried_forward"})
_DIGEST_KEYS = frozenset({
    "sha256", "prompt_hash", "input_hashes", "event_id", "event_hash",
    "prev_hash",
})


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def is_object_ref(value: str) -> bool:
    return bool(_OBJECT_REF.fullmatch(value))


def refs_in(value: Any, *, key: str | None = None) -> Iterable[str]:
    """Yield typed object-store references, not arbitrary SHA-256 digests.

    Agent prompt/input hashes and manifest checksums describe bytes but are not
    necessarily stored objects. Treating every ``sha256:...`` string as a graph
    edge made valid receipts unverifiable and let quoted digests perturb the
    object graph.
    """
    if isinstance(value, str):
        if (key in _REF_KEYS or key == "__ref__") and is_object_ref(value):
            yield value
    elif isinstance(value, dict):
        for child_key, item in value.items():
            if child_key in _DIGEST_KEYS:
                continue
            if child_key in _REF_MAP_KEYS and isinstance(item, dict):
                for mapped in item.values():
                    yield from refs_in(mapped, key="__ref__")
            else:
                yield from refs_in(item, key=child_key)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from refs_in(item, key="__ref__" if key in _REF_LIST_KEYS else key)


class ObjectStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, ref: str) -> Path:
        if not is_object_ref(ref):
            raise ValueError(f"invalid object reference: {ref!r}")
        return self.root / ref.removeprefix("sha256:")

    def put_bytes(self, value: bytes) -> str:
        ref = digest_bytes(value)
        path = self.path_for(ref)
        if not path.exists():
            path.write_bytes(value)
        elif path.read_bytes() != value:  # pragma: no cover - digest collision
            raise RuntimeError(f"content-address collision for {ref}")
        return ref

    def put_json(self, value: Any) -> str:
        return self.put_bytes(canonical_json(value))

    def read_bytes(self, ref: str) -> bytes:
        return self.path_for(ref).read_bytes()

    def read_json(self, ref: str) -> Any:
        return json.loads(self.read_bytes(ref))

    def verify(self, ref: str) -> bool:
        try:
            value = self.read_bytes(ref)
        except (OSError, ValueError):
            return False
        return digest_bytes(value) == ref

    def copy_graph(self, ref: str, destination: "ObjectStore",
                   copied: set[str] | None = None) -> set[str]:
        copied = copied if copied is not None else set()
        if ref in copied:
            return copied
        value = self.read_bytes(ref)
        destination.put_bytes(value)
        copied.add(ref)
        try:
            decoded = json.loads(value)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return copied
        for child in refs_in(decoded):
            if self.verify(child):
                self.copy_graph(child, destination, copied)
        return copied
