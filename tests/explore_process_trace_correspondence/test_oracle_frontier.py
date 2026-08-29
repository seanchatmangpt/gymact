import unittest

from gymact.explore_process_trace_correspondence.event import Event
from gymact.explore_process_trace_correspondence.frontier import Candidate, pareto
from gymact.explore_process_trace_correspondence.oracle import OracleWitness, require_independent
from gymact.explore_process_trace_correspondence.refusal import Refused
from gymact.explore_process_trace_correspondence.subject import Subject
from gymact.explore_process_trace_correspondence.trace import Trace


class OracleFrontierCourt(unittest.TestCase):
    def test_independence_and_nondominance(self):
        subject = Subject("owner/repo@" + "e" * 40)
        trace = Trace(subject, "BEAM", (Event("A", "o"),))
        with self.assertRaises(Refused):
            require_independent((OracleWitness("impl-a", trace), OracleWitness("impl-a", trace)))
        require_independent((OracleWitness("impl-a", trace), OracleWitness("impl-b", trace)))
        strong = Candidate("strong", 1, 1, 1.0, 2)
        weak = Candidate("weak", 0, 1, 0.5, 3)
        self.assertEqual(pareto((weak, strong)), (strong,))


if __name__ == "__main__":
    unittest.main()
