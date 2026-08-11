"""A real, sregym-SPECIFIC DSPy ReAct agent -- deliberately not the generic,
gym-agnostic `gymact.dspy_agent.GymActReActAgent`.

Why this exists as its own module: `GymActReActAgent`'s exact-match
grounding guard cannot express "this payload is a legitimately composed
value the model must synthesize" (a full kubectl command line; a free-form
diagnosis/mitigation description) -- only a binary per-binding exemption
(`create_capable_bindings`), which disables grounding entirely rather than
checking it. The real per-field fix (a generated grounding-policy pack
distinguishing bare-reference/composed/free-form fields) is deliberately
out of scope here -- skipped for now per direct instruction, tracked
separately.

Instead: real, hand-written `dspy.Signature`/typed-tool-function schemas,
one per real sregym capability, so DSPy gets a real, precise input contract
(not a bare `dict[str, Any]` payload) without needing any generated pack.
Every real capability call still routes through the real kernel `gym.act()`
-- no new authority path, matching every other DSPy integration in this
repo.

Also fixes, in the goal prompt itself, the real behavioral gap the generic
agent's first live run against sregym surfaced: the kernel-level `observe()`
only returns the conductor's `/status` stage marker (`{"stage": "setup"}`)
-- it never runs kubectl itself, so there is no cluster data to ground
anything on. The agent must actively call `run_kubectl` to get real
evidence; it will not appear passively. `DiagnoseSregymIncident`'s docstring
says this explicitly instead of leaving the model to (as happened, live,
before this fix) call `observe` repeatedly and give up.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from gymact.dspy_agent import HypothesisLedger, HypothesisState
from gymact.dspy_ocel import DspyOcelCallback
from gymact.epistemic_kernel import Fact, admit_diagnosis, validate_hypothesis
from gymact.models import ActuationIntent, Capability
from gymact.standing import require_standing

try:
    import dspy as _dspy
except ImportError:  # pragma: no cover - exercised via require_standing in tests
    _dspy = None


# --- Real, typed payload schemas -- one per real sregym DO capability -----
#
# Cross-checked directly against `SregymEnvironment.actuate()`'s own real
# parsing (`gymact/gyms/sregym.py`): `run_kubectl` reads `payload["command"]`
# as a required non-empty str; `submit_diagnosis`/`submit_mitigation` accept
# any JSON-serializable dict (rendered as-is via `_render_submit_answer`),
# but a diagnosis/mitigation is only ever real if it names a root cause and
# the real evidence for it -- so the schema requires both rather than
# leaving the shape to prose, the same discipline
# `.claude/rules/actuation-authority.md` already requires at the kernel
# boundary, applied here at the schema boundary instead.


class RunKubectlPayload(BaseModel):
    """A real, single kubectl command line to run against the real cluster."""

    command: str = Field(description="a full, real, directly-executable kubectl command line")


class SubmitDiagnosisPayload(BaseModel):
    """A real diagnosis of the incident's root cause."""

    root_cause: str = Field(description="the real, specific root cause identified")
    evidence: str = Field(
        description="the real kubectl output (or a precise summary of it) that supports "
        "root_cause -- never fabricated"
    )


class SubmitMitigationPayload(BaseModel):
    """A real, concrete kubectl-level fix for the diagnosed root cause."""

    mitigation: str = Field(
        description="the real, concrete kubectl-level remediation that would fix root_cause"
    )


# --- Real, deterministic structural-diff helper ----------------------------
#
# The core fix this session's live runs surfaced: a ReAct loop with only
# free-text `kubectl describe` tools ends up scanning many long, separate
# text blobs by eye, one at a time, to notice which single deployment
# differs from its peers -- exactly the kind of tedious, error-prone,
# mechanical comparison that should be done in code and handed to the model
# as one small structured result, not left to the LM's own attention over
# raw text. The parsing functions below are pure (no I/O) specifically so
# they can be unit-tested fast, offline, against real captured kubectl JSON
# fixtures -- no live cluster needed to iterate on the parsing logic
# itself. Real Pydantic models (not bare dicts) for the same reason
# `RunKubectlPayload` etc. above are Pydantic: a typed structural result
# lets DSPy/Pydantic validate and coerce the tool output, and gives a
# reader (human or LM) a precise, self-documenting shape instead of an
# untyped dict whose keys are only knowable by reading this file.


class K8sEnvVar(BaseModel):
    """Mirrors the real Kubernetes `core/v1.EnvVar` shape (only the two
    fields this module reads -- `valueFrom` env vars validate too, `value`
    just stays `None` for them, which is real and correct: their value
    isn't a literal in the pod spec)."""

    name: str
    value: str | None = None


class K8sResourceRequirements(BaseModel):
    """Mirrors the real Kubernetes `core/v1.ResourceRequirements` shape."""

    requests: dict[str, str] = Field(default_factory=dict)
    limits: dict[str, str] = Field(default_factory=dict)


class K8sContainer(BaseModel):
    """Mirrors the real Kubernetes `core/v1.Container` shape (fields this
    module reads only -- `model_config` below ignores every other real
    field like `ports`/`volumeMounts` rather than rejecting them)."""

    model_config = {"extra": "ignore"}

    image: str | None = None
    command: list[str] | None = None
    env: list[K8sEnvVar] = Field(default_factory=list)
    resources: K8sResourceRequirements = Field(default_factory=K8sResourceRequirements)


class K8sPodSpec(BaseModel):
    """Mirrors the real Kubernetes `core/v1.PodSpec` shape (containers only)."""

    model_config = {"extra": "ignore"}

    containers: list[K8sContainer] = Field(default_factory=list)


class K8sPodTemplateSpec(BaseModel):
    """Mirrors the real Kubernetes `core/v1.PodTemplateSpec` shape."""

    model_config = {"extra": "ignore"}

    spec: K8sPodSpec = Field(default_factory=K8sPodSpec)


class K8sDeploymentSpec(BaseModel):
    """Mirrors the real Kubernetes `apps/v1.DeploymentSpec` shape (this
    module's fields only)."""

    model_config = {"extra": "ignore"}

    replicas: int | None = None
    template: K8sPodTemplateSpec = Field(default_factory=K8sPodTemplateSpec)


class K8sObjectMeta(BaseModel):
    """Mirrors the real Kubernetes `meta/v1.ObjectMeta` shape (name only)."""

    model_config = {"extra": "ignore"}

    name: str | None = None


class K8sDeployment(BaseModel):
    """Mirrors the real Kubernetes `apps/v1.Deployment` resource shape --
    exactly what a real `kubectl get deployment <name> -o json` returns.
    `extra='ignore'` at every nested level (not the default pydantic
    'forbid') deliberately: a real Deployment object carries dozens of
    other real fields (`status`, `managedFields`, full `metadata.
    annotations`, ...) this module has no use for; validating against the
    real shape should not require re-declaring every field Kubernetes
    ships, only the ones this module reads."""

    model_config = {"extra": "ignore"}

    metadata: K8sObjectMeta = Field(default_factory=K8sObjectMeta)
    spec: K8sDeploymentSpec = Field(default_factory=K8sDeploymentSpec)


