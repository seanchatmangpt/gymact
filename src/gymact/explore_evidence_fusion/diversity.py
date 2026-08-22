from fractions import Fraction
def inverse_simpson_effective_size(clusters):
    sizes=[len(c) for c in clusters]; n=sum(sizes)
    return Fraction(n*n,sum(s*s for s in sizes)) if n else Fraction(0,1)
def normalized_diversity(clusters):
    n=sum(len(c) for c in clusters)
    return inverse_simpson_effective_size(clusters)/n if n else Fraction(0,1)
