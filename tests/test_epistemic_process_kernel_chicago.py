"""Chicago-style tests for `gymact.epistemic_process_kernel.next_kernel_action`
-- the pure, deterministic decision a real live cluster run exposed a real
bug in (4 SUPPORTED + 0 UNKNOWN was wrongly treated as closure, so
Discriminate never ran at all). No mocks, no LLM, no live cluster: this
function takes plain ints and returns a plain string, so the exact
regression is directly testable.
"""

from __future__ import annotations

from gymact.epistemic_dspy import CandidateClaim, EvidenceLinkProposal
from gymact.epistemic_process_kernel import _admit_claims, _admit_links, next_kernel_action


def test_one_supported_zero_unknown_reaches_closure():
    """1 SUPPORTED + rest REFUTED (0 UNKNOWN) -- the discriminator must
    NOT run; this is a genuinely clean result."""
    assert next_kernel_action(supported_count=1, unknown_count=0) == "closure"


def test_multiple_supported_zero_unknown_discriminates():
    """The exact real shape a live cluster run produced: 4 SUPPORTED + 0
    UNKNOWN. This is over-determined, not resolved -- the discriminator
    MUST run to try to partition the survivors."""
    assert next_kernel_action(supported_count=4, unknown_count=0) == "discriminate"


def test_unknown_hypotheses_discriminate():
    """Any real UNKNOWN remaining (under-determined, with or without a
    concurrent SUPPORTED) means the discriminator MUST run."""
    assert next_kernel_action(supported_count=0, unknown_count=2) == "discriminate"
    assert next_kernel_action(supported_count=1, unknown_count=1) == "discriminate"


def test_all_refuted_does_not_fake_diagnosis():
    """0 SUPPORTED + 0 UNKNOWN (every real candidate was falsified) must
    never be silently treated as closure -- the kernel re-hypothesizes
    instead of calling Discriminate against an empty frontier or
    fabricating a forced diagnosis."""
    assert next_kernel_action(supported_count=0, unknown_count=0) == "rehypothesize"


class TestAdmitLinks:
    """Real, Chicago-style tests for `_admit_links` -- the referential-
    integrity check that structurally enacts van der Aalst's "No AI Without
    PI!" (arXiv:2508.00116) requirement that a process-intelligence query
    answer be "based on process mining computations rather than guessing":
    a hypothesis-evidence link citing a fact_id absent from the real fact
    store is refused, never silently kept. Pure, deterministic Python -- no
    LLM, no mocks. Real `EvidenceLinkProposal` construction throughout.

    This class closes a real, found test-coverage gap: `_admit_links`'s
    `REFUSED:UNGROUNDED_LINK` path had zero direct test coverage before this
    (only exercised indirectly, if at all, through `run_episode`'s full
    live-LM loop, which every DSPy-dependent test in this repo already
    skips without a real GROQ_API_KEY). The sibling `REFUSED:UNGROUNDED_
    CLAIM` refusal (epistemic_process_kernel.py's `run_episode`, checking
    `claim.source_observation_ids` against real observation ids) is NOT
    tested here for the same reason every other `run_episode`-level
    assertion in this repo is absent without a live LM: it is reached only
    inside that function's real `dspy.context(lm=lm)` block, not a
    standalone pure function like `_admit_links` -- a real, honestly-named
    constraint of this environment, not an oversight."""

    def test_link_citing_a_real_fact_id_is_admitted(self):
        link = EvidenceLinkProposal(
            hypothesis_id="hyp:1",
            fact_id="fact:real",
            relation="SUPPORTS",
            why="the real fact directly supports this hypothesis",
        )

        admitted, refused_reasons = _admit_links([link], {"fact:real"})

        assert admitted == [link]
        assert refused_reasons == []

    def test_link_citing_a_fact_id_absent_from_the_real_store_is_refused(self):
        link = EvidenceLinkProposal(
            hypothesis_id="hyp:1",
            fact_id="fact:fabricated",
            relation="SUPPORTS",
            why="claims support from a fact that was never actually observed",
        )

        admitted, refused_reasons = _admit_links([link], {"fact:real"})

        assert admitted == []
        assert len(refused_reasons) == 1
        assert "REFUSED:UNGROUNDED_LINK" in refused_reasons[0]
        assert "hyp:1" in refused_reasons[0]
        assert "fact:fabricated" in refused_reasons[0]

    def test_mixed_real_and_fabricated_links_partition_correctly(self):
        grounded = EvidenceLinkProposal(
            hypothesis_id="hyp:a",
            fact_id="fact:real",
            relation="CONTRADICTS",
            why="a real fact that genuinely contradicts this hypothesis",
        )
        ungrounded = EvidenceLinkProposal(
            hypothesis_id="hyp:b",
            fact_id="fact:does-not-exist",
            relation="SUPPORTS",
            why="cites a fact_id no real observation ever produced",
        )

        admitted, refused_reasons = _admit_links(
            [grounded, ungrounded], {"fact:real"}
        )

        assert admitted == [grounded]
        assert len(refused_reasons) == 1
        assert "hyp:b" in refused_reasons[0]

    def test_empty_links_list_admits_nothing_and_refuses_nothing(self):
        admitted, refused_reasons = _admit_links([], {"fact:real"})

        assert admitted == []
        assert refused_reasons == []


