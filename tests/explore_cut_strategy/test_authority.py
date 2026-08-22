import unittest
from gymact.explore_cut_strategy.authority import ActionClass,require
class T(unittest.TestCase):
    def test_do_refused(self):
        require(ActionClass.CONSTRUCT)
        with self.assertRaisesRegex(PermissionError,"REFUSED_UNRECEIPTED_ACTUATION"):
            require(ActionClass.DO)
