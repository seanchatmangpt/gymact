import os
import tempfile
import unittest

from gymact.explore_train import Lineage
from gymact.explore_train.admission import AdmissionRule, admit
from gymact.explore_train.ahp import normalize
from gymact.explore_train.authority import AuthorityFence
from gymact.explore_train.benchmark import benchmark
from gymact.explore_train.brce import ConstructIntent, require_brce
from gymact.explore_train.compatibility import check
from gymact.explore_train.contracts import CandidateContract
from gymact.explore_train.contradictions import detect
from gymact.explore_train.dependencies import DependencyEdge
from gymact.explore_train.differential import compare
from gymact.explore_train.discovery import discover_capability
from gymact.explore_train.doe import full_factorial
from gymact.explore_train.engine import execute
from gymact.explore_train.failure import FailureInjection
from gymact.explore_train.graph_search import reachable
from gymact.explore_train.meta_selector import SelectionEvidence, choose
from gymact.explore_train.pugh import select
from gymact.explore_train.receipts import Receipt, digest_value
from gymact.explore_train.registry import CandidateRegistry
from gymact.explore_train.replay import replay_matches
from gymact.explore_train.roles import Agent, Authority, Planner, Policy, Role, assert_separated
from gymact.explore_train.runtime import RuntimeCandidate
from gymact.explore_train.semantics import SemanticEdge, canonical_edges
from gymact.explore_train.storage import JsonlStore, MemoryStore
from gymact.explore_train.world import CounterWorld


class ExploreTrainTests(unittest.TestCase):
    def test_lineage_and_identity(self):
        self.assertEqual(Lineage("K", "a" * 40).admitted_parent(), "a" * 40)
        candidate = CandidateContract("a", ("x",))
        self.assertEqual(len(candidate.digest()), 64)

    def test_registry_discovery_collision(self):
        registry = CandidateRegistry()
        candidate = CandidateContract("a", ("x",))
        registry.register(candidate)
        self.assertEqual(discover_capability(registry, "x").candidate_names, ("a",))
        with self.assertRaises(ValueError):
            registry.register(CandidateContract("a", ("y",)))

    def test_admission_authority(self):
        candidate = CandidateContract("a", ("x",))
        self.assertTrue(admit(candidate, AdmissionRule(frozenset({"x"}))).admitted)
        self.assertFalse(admit(candidate, AdmissionRule(frozenset({"y"}))).admitted)
        AuthorityFence().check("VERIFY")
        with self.assertRaises(PermissionError):
            AuthorityFence().check("DO")

    def test_decision_methods(self):
        self.assertEqual(select({"a": {"q": 1}, "b": {"q": 2}}, {"q": 3}).name, "b")
        matrix = {"a": {"a": 1, "b": 2}, "b": {"a": 0.5, "b": 1}}
        self.assertEqual(normalize(matrix)[0].name, "a")
        self.assertEqual(len(full_factorial({"a": (1, 2), "b": ("x", "y")})), 4)

    def test_compare_receipt_replay(self):
        self.assertEqual(compare({"x": 1}, {"x": 2})[0].path, "$.x")
        receipt = Receipt("s", "VERIFY", digest_value({"a": 1}), digest_value({"b": 2}))
        self.assertTrue(replay_matches(receipt, {"a": 1}, {"b": 2}))
        self.assertFalse(replay_matches(receipt, {"a": 2}, {"b": 2}))

    def test_failure_semantics_storage(self):
        with self.assertRaises(RuntimeError):
            FailureInjection("x", 1, "boom").apply(1)
        edge = SemanticEdge("s", "p", "o")
        self.assertEqual(canonical_edges([edge, edge]), (edge,))
        memory = MemoryStore()
        memory.append({"x": 1})
        self.assertEqual(memory.read(), ({"x": 1},))
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "r.jsonl")
            store = JsonlStore(path)
            store.append({"x": 1})
            self.assertEqual(store.read(), ({"x": 1},))

    def test_runtime_roles_brce(self):
        runtime = RuntimeCandidate("inc", lambda payload: {"x": payload["x"] + 1})
        self.assertEqual(runtime.run({"x": 1}), {"x": 2})
        actors = (Planner("p"), Policy("q"), Role("r"), Agent("a"), Authority("z"))
        self.assertTrue(assert_separated(*actors))
        self.assertFalse(ConstructIntent("c", {}).consequential())
        with self.assertRaises(PermissionError):
            require_brce("DO", False)

    def test_dependency_compatibility_world(self):
        edge = DependencyEdge("a", "f" * 40, "b", "c")
        self.assertTrue(edge.pinned())
        self.assertFalse(check({"x", "y"}, {"x"}).compatible)
        world = CounterWorld(2)
        self.assertEqual(world.simulate(world.construct(3)), 5)
        self.assertEqual(world.observe(), 2)

    def test_benchmark_meta_contradiction_graph(self):
        result = benchmark(
            "id",
            lambda case: case,
            ({"x": 1}, {"x": 2}),
            lambda case, observed: case == observed,
        )
        self.assertEqual(result.rate, 1)
        pick = choose(
            (
                SelectionEvidence("a", 1, 1, 2),
                SelectionEvidence("b", 0.9, 1, 0),
            )
        )
        self.assertEqual(pick.name, "b")
        self.assertIsNotNone(detect(({"x": 1}, {"x": 2}), "x"))
        graph = {"a": ("b",), "b": ("c",)}
        self.assertEqual(reachable(graph, "a", "c"), ("a", "b", "c"))

    def test_end_to_end_construct_only(self):
        candidate = CandidateContract("inc", ("transform",))
        runtime = RuntimeCandidate("inc", lambda payload: {"x": payload["x"] + 1})
        rule = AdmissionRule(frozenset({"transform"}))
        outcome = execute(candidate, runtime, {"x": 1}, rule)
        self.assertEqual(outcome.output, {"x": 2})
        self.assertTrue(replay_matches(outcome.receipt, {"x": 1}, {"x": 2}))


if __name__ == "__main__":
    unittest.main()
