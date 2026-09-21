"""CONSTRUCT8 projection from the canonical digest-bound action contract.

This module intentionally depends on :mod:`gymact.action_projection` rather than
redefining action semantics. The resulting byte remains a powerless CONSTRUCT artifact;
BRCE is still the only path to consequential DO.
"""

from __future__ import annotations

from gymact.action_projection import CanonicalActionContract
from gymact.construct8 import Construct8Word, manufacture_construct8


def project_construct8(contract: CanonicalActionContract) -> Construct8Word:
    """Project one canonical action contract to its digest-bound 8-bit control word."""

    return manufacture_construct8(
        contract.action,
        source_contract_digest=contract.contract_digest,
    )
