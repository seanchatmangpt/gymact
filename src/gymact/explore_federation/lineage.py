from dataclasses import dataclass


@dataclass(frozen=True)
class Lineage:
    predecessor_pr: int
    predecessor_head: str
    predecessor_branch: str
    state: str
    draft: bool


def admit_lineage(lineage: Lineage) -> Lineage:
    if lineage.state != "open" or not lineage.draft:
        raise ValueError("REFUSED_SCHEDULE_PR_LINEAGE")
    if len(lineage.predecessor_head) != 40:
        raise ValueError("REFUSED_INEXACT_PREDECESSOR")
    return lineage
