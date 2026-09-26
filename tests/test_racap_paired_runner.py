import pytest

from gymact.racap_paired_world import (
    CapabilityObservation,
    PairedCohortReplay,
    PairedExecutionOrder,
    PairedWorldCourt,
    PairedWorldIdentity,
    PairedWorldRunner,
    PairedWorldRun,
)


def _d(char: str) -> str:
    return "blake3:" + char * 64


def _identity(task: str, seed: int) -> PairedWorldIdentity:
    return PairedWorldIdentity(
        world_digest=_d("a"),
        task_digest=_d(task),
        seed=seed,
        budget_digest=_d("b"),
        evaluator_digest=_d("c"),
    )


class DeterministicBoundedExecutor:
    """A real in-memory bounded world used to exercise the runner contract."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def __call__(
        self,
        identity: PairedWorldIdentity,
        capability_digest: str,
    ) -> CapabilityObservation:
        self.calls.append((capability_digest, identity.seed))
        candidate = capability_digest == _d("2")
        score = 0.80 if candidate else 0.60
        outcome_char = "d" if candidate else "e"
        return CapabilityObservation(
            capability_digest=capability_digest,
            outcome_digest=_d(outcome_char),
            consequence_digest=_d("f"),
            receipt_digest=_d("1" if candidate else "3"),
            score=score,
            success=True,
            steps=4,
        )


def test_runner_executes_exact_pair_and_preserves_explicit_order() -> None:
    executor = DeterministicBoundedExecutor()
    runner = PairedWorldRunner(executor)

    record = runner.execute_pair(
        identity=_identity("4", 7),
        champion_capability_digest=_d("5"),
        candidate_capability_digest=_d("2"),
        order=PairedExecutionOrder.CANDIDATE_FIRST,
    )

    assert executor.calls == [(_d("2"), 7), (_d("5"), 7)]
    assert record.order is PairedExecutionOrder.CANDIDATE_FIRST
    assert record.evidence.delta == pytest.approx(0.20)
    assert record.authority == "none"
    assert record.execution_digest.startswith("blake3:")


def test_runner_alternates_order_across_cohort_without_changing_identity() -> None:
    executor = DeterministicBoundedExecutor()
    runner = PairedWorldRunner(executor)
    identities = (
        _identity("4", 1),
        _identity("5", 2),
        _identity("6", 3),
        _identity("7", 4),
    )

    cohort = runner.execute_cohort(
        identities=identities,
        champion_capability_digest=_d("5"),
        candidate_capability_digest=_d("2"),
    )

    assert len(cohort.evidence) == 4
    assert executor.calls == [
        (_d("5"), 1),
        (_d("2"), 1),
        (_d("2"), 2),
        (_d("5"), 2),
        (_d("5"), 3),
        (_d("2"), 3),
        (_d("2"), 4),
        (_d("5"), 4),
    ]


def test_runner_refuses_executor_that_returns_wrong_capability_identity() -> None:
    def wrong_executor(
        identity: PairedWorldIdentity,
        capability_digest: str,
    ) -> CapabilityObservation:
        del identity, capability_digest
        return CapabilityObservation(
            capability_digest=_d("9"),
            outcome_digest=_d("a"),
            consequence_digest=_d("b"),
            receipt_digest=_d("c"),
            score=1.0,
            success=True,
            steps=1,
        )

    with pytest.raises(
        ValueError,
        match="PAIRED_WORLD_EXECUTOR_CAPABILITY_MISMATCH",
    ):
        PairedWorldRunner(wrong_executor).execute_pair(
            identity=_identity("4", 1),
            champion_capability_digest=_d("5"),
            candidate_capability_digest=_d("2"),
        )


def test_cohort_digest_is_order_independent() -> None:
    court = PairedWorldCourt()
    first = PairedWorldRun(
        identity=_identity("4", 1),
        champion=DeterministicBoundedExecutor()(_identity("4", 1), _d("5")),
        candidate=DeterministicBoundedExecutor()(_identity("4", 1), _d("2")),
    )
    second = PairedWorldRun(
        identity=_identity("5", 2),
        champion=DeterministicBoundedExecutor()(_identity("5", 2), _d("5")),
        candidate=DeterministicBoundedExecutor()(_identity("5", 2), _d("2")),
    )

    forward = court.observe_cohort((first, second))
    reverse = court.observe_cohort((second, first))

    assert forward.cohort_digest == reverse.cohort_digest
    assert [e.identity_digest for e in forward.evidence] == [
        e.identity_digest for e in reverse.evidence
    ]


def test_replay_manifest_binds_all_evidence_and_is_order_stable() -> None:
    executor = DeterministicBoundedExecutor()
    court = PairedWorldCourt()
    runs = []
    for task, seed in (("4", 1), ("5", 2), ("6", 3)):
        identity = _identity(task, seed)
        runs.append(
            PairedWorldRun(
                identity=identity,
                champion=executor(identity, _d("5")),
                candidate=executor(identity, _d("2")),
            )
        )

    cohort = court.observe_cohort(tuple(reversed(runs)))
    manifest = PairedCohortReplay.from_cohort(cohort)

    assert len(manifest.identity_digests) == 3
    assert len(manifest.evidence_digests) == 3
    assert manifest.cohort_digest == cohort.cohort_digest
    assert manifest.manifest_digest.startswith("blake3:")
    assert manifest.authority == "none"
