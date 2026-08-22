from dataclasses import dataclass
import hashlib, json, re
HEX64=re.compile(r"^[0-9a-f]{64}$")
@dataclass(frozen=True)
class EvidenceSource:
    producer: str
    run_id: str
    artifact_digest: str
    family: str
    def __post_init__(self):
        if not self.producer or not self.run_id or not self.family or not HEX64.fullmatch(self.artifact_digest):
            raise ValueError("REFUSED_INVALID_EVIDENCE_SOURCE")
    @property
    def fingerprint(self):
        b=json.dumps({"producer":self.producer,"run":self.run_id,"artifact":self.artifact_digest,"family":self.family},sort_keys=True,separators=(",",":")).encode()
        return hashlib.sha256(b).hexdigest()
