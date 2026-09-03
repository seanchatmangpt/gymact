import unittest

from gymact.explore_rail_consensus.attribution import AttributionEdge, AttributionGraph
from gymact.explore_rail_consensus.signature import FailureSignature
from gymact.explore_rail_consensus.subject import Refusal


class AttributionTest(unittest.TestCase):
    def test_closed_graph_and_dangling_refusal(self):
        signature = FailureSignature.from_failure("collect", "E", "duplicate module")
        AttributionGraph(
            (signature,), (AttributionEdge(signature.digest, "tests/x", "trace", "exact-log"),)
        ).admit_closed()
        with self.assertRaisesRegex(Refusal, "REFUSED_DANGLING"):
            AttributionGraph((signature,), (AttributionEdge("bad", "x", "e", "b"),)).admit_closed()
