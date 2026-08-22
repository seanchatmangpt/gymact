from .evidence import Evidence
def classify_drift(evidence:Evidence,current_receipt:str,current_schema:str)->str:
    if evidence.receipt!=current_receipt:return 'SUPERSEDED_RECEIPT'
    if evidence.schema!=current_schema:return 'SCHEMA_DRIFT'
    return 'CURRENT'
