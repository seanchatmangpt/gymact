"""Capability-scoping contracts.

GymAct never treats a provider's own capability surface as automatically
reachable by every caller. Whether a given principal may invoke a given
capability is admitted only through an injected `CapabilityScope` that the
kernel owns -- the third instance this session of the same externalization
discipline `authority.py` (permission to actuate at all) and
`verification.py` (the verdict on what happened) already apply: a decision
that gates or judges a consequential operation must sit outside the thing
being gated or judged.

Before this module existed, nothing in gymact restricted which capabilities
a caller could invoke once authority was admitted -- any admitted actuation
could call any capability a provider exposed. A real consumer building on
gymact (autofde-lab's diagnosis pipeline) needed exactly this and built its
own ad hoc TOML-manifest allowlist (`CapabilityGate`) to fill the gap, with
no gymact-owned primitive to build on -- reimplementing, per-consumer, the
same shape `AuthorityResolver` already solved once for permission-to-act.
`CapabilityScope` is that primitive, generalized and centralized here so it
is never a consumer's private reimplementation again.

`principal` (see `models.MaterializationIntent`/`ActuationIntent`/
`AuthorityRequest`) is a bare string reference -- typically a `prov:Agent`
IRI, per this repo's own `.claude/rules/ontology.md` vocabulary table
("Contestant/Harness/Verifier -> prov:Agent + prov:Role, not separate
classes") -- never a new gymact-owned class. GymAct does not model agent
identity itself; it only threads whatever reference a caller supplies
through to `Receipt.principal` (already a real, if previously unwritten,
field) and to this scope check.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class CapabilityScope(Protocol):
    """External judge for principal-vs-capability admission.

    Never implemented by a provider, and never decided by the caller making
    the request -- injected into `GymAct`, exactly like `AuthorityResolver`
    and `PostconditionVerifier`.
    """

    def permits(self, *, principal: str | None, capability_ref: str) -> bool:
        """Return whether `principal` may invoke the capability named `capability_ref`.

        `principal` is whatever caller-supplied reference (or `None`, for an
        unscoped/unidentified caller) arrived on the intent -- this method
        never resolves or authenticates it, only consults its own real
        admission data.
        """
        ...


class AllowAllCapabilityScope:
    """Default, permissive scope -- every principal may invoke every
    capability. This is deliberately gymact's default: `CapabilityScope` is
    an opt-in restriction a caller injects, not a fail-closed gate like
    `AuthorityResolver` -- adding this module must not change behavior for
    any existing `GymAct()` construction that never supplies one.
    """

    def permits(self, *, principal: str | None, capability_ref: str) -> bool:
        del principal, capability_ref
        return True


class AllowListCapabilityScope:
    """Real, reusable replacement for a hand-rolled TOML-manifest capability
    gate. Maps each principal (or `None`, for an unscoped default) to the
    frozen set of capability IRIs it may invoke.

    Intentionally Python-native, not a file-loader: per this repo's own
    `.claude/rules/python-native.md` ("compose the ecosystem, don't
    generate/reinvent"), reading a TOML manifest into this shape is a
    consumer-side concern -- any caller wanting config-file-backed grants
    loads that file itself and constructs the mapping this class consumes.
    """

    def __init__(self, grants: Mapping[str | None, frozenset[str]]) -> None:
        self._grants = dict(grants)

    def permits(self, *, principal: str | None, capability_ref: str) -> bool:
        allowed = self._grants.get(principal)
        if allowed is None:
            allowed = self._grants.get(None, frozenset())
        return capability_ref in allowed
