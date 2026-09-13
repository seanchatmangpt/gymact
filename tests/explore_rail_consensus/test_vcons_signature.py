import unittest

from gymact.explore_rail_consensus.signature import FailureSignature


class SignatureTest(unittest.TestCase):
    def test_volatile_fields_normalize(self):
        left = FailureSignature.from_failure("collect", "E", "path /home/runner/work/a/b id 123456")
        right = FailureSignature.from_failure(
            "collect", "E", "path /home/runner/work/x/y id 987654"
        )
        self.assertEqual(left.digest, right.digest)
