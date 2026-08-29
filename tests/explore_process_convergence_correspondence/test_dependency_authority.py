from datetime import datetime, timezone
from fractions import Fraction
import unittest
from gymact.explore_process_convergence_correspondence import ActionClass, ClosureEpoch, DependencyGraph, ObligationState, Refused, State, SubjectEpoch, admit

class TestDependencyAuthority(unittest.TestCase):
    def test_red_parent_blocks_and_direct_do_refuses(self) -> None:
        epoch = ClosureEpoch(SubjectEpoch("seanchatmangpt/gymact@" + "a" * 40, 0), datetime(2026, 8, 23, 9, tzinfo=timezone.utc), (ObligationState("parent", State.FAIL, Fraction(1)), ObligationState("child", State.PASS, Fraction(1))))
        self.assertEqual(DependencyGraph({"child": ("parent",)}).blocking_cut(epoch), ("parent",))
        with self.assertRaises(Refused):
            admit(ActionClass.DO)
