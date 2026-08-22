import random

def inject_regime_shift(outcomes, *, seed, probability_ppm):
    rng=random.Random(seed); shifted=[]
    for value in outcomes:
        flip=rng.randrange(1_000_000)<probability_ppm
        shifted.append((not value) if flip else value)
    return tuple(shifted)