class DeploymentConfigSummary(BaseModel):
    """Compact, structural summary derived from a real `K8sDeployment` --
    deliberately excludes anything transient/noisy (restart counts, pod
    status, event timestamps), which live on Pods/ReplicaSets, not on the
    Deployment spec, and are exactly the kind of self-resolving startup
    noise this fix targets moving away from."""

    name: str | None = Field(default=None, description="the Deployment's name")
    image: str | None = Field(default=None, description="the primary container's image")
    command: list[str] | None = Field(
        default=None, description="the primary container's command override, if any"
    )
    env: list[str] = Field(
        default_factory=list, description="sorted 'NAME=value' env var pairs"
    )
    resource_requests: dict[str, str] = Field(default_factory=dict)
    resource_limits: dict[str, str] = Field(default_factory=dict)
    replicas: int | None = Field(default=None, description="desired replica count")


class WarningEvent(BaseModel):
    """One real Kubernetes Warning event: Kubernetes's own controllers
    already classify and summarize failures here (FailedCreate, BackOff,
    Unhealthy, FailedMount, Forbidden, webhook errors, ...)."""

    reason: str = Field(description="the event's short machine reason, e.g. 'FailedCreate'")
    object: str = Field(description="the involved object, e.g. 'ReplicaSet/<name>-<hash>'")
    message: str = Field(description="the real, human-readable event message")


def _summarize_one_deployment(raw_item: dict[str, Any]) -> DeploymentConfigSummary:
    """Real parsing of ONE real `kubectl get deployment <name> -o json`
    response (a single Kubernetes `Deployment` object -- deliberately not a
    `List`, see the truncation note on `_summarize_deployment_configs`).
    Validates against the real `K8sDeployment` shape first (real field
    names, real nesting -- Pydantic raises on a genuinely malformed
    object instead of silently defaulting every missing field to `None`
    the way manual `dict.get()` chains would) and only then derives the
    compact `DeploymentConfigSummary`."""
    deployment = K8sDeployment.model_validate(raw_item)
    containers = deployment.spec.template.spec.containers
    container = containers[0] if containers else K8sContainer()
    env_pairs = sorted(f"{env.name}={env.value}" for env in container.env)
    return DeploymentConfigSummary(
        name=deployment.metadata.name,
        image=container.image,
        command=container.command,
        env=env_pairs,
        resource_requests=container.resources.requests,
        resource_limits=container.resources.limits,
        replicas=deployment.spec.replicas,
    )


def _summarize_deployment_configs(
    raw_kubectl_json: dict[str, Any],
) -> list[DeploymentConfigSummary]:
    """Real parsing of a real `kubectl get deployments -n <ns> -o json`
    response (a real Kubernetes `List` of `Deployment` objects) into a
    list of `DeploymentConfigSummary`, via `_summarize_one_deployment`.

    NOT used against a live cluster for a namespace with many real
    deployments: sregym's own vendored kubectl-mcp server blindly truncates
    ANY tool result over 10,000 characters
    (`mcp_server/kubectl_server_helper/utils.py`'s `parse_text`), which a
    real bulk `-o json` response for ~19 deployments (each carrying
    `managedFields`/full `status`/annotations) reliably exceeds -- confirmed
    live this session: a real bulk fetch came back mid-JSON-string,
    unparseable. `list_deployment_configs` below therefore fetches ONE
    deployment at a time (each real response is far under 10k) and calls
    `_summarize_one_deployment` once per item instead. This function stays
    exported and tested against a real captured multi-item List fixture
    because the parsing logic itself (List -> per-item summary) is
    identical either way, and is the part worth unit-testing offline."""
    return [
        _summarize_one_deployment(item) for item in raw_kubectl_json.get("items", [])
    ]


# Real, general SRE differential-diagnosis taxonomy (standard k8s
# troubleshooting categories -- not specific to this or any one incident).
# Forcing a real finding against EVERY category, not just the first
# plausible pattern-match, is the exhaustive-checklist discipline a
# 10,000-hour SRE applies before committing to a root cause: a single
# hypothesis that skipped checking the other categories is much more
# likely to be a premature pattern-match than a verified diagnosis.
FAULT_CATEGORIES: tuple[str, ...] = (
    "container image/tag (compare against this app's other deployments)",
    "container command override",
    "environment variables",
    "resource requests/limits",
    "replica count / scheduling",
    "service port and selector (check BOTH the caller's config and the "
    "callee's actual service, not just one side)",
    "RBAC / admission control (Forbidden or webhook events)",
    "readiness/liveness probe configuration",
)


class CategoryCheck(BaseModel):
    """One real, evidence-backed finding for exactly one fault category
    from `FAULT_CATEGORIES`. 'no divergence found' is a real, valid,
    expected finding for most categories on most incidents -- the point
    isn't that every category is guilty, it's that every category was
    actually looked at using real tool output before being dismissed."""

    category: str = Field(description="one entry, verbatim, from FAULT_CATEGORIES")
    finding: str = Field(
        description="the real finding for this category, grounded in a real tool "
        "result -- 'no divergence found' is valid if that's genuinely what you saw"
    )
    why: str = Field(
        description="explicit justification for `finding` (at least a few real sentences, "
        "not one line): the specific real evidence value you checked, and why that value "
        "does (or does not) constitute a real anomaly for THIS category specifically -- not "
        "a restatement of `finding`. A short answer here usually means the check wasn't "
        "actually done against real evidence, just asserted.",
    )


# --- Concurrent, cheap-model theory panels ---------------------------------
#
# Two distinct, real fan-out strategies, both using `groq/llama-3.1-8b-
# instant` (560 t/s, $0.05/$0.08 per 1M tokens per Groq's own real pricing
# table) run concurrently via `asyncio.gather` -- cheap and fast enough to
# run many independent, narrowly-scoped calls instead of relying on one
# expensive model to hold discipline across a wide category/deployment set
# serially in one long reasoning trace. Neither panel touches the kernel or
# submits anything -- both are pure, read-only reasoning over evidence
# already gathered by `list_deployment_configs`/`list_recent_warning_events`,
# feeding INTO the main `gpt-oss-120b` ReAct loop as extra real evidence,
# never replacing its own investigation or submission authority.

DEFAULT_THEORY_MODEL_ID = "groq/llama-3.1-8b-instant"


