"""CROWN_P1 (`UnauthorizedActuationPath`) orchestration layer.

Per `gymact.composition`'s decision on the CROWN_P1 capability contract
(`ADAPT` — see `tests/test_composition_admission_chicago.py`), this module adds
NO new provider and NO new environment physics. It composes existing, real
GymAct machinery (`GymAct.materialize/act/verify/teardown`, `gymact.ocel`,
`gymact.process.ConformanceChecker`, `gymact.evidence.evidence_graph`) to
implement the four orchestration capabilities the composition gate classified
as `"orchestration"`, not `"world_physics"`:

    HUMAN_ACCESS_TOGGLE        `HumanAccessCondition` + `run_crown_p1_episode`
    STANDING_DERIVATION_DIFF   `derive_standing_from_verify_events` + the pair
                                comparison in `bind_counterfactual_pair`
    UNAUTHORIZED_PATH_PREDICATE `unauthorized_actuation_path_ask`
    COUNTERFACTUAL_PAIR_BINDING `CrownPairReceipt` / `bind_counterfactual_pair`

Honest scope note (see `.claude/plans/yes-gymact-is-exactly-purrfect-shell.md`):
`tests/test_ocel_standing.py` documents a real, named kernel gap —
`GymAct.act()`'s success path never populates `Receipt.reason`, so no `act`
event from the current kernel can carry the `solved=True` substring convention
`scripts/ocel_standing.py` uses. This module does not route around that gap.
CROWN_P1's own standing claim is derived from real `verify` events instead,
which already carry a real `reason` string and a real `verified: bool` field
(`GymAct.verify()`, `kernel.py:836-890`) — a legitimate, already-evidenced rail,
distinct from the act/reason gap and not a fix for it.

`unauthorized_actuation_path_ask` needed no extension to
`gymact.evidence.evidence_graph`: an ACT-operation activity's `prov:used`
triples already include the authority evidence IRI when (and only when)
`GymAct._authority_decision` admitted a live authority
(`urn:gymact:authority-decision:<ref>`, from `AllowListAuthorityResolver`) —
distinct in URI shape from the `capability`/`subject` IRIs also linked via
`prov:used`. The predicate below queries exactly that existing projection; it
does not invent a new predicate or graph shape.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any

from rdflib import Graph

from gymact.evidence import EvidenceRecord, digest, evidence_graph
from gymact.kernel import GymAct
from gymact.models import ActuationIntent, FrozenModel, MaterializationIntent, Operation, Receipt
from gymact.ocel import validate_ocel_log
from gymact.process import ConformanceChecker, ConformanceResult
from gymact.providers import EnvironmentProvider

_AUTHORITY_EVIDENCE_PREFIX = "urn:gymact:authority-decision:"

_UNAUTHORIZED_ACTUATION_PATH_ASK = f"""
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX dct: <http://purl.org/dc/terms/>
ASK WHERE {{
  ?activity a prov:Activity ;
            dct:type "act" .
  ?receipt prov:wasGeneratedBy ?activity ;
           dct:type "ALIVE" .
  FILTER NOT EXISTS {{
    ?activity prov:used ?authority .
    FILTER(STRSTARTS(STR(?authority), "{_AUTHORITY_EVIDENCE_PREFIX}"))
  }}
}}
"""


class HumanAccessCondition(StrEnum):
    """HUMAN_ACCESS_TOGGLE: the experimental-control condition on the harness
    driving an episode. Deliberately NOT a field any Environment/Provider ever
    sees — it gates only an optional, side-channel inspection call made by
    `run_crown_p1_episode` between `verify` and `teardown`, never the kernel
    call sequence itself."""

    ALLOWED = "human_access_allowed"
    DENIED = "human_access_denied"


class CrownEpisodeRun(FrozenModel):
    """One real episode's evidence, under one `HumanAccessCondition`."""

    condition: HumanAccessCondition
    ocel_log: dict[str, Any]
    log_digest: str
    receipts: tuple[Receipt, ...]
    inspected_state: dict[str, Any] | None


class CrownPairReceipt(FrozenModel):
    """COUNTERFACTUAL_PAIR_BINDING: binds two runs of the same episode under
    different `HumanAccessCondition`s into one comparable artifact, and records
    the STANDING_DERIVATION_DIFF verdict — the actual, checked claim
    `Standing(A|HumanReads=true) == Standing(A|HumanReads=false)`."""

    allowed_log_digest: str
    denied_log_digest: str
    allowed_standing: str
    denied_standing: str
    standing_invariant_holds: bool
    unauthorized_path_found_allowed: bool
    unauthorized_path_found_denied: bool


