from gymact.explore_ack_identity import Subject
from gymact.explore_ack_simulator import FailurePlan, simulate


def test_failure_simulation_replays_deterministically():
    consumers = (
        Subject("o/a", "a" * 40, "consumer"),
        Subject("o/b", "b" * 40, "consumer"),
    )
    plan = FailurePlan(42, 0.35, 2)
    assert simulate("evt", consumers, plan) == simulate("evt", consumers, plan)
