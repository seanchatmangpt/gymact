from itertools import product

def full_factorial(factors:dict[str,tuple])->tuple[dict,...]:
    keys=tuple(sorted(factors))
    return tuple(dict(zip(keys,vals)) for vals in product(*(factors[k] for k in keys)))
