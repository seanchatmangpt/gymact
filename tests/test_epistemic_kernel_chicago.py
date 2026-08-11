"""Chicago-style tests for `gymact.epistemic_kernel`. No mocks: pure,
deterministic Python -- no LLM, no live cluster, real
`HypothesisLedger`/`Fact` construction and real assertions on
`admit_diagnosis`'s actual return value. Every `reasoning` string below is
real, substantive justification text for its own hypothesis -- not padding
manufactured to clear a length check.
"""

from __future__ import annotations

from gymact.dspy_agent import HypothesisLedger, HypothesisState
from gymact.epistemic_kernel import Fact, _evidence_is_grounded, admit_diagnosis


class TestEvidenceIsGrounded:
    def test_real_fact_id_present_in_store_is_grounded(self):
        assert _evidence_is_grounded(["fact:image_repo:geo"], {"fact:image_repo:geo"})

    def test_unknown_fact_id_is_not_grounded(self):
        assert not _evidence_is_grounded(["fact:does_not_exist"], {"fact:image_repo:geo"})

    def test_empty_evidence_ids_is_never_grounded(self):
        assert not _evidence_is_grounded([], {"fact:image_repo:geo"})

    def test_partial_citation_of_real_and_fake_ids_is_not_grounded(self):
        # ALL cited ids must be real -- one fabricated id among real ones
        # still fails referential integrity.
        assert not _evidence_is_grounded(
            ["fact:image_repo:geo", "fact:fabricated"], {"fact:image_repo:geo"}
        )


