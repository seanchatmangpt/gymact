from .certificate import DualCertificate
from .engine_identity import require_independent
from .refusal import DualChainRefusal

def admit_certificate(cert: DualCertificate) -> str:
    require_independent(cert.primal_engine, cert.verifier_engine)
    if not cert.feasible:
        raise DualChainRefusal("DUAL_INFEASIBLE")
    if not cert.complementary:
        raise DualChainRefusal("COMPLEMENTARITY_VIOLATION")
    if cert.primal_cost != cert.dual_cost:
        raise DualChainRefusal("STRONG_DUALITY_GAP")
    return "ADMITTED_EXACT_PRIMAL_DUAL_CORRESPONDENCE"
