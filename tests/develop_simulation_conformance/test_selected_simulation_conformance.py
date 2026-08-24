from gymact.develop_simulation_conformance.calibration import calibrate
from gymact.develop_simulation_conformance.currentness import Generation, current
from gymact.develop_simulation_conformance.idempotency import IdempotencyRecord, admit
from gymact.develop_simulation_conformance.partial_order import normalize
from gymact.develop_simulation_conformance.provider_oracle import ProviderResult, require_differential_equivalence
from gymact.develop_simulation_conformance.qualification import qualify


def test_selected_simulation_conformance_closure():
    admit([IdempotencyRecord("k", "a" * 64, "b" * 64), IdempotencyRecord("k", "a" * 64, "b" * 64)])
    assert normalize(["a", "b", "c"], [("a", "c"), ("b", "c")])[-1] == "c"
    cal = calibrate([0.5, 0.7, 0.2], [0.5, 0.6, 0.3])
    results = [ProviderResult("p1", "i1", "s", "r"), ProviderResult("p2", "i2", "s", "r")]
    assert require_differential_equivalence(results)
    assert current([Generation(1, "s"), Generation(2, "t")]).generation == 2
    assert qualify(cal.rmse, 2, []).standing == "PARTIAL_ALIVE"
    assert qualify(cal.rmse, 2, ["BUILD_BROKEN"]).standing == "BUILD_BROKEN"
