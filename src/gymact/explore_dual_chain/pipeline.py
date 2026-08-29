from fractions import Fraction
from .certificate import DualCertificate
from .complementarity import verify_complementarity
from .correspondence import admit_certificate
from .dual import DualPotential
from .feasibility import verify_dual_feasible
from .metric import CostMatrix
from .primal import PrimalPlan
from .strong_duality import verify_strong_duality

def verify(plan: PrimalPlan, dual: DualPotential, metric: CostMatrix, mu: dict[str, Fraction], nu: dict[str, Fraction], cert: DualCertificate) -> str:
    verify_dual_feasible(dual, metric)
    verify_complementarity(plan, dual, metric)
    verify_strong_duality(plan, dual, mu, nu)
    return admit_certificate(cert)
