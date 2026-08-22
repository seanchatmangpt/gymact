import unittest
from datetime import datetime, timezone, timedelta
from gymact.explore_federation.subject import Subject
from gymact.explore_federation.window import Window
from gymact.explore_federation.observation import Observation
from gymact.explore_federation.admission import admit
from gymact.explore_federation.standing import standing
from gymact.explore_federation.delta import diff
from gymact.explore_federation.lineage import Lineage, admit_lineage
from gymact.explore_federation.capability import Candidate, discover
from gymact.explore_federation.compatibility import compatible
from gymact.explore_federation.dependency import topo
from gymact.explore_federation.pareto import frontier
from gymact.explore_federation.pugh import rank
from gymact.explore_federation.ahp import geometric_priority
from gymact.explore_federation.doe import full_factorial
from gymact.explore_federation.runtime import execute
from gymact.explore_federation.storage import MemoryStore, encode_jsonl
from gymact.explore_federation.failure import inject
from gymact.explore_federation.compare import compare
from gymact.explore_federation.contradiction import detect
from gymact.explore_federation.authority import require
from gymact.explore_federation.receipt import make
from gymact.explore_federation.replay import verify
from gymact.explore_federation.selector import select
from gymact.explore_federation.engine import construct

SHA="a"*40
class TestFederation(unittest.TestCase):
  def test_subject_window_admission(self):
    s=Subject("o/r",SHA,"main"); now=datetime.now(timezone.utc); w=Window(now-timedelta(seconds=1),now+timedelta(seconds=1))
    o=Observation(s,"ci","PASS",now); self.assertEqual(admit([o],SHA,w),(o,)); self.assertEqual(standing(["PASS"]),"PARTIAL_ALIVE")
  def test_delta_lineage(self):
    self.assertTrue(diff({"a":1},{"a":2})[0].changed)
    self.assertEqual(admit_lineage(Lineage(1,SHA,"b","open",True)).predecessor_pr,1)
  def test_candidate_dependency(self):
    cs=[Candidate("b",frozenset({"x"})),Candidate("a",frozenset({"x","y"}))]
    self.assertEqual([c.id for c in discover(cs,{"x","y"})],["a"]); self.assertTrue(compatible({"x"},{"x","y"})); self.assertEqual(topo({"a":{"b"},"b":set()}),("b","a"))
  def test_selection_math(self):
    self.assertEqual(frontier({"a":(1,2),"b":(2,1),"c":(0,0)}),("a","b"))
    self.assertEqual(rank({"a":{"q":1},"b":{"q":2}},{"q":1})[0][0],"b")
    self.assertEqual(geometric_priority({"a":(1,1),"b":(2,2)})[0][0],"b")
    self.assertEqual(len(full_factorial({"a":(1,2),"b":(3,4)})),4)
  def test_runtime_storage_failure(self):
    self.assertEqual(execute("dict",lambda p:p["x"]+1,{"x":1}).value,2)
    m=MemoryStore();m.append({"b":2,"a":1});self.assertEqual(m.replay()[0]["a"],1);self.assertIn('"a":1',encode_jsonl([{"b":2,"a":1}]))
    with self.assertRaises(RuntimeError): inject(1,fail=True)
  def test_compare_contradiction(self):
    self.assertEqual(compare({"a":1},{"a":2}),("$.a",)); self.assertEqual(len(detect([("ci","PASS"),("ci","FAIL")])),1)
  def test_authority_receipt_replay(self):
    self.assertEqual(require("CONSTRUCT"),"CONSTRUCT")
    with self.assertRaises(PermissionError): require("DO")
    r=make({"x":1}); self.assertTrue(verify(r)); r["body"]["payload"]["x"]=2
    with self.assertRaises(ValueError): verify(r)
  def test_selector_engine(self):
    winner,alts=select({"a":(1,2),"b":(2,1)}); self.assertIn(winner,alts)
    out=construct({"a":(1,2),"b":(2,1)}); self.assertFalse(out["receipt"]["body"]["actuation_performed"])
if __name__=="__main__": unittest.main()
