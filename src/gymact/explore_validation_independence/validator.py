from dataclasses import dataclass

from .provenance import Provenance
from .refusal import Refused


@dataclass(frozen=True)
class ValidatorWitness:
    validator_id: str
    provenance: Provenance
    oracle_digest: str

    def require_independent(self, other: "ValidatorWitness") -> None:
        if self.validator_id == other.validator_id or self.oracle_digest == other.oracle_digest:
            raise Refused("VALIDATOR_ALIAS")
        self.provenance.require_distinct(other.provenance)
