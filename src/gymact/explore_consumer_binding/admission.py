from datetime import datetime
from .claim import ConsumptionClaim
from .evidence import Evidence
from .lease import EvidenceLease
from .scope import scope_satisfies
def admit(claim:ConsumptionClaim,evidence:Evidence,lease:EvidenceLease,now:datetime,current_receipt:str,current_schema:str)->str:
    if claim.producer!=evidence.subject: raise ValueError('REFUSED_FOREIGN_PRODUCER')
    if claim.receipt!=evidence.receipt: raise ValueError('REFUSED_RECEIPT_MISMATCH')
    if evidence.receipt!=current_receipt: raise ValueError('REFUSED_SUPERSEDED_RECEIPT')
    if evidence.schema!=current_schema: raise ValueError('REFUSED_SCHEMA_DRIFT')
    if not lease.contains(now): raise ValueError('REFUSED_LEASE_NOT_CURRENT')
    if not scope_satisfies(evidence.scope,claim.required_scope): raise ValueError('REFUSED_SCOPE_INSUFFICIENT')
    return 'ADMITTED'
