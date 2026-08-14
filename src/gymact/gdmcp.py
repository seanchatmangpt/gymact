"""Generated Deterministic MCP (gdmcp) compiler for bounded GymAct worlds.

The compiler contains no benchmark-specific solution table.  Known solution
semantics are manufactured from ``ggen/sregym-e2e-pack/ontology.ttl`` into
``gymact.generated.sregym_mcp_catalog``.  This module only validates, binds,
and compiles that admitted projection into ordinary ``ActuationIntent`` values.
Those intents still cross capability scope, authority admission, and BRCE.

Provenance note: this file is a real, unmodified, read-only reference port
pulled directly from `origin/agent/gdmcp-sregym-deterministic-solutions`
(commit `82312ec`, draft PR #45) onto `main` for the `gdmcp_bpmn_bridge`
integration -- it is not a branch merge; the branch itself remains exactly
as unmerged/draft as it was. `src/gymact/generated/sregym_mcp_catalog.py`
was pulled alongside it (this module's one real, self-contained dependency,
75 lines, zero `autofde_lab` imports) for the same reason.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any, Literal

from gymact.generated.sregym_mcp_catalog import (
    PROGRAM_SOURCE_ROWS,
    PROGRAM_STEP_ROWS,
    SREGYM_CAPABILITY_ROWS,
    SREGYM_LITE_PROBLEMS,
    SREGYM_UPSTREAM_REVISION,
)
from gymact.models import ActuationIntent, FrozenModel

SREGYM_RUN_KUBECTL = "urn:gymact:sregym:capability:run_kubectl"
SREGYM_SUBMIT_DIAGNOSIS = "urn:gymact:sregym:capability:submit_diagnosis"
SREGYM_SUBMIT_MITIGATION = "urn:gymact:sregym:capability:submit_mitigation"

_GDMCP_SREGYM_CAPABILITIES = frozenset(
    row["iri"] for row in SREGYM_CAPABILITY_ROWS if row["consequence"] == "DO"
)
_PLACEHOLDER_RE = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")
_K8S_NAMESPACE_RE = re.compile(r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$")


class GdmcpRefusal(RuntimeError):
    """Typed fail-closed outcome from deterministic program admission."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"REFUSED:{code}:{detail}")


class GdmcpStep(FrozenModel):
    capability: str
    payload_template: dict[str, Any]
    purpose: str
    source_ref: str


