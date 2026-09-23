"""Chicago-style: a real GymAct episode driven against real, upstream
`tau2` (Sierra's tau2-bench / tau^3-bench, `vendor-tau2-bench` pin in
autofde-lab's `docs/papers/gym-lock.ttl`) -- no vendored/reimplemented
domain logic, no mocked `tau2.environment.environment.Environment`.

`GymAct.materialize` really instantiates `Tau2BenchEnvironment`, which
really wraps a real `tau2.domains.retail.environment.get_environment()`
object; every `act()` call below really calls the real domain's
`Environment.use_tool`, and `verify()` really replays the task's own
shipped reference trajectory on a fresh env and compares real DB hashes
(tau2's own `RewardType.DB` mechanism) -- no fabricated pass/fail.

Requires `TAU2_DATA_DIR` to point at a real local checkout of tau2-bench's
`data/tau2` directory (its task/domain JSON fixtures are not published as
part of the installable Python package -- a real, environment-fixable gap,
not a design choice of this module). If unset, or if `tau2` itself is not
installed (its `tau2-bench` extra requires Python >=3.12,<3.14), these
tests degrade to a named, visible skip via `require_standing`, never a
silent mock substitution.

Live end-to-end tau2-bench evaluation (`tau2 run`) drives a real LLM user
simulator and genuinely requires a configured LLM API key -- out of scope
here and for this provider (see `tau2_bench.py`'s module docstring); this
file exercises exactly the deterministic, LLM-free substrate the provider
implements: real tool capabilities, real DB mutation, real
`env_assertions`/DB-hash verification.
"""

from __future__ import annotations

import os

import pytest

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent
from gymact.models import ActuationIntent, Operation
from gymact.standing import require_standing

try:
    import tau2  # noqa: F401

    TAU2_IMPORTABLE = True
except ImportError:
    TAU2_IMPORTABLE = False

_DATA_DIR = os.environ.get("TAU2_DATA_DIR")
_TASK_DATA_AVAILABLE = bool(_DATA_DIR) and os.path.isdir(
    os.path.join(_DATA_DIR, "tau2", "domains", "retail")
)

require_standing(
    "LOCAL_GYM:tau2-bench",
    available=TAU2_IMPORTABLE and _TASK_DATA_AVAILABLE,
    reason=(
        "tau2 is not installed (gyms extra 'tau2-bench', Python >=3.12,<3.14) "
        "or TAU2_DATA_DIR is not set to a real local checkout of tau2-bench's "
        "data/tau2 directory (its task/domain fixtures are not shipped in the "
        "installable package)."
    ),
)

from gymact.gyms.tau2_bench import Tau2BenchProvider  # noqa: E402

RETAIL_TASK_0 = "0"
EXCHANGE_CAPABILITY = "urn:gymact:tau2-bench:capability:retail:exchange_delivered_order_items"
FIND_USER_CAPABILITY = "urn:gymact:tau2-bench:capability:retail:find_user_id_by_name_zip"
AUTHORITY = "urn:test:tau2-bench:authority"


def _gym() -> GymAct:
    instance = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    instance.register_provider(Tau2BenchProvider())
    return instance


async def test_materialize_builds_real_retail_domain_and_task() -> None:
    gym_instance = _gym()
    materialized = await gym_instance.materialize(
        MaterializationIntent(
            provider="tau2-bench",
            config={"domain": "retail", "task_id": RETAIL_TASK_0},
        )
    )
    assert materialized.accepted is True
    assert materialized.standing == "ALIVE"
    episode_id = materialized.episode.episode_id

    observation = await gym_instance.observe(episode_id)
    assert observation.state["domain"] == "retail"
    assert observation.state["task_id"] == RETAIL_TASK_0
    # A real retail domain DB really has these top-level real tables.
    assert set(observation.state["db"].keys()) == {"products", "users", "orders"}
    assert observation.state["trajectory"] == []

    await gym_instance.teardown(episode_id)


async def test_capabilities_are_real_tau2_tools_classified_by_real_mutation_flag() -> None:
    gym_instance = _gym()
    materialized = await gym_instance.materialize(
        MaterializationIntent(provider="tau2-bench", config={"domain": "retail"})
    )
    episode_id = materialized.episode.episode_id
    environment = gym_instance._episodes[episode_id].environment  # real materialized world

    capabilities = environment.capabilities()
    by_binding = {c.binding: c for c in capabilities}
    assert "exchange_delivered_order_items" in by_binding
    assert by_binding["exchange_delivered_order_items"].consequence.value == "DO"
    assert "find_user_id_by_name_zip" in by_binding
    assert by_binding["find_user_id_by_name_zip"].consequence.value == "READ"

    await gym_instance.teardown(episode_id)


async def test_read_capability_cannot_be_smuggled_through_actuation() -> None:
    gym_instance = _gym()
    materialized = await gym_instance.materialize(
        MaterializationIntent(
            provider="tau2-bench",
            config={"domain": "retail", "task_id": RETAIL_TASK_0},
        )
    )
    episode_id = materialized.episode.episode_id

    result = await gym_instance.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=FIND_USER_CAPABILITY,
            payload={"first_name": "Yusuf", "last_name": "Rossi", "zip": "19122"},
        )
    )
    assert result.accepted is False
    assert result.receipt.reason == "READ_CAPABILITY_IS_NOT_ACTUATION"

    await gym_instance.teardown(episode_id)