class TestAdmitClaims:
    """Real, Chicago-style tests for `_admit_claims` -- the sibling of
    `_admit_links` above, structurally enacting the same van der Aalst
    "No AI Without PI!" (arXiv:2508.00116) requirement that a
    process-intelligence query answer be "based on process mining
    computations rather than guessing": a `CandidateClaim` citing an
    observation id no real Discriminate call actually produced is
    refused, never silently kept. Pure, deterministic Python -- no LLM,
    no mocks. Real `CandidateClaim` construction throughout (a plain
    Pydantic `BaseModel` -- only `CandidateClaimExtractor`, the DSPy
    module that PRODUCES claims, needs a live LM; constructing a
    `CandidateClaim` instance directly does not).

    This class closes the real, found test-coverage gap named in
    `TestAdmitLinks`'s own docstring above: the `REFUSED:UNGROUNDED_CLAIM`
    refusal previously lived inline inside `run_episode`'s real
    `dspy.context(lm=lm)` block and had zero direct test coverage."""

    def test_claim_citing_only_real_observation_ids_is_admitted(self):
        claim = CandidateClaim(
            subject="pod:web-1",
            predicate="status",
            value="CrashLoopBackOff",
            source_observation_ids=["obs:0"],
            rationale="the real kubectl output directly reports this status",
        )

        admitted, refused_reasons = _admit_claims([claim], {"obs:0"})

        assert admitted == [claim]
        assert refused_reasons == []

    def test_claim_citing_a_fabricated_observation_id_is_refused(self):
        claim = CandidateClaim(
            subject="pod:web-1",
            predicate="status",
            value="CrashLoopBackOff",
            source_observation_ids=["obs:fabricated"],
            rationale="claims support from an observation that was never actually made",
        )

        admitted, refused_reasons = _admit_claims([claim], {"obs:0"})

        assert admitted == []
        assert len(refused_reasons) == 1
        assert "REFUSED:UNGROUNDED_CLAIM" in refused_reasons[0]

    def test_mixed_real_and_fabricated_claims_partition_correctly(self):
        grounded = CandidateClaim(
            subject="pod:web-1",
            predicate="status",
            value="CrashLoopBackOff",
            source_observation_ids=["obs:0"],
            rationale="a real observation that genuinely reports this status",
        )
        ungrounded = CandidateClaim(
            subject="pod:web-2",
            predicate="status",
            value="Running",
            source_observation_ids=["obs:does-not-exist"],
            rationale="cites an observation id no real Discriminate call ever produced",
        )

        admitted, refused_reasons = _admit_claims(
            [grounded, ungrounded], {"obs:0"}
        )

        assert admitted == [grounded]
        assert len(refused_reasons) == 1
        assert "REFUSED:UNGROUNDED_CLAIM" in refused_reasons[0]

    def test_empty_claims_list_admits_nothing_and_refuses_nothing(self):
        admitted, refused_reasons = _admit_claims([], {"obs:0"})

        assert admitted == []
        assert refused_reasons == []
