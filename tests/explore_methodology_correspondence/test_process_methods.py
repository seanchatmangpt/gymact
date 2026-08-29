import unittest
from fractions import Fraction
from gymact.explore_methodology_correspondence.discovery import directly_follows
from gymact.explore_methodology_correspondence.conformance import conformance
from gymact.explore_methodology_correspondence.simulation import simulate
from gymact.explore_methodology_correspondence.prediction import predict_next

class TestProcessMethods(unittest.TestCase):
    def test_method_family(self):
        traces=(('A','B'),('A','C'))
        self.assertEqual(directly_follows(traces),{('A','B'):1,('A','C'):1})
        self.assertEqual(conformance(('A','B'),('A','B')),Fraction(1,1))
        self.assertEqual(simulate('s',{'s':'A'},{('s','A'):'e'}).terminal,'e')
        self.assertEqual(predict_next(traces,('A',))[1],1)
