from enum import Enum
from .provenance import ProvenanceGraph
class Relation(str,Enum):
    SAME_EVIDENCE="SAME_EVIDENCE"; CORRELATED="CORRELATED"; INDEPENDENT="INDEPENDENT"; UNKNOWN="UNKNOWN"
def relate(a,b,graph:ProvenanceGraph, explicit_independent=False):
    if a.evidence_id==b.evidence_id or a.source.fingerprint==b.source.fingerprint:
        return Relation.SAME_EVIDENCE
    if explicit_independent:
        return Relation.INDEPENDENT
    if a.source.producer==b.source.producer or a.source.run_id==b.source.run_id or a.source.family==b.source.family:
        return Relation.CORRELATED
    if graph.derives(a.evidence_id,b.evidence_id) or graph.derives(b.evidence_id,a.evidence_id):
        return Relation.CORRELATED
    return Relation.UNKNOWN
