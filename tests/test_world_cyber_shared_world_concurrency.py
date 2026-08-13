"""Concurrent actuations on the same shared world must not lose a committed
effect.

`SharedDependencyWorldEnvironment` composes through `DependencyWorldEnvironment`'s
own `checkpoint()`/`restore()` contract under a per-world lock. That lock must
genuinely exclude concurrent coroutines sharing one `world_id` -- a
`threading.RLock` held across `await` points does not, because its
reentrancy is thread-scoped, not task-scoped, so a second concurrently
scheduled `asyncio` task can "recursively" acquire it while the first task is
still suspended inside the critical section. That silently drops a receipted
actuation's effect from the shared world -- exactly the `request accepted !=
world changed` collapse this repo's consequence law forbids -- with no
refusal, no error, no evidence of the collision.
"""

from __future__ import annotations

import asyncio

from gymact.gyms.world_cyber import build_world_cyber_provider


def run(coro):
    return asyncio.run(coro)


def test_concurrent_actuations_on_one_shared_world_do_not_lose_an_effect() -> None:
    async def scenario() -> None:
        provider = build_world_cyber_provider()
        world_id = "concurrency-regression"
        red = await provider.materialize(
            scenario=None,
            config={"actor": "red", "world_id": world_id, "requires_authority": False},
        )
        blue = await provider.materialize(
            scenario=None,
            config={"actor": "blue", "world_id": world_id, "requires_authority": False},
        )
        observer = await provider.materialize(
            scenario=None,
            config={"actor": "observer", "world_id": world_id, "requires_authority": False},
        )

        red_cap = next(cap for cap in red.capabilities() if cap.binding == "degrade-service")
        blue_cap = next(cap for cap in blue.capabilities() if cap.binding == "failover-service")

        async def actuate_with_widened_race_window(env, capability, target):
            # Widen the window between load and save so two concurrently
            # scheduled tasks are certain to interleave if the lock does not
            # genuinely exclude them.
            original_save = env._save

            async def delayed_save() -> None:
                await asyncio.sleep(0.02)
                await original_save()

            env._save = delayed_save
            return await env.actuate(capability, {"target": target})

        red_effect, blue_effect = await asyncio.gather(
            actuate_with_widened_race_window(red, red_cap, "cloud-control"),
            actuate_with_widened_race_window(blue, blue_cap, "cloud-control"),
        )

        # Both actuations were admitted individually (each returned a normal
        # effect dict a caller would receipt) -- so a serialized world must
        # reflect both step transitions, not silently collapse to one.
        steps = sorted((red_effect["before_step"], red_effect["after_step"]))
        steps += sorted((blue_effect["before_step"], blue_effect["after_step"]))
        assert sorted(steps) == [0, 1, 1, 2]

        truth = await observer.observe()
        assert truth["world_step"] == 2

        await red.teardown()
        await blue.teardown()
        await observer.teardown()

    run(scenario())