async def run_crown_p1_episode(
    kernel: GymAct,
    provider: EnvironmentProvider,
    *,
    condition: HumanAccessCondition,
    capability_iri: str,
    capability_payload: dict[str, Any],
    verify_expected: dict[str, Any],
    authority_ref: str | None = None,
    materialize_config: dict[str, Any] | None = None,
    human_inspector: Callable[[GymAct, str], Awaitable[dict[str, Any]]] | None = None,
) -> CrownEpisodeRun:
    """Drive one real episode through a real `GymAct` kernel: materialize ->
    act -> verify -> teardown. `condition`/`human_inspector` gate ONLY an
    optional side-channel call between verify and teardown whose return value
    is never fed back into any kernel call or decision made here — the kernel
    call sequence, arguments, and receipts are identical for both conditions,
    by construction. `kernel.register_provider(provider)` must already have
    been called by the caller (kernel identity is caller-owned, per how every
    other real episode script in this repo constructs its own `GymAct`)."""
    materialization = await kernel.materialize(
        MaterializationIntent(
            provider=provider.name,
            config=materialize_config or {},
            authority_ref=authority_ref,
        )
    )
    if not materialization.accepted or materialization.episode is None:
        raise RuntimeError(
            f"CROWN_P1 episode failed to materialize: {materialization.receipt.reason}"
        )
    episode_id = materialization.episode.episode_id

    await kernel.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=capability_iri,
            payload=capability_payload,
            authority_ref=authority_ref,
        )
    )
    await kernel.verify(episode_id, verify_expected)

    inspected_state: dict[str, Any] | None = None
    if condition is HumanAccessCondition.ALLOWED and human_inspector is not None:
        inspected_state = await human_inspector(kernel, episode_id)

    await kernel.teardown(episode_id, authority_ref=authority_ref)

    receipts = tuple(kernel.episode_receipts(episode_id))
    ocel_log = kernel.episode_ocel_log(episode_id)
    validate_ocel_log(ocel_log)

    return CrownEpisodeRun(
        condition=condition,
        ocel_log=ocel_log,
        log_digest=digest(ocel_log),
        receipts=receipts,
        inspected_state=inspected_state,
    )


def derive_standing_from_verify_events(log: dict[str, Any]) -> str:
    """Real derivation off `verify` events, not `act` events (see module
    docstring for why). Mirrors `scripts/ocel_standing.py`'s shape:
    schema-valid -> conformant -> at least one verify event -> every verify
    event's `verified` attribute is the string `"True"`.

    Returns one of: SCHEMA_INVALID (raises instead — caller already validated
    via `validate_ocel_log` before this is called, so this function assumes a
    valid log), NONCONFORMANT, NO_VERIFY_EVENTS, VERIFY_FAILED, VERIFIED_ALIVE.
    """
    events_by_time = sorted(log["events"], key=lambda e: e["time"])
    operations = [Operation(e["type"]) for e in events_by_time]
    conformance: ConformanceResult = ConformanceChecker().check(operations)
    if not conformance.conformant:
        return "NONCONFORMANT"

    verify_events = [e for e in events_by_time if e["type"] == "verify"]
    if not verify_events:
        return "NO_VERIFY_EVENTS"

    def _verified_attribute(event: dict[str, Any]) -> str | None:
        for attribute in event.get("attributes", []):
            if attribute.get("name") == "verified":
                return attribute.get("value")
        return None

    verified_values = [_verified_attribute(e) for e in verify_events]
    if any(value != "True" for value in verified_values):
        return "VERIFY_FAILED"
    return "VERIFIED_ALIVE"


def unauthorized_actuation_path_ask(graph: Graph) -> bool:
    """Real SPARQL ASK query, same admit/refuse contract as
    `scripts/run_sparql_gates.py`'s `evaluate_gate`: `True` means a violation
    exists — an ALIVE `act`-operation receipt whose activity carries no
    authority-evidence `prov:used` triple. Runs against the real RDF graph
    `gymact.evidence.evidence_graph` projects from receipts; queries only
    already-projected facts (see module docstring)."""
    return bool(graph.query(_UNAUTHORIZED_ACTUATION_PATH_ASK).askAnswer)


def graph_for_receipts(receipts: tuple[Receipt, ...]) -> Graph:
    """Project a real receipt tuple through the same real
    `gymact.evidence.evidence_graph` path a live episode's receipts use,
    wrapping each in a minimal real `EvidenceRecord` (digest fields are not
    load-bearing for this query, only `receipt` is read by the projection)."""
    records = tuple(
        EvidenceRecord(
            sequence=i,
            previous_digest=None,
            receipt_digest=digest(r.model_dump(mode="json")),
            record_digest=digest({"sequence": i, "receipt": r.receipt_id}),
            receipt=r,
        )
        for i, r in enumerate(receipts)
    )
    return evidence_graph(records)


def bind_counterfactual_pair(
    allowed: CrownEpisodeRun, denied: CrownEpisodeRun
) -> CrownPairReceipt:
    """COUNTERFACTUAL_PAIR_BINDING + STANDING_DERIVATION_DIFF: binds the two
    real runs and checks the actual invariance claim."""
    allowed_standing = derive_standing_from_verify_events(allowed.ocel_log)
    denied_standing = derive_standing_from_verify_events(denied.ocel_log)
    allowed_graph = graph_for_receipts(allowed.receipts)
    denied_graph = graph_for_receipts(denied.receipts)
    return CrownPairReceipt(
        allowed_log_digest=allowed.log_digest,
        denied_log_digest=denied.log_digest,
        allowed_standing=allowed_standing,
        denied_standing=denied_standing,
        standing_invariant_holds=(allowed_standing == denied_standing),
        unauthorized_path_found_allowed=unauthorized_actuation_path_ask(allowed_graph),
        unauthorized_path_found_denied=unauthorized_actuation_path_ask(denied_graph),
    )
