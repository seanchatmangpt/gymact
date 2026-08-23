from __future__ import annotations

from dataclasses import dataclass

from .refusal import REFUSED_UNPROVEN_INDEPENDENCE, Refused


@dataclass(frozen=True, slots=True)
class IndependenceProof:
    left_model: str
    right_model: str
    left_implementation: str
    right_implementation: str
    proof_digest: str

    def require(self) -> None:
        shared_model = self.left_model == self.right_model
        shared_implementation = self.left_implementation == self.right_implementation
        if shared_model or shared_implementation:
            raise Refused(
                REFUSED_UNPROVEN_INDEPENDENCE,
                "shared model or implementation",
            )
        if len(self.proof_digest) != 64:
            raise Refused(REFUSED_UNPROVEN_INDEPENDENCE, "invalid proof digest")