class GdmcpProgram(FrozenModel):
    profile: Literal["sregym"] = "sregym"
    problem_id: str
    upstream_revision: str = SREGYM_UPSTREAM_REVISION
    steps: tuple[GdmcpStep, ...]
    llm_calls: Literal[0] = 0
    source_refs: tuple[str, ...]

    def digest(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()


class CompiledGdmcpProgram(FrozenModel):
    program_digest: str
    problem_id: str
    upstream_revision: str
    llm_calls: Literal[0] = 0
    intents: tuple[ActuationIntent, ...]


class GdmcpCoverage(FrozenModel):
    corpus: str
    admitted_subjects: int
    compiled_subjects: int
    deterministic_projection_ratio: float


def _programs_from_projection() -> dict[str, GdmcpProgram]:
    sources: dict[str, list[str]] = defaultdict(list)
    for problem_id, source_ref in PROGRAM_SOURCE_ROWS:
        sources[problem_id].append(source_ref)

    steps: dict[str, list[tuple[int, GdmcpStep]]] = defaultdict(list)
    for problem_id, order, capability, payload, purpose, source_ref in PROGRAM_STEP_ROWS:
        if capability not in _GDMCP_SREGYM_CAPABILITIES:
            raise RuntimeError(f"GDMCP_GENERATED_NON_DO_CAPABILITY:{capability}")
        steps[problem_id].append(
            (
                int(order),
                GdmcpStep(
                    capability=capability,
                    payload_template=dict(payload),
                    purpose=purpose,
                    source_ref=source_ref,
                ),
            )
        )

    if set(sources) != set(steps):
        raise RuntimeError(
            f"GDMCP_GENERATED_PROGRAM_SET_DIVERGENCE:sources={sorted(sources)},steps={sorted(steps)}"
        )

    result: dict[str, GdmcpProgram] = {}
    for problem_id in sorted(steps):
        ordered = sorted(steps[problem_id], key=lambda item: item[0])
        ordinals = [item[0] for item in ordered]
        if ordinals != list(range(1, len(ordered) + 1)):
            raise RuntimeError(f"GDMCP_GENERATED_STEP_ORDER_INVALID:{problem_id}:{ordinals}")
        result[problem_id] = GdmcpProgram(
            problem_id=problem_id,
            source_refs=tuple(sources[problem_id]),
            steps=tuple(step for _, step in ordered),
        )
    return result


_SREGYM_PROGRAMS = _programs_from_projection()


def known_sregym_programs() -> tuple[GdmcpProgram, ...]:
    return tuple(_SREGYM_PROGRAMS[key] for key in sorted(_SREGYM_PROGRAMS))


def sregym_lite_coverage() -> GdmcpCoverage:
    compiled = len(set(SREGYM_LITE_PROBLEMS) & set(_SREGYM_PROGRAMS))
    total = len(SREGYM_LITE_PROBLEMS)
    return GdmcpCoverage(
        corpus=f"SREGym-Lite@{SREGYM_UPSTREAM_REVISION}",
        admitted_subjects=total,
        compiled_subjects=compiled,
        deterministic_projection_ratio=compiled / total,
    )


def _collect_placeholders(value: Any) -> set[str]:
    if isinstance(value, str):
        return set(_PLACEHOLDER_RE.findall(value))
    if isinstance(value, dict):
        found: set[str] = set()
        for item in value.values():
            found.update(_collect_placeholders(item))
        return found
    if isinstance(value, (list, tuple)):
        found: set[str] = set()
        for item in value:
            found.update(_collect_placeholders(item))
        return found
    return set()


def _validate_binding(name: str, value: str) -> None:
    if name != "namespace":
        raise GdmcpRefusal("GDMCP_UNKNOWN_BINDING", name)
    if len(value) > 63 or not _K8S_NAMESPACE_RE.fullmatch(value):
        raise GdmcpRefusal("GDMCP_INVALID_NAMESPACE", value)


def _render(value: Any, bindings: dict[str, str]) -> Any:
    if isinstance(value, str):
        rendered = value
        for name, replacement in bindings.items():
            rendered = rendered.replace("{{" + name + "}}", replacement)
        return rendered
    if isinstance(value, dict):
        return {key: _render(item, bindings) for key, item in value.items()}
    if isinstance(value, list):
        return [_render(item, bindings) for item in value]
    if isinstance(value, tuple):
        return tuple(_render(item, bindings) for item in value)
    return value


def _idempotency_key(
    *,
    program_digest: str,
    episode_id: str,
    step_index: int,
    capability: str,
    payload: dict[str, Any],
    authority_ref: str | None,
    principal: str | None,
) -> str:
    canonical = json.dumps(
        {
            "program_digest": program_digest,
            "episode_id": episode_id,
            "step_index": step_index,
            "capability": capability,
            "payload": payload,
            "authority_ref": authority_ref,
            "principal": principal,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def compile_sregym_solution(
    problem_id: str,
    *,
    episode_id: str,
    upstream_revision: str,
    bindings: dict[str, str],
    authority_ref: str | None = None,
    principal: str | None = "urn:gymact:agent:gdmcp",
) -> CompiledGdmcpProgram:
    """Compile one ontology-admitted SREGym solution into exact GymAct intents.

    There is no LLM path. Unknown subjects belong at the novelty boundary and
    fail closed rather than becoming an unreceipted improvisation.
    """
    if upstream_revision != SREGYM_UPSTREAM_REVISION:
        raise GdmcpRefusal(
            "GDMCP_SUBJECT_DRIFT",
            f"expected={SREGYM_UPSTREAM_REVISION},observed={upstream_revision}",
        )

    program = _SREGYM_PROGRAMS.get(problem_id)
    if program is None:
        raise GdmcpRefusal("GDMCP_SOLUTION_UNKNOWN", problem_id)

    required_bindings: set[str] = set()
    for step in program.steps:
        required_bindings.update(_collect_placeholders(step.payload_template))
    if set(bindings) != required_bindings:
        raise GdmcpRefusal(
            "GDMCP_BINDING_SET_MISMATCH",
            f"required={sorted(required_bindings)},observed={sorted(bindings)}",
        )
    for name, value in bindings.items():
        if not isinstance(value, str):
            raise GdmcpRefusal("GDMCP_BINDING_NOT_STRING", name)
        _validate_binding(name, value)

    program_digest = program.digest()
    intents: list[ActuationIntent] = []
    for index, step in enumerate(program.steps):
        if step.capability not in _GDMCP_SREGYM_CAPABILITIES:
            raise GdmcpRefusal("GDMCP_CAPABILITY_NOT_ADMITTED", step.capability)
        payload = _render(step.payload_template, bindings)
        intents.append(
            ActuationIntent(
                episode_id=episode_id,
                capability=step.capability,
                payload=payload,
                authority_ref=authority_ref,
                principal=principal,
                idempotency_key=_idempotency_key(
                    program_digest=program_digest,
                    episode_id=episode_id,
                    step_index=index,
                    capability=step.capability,
                    payload=payload,
                    authority_ref=authority_ref,
                    principal=principal,
                ),
            )
        )

    return CompiledGdmcpProgram(
        program_digest=program_digest,
        problem_id=program.problem_id,
        upstream_revision=program.upstream_revision,
        intents=tuple(intents),
    )
