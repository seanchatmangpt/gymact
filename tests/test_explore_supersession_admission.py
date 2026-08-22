from datetime import UTC, datetime

import pytest

from gymact.explore_supersession.admission import admit
from gymact.explore_supersession.epoch import Epoch
from gymact.explore_supersession.evidence import Evidence, Outcome
from gymact.explore_supersession.subject import Refusal, Subject


def test_admission_refuses_foreign_repository():
    subject = Subject("seanchatmangpt/gymact", "a" * 40)
    foreign = Subject("seanchatmangpt/chatman-ecosystem", "b" * 40)
    row = Evidence(
        foreign,
        Epoch(datetime.now(UTC)),
        "ci",
        "repo",
        Outcome.PASS,
        "run-1",
    )
    with pytest.raises(Refusal, match="REFUSED_FOREIGN_REPOSITORY_EVIDENCE"):
        admit(subject, [row])