async def test_do_capability_is_fail_closed_without_authority() -> None:
    gym_instance = _gym()
    materialized = await gym_instance.materialize(
        MaterializationIntent(
            provider="tau2-bench",
            config={"domain": "retail", "task_id": RETAIL_TASK_0},
        )
    )
    episode_id = materialized.episode.episode_id

    result = await gym_instance.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=EXCHANGE_CAPABILITY,
            payload={
                "order_id": "#W2378156",
                "item_ids": ["1151293680", "4983901480"],
                "new_item_ids": ["7706410293", "7747408585"],
                "payment_method_id": "credit_card_9513926",
            },
            # No authority_ref: the consequence law is fail-closed by default.
        )
    )
    assert result.accepted is False
    assert result.receipt.reason == "LIVE_AUTHORITY_REQUIRED"

    observation = await gym_instance.observe(episode_id)
    assert observation.state["trajectory"] == []

    await gym_instance.teardown(episode_id)


async def test_real_do_capability_mutates_the_real_domain_db_and_is_receipted() -> None:
    gym_instance = _gym()
    materialized = await gym_instance.materialize(
        MaterializationIntent(
            provider="tau2-bench",
            config={"domain": "retail", "task_id": RETAIL_TASK_0},
        )
    )
    episode_id = materialized.episode.episode_id
    before = await gym_instance.observe(episode_id)
    before_hash = before.state["db_hash"]

    result = await gym_instance.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=EXCHANGE_CAPABILITY,
            payload={
                "order_id": "#W2378156",
                "item_ids": ["1151293680", "4983901480"],
                "new_item_ids": ["7706410293", "7747408585"],
                "payment_method_id": "credit_card_9513926",
            },
            authority_ref=AUTHORITY,
        )
    )
    assert result.accepted is True
    assert result.receipt.operation == Operation.ACT

    after = await gym_instance.observe(episode_id)
    assert after.state["db_hash"] != before_hash
    assert len(after.state["trajectory"]) == 1
    assert after.state["trajectory"][0]["tool"] == "exchange_delivered_order_items"

    await gym_instance.teardown(episode_id)


async def test_verify_replays_real_reference_trajectory_and_matches_real_db_hash() -> None:
    """Task 0's shipped `evaluation_criteria.actions` is exactly the
    sequence this test drives -- so verify() (which internally replays that
    same reference trajectory on a fresh env, per tau2's own
    `RewardType.DB` mechanism) must report a real, LLM-free pass."""
    gym_instance = _gym()
    materialized = await gym_instance.materialize(
        MaterializationIntent(
            provider="tau2-bench",
            config={"domain": "retail", "task_id": RETAIL_TASK_0},
        )
    )
    episode_id = materialized.episode.episode_id

    result = await gym_instance.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=EXCHANGE_CAPABILITY,
            payload={
                "order_id": "#W2378156",
                "item_ids": ["1151293680", "4983901480"],
                "new_item_ids": ["7706410293", "7747408585"],
                "payment_method_id": "credit_card_9513926",
            },
            authority_ref=AUTHORITY,
        )
    )
    assert result.accepted is True

    verification = await gym_instance.verify(episode_id, {})
    assert verification.passed is True
    assert verification.observed["checks"]["db"] is True
    assert (
        verification.observed["db_check"]["reference_hash"]
        == verification.observed["db_check"]["actual_hash"]
    )

    await gym_instance.teardown(episode_id)


async def test_verify_fails_closed_when_task_is_left_unsolved() -> None:
    gym_instance = _gym()
    materialized = await gym_instance.materialize(
        MaterializationIntent(
            provider="tau2-bench",
            config={"domain": "retail", "task_id": RETAIL_TASK_0},
        )
    )
    episode_id = materialized.episode.episode_id

    # No actuation at all: the real domain DB never reaches the reference
    # end state, so verify() must genuinely fail, never a fabricated pass.
    verification = await gym_instance.verify(episode_id, {})
    assert verification.passed is False
    assert verification.observed["checks"]["db"] is False

    await gym_instance.teardown(episode_id)


async def test_unknown_task_id_is_refused_not_silently_substituted() -> None:
    gym_instance = _gym()
    materialized = await gym_instance.materialize(
        MaterializationIntent(
            provider="tau2-bench",
            config={"domain": "retail", "task_id": "not-a-real-task-id"},
        )
    )
    assert materialized.accepted is False


async def test_illegal_tool_call_is_refused_and_does_not_mutate_real_state() -> None:
    gym_instance = _gym()
    materialized = await gym_instance.materialize(
        MaterializationIntent(
            provider="tau2-bench",
            config={"domain": "retail", "task_id": RETAIL_TASK_0},
        )
    )
    episode_id = materialized.episode.episode_id
    before = await gym_instance.observe(episode_id)

    result = await gym_instance.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=EXCHANGE_CAPABILITY,
            # order_id does not exist in the real retail DB -- the real
            # tau2 tool raises; the real Tau2BenchEnvironment must not
            # swallow that into a fabricated success.
            payload={
                "order_id": "#W0000000",
                "item_ids": ["1151293680"],
                "new_item_ids": ["7706410293"],
                "payment_method_id": "credit_card_9513926",
            },
            authority_ref=AUTHORITY,
        )
    )
    assert result.accepted is False

    after = await gym_instance.observe(episode_id)
    assert after.state["db_hash"] == before.state["db_hash"]

    await gym_instance.teardown(episode_id)


@pytest.mark.parametrize("domain", ["retail", "airline"])
async def test_materialize_supports_both_core_domains(domain: str) -> None:
    gym_instance = _gym()
    materialized = await gym_instance.materialize(
        MaterializationIntent(provider="tau2-bench", config={"domain": domain})
    )
    assert materialized.accepted is True
    episode_id = materialized.episode.episode_id
    observation = await gym_instance.observe(episode_id)
    assert observation.state["domain"] == domain
    await gym_instance.teardown(episode_id)
