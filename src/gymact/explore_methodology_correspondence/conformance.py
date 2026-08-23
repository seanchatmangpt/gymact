from fractions import Fraction

def conformance(observed: tuple[str,...], expected: tuple[str,...]) -> Fraction:
    if not expected: return Fraction(int(not observed),1)
    matched=sum(1 for i,a in enumerate(observed[:len(expected)]) if a==expected[i])
    return Fraction(matched,len(expected))
