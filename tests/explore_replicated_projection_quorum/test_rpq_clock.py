import unittest

from gymact.explore_replicated_projection_quorum.clock import ClockRelation, VectorClock

class ClockCourt(unittest.TestCase):
    def test_partial_order_and_join(self):
        a = VectorClock.from_dict({"a": 1, "b": 0})
        b = VectorClock.from_dict({"a": 2, "b": 0})
        c = VectorClock.from_dict({"a": 1, "b": 1})
        self.assertIs(a.compare(b), ClockRelation.BEFORE)
        self.assertIs(b.compare(c), ClockRelation.CONCURRENT)
        self.assertEqual(b.join(c).as_dict(), {"a": 2, "b": 1})

if __name__ == "__main__":
    unittest.main()
