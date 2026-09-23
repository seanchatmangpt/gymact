import unittest

from gymact.explore_semantic_projection_currentness.currentness import ProjectionEpoch
from gymact.explore_semantic_projection_currentness.engine import construct_plan
from gymact.explore_semantic_projection_currentness.selectors import SelectorKind
from gymact.explore_semantic_projection_currentness.storage import StorageKind
from gymact.explore_semantic_projection_currentness.subject import Refusal, Subject
from tests.explore_semantic_projection_currentness._fixtures import DIGEST, SHA, fixtures


class Court(unittest.TestCase):
    def test_chicago_projection_frontier_constructs_no_do_receipt(self):
        semantic_type, rdf, ash, wasm, _, ash_witness, wasm_witness = fixtures()
        subject = Subject("seanchatmangpt/gymact", SHA)
        epoch = ProjectionEpoch(subject, 7, DIGEST, "b" * 64)
        plan = construct_plan(
            subject=subject,
            semantic_type=semantic_type,
            candidates=(rdf, ash, wasm),
            witnesses=(ash_witness, wasm_witness),
            epoch=epoch,
            selector=SelectorKind.MINIMAX_REGRET,
            durable=True,
            transactional=True,
        )
        self.assertGreaterEqual(len(plan.pareto), 1)
        self.assertEqual(plan.storage.kind, StorageKind.SQLITE)
        self.assertFalse(plan.receipt.actuation_performed)
        self.assertTrue(plan.receipt.replay(plan.receipt.digest))
        with self.assertRaisesRegex(Refusal, "REFUSED_UNRECEIPTED_ACTUATION"):
            construct_plan(
                subject=subject,
                semantic_type=semantic_type,
                candidates=(rdf, ash),
                witnesses=(ash_witness,),
                epoch=epoch,
                selector=SelectorKind.MAX_FIDELITY,
                action="DO",
            )


if __name__ == "__main__":
    unittest.main()
