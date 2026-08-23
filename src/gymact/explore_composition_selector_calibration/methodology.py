from .refusals import Refused
REQUIRED=frozenset({'discovery','conformance','simulation','prediction','optimization','intervention','monitoring','event-centric','object-centric','declarative','procedural'})
def require_closure(observed:frozenset[str])->None:
    missing=REQUIRED-observed
    if missing: raise Refused('INCOMPLETE_METHODOLOGY',','.join(sorted(missing)))