class TestAdmitDiagnosis:
    def test_empty_ledger_is_refused(self):
        facts = [Fact(id="fact:a", subject="s", predicate="p", value="v")]
        admitted, reason = admit_diagnosis([], facts)
        assert not admitted
        assert "NO_HYPOTHESES" in reason

    def test_missing_category_is_refused_even_if_present_ones_look_fine(self):
        """Real, mechanical count check: a ledger with fewer entries than
        `expected_hypothesis_count` is refused even when every present
        entry is individually well-formed -- an omitted category is not
        distinguishable from a checked-and-clean one without this check."""
        facts = [Fact(id="fact:alpha", subject="A", predicate="p", value="outlier")]
        hypotheses = [
            HypothesisLedger(
                hypothesis="A",
                evidence_ids=["fact:alpha"],
                reasoning=(
                    "Hypothesis A claims subject A's property p is a real outlier. "
                    "fact:alpha shows p='outlier' for subject A directly, matching "
                    "exactly what this hypothesis predicts -- there is no other real "
                    "fact in this store that contradicts that value, so it is "
                    "supported on this single, directly-relevant citation alone."
                ),
                state=HypothesisState.SUPPORTED,
            ),
        ]
        admitted, reason = admit_diagnosis(hypotheses, facts, expected_hypothesis_count=3)
        assert not admitted
        assert "MISSING_CATEGORY" in reason
        assert "3" in reason and "1" in reason

    def test_expected_hypothesis_count_met_does_not_trigger_missing_category(self):
        """When the count is satisfied, MISSING_CATEGORY must not fire even
        though downstream checks (UNCHECKED_HYPOTHESIS here) still can --
        the count check and the per-entry checks are independent gates."""
        facts = [Fact(id="fact:alpha", subject="A", predicate="p", value="outlier")]
        hypotheses = [
            HypothesisLedger(
                hypothesis="A",
                evidence_ids=["fact:alpha"],
                reasoning=(
                    "Hypothesis A claims subject A's property p is a real outlier. "
                    "fact:alpha shows p='outlier' for subject A directly, matching "
                    "exactly what this hypothesis predicts -- there is no other real "
                    "fact in this store that contradicts that value, so it is "
                    "supported on this single, directly-relevant citation alone."
                ),
                state=HypothesisState.SUPPORTED,
            ),
            HypothesisLedger(hypothesis="B", evidence_ids=[], state=HypothesisState.UNKNOWN),
        ]
        admitted, reason = admit_diagnosis(hypotheses, facts, expected_hypothesis_count=2)
        assert not admitted
        assert "MISSING_CATEGORY" not in reason
        assert "UNCHECKED_HYPOTHESIS" in reason

    def test_no_supported_hypothesis_is_refused(self):
        facts = [
            Fact(id="fact:a", subject="A", predicate="p", value="v-alpha"),
            Fact(id="fact:b", subject="B", predicate="p", value="v-beta"),
        ]
        hypotheses = [
            HypothesisLedger(
                hypothesis="A",
                evidence_ids=["fact:a"],
                reasoning=(
                    "Hypothesis A predicts that subject A's property p would equal a "
                    "specific expected value if this hypothesis were the real cause. "
                    "The cited fact:a shows p='v-alpha' for subject A, which is a "
                    "plain observation and does not match the pattern this hypothesis "
                    "requires, so it is refuted by that fact alone."
                ),
                state=HypothesisState.REFUTED,
            ),
            HypothesisLedger(
                hypothesis="B",
                evidence_ids=["fact:b"],
                reasoning=(
                    "Hypothesis B predicts that subject B's property p would equal a "
                    "specific expected value if this hypothesis were the real cause. "
                    "The cited fact:b shows p='v-beta' for subject B, which likewise "
                    "does not match what this hypothesis requires, so it is refuted."
                ),
                state=HypothesisState.REFUTED,
            ),
        ]
        admitted, reason = admit_diagnosis(hypotheses, facts)
        assert not admitted
        assert "NO_SUPPORTED_HYPOTHESIS" in reason

    def test_multiple_supported_hypotheses_is_refused(self):
        facts = [
            Fact(id="fact:alpha", subject="A", predicate="p", value="outlier"),
            Fact(id="fact:beta", subject="B", predicate="p", value="outlier"),
        ]
        hypotheses = [
            HypothesisLedger(
                hypothesis="A",
                evidence_ids=["fact:alpha"],
                reasoning=(
                    "Hypothesis A claims subject A's property p is a real outlier. "
                    "fact:alpha shows p='outlier' for subject A directly, which is "
                    "exactly the value this hypothesis predicts, so it is supported "
                    "on its own real evidence."
                ),
                state=HypothesisState.SUPPORTED,
            ),
            HypothesisLedger(
                hypothesis="B",
                evidence_ids=["fact:beta"],
                reasoning=(
                    "Hypothesis B claims subject B's property p is a real outlier. "
                    "fact:beta shows p='outlier' for subject B directly, which is "
                    "exactly the value this hypothesis predicts, so it is also "
                    "supported on its own real evidence."
                ),
                state=HypothesisState.SUPPORTED,
            ),
        ]
        admitted, reason = admit_diagnosis(hypotheses, facts)
        assert not admitted
        assert "MULTIPLE_SUPPORTED_HYPOTHESES" in reason

    def test_unchecked_hypothesis_is_refused(self):
        facts = [Fact(id="fact:alpha", subject="A", predicate="p", value="outlier")]
        hypotheses = [
            HypothesisLedger(
                hypothesis="A",
                evidence_ids=["fact:alpha"],
                reasoning=(
                    "Hypothesis A claims subject A's property p is a real outlier. "
                    "fact:alpha shows p='outlier' for subject A directly, matching "
                    "exactly what this hypothesis predicts -- there is no other real "
                    "fact in this store that contradicts that value, so it is "
                    "supported on this single, directly-relevant citation alone."
                ),
                state=HypothesisState.SUPPORTED,
            ),
            HypothesisLedger(hypothesis="B", evidence_ids=[], state=HypothesisState.UNKNOWN),
        ]
        admitted, reason = admit_diagnosis(hypotheses, facts)
        assert not admitted
        assert "UNCHECKED_HYPOTHESIS" in reason
        assert "EVIDENCE_CITED_BUT_UNRESOLVED" not in reason

    def test_evidence_cited_but_unresolved_is_refused_with_a_more_specific_reason(self):
        """Reproduces the EXACT real shape a live run this session produced:
        a hypothesis cites a real, relevant fact_id but is left at UNKNOWN
        with blank reasoning -- the model found something and never used
        it to reach a verdict. This must be distinguishable from the
        genuinely-nothing-found case (`test_unchecked_hypothesis_is_refused`
        above), since the retry feedback needed to close each gap differs:
        one needs "go investigate," the other needs "you already have
        enough -- decide.\""""
        facts = [
            Fact(
                id="fact:command_outlier:geo",
                subject="deployment/geo",
                predicate="command_outlier",
                value="True",
            ),
            Fact(id="fact:image_outlier:geo", subject="deployment/geo",
                 predicate="image_outlier", value="True"),
        ]
        hypotheses = [
            # A real SUPPORTED hypothesis, so NO_SUPPORTED_HYPOTHESIS
            # doesn't mask the check this test actually targets.
            HypothesisLedger(
                hypothesis="The geo deployment's outlier image is causing the failure.",
                evidence_ids=["fact:image_outlier:geo"],
                reasoning=(
                    "fact:image_outlier:geo shows geo's image is a real, mechanically-"
                    "detected outlier against the majority image shared by its peers, "
                    "which is exactly the divergence this hypothesis predicts, so it is "
                    "supported by this fact alone."
                ),
                state=HypothesisState.SUPPORTED,
            ),
            HypothesisLedger(
                hypothesis="The geo deployment's custom command is causing the failure.",
                evidence_ids=["fact:command_outlier:geo"],
                reasoning="",
                state=HypothesisState.UNKNOWN,
            ),
        ]
        admitted, reason = admit_diagnosis(hypotheses, facts)
        assert not admitted
        assert "EVIDENCE_CITED_BUT_UNRESOLVED" in reason
        assert "fact:command_outlier:geo" in reason

    def test_insufficient_reasoning_is_refused(self):
        """Real, kernel-side defense-in-depth: this check must catch a
        too-short `reasoning` on its own, without relying on any
        Pydantic-level enforcement (a hard `model_validator` was tried and
        reverted after a real, live run showed it crash DSPy's JSON
        adapter -- see `HypothesisLedger.reasoning`'s own NOTE in
        `gymact.dspy_agent`). Regular construction is enough to exercise
        this, since `HypothesisLedger` no longer validates length itself."""
        facts = [Fact(id="fact:alpha", subject="A", predicate="p", value="outlier")]
        supported = HypothesisLedger(
            hypothesis="A",
            evidence_ids=["fact:alpha"],
            reasoning="matches, so supported",
            state=HypothesisState.SUPPORTED,
        )
        admitted, reason = admit_diagnosis([supported], facts)
        assert not admitted
        assert "INSUFFICIENT_REASONING" in reason

    def test_real_referential_integrity_failure_is_correctly_rejected(self):
        """A hypothesis is REFUTED/SUPPORTED by citing evidence_ids that
        don't actually name a real Fact in the store -- e.g. an id the
        model invented, or one belonging to a different fact than the
        text implies. This is exactly the failure `admit_diagnosis` exists
        to catch, checked as real referential integrity, never NLP
        matching."""
        facts = [
            Fact(
                id="fact:image_repo:geo",
                subject="deployment/geo",
                predicate="image_repository",
                value="yinfangchen/geo",
            ),
            Fact(
                id="fact:majority_image_repo",
                subject="workload-class/hotel-reservation",
                predicate="majority_image_repository",
                value="ghcr.io/sregym/hotel-reservation",
            ),
            Fact(
                id="fact:geo_panic_log",
                subject="deployment/geo",
                predicate="pod_log_excerpt",
                value="panic: no reachable servers connecting to mongodb-geo:27777",
            ),
            Fact(
                id="fact:mongodb_geo_service_port",
                subject="service/mongodb-geo",
                predicate="service_port",
                value="27017",
            ),
        ]
        hypotheses = [
            HypothesisLedger(
                hypothesis="Container image/tag mismatch causing the failure",
                evidence_ids=["fact:pods_running_fine"],  # fabricated id, not real
                reasoning=(
                    "This hypothesis predicts geo's image would differ from its peers' "
                    "image if it were the real cause. The cited fact claims all pods "
                    "are running fine, which speaks to pod scheduling/health, not to "
                    "the container image field at all, so it does not evaluate this "
                    "hypothesis's actual predicate -- but the cited id is also not a "
                    "real fact in the store, which is the concrete defect this test "
                    "checks."
                ),
                state=HypothesisState.REFUTED,
            ),
            HypothesisLedger(
                hypothesis="Service port mismatch between geo and mongodb-geo",
                evidence_ids=["fact:geo_panic_log", "fact:mongodb_geo_service_port"],
                reasoning=(
                    "This hypothesis predicts geo's pod logs would show a connection "
                    "failure whose target port does not match mongodb-geo's real "
                    "Service port. fact:geo_panic_log shows geo's own logs citing port "
                    "27777, while fact:mongodb_geo_service_port shows the real Service "
                    "exposes 27017 -- both facts directly evaluate this hypothesis's "
                    "predicate and the mismatch between them is exactly what it claims."
                ),
                state=HypothesisState.SUPPORTED,
            ),
        ]
        admitted, reason = admit_diagnosis(hypotheses, facts)
        assert not admitted
        assert "UNGROUNDED_EVIDENCE" in reason
        assert "image/tag mismatch" in reason.lower() or "image" in reason.lower()

    def test_real_correctly_grounded_diagnosis_is_admitted(self):
        facts = [
            Fact(
                id="fact:image_repo:geo",
                subject="deployment/geo",
                predicate="image_repository",
                value="yinfangchen/geo",
            ),
            Fact(
                id="fact:majority_image_repo",
                subject="workload-class/hotel-reservation",
                predicate="majority_image_repository",
                value="ghcr.io/sregym/hotel-reservation",
            ),
            Fact(
                id="fact:no_rbac_warnings",
                subject="namespace/hotel-reservation",
                predicate="rbac_warning_events",
                value="none",
            ),
        ]
        hypotheses = [
            HypothesisLedger(
                hypothesis="Container image/tag mismatch causing the failure",
                evidence_ids=["fact:image_repo:geo", "fact:majority_image_repo"],
                reasoning=(
                    "This hypothesis predicts geo's image repository would differ "
                    "from the majority repository shared by its peers if it were the "
                    "real cause. fact:image_repo:geo shows geo's real image is "
                    "'yinfangchen/geo', and fact:majority_image_repo shows the real "
                    "majority repository across peers is "
                    "'ghcr.io/sregym/hotel-reservation' -- these two facts directly "
                    "evaluate this hypothesis's predicate and confirm the mismatch it "
                    "claims, with no alternative reading that would make them agree."
                ),
                state=HypothesisState.SUPPORTED,
            ),
            HypothesisLedger(
                hypothesis="RBAC or admission control preventing pod start",
                evidence_ids=["fact:no_rbac_warnings"],
                reasoning=(
                    "This hypothesis predicts real Forbidden/webhook warning events "
                    "would exist if RBAC or an admission controller were blocking the "
                    "pod. fact:no_rbac_warnings shows the real warning-event evidence "
                    "contains none, which directly contradicts what this hypothesis "
                    "requires to be true, so it is refuted by that fact's real value."
                ),
                state=HypothesisState.REFUTED,
            ),
        ]
        admitted, reason = admit_diagnosis(hypotheses, facts)
        assert admitted
        assert "image/tag mismatch" in reason.lower()
