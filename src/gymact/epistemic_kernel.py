"""A real, minimal slice of a real "epistemic process kernel": a
deterministic, mechanical admission gate over a `HypothesisLedger`, applied
BEFORE a diagnosis is accepted -- not a bigger DSPy signature, not another
ReAct prompt. Pure Python, no LLM.

Why this exists: today `DiagnoseSregymIncident` (and any similarly-shaped
gym-specific Signature) both REASONS and DECIDES WHEN TO STOP REASONING --
the model itself judges whether a hypothesis is "supported enough." A real,
live mock-harness run this session showed exactly the failure this
predicts: the model produced a real hypothesis ledger correctly containing
the right candidate, then REFUTED it citing evidence that, checked
mechanically against the real facts, does not actually support that
refutation -- a plausible-sounding but ungrounded justification.

Increment 1 (typed evidence IDs): a second real, live run then falsified
the FIRST version of this module's own grounding check. That first version
matched `evidence` prose against `facts` prose via word overlap -- and the
model started citing evidence by identity ("observation_0", "F17") instead
of by restating the fact's text, which the word-overlap check could not
recognize. That is exactly the wrong representation boundary: grounding
should never depend on whether two humans/models happened to phrase the
same fact the same way. This module now requires real, typed `Fact`
objects with stable string `id`s, and a hypothesis's `evidence_ids` (see
`gymact.dspy_agent.HypothesisLedger`) are checked by real referential
integrity -- `Grounded(H) <=> forall f in evidence_ids(H), f in
{fact.id for fact in facts}` -- not by any NLP matching at all. No
stopwords, no substring matching, no word overlap: deleted, not improved.

Generic, gym-agnostic -- operates only on `gymact.dspy_agent.
HypothesisLedger` and a real `list[Fact]`, no sregym-specific knowledge.
Deliberately scoped: this is NOT the full state-machine kernel described in
the larger "Epistemic Process Kernel" architecture (owning Normalize/
Hypothesize/Discriminate/Diagnose as separate, kernel-sequenced
transitions) -- that is real, larger follow-on work. This module only
builds the pieces proven valuable by real, live failures: a typed evidence
graph and a diagnosis-admission gate over it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from gymact.dspy_agent import HypothesisLedger, HypothesisState

# Mirrors `HypothesisLedger._MIN_REASONING_LENGTH` -- kept as a separate,
# explicit constant here (not imported) since this module's check is a
# deliberate, independent re-verification, not a reuse of the same trust.
_MIN_REASONING_LENGTH = 200


class Fact(BaseModel):
    """One real, typed, ID-addressable unit of evidence -- the concrete
    replacement for a free-text `normalized_facts: list[str]` entry. A
    hypothesis's `evidence_ids` must name real `Fact.id`s; grounding is
    then a trivial, exact, mechanical membership check, never a fuzzy
    match. `subject`/`predicate`/`value` are deliberately loose strings
    (not a full RDF triple store) -- this is the smallest real typed
    representation that fixes the ID-citation defect, not a general
    knowledge-graph engine."""

    id: str = Field(description="a stable, unique identifier, e.g. 'fact:replicas:some-deployment'")
    subject: str = Field(description="what this fact is about, e.g. 'deployment/some-deployment'")
    predicate: str = Field(description="the real property/relation being asserted")
    value: str = Field(description="the real, observed value")
    provenance: list[str] = Field(
        default_factory=list,
        description="how this fact was derived -- a tool name, another fact's id, or both",
    )


def _evidence_is_grounded(evidence_ids: list[str], fact_ids: set[str]) -> bool:
    """Real referential-integrity check, nothing more: every cited
    `evidence_ids` entry must name a real `Fact` actually present in
    `fact_ids`. An empty citation list is never grounded -- a hypothesis
    that reached SUPPORTED/REFUTED without citing any real fact ID has
    stated a conclusion, not shown its work."""
    if not evidence_ids:
        return False
    return all(fact_id in fact_ids for fact_id in evidence_ids)


def validate_hypothesis(h: HypothesisLedger, facts: list[Fact]) -> tuple[bool, str]:
    """Real, per-entry validity check -- factored out of `admit_diagnosis`
    so a caller doing ISOLATED, per-category resolution (one hypothesis at
    a time, each blind to the others -- see `dspy_sregym_agent.
    _resolve_one_category`) can validate a single `HypothesisLedger` on
    its own, without the ledger-level SUPPORTED-cardinality checks that
    only make sense once the full ledger is assembled. `admit_diagnosis`
    itself calls this for every entry in its own loop -- one real
    implementation, two real call sites, not a duplicated copy."""
    fact_ids = {f.id for f in facts}

    if h.state is HypothesisState.UNKNOWN:
        if h.evidence_ids:
            return (
                False,
                f"REFUSED:EVIDENCE_CITED_BUT_UNRESOLVED -- hypothesis {h.hypothesis!r} "
                f"already cites real fact_id(s) {h.evidence_ids!r} as relevant, but was "
                "left at UNKNOWN with no reasoning -- you already found evidence for this "
                "hypothesis; decide now whether it actually SUPPORTS or REFUTES the "
                "hypothesis and write the reasoning explaining why, don't leave a real "
                "citation dangling with no verdict",
            )
        return (
            False,
            f"REFUSED:UNCHECKED_HYPOTHESIS -- {h.hypothesis!r} was never actually "
            "checked (state=UNKNOWN)",
        )

    if not _evidence_is_grounded(h.evidence_ids, fact_ids):
        return (
            False,
            f"REFUSED:UNGROUNDED_EVIDENCE -- hypothesis {h.hypothesis!r} is "
            f"{h.state.value.upper()} but its evidence_ids {h.evidence_ids!r} do not all "
            "name a real Fact.id in the fact store",
        )

    if len(h.reasoning) < _MIN_REASONING_LENGTH:
        return (
            False,
            f"REFUSED:INSUFFICIENT_REASONING -- hypothesis {h.hypothesis!r} is "
            f"{h.state.value.upper()} but its reasoning is only {len(h.reasoning)} chars "
            f"(minimum {_MIN_REASONING_LENGTH}). The length floor is not itself the "
            "point -- a one-line conclusion that cites a real fact_id but never states "
            "why that fact's specific value settles THIS hypothesis's predicate (rather "
            "than some other, unrelated property of the same resource) is exactly the "
            "shape of an ungrounded-in-substance verdict, even when the citation itself "
            "is real. A short answer has no room to do that work; a genuinely short "
            "justification is a sign the model skipped the check, not evidence it was "
            "fast. Rewrite reasoning to state, explicitly: (1) the exact predicate this "
            "hypothesis claims (what would have to be true of the cited fact's value for "
            "this hypothesis to be correct), (2) each cited fact's actual value and "
            "whether it evaluates that exact predicate or a different one, (3) what a "
            "genuine counter-example would look like, and whether the cited facts rule "
            "it out.",
        )

    return True, f"VALID -- {h.hypothesis!r} is {h.state.value.upper()} and grounded"


def admit_diagnosis(
    hypotheses: list[HypothesisLedger],
    facts: list[Fact],
    *,
    expected_hypothesis_count: int | None = None,
) -> tuple[bool, str]:
    """The real admission gate. Returns `(admitted, reason)` -- `reason`
    always names the SPECIFIC real violation on rejection, never a bare
    `False`, so a rejected diagnosis is debuggable, not just blocked.

    Real, checkable criteria:
    0. If `expected_hypothesis_count` is given, the ledger has at least
       that many entries -- a real, mechanical count check catching a
       category dropped ENTIRELY from the output (as opposed to criterion
       3 below, which only catches a category that's present but left
       `UNKNOWN`). Deliberately count-only, not a per-category identity
       match: `HypothesisLedger` has no `category` field to match against,
       and inventing fuzzy text-matching between a hypothesis's free-text
       `hypothesis` field and a category label would reintroduce exactly
       the kind of prose matching Increment 1 removed for evidence
       grounding. This module stays gym-agnostic -- the caller (which
       knows its own category taxonomy) supplies the expected count, not
       the category names themselves.
    1. Exactly one hypothesis is `SUPPORTED` (zero means nothing was
       actually concluded; more than one means the ledger itself is
       internally inconsistent -- a real diagnosis names ONE root cause).
    2. Every `SUPPORTED`/`REFUTED` hypothesis's `evidence_ids` are real
       and present in `facts` (an `UNKNOWN` hypothesis is allowed to have
       no evidence yet -- that's what `UNKNOWN` means).
    3. No hypothesis is left `UNKNOWN` -- every real candidate must have
       actually been checked, matching the exhaustive-checklist principle
       (a category nobody looked at is not evidence of anything). A
       hypothesis left `UNKNOWN` despite already citing real
       `evidence_ids` is refused with a MORE specific reason
       (`EVIDENCE_CITED_BUT_UNRESOLVED`) than a genuinely-unchecked one
       (`UNCHECKED_HYPOTHESIS`) -- the model already found something
       relevant and needs to be told to conclude, not to search again."""
    if not hypotheses:
        return False, "REFUSED:NO_HYPOTHESES -- an empty hypothesis ledger admits nothing"

    if expected_hypothesis_count is not None and len(hypotheses) < expected_hypothesis_count:
        missing = expected_hypothesis_count - len(hypotheses)
        return (
            False,
            f"REFUSED:MISSING_CATEGORY -- expected {expected_hypothesis_count} hypotheses "
            f"(one per required category) but only {len(hypotheses)} were returned "
            f"({missing} missing entirely) -- every required category needs a real "
            "HypothesisLedger entry, even one that ends UNKNOWN because nothing was found; "
            "an omitted category is not evidence it was checked and found clean",
        )

    supported = [h for h in hypotheses if h.state is HypothesisState.SUPPORTED]
    if len(supported) == 0:
        return False, "REFUSED:NO_SUPPORTED_HYPOTHESIS -- no hypothesis reached SUPPORTED"
    if len(supported) > 1:
        names = [h.hypothesis for h in supported]
        return (
            False,
            f"REFUSED:MULTIPLE_SUPPORTED_HYPOTHESES -- {names!r}, a real diagnosis "
            "names exactly one root cause",
        )

    for h in hypotheses:
        valid, reason = validate_hypothesis(h, facts)
        if not valid:
            return False, reason

    return True, f"ADMITTED -- {supported[0].hypothesis!r} is the sole supported hypothesis"
