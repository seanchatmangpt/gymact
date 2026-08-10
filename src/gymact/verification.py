"""Postcondition verification contracts.

GymAct never treats a provider's own `Environment.verify()` report as the
verdict. Independent verification is admitted only through an injected
`PostconditionVerifier` that the kernel owns -- exactly the same
externalization discipline `authority.py` already applies to consequential
operations: an actor must not also be the judge of its own outcome.

Before this module existed, `GymAct.verify()` called `state.environment.
verify(expected)` and trusted whatever `(passed, observed)` tuple the
provider returned as the result -- the provider both produced the
observation and rendered the verdict. A dishonest provider's `verify()`
could return `passed=True` unconditionally and nothing downstream would
catch it (confirmed concretely in `gymact.gyms.vendor_benchmarks`'s and
`gymact.gyms.sregym`'s own `verify()` implementations, both of which compute
`passed` from their own observation with no external check).

`VerificationResult`'s own docstring already says "Independent predicate
result over observed state" -- this module is what makes that true. The
provider's own `verify()` report is still collected (as an audit signal, not
discarded), but the `passed` value callers actually see and act on is now
computed by this externally-injected judge over the kernel's own `observe()`
read, never by the provider being graded. A divergence between the
provider's self-report and the independent judgment is itself real, positive
evidence of a dishonest or buggy provider, and is recorded on the resulting
Receipt rather than silently discarded.

The default `DictSubsetVerifier` reproduces `gymact.local_providers`'s own
`_partial_match` recursive-subset semantics exactly (a strict superset of
the flatter `all(observed.get(k) == v for k, v in expected.items())` logic
`vendor_benchmarks.py`/`sregym.py` separately reimplement -- recursive
partial match degrades to that same flat comparison at any leaf that isn't
itself a dict) -- centralizing it here does not change what "passed" means
for any existing provider; it only moves who is trusted to compute it.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


def _partial_match(observed: object, expected: object, *, path: str = "") -> list[str]:
    """Recursive subset match; returns the sorted dotted-paths that mismatched
    (empty list means a full match). Mirrors `gymact.local_providers._partial_match`
    exactly, extended only to collect diagnostic paths instead of a bare bool."""
    if isinstance(expected, dict):
        if not isinstance(observed, dict):
            return [path or "<root>"]
        mismatches: list[str] = []
        for key, value in expected.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key not in observed:
                mismatches.append(child_path)
                continue
            mismatches.extend(_partial_match(observed[key], value, path=child_path))
        return mismatches
    return [] if observed == expected else [path or "<root>"]


@runtime_checkable
class PostconditionVerifier(Protocol):
    """External judge for observed-vs-expected state.

    Never implemented by a provider/Environment -- injected into `GymAct`,
    exactly like `AuthorityResolver`. A provider's own `Environment.verify()`
    remains part of the `Environment` protocol as a legacy/audit signal (see
    `gymact.providers.Environment`), but this is the sole real judge of
    `VerificationResult.passed`.
    """

    def judge(self, expected: dict[str, Any], observed: dict[str, Any]) -> tuple[bool, str]:
        """Return (passed, reason).

        `reason` must be a fixed, judge-authored string -- never provider
        text -- naming which expected keys mismatched on failure, or a fixed
        success marker on success, so a Receipt's `reason` field can safely
        record it without laundering an untrusted provider's own claim.
        """
        ...


class DictSubsetVerifier:
    """Default, safe, mechanical, kernel-owned comparator.

    `expected` is treated as a required recursive subset of `observed`: every
    key in `expected` must be present in `observed` with an equal value,
    recursing into nested dicts; keys in `observed` not mentioned in
    `expected` are ignored at every level. This is `gymact.local_providers.
    _partial_match`'s own semantics, reproduced here so it is the kernel's
    own computation, never a provider's to game.
    """

    def judge(self, expected: dict[str, Any], observed: dict[str, Any]) -> tuple[bool, str]:
        mismatched = sorted(_partial_match(observed, expected))
        if mismatched:
            return False, f"VERIFY_MISMATCH:{','.join(mismatched)}"
        return True, "VERIFIED:SUBSET_MATCH"