async def _gather_category_theories(
    evidence: dict[str, Any],
    *,
    categories: tuple[str, ...] = FAULT_CATEGORIES,
    theory_model_id: str = DEFAULT_THEORY_MODEL_ID,
    ocel_callback: Any = None,
) -> list[CategoryCheck]:
    """Concurrent panel #1: one real, independent, cheap LM call per
    `FAULT_CATEGORIES` entry, each scoped to reason about ONLY that one
    category against the SAME real evidence -- a specialist who can't be
    talked out of checking their one thing by a more textually-salient
    distractor elsewhere in the evidence, unlike one generalist model
    holding a checklist across all categories in a single serial pass."""
    if _dspy is None:  # pragma: no cover - guarded by require_standing at call sites
        raise ImportError("gymact.dspy_sregym_agent requires the optional 'dspy' extra")
    dspy = _dspy

    class CategoryTheory(dspy.Signature):
        """Given real Kubernetes evidence (deployment configs and/or
        warning events), determine whether THIS ONE category shows a real
        anomaly. Do not reason about any other category -- a separate
        specialist is checking those independently. 'no divergence found'
        is a valid, expected finding for most categories on most
        incidents -- only report a real anomaly you can point to directly
        in the evidence."""

        category: str = dspy.InputField(desc="the ONE fault category to check")
        evidence: dict[str, Any] = dspy.InputField(
            desc="real Kubernetes evidence: deployment configs and/or warning events"
        )
        finding: str = dspy.OutputField(
            desc="the real finding for this category, grounded directly in evidence"
        )
        # Verbose-justification field, required as the LAST output field on
        # every Signature in this module -- a real, live run showed a
        # short, conclusory answer reach a wrong verdict despite citing
        # real evidence; writing out WHY is the check against that. Length
        # requested in the desc text, deliberately NOT a hard pydantic
        # `min_length` -- a real, live run showed DSPy's JSON adapter
        # crash (not retry) on a `ValidationError` from a nested output
        # model's length constraint; see `HypothesisLedger.reasoning`'s
        # own NOTE in `gymact.dspy_agent` for the full explanation.
        why: str = dspy.OutputField(
            desc="explicit justification (at least a few real sentences, not one line) "
            "connecting the real evidence value you checked to `finding` -- not a "
            "restatement of `finding`. A short answer here usually means the check was "
            "asserted, not actually done against real evidence.",
        )

    lm = dspy.LM(theory_model_id, max_tokens=1000)
    callbacks = [ocel_callback] if ocel_callback is not None else []

    async def _one(category: str) -> CategoryCheck:
        with dspy.context(lm=lm, callbacks=callbacks):
            prediction = await dspy.Predict(CategoryTheory).acall(
                category=category, evidence=evidence
            )
        return CategoryCheck(category=category, finding=prediction.finding, why=prediction.why)

    results = await asyncio.gather(*(_one(category) for category in categories))
    return list(results)



# Real, mechanical derivation, not a hand-picked list: every field of
# `DeploymentConfigSummary` except `name` (the identity, not a comparable
# attribute) is a real candidate for transpose-and-vote outlier detection.
# A hand-typed tuple duplicating these names would silently drift out of
# sync the next time `DeploymentConfigSummary` gains a field, AND -- the
# real defect a review caught -- reads as hardcoding this benchmark's
# known fault space rather than deriving "what's comparable" from the
# actual typed model. Adding a field to `DeploymentConfigSummary` now
# automatically extends what this panel (and `_derive_deterministic_facts`
# below) checks, with no second list to remember to update.
FIELD_NAMES_TO_TRANSPOSE: tuple[str, ...] = tuple(
    name for name in DeploymentConfigSummary.model_fields if name != "name"
)


def _field_as_str(deployment: DeploymentConfigSummary, field_name: str) -> str:
    """Real, deterministic stringification of one field's value, for
    exact-match comparison across peers -- `json.dumps(..., sort_keys=True)`
    so two dicts/lists with the same real content always stringify
    identically regardless of key/element order."""
    value = getattr(deployment, field_name)
    return json.dumps(value, sort_keys=True, default=str)


class FieldOutlierResult(BaseModel):
    """The real, transposed-and-voted outcome for ONE field across every
    real peer deployment."""

    field_name: str
    majority_value: str = Field(description="the value shared by the most peers")
    outliers: list[str] = Field(
        default_factory=list, description="peer names whose value differs from majority_value"
    )
    reasoning: str = Field(description="one sentence naming the real outlier(s), or why none exist")
    why: str = Field(
        description="explicit justification (at least a few real sentences, not one line): "
        "the actual transposed_column values you wrote out, why majority_value is the "
        "majority, and -- for each named outlier -- why its value genuinely differs (not "
        "merely why it's expected to differ given its role).",
    )


async def _gather_field_outlier_flags(
    deployments: list[DeploymentConfigSummary],
    *,
    fields: tuple[str, ...] = FIELD_NAMES_TO_TRANSPOSE,
    theory_model_id: str = DEFAULT_THEORY_MODEL_ID,
    ocel_callback: Any = None,
) -> list[FieldOutlierResult]:
    """Concurrent panel #2: one real, independent, cheap LM call per FIELD
    (not per deployment) -- the human-cognition-correct axis. A person
    spotting the odd deployment out of 19 doesn't re-read each full record
    top to bottom; they mentally TRANSPOSE one field into a column across
    all peers and scan down it -- exact repetition makes the outlier
    perceptually obvious (Treisman's visual "pop-out" effect) once values
    are lined up for direct comparison, which a row-oriented record list
    never gives either a human or an LM. This panel forces that same
    transpose-then-vote procedure as explicit, ordered DSPy output fields
    (`transposed_column` before `majority_value` before `outliers`) so the
    model can't skip straight to a vague conclusion -- it has to actually
    write out the column first, the same way a human would write out a
    column on paper before noticing what stands out.

    Complementary to the category panel: the category panel asks "is
    there an image-tag problem anywhere?" (in prose); this panel does the
    mechanical column-comparison FOR every relevant field at once and
    hands back the real, already-voted conclusion, not raw data to
    re-derive it from."""
    if _dspy is None:  # pragma: no cover - guarded by require_standing at call sites
        raise ImportError("gymact.dspy_sregym_agent requires the optional 'dspy' extra")
    dspy = _dspy

    class SpotFieldOutlier(dspy.Signature):
        """Human-style outlier detection over ONE field across a set of
        peer deployments -- NOT by reading each full record, but by first
        writing out this one field's real value for every peer as a flat
        column (mentally transposing the list), then noticing which value
        is the majority and which peer(s) don't match it. If ALL peers
        share the same value, or if divergence on this specific field is
        naturally expected given each peer's own distinct role rather than
        a real misconfiguration, say so explicitly, with your own real
        reasoning for why -- do not force a false outlier."""

        field_name: str = dspy.InputField(desc="which single field is being compared")
        peer_values: dict[str, str] = dspy.InputField(
            desc="peer deployment name -> this field's real value, already extracted"
        )
        transposed_column: list[str] = dspy.OutputField(
            desc="the flat list of values you actually wrote out, in peer order -- do "
            "this FIRST, before judging anything"
        )
        majority_value: str = dspy.OutputField(desc="the value shared by the most peers")
        outliers: list[str] = dspy.OutputField(
            desc="peer names whose value genuinely differs from majority_value; empty "
            "list if none, or if the difference is expected given each peer's role"
        )
        reasoning: str = dspy.OutputField(
            desc="one sentence naming the real outlier(s), or explaining why none exist"
        )
        # Verbose-justification field, required as the LAST output field
        # (see `CategoryTheory.why`'s comment for why this exists and why
        # length is requested in prose, not a hard `min_length`).
        why: str = dspy.OutputField(
            desc="explicit justification (at least a few real sentences, not one line): "
            "restate the transposed_column values, explain why majority_value is the "
            "majority, and for each outlier explain why its value genuinely differs rather "
            "than being expected given its own role.",
        )

    lm = dspy.LM(theory_model_id, max_tokens=800)
    callbacks = [ocel_callback] if ocel_callback is not None else []

    async def _one(field_name: str) -> FieldOutlierResult:
        peer_values = {d.name or "?": _field_as_str(d, field_name) for d in deployments}
        with dspy.context(lm=lm, callbacks=callbacks):
            prediction = await dspy.Predict(SpotFieldOutlier).acall(
                field_name=field_name, peer_values=peer_values
            )
        return FieldOutlierResult(
            field_name=field_name,
            majority_value=prediction.majority_value,
            outliers=list(prediction.outliers),
            reasoning=prediction.reasoning,
            why=prediction.why,
        )

    results = await asyncio.gather(*(_one(field_name) for field_name in fields))
    return list(results)


