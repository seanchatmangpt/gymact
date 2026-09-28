"""Edge-local recovery."""
def recover(edges:tuple[str,...],failed:frozenset[str])->str|None:return next((e for e in edges if e not in failed),None)
def exclude(failed:frozenset[str],edge:str)->frozenset[str]:return failed|{edge}
