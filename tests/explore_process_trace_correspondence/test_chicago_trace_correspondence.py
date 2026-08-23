import unittest

from gymact.explore_process_trace_correspondence.event import Event
from gymact.explore_process_trace_correspondence.methodology import REQUIRED, require_complete
from gymact.explore_process_trace_correspondence.oracle import OracleWitness
from gymact.explore_process_trace_correspondence.qualification import qualify
from gymact.explore_process_trace_correspondence.receipt import replay
from gymact.explore_process_trace_correspondence.standing import Standing
from gymact.explore_process_trace_correspondence.subject import Subject
from gymact.explore_process_trace_correspondence.trace import Trace


class ChicagoTraceCorrespondenceCourt(unittest.TestCase):
    def test_same_subject_same_trace_caps_at_partial_alive_and_hard_failure_dominates(self):
        subject = Subject("seanchatmangpt/gymact@" + "1" * 40)
        events = (
            Event("discover", "case-1"),
            Event("conform", "case-1"),
            Event("construct", "case-1"),
        )
        beam = Trace(subject, "BEAM", events)
        wasm = Trace(subject, "WASM", events)
        witnesses = (
            OracleWitness("oracle-beam", beam),
            OracleWitness("oracle-wasm", wasm),
        )
        require_complete(REQUIRED)
        good = qualify(beam, wasm, witnesses)
        self.assertEqual(good.standing, Standing.PARTIAL_ALIVE)
        self.assertTrue(replay(good.receipt, good.receipt.digest()))
        broken = qualify(beam, wasm, witnesses, hard_failure=True)
        self.assertEqual(broken.standing, Standing.BUILD_BROKEN)
        self.assertFalse(broken.receipt.actuation_performed)


if __name__ == "__main__":
    unittest.main()
