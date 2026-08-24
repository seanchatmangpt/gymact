from .certificate import Certificate
from .refusal import FederationRefusal


def current_frontier(certificates: tuple[Certificate, ...]) -> tuple[Certificate, ...]:
    if not certificates:
        raise FederationRefusal("EMPTY_CERTIFICATE_SET")
    generation = max(c.generation for c in certificates)
    current = tuple(c for c in certificates if c.generation == generation)
    semantic = {c.semantic_digest for c in current}
    if len(semantic) != 1:
        raise FederationRefusal("DIVERGENT_CURRENT_SEMANTICS")
    return current
