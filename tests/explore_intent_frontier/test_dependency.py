import unittest
from gymact.explore_intent_frontier.dependency import DependencyEdge,propagate_blockers,topological
from gymact.explore_intent_frontier.subject import Subject
class TestDependency(unittest.TestCase):
    def test_order_cycle_and_blocker_propagation(self):
        a,b=Subject("a/a","1"*40),Subject("a/b","2"*40); e=DependencyEdge(a,b)
        order=topological((b,a),(e,)); self.assertEqual(order,(a,b))
        out=propagate_blockers(order,(e,),{a.identity:"BUILD_BROKEN",b.identity:"PARTIAL_ALIVE"})
        self.assertEqual(out[b.identity],"BLOCKED")
        with self.assertRaisesRegex(ValueError,"REFUSED_DEPENDENCY_CYCLE"):
            topological((a,b),(e,DependencyEdge(b,a)))
if __name__=="__main__": unittest.main()