# --- Real, mechanical (LLM-free) predicate projection -----------------------
#
# Increment 3-min of the epistemic-kernel direction, corrected after a real
# review catch: an earlier version of this function computed a real
# majority-vote outlier ONLY for the `image` field and hardwired its
# result into forcing the "image drift" hypothesis's state -- for THIS
# scenario, that field is exactly the injected fault, so privileging it by
# name is answer-injection dressed as infrastructure, not a general
# mechanical capability. Fixed: this now applies the identical
# majority-vote outlier check to EVERY field in `FIELD_NAMES_TO_TRANSPOSE`
# uniformly -- the same fields `_gather_field_outlier_flags` already asks
# an LLM panel to vote on, computed exactly instead of by LLM judgment,
# with no field treated specially. It produces real, typed, ID-addressable
# `Fact`s the ReAct loop MAY cite as evidence_ids; it does not decide, or
# even see, which hypothesis they belong to, and it never overrides an
# LLM-produced hypothesis state. Deliberately scoped to exact-match
# majority-vote outlier detection only -- the other predicate families
# named in the broader proposal (service/port/selector, scheduling,
# probes) remain real, named, un-built future work.
def _derive_deterministic_facts(
    deployments: list[DeploymentConfigSummary],
    *,
    fields: tuple[str, ...] = FIELD_NAMES_TO_TRANSPOSE,
) -> list[Fact]:
    """Pure, deterministic majority-vote outlier detection, applied
    identically to every field in `fields` -- computed once in host
    Python. For each field: one `majority_<field>` fact (the exact-match
    plurality value across all named deployments) plus one
    `<field>_outlier` fact per deployment (`\"True\"`/`\"False\"`)."""
    facts: list[Fact] = []
    for field_name in fields:
        values: dict[str, str] = {}
        for d in deployments:
            if not d.name:
                continue
            values[d.name] = _field_as_str(d, field_name)
        if not values:
            continue

        counts: dict[str, int] = {}
        for value in values.values():
            counts[value] = counts.get(value, 0) + 1
        majority_value = max(counts, key=lambda v: counts[v])

        majority_fact_id = f"fact:majority_{field_name}"
        facts.append(
            Fact(
                id=majority_fact_id,
                subject="workload-class:hotel-reservation",
                predicate=f"majority_{field_name}",
                value=majority_value,
                provenance=["list_deployment_configs"],
            )
        )
        for name, value in values.items():
            value_fact_id = f"fact:{field_name}:{name}"
            facts.append(
                Fact(
                    id=value_fact_id,
                    subject=f"deployment/{name}",
                    predicate=field_name,
                    value=value,
                    provenance=["list_deployment_configs"],
                )
            )
            facts.append(
                Fact(
                    id=f"fact:{field_name}_outlier:{name}",
                    subject=f"deployment/{name}",
                    predicate=f"{field_name}_outlier",
                    value=str(value != majority_value),
                    provenance=[value_fact_id, majority_fact_id],
                )
            )
    return facts


def _extract_text(raw: dict[str, Any]) -> str:
    """Shared plumbing (module-level so both `_build_tools`'s closures and
    `run_diagnosis`'s own shared-context pre-step can reuse it): a real
    `run_kubectl`/`_run_kubectl_raw` outcome's kubectl stdout lives at
    `kubectl_output.result_text[0].text`."""
    blocks = raw.get("kubectl_output", {}).get("result_text", [])
    return blocks[0].get("text", "") if blocks else ""


def _render_evidence_ids(evidence_ids: list[str], fact_store: list[Fact]) -> str:
    """Real, human-readable rendering of a hypothesis's cited fact ids --
    used to build a submission-time evidence narrative, never for
    grounding (grounding is the real referential-integrity check in
    `gymact.epistemic_kernel.admit_diagnosis`)."""
    by_id = {f.id: f for f in fact_store}
    parts = []
    for fact_id in evidence_ids:
        f = by_id.get(fact_id)
        parts.append(f"{fact_id}={f.value!r}" if f is not None else f"{fact_id}=<missing>")
    return "; ".join(parts)


class IncidentContext(BaseModel):
    """The real, known-structured facts about which subject is under
    investigation -- NOT a place for prose instructions (those belong in
    `DiagnoseSregymIncident`'s own docstring, not duplicated here) and NOT
    a place for a description of the actual fault (sregym hands the agent
    no such thing -- the real conductor's only public surface, GET
    /status, returns just a stage marker; the incident's real natural-
    language root cause lives only inside the problem's own grading oracle,
    never exposed to the agent -- see `misconfig_app.py`'s `root_cause`).
    So this model's fields are deliberately limited to what's genuinely
    known ahead of time: which app/namespace to investigate."""

    namespace: str = Field(description="the real Kubernetes namespace under investigation")
    app_name: str = Field(description="the real application name under investigation")


@dataclass
class SregymAgentStep:
    """One real tool invocation this agent actually made, in order."""

    tool_name: str
    payload: dict[str, Any]
    result: Any


@dataclass
class SregymAgentRunResult:
    """What a bounded `run_diagnosis()` call actually produced."""

    root_cause: str
    mitigation: str
    diagnosis_submitted: bool
    mitigation_submitted: bool
    normalized_facts: list[str] = field(default_factory=list)
    hypotheses: list[HypothesisLedger] = field(default_factory=list)
    # Real, deterministic post-hoc check (`gymact.epistemic_kernel.
    # admit_diagnosis`) -- distinct from and never collapsed with sregym's
    # own real oracle verdict. `kernel_admitted=False` means the model's
    # own hypothesis ledger failed a real, mechanical groundedness check
    # (e.g. a REFUTED/SUPPORTED entry whose cited evidence doesn't
    # actually correspond to any real normalized_fact) -- a real signal
    # independent of whether sregym's separate LLM-judge oracle happens
    # to agree with the submitted answer.
    kernel_admitted: bool = False
    kernel_admission_reason: str = ""
    steps: list[SregymAgentStep] = field(default_factory=list)


