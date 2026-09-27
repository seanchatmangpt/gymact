"""Lane-7 smoke: witness whether the prior incarnation's kernel executes at all."""
import sys, traceback
sys.path.insert(0, "/Users/sac/gymact/src")

from gymact.execution_loop import (
    AutonomousLoop, ExecutionRequest, SubjectRef, AuthorityGrant,
    ResourceConstraints, EpisodeStanding, LegalOutcome,
)

class Reg:
    def is_valid(self, grant): return True

class Probe:
    def disk_mb_available(self): return 10_000
    def cpu_cores_available(self): return 8.0

class Verifier:
    def verify(self, subject_after, effect_digest, request): return True, "ok"

class OkProvider:
    capabilities = ["exec"]; transport = "fake:inline"; availability = True
    cost = 0.0; concurrency = 1; authority_ceiling = "DO"; receipt_protocol = "fake"
    def current_subject_sha(self, repo): return "a" * 40
    def resolve_subject(self, repo): return SubjectRef(repo=repo, sha="a" * 40)
    def claim(self, request): from gymact.execution_loop import ClaimPin; return ClaimPin(provider_execution_id="pe-1", pinned_subject_sha="a" * 40)
    def execute(self, request, provider_execution_id):
        return {"effect_digest": "d" * 8, "subject_after_sha": "a" * 40, "actuation_count": 1, "consequence": {"changed": 1}}
    def fetch_receipt(self, provider_execution_id): return None
    def ack(self, receipt): pass

req = ExecutionRequest(
    work_order="WO-SMOKE-1",
    capability_requirements=["exec"],
    subject=SubjectRef(repo="gymact", sha="a" * 40),
    authority=AuthorityGrant(ceiling="DO", grant="lane-7", actor="operator"),
    evidence_requirements=["verifier"],
    resource_constraints=ResourceConstraints(),
)
loop = AutonomousLoop([OkProvider()], Verifier(), Reg(), Probe())
try:
    result = loop.run(req)
    print("RUN OK:", result.outcome, result.standing, "events:", len(result.events))
except Exception as exc:
    print("RUN FAILED:", type(exc).__name__, exc)
    traceback.print_exc()
    sys.exit(3)
