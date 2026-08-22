import unittest
from gymact.explore_invalidation.model import Binding, Refusal, Subject

class T(unittest.TestCase):
    def test_binding_contract(self):
        s=Subject("o/r","a"*40); c=Subject("o/c","b"*40)
        Binding(s,c,"c"*64,"v1","REPOSITORY","b1")
        with self.assertRaisesRegex(Refusal,"MALFORMED_BINDING"):
            Binding(s,c,"x","v1","REPOSITORY","b1")