class SregymDiagnosisAgent:
    """Real, sregym-specific DSPy ReAct agent. Drives one real, already-
    materialized sregym episode through the real GymAct kernel using real,
    typed tool signatures (`RunKubectlPayload`/`SubmitDiagnosisPayload`/
    `SubmitMitigationPayload`) instead of the generic agent's bare
    `dict[str, Any]` + grounding-guard mechanism."""

    def __init__(
        self,
        gym: Any,
        episode_id: str,
        *,
        authority_ref: str,
        judge_model_id: str = "groq/openai/gpt-oss-20b",
        max_iters: int = 12,
    ) -> None:
        require_standing(
            "LOCAL_EXTRA:dspy",
            available=_dspy is not None,
            reason="gymact.dspy_sregym_agent requires the optional 'dspy' extra: "
            "install with `pip install 'gymact[dspy]'` or `uv sync --extra dspy`.",
        )
        self._dspy = _dspy
        self._gym = gym
        self._episode_id = episode_id
        self._authority_ref = authority_ref
        self._judge_model_id = judge_model_id
        self._max_iters = max_iters
        self.last_ocel_callback: DspyOcelCallback | None = None

    def _find_capability(self, binding: str) -> Capability:
        for capability in self._gym.capabilities(self._episode_id):
            if capability.binding == binding:
                return capability
        raise LookupError(f"no real capability with binding {binding!r} on this episode")

    def _build_tools(
        self, steps: list[SregymAgentStep], namespace: str
    ) -> tuple[list[Any], Any, Any]:
        dspy = self._dspy
        gym = self._gym
        episode_id = self._episode_id
        authority_ref = self._authority_ref

        async def observe() -> dict[str, Any]:
            """Read the real, current conductor status. This does NOT run
            kubectl -- it only reports the benchmark's own stage marker
            (e.g. {"stage": "setup"}). Real cluster evidence (pods,
            deployments, events) only comes from calling run_kubectl."""
            state = (await gym.observe(episode_id)).state
            steps.append(SregymAgentStep(tool_name="observe", payload={}, result=state))
            return state

        async def _run_kubectl_raw(command: str) -> dict[str, Any]:
            """Shared plumbing: real `run_kubectl` capability call, real
            kernel `gym.act()`, real `effect` extraction -- used by both the
            `run_kubectl` tool and `list_deployment_configs` below so the
            latter isn't a second, divergent path to the same real
            actuation."""
            capability = self._find_capability("run_kubectl")
            result = await gym.act(
                ActuationIntent(
                    episode_id=episode_id,
                    capability=capability.iri,
                    payload={"command": command},
                    authority_ref=authority_ref,
                )
            )
            return {
                "accepted": result.accepted,
                "standing": result.standing.value,
                "reason": result.receipt.reason,
                # The real kubectl output lives on `effect` (the raw
                # `SregymEnvironment.actuate()` return, carrying
                # `result_text`) -- `observation` is the kernel's SEPARATE
                # post-actuation `gym.observe()` call, which for sregym only
                # re-reads the conductor's `/status` stage marker and was
                # wrongly surfaced here first, hiding the real kubectl
                # output from the model entirely (confirmed live: three
                # real run_kubectl calls all "succeeded" per `accepted`,
                # but the model saw only {"stage": "setup"} each time and
                # correctly refused to fabricate a diagnosis from nothing).
                "kubectl_output": result.effect or {},
            }

        async def run_kubectl(payload: RunKubectlPayload) -> dict[str, Any]:
            """Execute a real kubectl command against the real cluster and
            return its real output. This is the ONLY source of real
            evidence about the actual misconfiguration -- call this to
            investigate, do not just keep calling observe. For a systematic
            comparison of every deployment's config, prefer
            list_deployment_configs instead of many separate `describe`
            calls."""
            outcome = await _run_kubectl_raw(payload.command)
            steps.append(
                SregymAgentStep(
                    tool_name="run_kubectl", payload=payload.model_dump(), result=outcome
                )
            )
            return outcome

        async def list_deployment_configs() -> dict[str, Any]:
            """Real, structured, one-shot comparison of EVERY deployment's
            config in the hotel-reservation namespace: image, command, env,
            resource requests/limits, replicas -- deliberately excludes
            transient signals (restart counts, pod status), which are
            common during startup and often self-resolve. Call this EARLY,
            before individual `describe`/`logs` calls: a deployment whose
            config differs from its peers along ANY of these fields is much
            stronger evidence of the actual injected misconfiguration than
            a pod that merely restarted."""
            # Real defect found and fixed forward this session: a single
            # bulk `kubectl get deployments -o json` reliably exceeds
            # sregym's own kubectl-mcp server's blind 10,000-char
            # truncation for a real ~19-deployment app (confirmed live:
            # the JSON came back cut mid-string, unparseable) -- silently
            # returning an empty list on a JSONDecodeError there would be
            # indistinguishable from "no deployments exist." Fetch names
            # first (small), then one real per-deployment call each (each
            # real response is far under 10k), so truncation can't corrupt
            # the whole result -- at worst ONE deployment's fetch fails,
            # named explicitly below, never silently dropped.
            names_raw = await _run_kubectl_raw(
                f"kubectl get deployments -n {namespace} -o "
                "jsonpath={.items[*].metadata.name}"
            )
            names = _extract_text(names_raw).split()
            summaries: list[DeploymentConfigSummary] = []
            errors: list[str] = []
            for name in names:
                raw = await _run_kubectl_raw(
                    f"kubectl get deployment {name} -n {namespace} -o json"
                )
                text = _extract_text(raw)
                if text.endswith("... [truncated]"):
                    errors.append(f"{name}: response truncated, skipped")
                    continue
                try:
                    summaries.append(_summarize_one_deployment(json.loads(text)))
                except json.JSONDecodeError as exc:
                    errors.append(f"{name}: unparseable ({exc})")
            result: dict[str, Any] = {
                "deployments": [summary.model_dump() for summary in summaries]
            }
            if errors:
                result["errors"] = errors
            steps.append(
                SregymAgentStep(
                    tool_name="list_deployment_configs", payload={}, result=result
                )
            )
            return result

        async def list_recent_warning_events() -> dict[str, Any]:
            """Real, chronological list of this namespace's recent
            Kubernetes Warning events (FailedCreate, BackOff, Unhealthy,
            FailedMount, Forbidden, webhook failures, etc.) -- this is
            usually the FASTEST way to see what's actually going wrong,
            since Kubernetes's own controllers already classify and
            summarize failures here. Call this EARLY too, alongside
            list_deployment_configs -- a structural config diff tells you
            WHAT differs; events often tell you WHY it matters right now."""
            raw = await _run_kubectl_raw(
                f"kubectl get events -n {namespace} --field-selector "
                "type=Warning --sort-by=.lastTimestamp -o "
                "jsonpath={range .items[*]}{.reason}{\"\\t\"}{.involvedObject.kind}"
                "/{.involvedObject.name}{\"\\t\"}{.message}{\"\\n\"}{end}"
            )
            text = _extract_text(raw)
            events: list[WarningEvent] = []
            for line in text.splitlines():
                parts = line.split("\t")
                if len(parts) == 3:
                    events.append(
                        WarningEvent(reason=parts[0], object=parts[1], message=parts[2])
                    )
            result: dict[str, Any] = {
                "warning_events": [event.model_dump() for event in events]
            }
            steps.append(
                SregymAgentStep(
                    tool_name="list_recent_warning_events", payload={}, result=result
                )
            )
            return result

        async def submit_diagnosis(payload: SubmitDiagnosisPayload) -> dict[str, Any]:
            """Submit the real, evidence-backed diagnosis. Only call this
            after run_kubectl has actually shown you real evidence -- never
            fabricate root_cause or evidence."""
            capability = self._find_capability("submit_diagnosis")
            result = await gym.act(
                ActuationIntent(
                    episode_id=episode_id,
                    capability=capability.iri,
                    payload=payload.model_dump(),
                    authority_ref=authority_ref,
                )
            )
            outcome = {
                "accepted": result.accepted,
                "standing": result.standing.value,
                "reason": result.receipt.reason,
            }
            steps.append(
                SregymAgentStep(
                    tool_name="submit_diagnosis", payload=payload.model_dump(), result=outcome
                )
            )
            return outcome

        async def submit_mitigation(payload: SubmitMitigationPayload) -> dict[str, Any]:
            """Submit the real, concrete mitigation. Only call this after
            submit_diagnosis."""
            capability = self._find_capability("submit_mitigation")
            result = await gym.act(
                ActuationIntent(
                    episode_id=episode_id,
                    capability=capability.iri,
                    payload=payload.model_dump(),
                    authority_ref=authority_ref,
                )
            )
            outcome = {
                "accepted": result.accepted,
                "standing": result.standing.value,
                "reason": result.receipt.reason,
            }
            steps.append(
                SregymAgentStep(
                    tool_name="submit_mitigation", payload=payload.model_dump(), result=outcome
                )
            )
            return outcome

        # Real pre-actuation admission (Increment 2 of the epistemic-kernel
        # direction): `submit_diagnosis`/`submit_mitigation` are
        # DELIBERATELY NOT included in the tool list handed to the free
        # ReAct loop below -- a real, consequential `gym.act()` call must
        # never be reachable purely because an uncontrolled LLM loop
        # decided to call it. ReAct can only manufacture CANDIDATE
        # diagnosis/mitigation data; the kernel (`run_diagnosis`, real
        # host Python) calls these two closures directly, and only after
        # `admit_diagnosis()` admits the candidate. This is the concrete
        # form of `DO ⟹ DiagnosisAdmitted ∧ MitigationAdmitted` --
        # materially stronger than a post-hoc check, matching this
        # module's own real `.claude/rules/actuation-authority.md` law
        # (`Intent ≠ Action ≠ Effect ≠ Verified Effect`) applied one layer
        # higher, to the REASONING that produces the intent, not just the
        # actuation itself.
        react_tools = [
            dspy.Tool(observe, name="observe"),
            dspy.Tool(list_deployment_configs, name="list_deployment_configs"),
            dspy.Tool(list_recent_warning_events, name="list_recent_warning_events"),
            dspy.Tool(run_kubectl, name="run_kubectl"),
        ]
        return react_tools, submit_diagnosis, submit_mitigation

    async def run_diagnosis(self, incident: IncidentContext) -> SregymAgentRunResult:
        """Run a bounded, real ReAct loop diagnosing and mitigating a real
        sregym incident. Before the main ReAct loop runs, two real,
        concurrent, cheap-model (llama-3.1-8b-instant) specialist panels
        gather real evidence-grounded theories -- fed into the main
        gpt-oss-120b loop as extra input evidence, never replacing its own
        investigation or submission authority."""
        dspy = self._dspy
        steps: list[SregymAgentStep] = []
        react_tools, submit_diagnosis, submit_mitigation = self._build_tools(
            steps, incident.namespace
        )
        tool_by_name = {tool.name: tool for tool in react_tools}

        # Real, general mechanism -- not a fact hardcoded for this one
        # scenario's answer. A live run this session showed the model
        # correctly diagnose a real service-port mismatch in its own
        # free-text ReAct reasoning, then abandon that correct conclusion
        # in the structured hypotheses output because it had no real
        # `fact_id` to cite for it: `_derive_deterministic_facts` only
        # covers 6 structural fields (image/command/env/resources/
        # replicas), never a live relational check like service-port-vs-
        # container-port, and can't cover every possible K8s predicate in
        # advance. This tool is the general fix: it lets ReAct mint a new,
        # citable `Fact` from ANY of its own real tool-call observations,
        # for ANY category, closing the "correct answer but nowhere to
        # ground it" gap without privileging any one predicate.
        dynamic_facts: list[Fact] = []

        async def record_fact(subject: str, predicate: str, value: str) -> dict[str, Any]:
            """Record one new, citable fact from something you ACTUALLY
            observed via a real tool call (run_kubectl,
            list_deployment_configs, list_recent_warning_events) -- never
            a guess, a restated hypothesis, or a conclusion. Returns the
            real fact_id assigned; cite it verbatim in a hypothesis's
            evidence_ids if you use it. Call this as soon as you notice
            something concrete and citable that isn't already covered by
            the pre-computed facts you were given."""
            fact_id = f"fact:observed:{len(dynamic_facts)}"
            fact = Fact(
                id=fact_id,
                subject=subject,
                predicate=predicate,
                value=value,
                provenance=["record_fact"],
            )
            dynamic_facts.append(fact)
            result = {"fact_id": fact_id}
            steps.append(
                SregymAgentStep(
                    tool_name="record_fact",
                    payload={"subject": subject, "predicate": predicate, "value": value},
                    result=result,
                )
            )
            return result

        react_tools = [*react_tools, dspy.Tool(record_fact, name="record_fact")]

        # Real OCEL 2.0 log of this DSPy run's OWN execution trace (every
        # LM/tool/module call, panels included) -- see `gymact.dspy_ocel`'s
        # module docstring for why this is a SEPARATE log from the kernel's
        # Receipt-based one, not a reuse of Operation/Receipt.
        ocel_callback = DspyOcelCallback(run_id=self._episode_id)
        self.last_ocel_callback = ocel_callback

        # Real pre-pass: gather the same structural evidence the main loop
        # would gather anyway (via the SAME real tools, SAME kernel path --
        # not a second, divergent data source), then hand it to both cheap
        # concurrent panels before the expensive model starts reasoning.
        deployment_result = await tool_by_name["list_deployment_configs"].acall()
        events_result = await tool_by_name["list_recent_warning_events"].acall()
        deployments = [
            DeploymentConfigSummary.model_validate(item)
            for item in deployment_result.get("deployments", [])
        ]
        evidence = {**deployment_result, **events_result}

        category_theories, field_outlier_flags = await asyncio.gather(
            _gather_category_theories(evidence, ocel_callback=ocel_callback),
            _gather_field_outlier_flags(deployments, ocel_callback=ocel_callback),
        )
        steps.append(
            SregymAgentStep(
                tool_name="panel:category_theories",
                payload={},
                result=[theory.model_dump() for theory in category_theories],
            )
        )
        steps.append(
            SregymAgentStep(
                tool_name="panel:field_outlier_flags",
                payload={},
                result=[flag.model_dump() for flag in field_outlier_flags],
            )
        )

        # Real Normalize stage (human-loop Phase 6): convert structured
        # evidence into explicit semantic facts BEFORE any hypothesis is
        # allowed to form. This is the concrete answer to a real, repeated
        # failure this session: the model had `geo`'s differing image
        # sitting directly in `list_deployment_configs`'s own output and
        # in `field_outlier_flags`, and still reasoned past it to a wrong
        # conclusion -- it never had to STATE the fact explicitly first.
        # Run as its own separate `dspy.Predict` call (not folded into the
        # main ReAct loop) so normalization can't be skipped under time/
        # iteration pressure the way an optional checklist field could be.
        class NormalizeEvidence(dspy.Signature):
            """Convert real, structured evidence into explicit, plain
            semantic facts. A fact states one real, checkable divergence
            or confirmation you can point to directly in the evidence,
            named specifically (which real field, which real deployment
            or object, which real values being compared) -- never a vague
            summary and never a guess about which field matters most;
            state EVERY real divergence you can find across every field,
            not just the first one you notice. Each fact must be
            traceable to a specific real value already present in the
            evidence. Do NOT draw any conclusion about root cause here --
            that is a later, separate step; this step only establishes
            what is actually true."""

            deployment_configs: dict[str, Any] = dspy.InputField()
            warning_events: dict[str, Any] = dspy.InputField()
            category_theories: list[CategoryCheck] = dspy.InputField()
            field_outlier_flags: list[FieldOutlierResult] = dspy.InputField()
            normalized_facts: list[str] = dspy.OutputField(
                desc="plain semantic facts, each traceable to a specific real evidence value"
            )
            # Verbose-justification field, required as the LAST output
            # field on every Signature in this module (see
            # `CategoryTheory.why`'s comment for why this exists).
            why: str = dspy.OutputField(
                desc="explicit account of your coverage (at least a few real sentences, not "
                "one line): which real evidence sources (deployment_configs fields, "
                "warning_events, category_theories, field_outlier_flags) you actually "
                "walked, and why you're confident no real divergence was missed -- not a "
                "restatement of normalized_facts.",
            )

        normalize_lm = dspy.LM(self._judge_model_id, max_tokens=4000)
        with dspy.context(lm=normalize_lm, callbacks=[ocel_callback]):
            normalize_prediction = await dspy.Predict(NormalizeEvidence).acall(
                deployment_configs=deployment_result,
                warning_events=events_result,
                category_theories=category_theories,
                field_outlier_flags=field_outlier_flags,
            )
        normalized_facts = list(normalize_prediction.normalized_facts)
        steps.append(
            SregymAgentStep(
                tool_name="normalize_evidence", payload={}, result=normalized_facts
            )
        )

        # Increment 1 (typed evidence IDs): wrap every fact -- both the
        # mechanically-derived predicate facts and the LLM-normalized prose
        # facts -- into one real, ID-addressable `fact_store`. A live run
        # this session falsified prose-vs-prose word-overlap grounding: the
        # model started citing evidence by identity ("observation_0") the
        # matcher couldn't recognize. Assigning a real, stable id to every
        # fact up front and requiring hypotheses to cite those exact ids
        # removes the need for any text matching at all -- grounding
        # becomes trivial set membership.
        deterministic_facts = _derive_deterministic_facts(deployments)
        normalized_fact_objects = [
            Fact(
                id=f"fact:normalized:{i}",
                subject=incident.namespace,
                predicate="normalized_observation",
                value=fact_text,
                provenance=["normalize_evidence"],
            )
            for i, fact_text in enumerate(normalized_facts)
        ]
        fact_store = deterministic_facts + normalized_fact_objects

        # --- Stage: Discriminate -- resolve EVERY category in isolation --
        #
        # The core redesign this session's live runs pointed to: the
        # single combined signature above used to do investigation,
        # per-category resolution, AND final root-cause selection all in
        # one shot, one trajectory. Repeated live runs showed the same
        # concrete failure mode: the model would reach a real, causally
        # SUFFICIENT explanation for one category (a real, valid SRE
        # heuristic -- stop once you have a full explanation) and, having
        # satisfied itself, leave a DIFFERENT category (with real,
        # available evidence, sometimes already cited) completely
        # unresolved. That is not a reasoning defect so much as a
        # structural one: nothing stopped early satisfaction on one
        # category from starving the others of attention within a single
        # shared trajectory.
        #
        # Fix: give every category its OWN isolated resolution -- a
        # separate, concurrent `dspy.ReAct` call per FAULT_CATEGORIES
        # entry, each blind to whether any other category has already
        # been resolved or looks "sufficient." No category can be
        # starved by another's early satisfaction because none of them
        # can see the others at all. Root-cause SELECTION only happens
        # afterward, in a separate synthesis stage, over the now-fully-
        # resolved ledger.
        class ResolveHypothesis(dspy.Signature):
            """You are the most senior Kubernetes SRE anyone here has ever
            worked with, sitting the practical exam for the highest real
            certification in the field -- graded not on speed, but on
            whether the ONE category you were assigned was actually,
            individually ruled in or out with cited evidence, not
            assumed. You have no visibility into any other category's
            investigation or conclusion; that is deliberate -- your job
            is to resolve THIS one category as rigorously as if it were
            the only thing that mattered, not to guess whether some other
            category already "found the answer."

            `observe` only reports the benchmark's own stage marker, never
            real cluster data. You are given deployment_configs and
            warning_events -- the SAME real evidence already gathered
            once before any category resolver started; read them
            directly rather than re-fetching what's already in front of
            you. Call run_kubectl only for whatever THIS category
            specifically still needs beyond what's already provided.
            Never fabricate a finding -- every claim must trace back to
            real evidence already given or a real tool result.

            You are given facts -- a real, ID-addressable list of
            established facts, each formatted as "<fact_id>: <value>".
            Some were computed by an exact-match majority-vote check
            applied UNIFORMLY across every structural field this
            benchmark tracks (image, command, env, resource_requests,
            resource_limits, replicas) -- real, mechanically-verified
            facts, equally available for any field; a mechanical fact
            existing for a field is not itself evidence that field is the
            fault. The pre-computed facts do NOT cover every possible
            category -- e.g. no fact ever tells you whether a service's
            port matches what its caller actually connects to; that can
            only come from your own real investigation. When run_kubectl
            (or any tool) shows you something concrete and citable that
            isn't already in facts, call record_fact(subject, predicate,
            value) to mint a real fact_id for it, then cite that returned
            id in evidence_ids exactly like any other fact.

            You are also given category_theory -- one concurrent
            specialist panel's independent finding for THIS SAME category
            (not the others). Cross-check your own investigation against
            it, but don't defer to it blindly -- the panel can be wrong.

            Resolve `category`'s state: SUPPORTED only when a real cited
            fact directly backs it, REFUTED when a real cited fact
            directly contradicts it, UNKNOWN only if you genuinely find
            nothing relevant after real investigation. Never default to
            SUPPORTED without a cited fact_id, and never invent a fact_id
            that isn't literally present in facts. If you put ANY real
            fact_id into evidence_ids, you MUST also resolve to SUPPORTED
            or REFUTED and write real reasoning -- citing a fact and
            leaving state UNKNOWN is refused, not accepted.

            reasoning is required structure once state is SUPPORTED or
            REFUTED (do this the first time, not only on retry): (1)
            state the EXACT predicate this category's hypothesis claims;
            (2) for EACH id in evidence_ids, state that fact's actual
            value and whether it evaluates that exact predicate or a
            different, merely-adjacent one; (3) state what a genuine
            counter-example would look like, and whether the cited facts
            rule it out. A short, conclusory sentence covering only one
            of these three is not acceptable.

            If kernel_feedback is non-empty, your previous attempt at
            THIS category was REFUSED by a real, deterministic admission
            check for the specific reason given -- investigate further
            and correct exactly that gap before answering again."""

            incident: IncidentContext = dspy.InputField(
                desc="the real subject (namespace/app) under investigation"
            )
            category: str = dspy.InputField(
                desc="the ONE fault category you are resolving -- you have no visibility "
                "into any other category's evidence, investigation, or conclusion"
            )
            # Real, already-gathered raw evidence -- the SAME dicts
            # `list_deployment_configs`/`list_recent_warning_events`
            # already returned once, before any per-category resolver
            # started, threaded forward here so you are not re-fetching
            # from scratch what the pre-pass already collected. This
            # mirrors dspy.ReAct's own `trajectory` mechanism: context
            # already gathered flows forward mechanically, not
            # rediscovered blind by every downstream step.
            deployment_configs: dict[str, Any] = dspy.InputField(
                desc="the real, already-fetched structural config of every deployment in "
                "the namespace"
            )
            warning_events: dict[str, Any] = dspy.InputField(
                desc="the real, already-fetched recent Kubernetes Warning events for the "
                "namespace"
            )
            facts: list[str] = dspy.InputField(
                desc="real facts, each formatted as '<fact_id>: <value>' -- cite the "
                "fact_id verbatim in evidence_ids, never the value text"
            )
            category_theory: CategoryCheck = dspy.InputField(
                desc="a concurrent specialist panel's independent finding for this exact "
                "category -- cross-check against it, don't defer to it blindly"
            )
            kernel_feedback: str = dspy.InputField(
                desc="empty on the first attempt at this category; otherwise the real "
                "reason gymact.epistemic_kernel.validate_hypothesis refused the prior "
                "candidate for THIS category -- address this specific gap"
            )
            hypothesis: str = dspy.OutputField(
                desc="the real, specific candidate explanation for this one category"
            )
            evidence_ids: list[str] = dspy.OutputField(
                desc="real fact_id(s), copied verbatim, this conclusion is grounded in -- "
                "empty only while state is UNKNOWN"
            )
            reasoning: str = dspy.OutputField(
                desc="required 3-part structure once state is SUPPORTED/REFUTED -- see "
                "signature docstring"
            )
            state: HypothesisState = dspy.OutputField(
                desc="SUPPORTED, REFUTED, or UNKNOWN for this one category"
            )

        resolve_lm = dspy.LM(self._judge_model_id, max_tokens=6000)

        # Real, live infrastructure limit hit this session: 8 fully
        # concurrent isolated resolvers, each running its own real ReAct
        # trajectory against the same rate-limited Groq model, blew
        # through the account's tokens-per-minute quota
        # (`LMRateLimitError`, real 250k TPM ceiling on
        # `groq/openai/gpt-oss-120b`). Throttled with a semaphore rather
        # than reducing concurrency to 1 (which would just recreate the
        # old single-shared-trajectory bottleneck this redesign exists to
        # remove) -- a few real categories in flight at once, not all 8.
        _resolve_semaphore = asyncio.Semaphore(3)

        async def _resolve_one_category(category: str) -> HypothesisLedger:
            theory = next(
                (t for t in category_theories if t.category == category),
                CategoryCheck(
                    category=category,
                    finding="no panel finding available for this category",
                    why="the concurrent category-theory panel did not return an entry for "
                    "this category -- resolve it from your own real investigation instead.",
                ),
            )
            kernel_feedback_local = ""
            h = HypothesisLedger(hypothesis=category, state=HypothesisState.UNKNOWN)
            for attempt in range(2):
                current_fact_store = fact_store + dynamic_facts
                current_facts_for_citation = [f"{f.id}: {f.value}" for f in current_fact_store]
                resolve_react = dspy.ReAct(ResolveHypothesis, tools=react_tools, max_iters=6)
                async with _resolve_semaphore:
                    with dspy.context(lm=resolve_lm, callbacks=[ocel_callback]):
                        pred = await resolve_react.acall(
                            incident=incident,
                            category=category,
                            deployment_configs=deployment_result,
                            warning_events=events_result,
                            facts=current_facts_for_citation,
                            category_theory=theory,
                            kernel_feedback=kernel_feedback_local,
                        )
                h = HypothesisLedger(
                    hypothesis=pred.hypothesis,
                    evidence_ids=list(pred.evidence_ids),
                    reasoning=pred.reasoning,
                    state=pred.state,
                )
                valid, reason = validate_hypothesis(h, fact_store + dynamic_facts)
                steps.append(
                    SregymAgentStep(
                        tool_name="resolve_category",
                        payload={"category": category, "attempt": attempt + 1},
                        result={"valid": valid, "reason": reason},
                    )
                )
                if valid or attempt == 1:
                    return h
                kernel_feedback_local = reason
            return h

        hypotheses = list(
            await asyncio.gather(*(_resolve_one_category(c) for c in FAULT_CATEGORIES))
        )

        current_fact_store = fact_store + dynamic_facts
        kernel_admitted, kernel_admission_reason = admit_diagnosis(
            hypotheses, current_fact_store, expected_hypothesis_count=len(FAULT_CATEGORIES)
        )

        # --- Stage: Diagnose -- select root_cause and synthesize a
        # mitigation ONLY from the now-fully-resolved ledger. This stage
        # never investigates and never decides a category's state --
        # by the time it runs, the ledger is either admitted (exactly
        # one real SUPPORTED entry) or not; either way, this stage's only
        # job is selection and mitigation synthesis, not discrimination.
        root_cause = ""
        mitigation = ""
        diagnosis_submitted = False
        mitigation_submitted = False
        if kernel_admitted:
            supported = next(h for h in hypotheses if h.state is HypothesisState.SUPPORTED)
            root_cause = supported.hypothesis

            class SynthesizeMitigation(dspy.Signature):
                """Given a real, already-confirmed root_cause (independently
                admitted by a deterministic kernel gate, not your own
                judgment) and the real evidence that grounds it, propose a
                concrete, real kubectl-level mitigation. Do not
                re-litigate whether root_cause is correct -- it already
                passed real admission; your job is only to fix it."""

                incident: IncidentContext = dspy.InputField(
                    desc="the real subject (namespace/app) under investigation"
                )
                root_cause: str = dspy.InputField(desc="the real, already-confirmed root cause")
                supporting_reasoning: str = dspy.InputField(
                    desc="the real reasoning that grounded root_cause's admission"
                )
                mitigation: str = dspy.OutputField(
                    desc="the real, concrete kubectl-level fix proposed"
                )
                why: str = dspy.OutputField(
                    desc="explicit justification (at least a few real sentences, not one "
                    "line) for mitigation: why it actually addresses root_cause "
                    "specifically, not just a generically plausible fix for the general "
                    "category of problem."
                )

            synth_lm = dspy.LM(self._judge_model_id, max_tokens=4000)
            with dspy.context(lm=synth_lm, callbacks=[ocel_callback]):
                synth_prediction = await dspy.ChainOfThought(SynthesizeMitigation).acall(
                    incident=incident,
                    root_cause=root_cause,
                    supporting_reasoning=supported.reasoning,
                )
            mitigation = synth_prediction.mitigation
            steps.append(
                SregymAgentStep(
                    tool_name="synthesize_mitigation",
                    payload={},
                    result={"mitigation": mitigation, "why": synth_prediction.why},
                )
            )

            diagnosis_outcome = await submit_diagnosis(
                SubmitDiagnosisPayload(
                    root_cause=root_cause,
                    evidence=(
                        f"{supported.reasoning} "
                        f"[{_render_evidence_ids(supported.evidence_ids, current_fact_store)}]"
                    ),
                )
            )
            diagnosis_submitted = bool(diagnosis_outcome["accepted"])
            if diagnosis_submitted:
                mitigation_outcome = await submit_mitigation(
                    SubmitMitigationPayload(mitigation=mitigation)
                )
                mitigation_submitted = bool(mitigation_outcome["accepted"])
        else:
            # Not admitted -- no real root_cause was confirmed. Report the
            # best candidate's own text (if any single one is SUPPORTED,
            # even amid an otherwise-unadmitted ledger, e.g.
            # MULTIPLE_SUPPORTED_HYPOTHESES) honestly, rather than
            # fabricating a root_cause/mitigation that was never actually
            # admitted.
            supported_candidates = [h for h in hypotheses if h.state is HypothesisState.SUPPORTED]
            if len(supported_candidates) == 1:
                root_cause = supported_candidates[0].hypothesis

        return SregymAgentRunResult(
            root_cause=root_cause,
            mitigation=mitigation,
            diagnosis_submitted=diagnosis_submitted,
            mitigation_submitted=mitigation_submitted,
            normalized_facts=normalized_facts,
            hypotheses=hypotheses,
            kernel_admitted=kernel_admitted,
            kernel_admission_reason=kernel_admission_reason,
            steps=steps,
        )
