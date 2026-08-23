from .receipt import Receipt
from .refusals import Refused
def replay(receipt:Receipt,expected_digest:str)->str:
    if receipt.actuation_performed:raise Refused('REPORTED_ACTUATION')
    if receipt.digest()!=expected_digest:raise Refused('RECEIPT_DRIFT')
    return 'REPLAY_MATCH'
