from dataclasses import asdict, dataclass
import hashlib, json

@dataclass(frozen=True)
class QualificationReceipt:
    subject: str
    cut_id: str
    strategy: str
    store: str
    standing: str
    actuation_performed: bool=False

    def __post_init__(self) -> None:
        if self.actuation_performed:
            raise ValueError("REFUSED_RECEIPT_ACTUATION")

    def digest(self) -> str:
        payload=json.dumps(asdict(self),sort_keys=True,separators=(",",":"))
        return hashlib.sha256(payload.encode()).hexdigest()

def replay(receipt: QualificationReceipt, digest: str) -> bool:
    return receipt.digest() == digest and not receipt.actuation_performed
