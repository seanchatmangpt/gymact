import unittest

from gymact.explore_replicated_projection_quorum.admission import admit_observations
from gymact.explore_replicated_projection_quorum.refusal import Refused

from .world import NOW, SEMANTIC, SUBJECT, UNIVERSE, WINDOW, projection


class AdmissionCourt(unittest.TestCase):
    def test_duplicate_replica_cannot_inflate_evidence(self):
        with self.assertRaisesRegex(Refused, "REFUSED_DUPLICATE_REPLICA_OBSERVATION"):
            admit_observations(
                (projection("r1"), projection("r1")),
                subject=SUBJECT,
                semantic_digest=SEMANTIC,
                universe=UNIVERSE,
                window=WINDOW,
                now=NOW,
            )


if __name__ == "__main__":
    unittest.main()
