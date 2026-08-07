"""Chicago-style tests for the zero-unreceipted-actuation invariant.

Exercises the real ReferenceEnvironment directly — no unittest.mock, no patched
collaborators. See .claude/rules/actuation-authority.md and
~/.claude/rules/testing-chicago-style.md.
"""

from __future__ import annotations

from gymact import ActuationResult, Capability, Consequence, Intent, ReferenceEnvironment, Standing


def _environment_with(consequence: Consequence) -> tuple[ReferenceEnvironment, Capability]:
    env = ReferenceEnvironment()
    capability = Capability(id="cap-1", title="Test capability", consequence=consequence)
    env.register(capability, initial_state={"count": 0})
    return env, capability


def test_observe_never_requires_authority() -> None:
    """observe() returns real state without any authority reference."""
    env, capability = _environment_with(Consequence.DO)

    state = env.observe(capability.id)

    assert state == {"count": 0}


def test_do_actuation_without_authority_is_refused_not_applied() -> None:
    """A DO intent with no authority_ref is refused and leaves state untouched."""
    env, capability = _environment_with(Consequence.DO)
    intent = Intent(capability_id=capability.id, payload={"count": 1}, idempotency_key="k1")

    result: ActuationResult = env.actuate(intent)

    assert result.standing is Standing.REFUSED
    assert result.reason is not None
    assert "authority_ref" in result.reason
    assert env.observe(capability.id) == {"count": 0}


def test_do_actuation_with_authority_is_accepted_and_receipted() -> None:
    """A DO intent with an authority_ref is accepted, applied, and fully receipted."""
    env, capability = _environment_with(Consequence.DO)
    intent = Intent(
        capability_id=capability.id,
        payload={"count": 1},
        authority_ref="policy:incident-42",
        idempotency_key="k2",
    )

    result = env.actuate(intent)

    assert result.standing is Standing.ACCEPTED
    assert result.pre_state == {"count": 0}
    assert result.post_state == {"count": 1}
    assert result.intent == intent
    assert env.observe(capability.id) == {"count": 1}


def test_read_actuation_requires_no_authority() -> None:
    """A READ-consequence capability may be actuated without an authority_ref."""
    env, capability = _environment_with(Consequence.READ)
    intent = Intent(capability_id=capability.id, payload={"count": 5}, idempotency_key="k3")

    result = env.actuate(intent)

    assert result.standing is Standing.ACCEPTED
    assert env.observe(capability.id) == {"count": 5}
