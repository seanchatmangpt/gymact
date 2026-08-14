"""Provider-agnostic deterministic MCP program compilation -- the
generalization of `gdmcp.py`'s SREGym-specific pattern (real, committed on
the unmerged branch `agent/gdmcp-sregym-deterministic-solutions`, draft PR
#45) into something that composes only already-`MERGED` GymAct primitives.

Per this repo's own git-workflow discipline, unmerged/draft work is a design
precedent, not a dependency: this module reimplements `gdmcp`'s real shape
(a frozen catalog of parameterized steps, `{{placeholder}}` payload
templates, fail-closed on an unknown key, zero LLM calls to compile or
replay) generically, keyed by `(provider_name, problem_id)` instead of
hardcoded to `"sregym"`, and using `gymact.mcp_process_control
.ProcessControlGraph` (this session's own `ADAPT`-admitted work) as the
step-ordering/licensing structure instead of `gdmcp`'s flat linear list.

Scope, stated explicitly: this module ships one real, worked example (see
`tests/test_deterministic_program_chicago.py`) against
`gymact.providers.MemoryProvider`, not a full per-gym catalog for every
registered provider. A gym that needs a genuinely multi-step, persistent
session -- the shape `gymact.gyms.sregym.SregymVendorProvider` (merged, PR
#25) already demonstrates, a live MCP `Client` session held open across
several real actuations rather than one-shot subprocess calls per step --
would compose the same `DeterministicProgramSpec`/`run_deterministic_program`
machinery below against that provider; building that catalog out for SREGym's
21 subjects remains `gdmcp`'s own, separate, unmerged scope, not duplicated
here.
"""

from __future__ import annotations

import re
from typing import Any

from gymact.kernel import GymAct
from gymact.mcp_process_control import DispatchRefusal, ProcessControlGraph, dispatch
from gymact.models import ActuationResult, FrozenModel

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


class DeterministicProgramSpec(FrozenModel):
    """One admitted, hand/ontology-authored program targeting one provider.
    `step_order` is the deterministic replay sequence (defense-in-depth: each
    step is also independently checked against `graph.licensed_next` at
    dispatch time, so a `step_order`/`graph` drift is caught, not silently
    trusted). `payload_templates` maps `capability_ref -> {{placeholder}}`-
    templated payload dict, same rendering convention `gdmcp.py` already
    proved out."""

    provider_name: str
    problem_id: str
    graph: ProcessControlGraph
    step_order: tuple[str, ...]
    payload_templates: dict[str, dict[str, Any]]
    required_bindings: frozenset[str]


class ProgramNotFound(RuntimeError):
    """Fail-closed refusal for an unknown (provider_name, problem_id) or a
    missing required binding -- mirrors gdmcp's GDMCP_SOLUTION_UNKNOWN /
    binding-validation refusals; never falls back to an LLM."""


def _render(template: dict[str, Any], bindings: dict[str, str]) -> dict[str, Any]:
    def render_value(value: Any) -> Any:
        if isinstance(value, str):
            def substitute(match: re.Match[str]) -> str:
                key = match.group(1)
                if key not in bindings:
                    raise ProgramNotFound(f"PROGRAM_REFUSED:MISSING_BINDING:{key}")
                return bindings[key]

            return _PLACEHOLDER_RE.sub(substitute, value)
        if isinstance(value, dict):
            return {k: render_value(v) for k, v in value.items()}
        return value

    return {k: render_value(v) for k, v in template.items()}


async def run_deterministic_program(
    kernel: GymAct,
    spec: DeterministicProgramSpec,
    episode_id: str,
    *,
    bindings: dict[str, str],
    authority_ref: str | None = None,
) -> tuple[ActuationResult, ...]:
    """Real, llm_calls=0 replay of `spec.step_order` through
    `mcp_process_control.dispatch` -- composing real graph licensing, real
    kernel.act() (CapabilityScope/AuthorityResolver unchanged), and real
    post-hoc ConformanceChecker replay, the same three already-`ALIVE`
    collaborators `dispatch` itself composes. Refuses (raises
    `ProgramNotFound`) before making any real kernel call if a required
    binding is missing."""
    missing = spec.required_bindings - bindings.keys()
    if missing:
        raise ProgramNotFound(f"PROGRAM_REFUSED:MISSING_BINDINGS:{sorted(missing)!r}")

    results: list[ActuationResult] = []
    for capability_iri in spec.step_order:
        template = spec.payload_templates[capability_iri]
        payload = _render(template, bindings)
        try:
            result = await dispatch(
                kernel,
                spec.graph,
                episode_id,
                capability_iri=capability_iri,
                payload=payload,
                authority_ref=authority_ref,
            )
        except DispatchRefusal as exc:
            raise ProgramNotFound(f"PROGRAM_REFUSED:{exc}") from exc
        results.append(result)
    return tuple(results)


def compile_program(
    catalog: dict[tuple[str, str], DeterministicProgramSpec],
    *,
    provider_name: str,
    problem_id: str,
) -> DeterministicProgramSpec:
    """Real catalog lookup -- fail-closed. Mirrors
    `gdmcp.compile_sregym_solution`'s `GDMCP_SOLUTION_UNKNOWN` refusal for
    any `(provider_name, problem_id)` not present in the admitted catalog,
    generalized past a single hardcoded `_SREGYM_PROGRAMS` dict."""
    spec = catalog.get((provider_name, problem_id))
    if spec is None:
        raise ProgramNotFound(
            f"PROGRAM_REFUSED:UNKNOWN_PROGRAM:provider={provider_name!r} "
            f"problem_id={problem_id!r}"
        )
    return spec
