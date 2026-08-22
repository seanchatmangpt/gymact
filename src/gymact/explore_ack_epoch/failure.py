import random
def failure_plan(consumers:list[str], seed:int, probability:float)->dict[str,bool]:
    if not 0<=probability<=1: raise ValueError("REFUSED[INVALID_FAILURE_PROBABILITY]")
    r=random.Random(seed)
    return {c:r.random()<probability for c in sorted(consumers)}
