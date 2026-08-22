import unittest
from gymact.explore_invalidation.model import Binding, Refusal, Subject
from gymact.explore_invalidation.renewal import renew

class T(unittest.TestCase):
    def test_schema_drift_refused(self):
        a=Subject("o/a","a"*40); b=Subject("o/b","b"*40); binding=Binding(a,b,"c"*64,"v1","FOCUSED","1")
        with self.assertRaisesRegex(Refusal,"SCHEMA_DRIFT"):
            renew(binding,receipt="d"*64,schema="v2",binding_id="2")
