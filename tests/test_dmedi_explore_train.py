import os, tempfile, unittest
from gymact.explore_train import Lineage
from gymact.explore_train.contracts import CandidateContract
from gymact.explore_train.registry import CandidateRegistry
from gymact.explore_train.discovery import discover_capability
from gymact.explore_train.admission import AdmissionRule, admit
from gymact.explore_train.authority import AuthorityFence
from gymact.explore_train.pugh import select
from gymact.explore_train.ahp import normalize
from gymact.explore_train.doe import full_factorial
from gymact.explore_train.differential import compare
from gymact.explore_train.receipts import Receipt, digest_value
from gymact.explore_train.replay import replay_matches
from gymact.explore_train.failure import FailureInjection
from gymact.explore_train.semantics import SemanticEdge, canonical_edges
from gymact.explore_train.storage import MemoryStore, JsonlStore
from gymact.explore_train.runtime import RuntimeCandidate
from gymact.explore_train.roles import Planner, Policy, Role, Agent, Authority, assert_separated
from gymact.explore_train.brce import ConstructIntent, require_brce
from gymact.explore_train.dependencies import DependencyEdge
from gymact.explore_train.compatibility import check
from gymact.explore_train.world import CounterWorld
from gymact.explore_train.benchmark import benchmark
from gymact.explore_train.meta_selector import SelectionEvidence, choose
from gymact.explore_train.contradictions import detect
from gymact.explore_train.graph_search import reachable
from gymact.explore_train.engine import execute

class ExploreTrainTests(unittest.TestCase):
    def test_lineage_and_identity(self):
        self.assertEqual(Lineage("K", "a"*40).admitted_parent(), "a"*40)
        c=CandidateContract("a",("x",)); self.assertEqual(len(c.digest()),64)
    def test_registry_discovery_collision(self):
        r=CandidateRegistry(); c=CandidateContract("a",("x",)); r.register(c)
        self.assertEqual(discover_capability(r,"x").candidate_names,("a",))
        with self.assertRaises(ValueError): r.register(CandidateContract("a",("y",)))
    def test_admission_authority(self):
        c=CandidateContract("a",("x",)); self.assertTrue(admit(c,AdmissionRule(frozenset({"x"}))).admitted)
        self.assertFalse(admit(c,AdmissionRule(frozenset({"y"}))).admitted)
        AuthorityFence().check("VERIFY")
        with self.assertRaises(PermissionError): AuthorityFence().check("DO")
    def test_decision_methods(self):
        self.assertEqual(select({"a":{"q":1},"b":{"q":2}},{"q":3}).name,"b")
        self.assertEqual(normalize({"a":{"a":1,"b":2},"b":{"a":.5,"b":1}})[0].name,"a")
        self.assertEqual(len(full_factorial({"a":(1,2),"b":("x","y")})),4)
    def test_compare_receipt_replay(self):
        self.assertEqual(compare({"x":1},{"x":2})[0].path,"$.x")
        r=Receipt("s","VERIFY",digest_value({"a":1}),digest_value({"b":2}))
        self.assertTrue(replay_matches(r,{"a":1},{"b":2}))
        self.assertFalse(replay_matches(r,{"a":2},{"b":2}))
    def test_failure_semantics_storage(self):
        with self.assertRaises(RuntimeError): FailureInjection("x",1,"boom").apply(1)
        e=SemanticEdge("s","p","o"); self.assertEqual(canonical_edges([e,e]),(e,))
        m=MemoryStore(); m.append({"x":1}); self.assertEqual(m.read(),({"x":1},))
        with tempfile.TemporaryDirectory() as d:
            p=os.path.join(d,"r.jsonl"); j=JsonlStore(p); j.append({"x":1}); self.assertEqual(j.read(),({"x":1},))
    def test_runtime_roles_brce(self):
        rt=RuntimeCandidate("inc",lambda p:{"x":p["x"]+1}); self.assertEqual(rt.run({"x":1}),{"x":2})
        self.assertTrue(assert_separated(Planner("p"),Policy("q"),Role("r"),Agent("a"),Authority("z")))
        self.assertFalse(ConstructIntent("c",{}).consequential())
        with self.assertRaises(PermissionError): require_brce("DO",False)
    def test_dependency_compatibility_world(self):
        e=DependencyEdge("a","f"*40,"b","c"); self.assertTrue(e.pinned())
        self.assertFalse(check({"x","y"},{"x"}).compatible)
        w=CounterWorld(2); self.assertEqual(w.simulate(w.construct(3)),5); self.assertEqual(w.observe(),2)
    def test_benchmark_meta_contradiction_graph(self):
        b=benchmark("id",lambda c:c,({"x":1},{"x":2}),lambda c,o:c==o); self.assertEqual(b.rate,1)
        pick=choose((SelectionEvidence("a",1,1,2),SelectionEvidence("b",.9,1,0))); self.assertEqual(pick.name,"b")
        self.assertIsNotNone(detect(({"x":1},{"x":2}),"x"))
        self.assertEqual(reachable({"a":("b",),"b":("c",)},"a","c"),("a","b","c"))
    def test_end_to_end_construct_only(self):
        c=CandidateContract("inc",("transform",)); rt=RuntimeCandidate("inc",lambda p:{"x":p["x"]+1})
        out=execute(c,rt,{"x":1},AdmissionRule(frozenset({"transform"})))
        self.assertEqual(out.output,{"x":2}); self.assertTrue(replay_matches(out.receipt,{"x":1},{"x":2}))

if __name__ == "__main__": unittest.main()
