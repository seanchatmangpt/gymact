"""Unknown outcomes require reconciliation."""
from dataclasses import replace
from .envelope import Envelope
def reconcile(e:Envelope,observed:str|None)->Envelope:
    return replace(e,outcome=observed if observed in {"succeeded","failed"} else "reconcile")
