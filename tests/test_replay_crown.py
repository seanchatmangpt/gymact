from dataclasses import dataclass

from gymact.replay import ReplayExpectation, ReplayMode, replay_ledger


@dataclass
class Receipt:
    receipt_id: str
    parent_receipt_ids: tuple[str, ...] = ()
    subject_ref: str | None = None
    capability_ref: str | None = None
    policy_revision: str | None = None
    principal: str | None = None


@dataclass
class Record:
    record_digest: str
    receipt: Receipt


class Ledger:
    def __init__(self, records: list[Record], valid: bool = True) -> None:
        self._records = tuple(records)
        self._valid = valid

    def verify(self) -> bool:
        return self._valid

    def records(self) -> tuple[Record, ...]:
        return self._records


def test_replay_validates_parent_closure_and_identity() -> None:
    ledger = Ledger(
        [
            Record(
                "a",
                Receipt(
                    "r1",
                    subject_ref="s",
                    capability_ref="c",
                    policy_revision="p",
                ),
            ),
            Record(
                "b",
                Receipt(
                    "r2",
                    ("r1",),
                    subject_ref="s",
                    capability_ref="c",
                    policy_revision="p",
                ),
            ),
        ]
    )
    report = replay_ledger(
        ledger,
        expected=ReplayExpectation(
            subject_ref="s",
            capability_ref="c",
            policy_revision="p",
        ),
    )
    assert report.valid
    assert report.record_count == 2
    assert report.head_digest == "b"


def test_replay_detects_tamper_and_forward_parent() -> None:
    assert replay_ledger(Ledger([], valid=False)).mismatches == (
        "EVIDENCE_CHAIN_INVALID",
    )
    report = replay_ledger(Ledger([Record("a", Receipt("r1", ("future",)))]))
    assert not report.valid
    assert report.mismatches[0].startswith("PARENT_RECEIPT_MISSING_OR_FORWARD")


def test_live_reexecution_is_refused_by_default_and_never_executes() -> None:
    report = replay_ledger(Ledger([]), mode=ReplayMode.LIVE_REEXECUTION)
    assert not report.valid
    assert report.mismatches == ("LIVE_REEXECUTION_REFUSED",)

    admitted = replay_ledger(
        Ledger([]),
        mode=ReplayMode.LIVE_REEXECUTION,
        allow_live_reexecution=True,
    )
    assert admitted.valid
    assert admitted.live_reexecution_admitted
