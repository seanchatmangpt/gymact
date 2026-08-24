from dataclasses import dataclass

from .certificate import Certificate
from .refusal import FederationRefusal
from .runtime import RuntimeProjection


@dataclass(frozen=True)
class RuntimeWitness:
    certificate: Certificate
    runtime: RuntimeProjection


def admit_correspondence(left: RuntimeWitness, right: RuntimeWitness) -> None:
    if left.certificate.subject != right.certificate.subject:
        raise FederationRefusal("SUBJECT_DIVERGENCE")
    if left.runtime.identity == right.runtime.identity:
        raise FederationRefusal("RUNTIME_NOT_DISTINCT")
    if left.certificate.semantic_digest != right.certificate.semantic_digest:
        raise FederationRefusal("SEMANTIC_DIVERGENCE")
    if left.certificate.result_digest != right.certificate.result_digest:
        raise FederationRefusal("RESULT_DIVERGENCE")
