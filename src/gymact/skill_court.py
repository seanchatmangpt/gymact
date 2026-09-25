"""Bind provenance-qualified collective skills to the existing DCM decision court.

This module consumes the ggen-marketplace court contract as data. It does not own the
contract's semantic source and cannot grant DO authority. A qualified bundle may enter the
existing DCM graph court for bounded exploration only; irreversible selection/execution remain
separate APIs with their existing authority requirements.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import ConfigDict, Field, model_validator

from gymact.dcm_runtime import DCMDecisionCourt, DecisionCourtRecord, DecisionCourtRequest
from gymact.evidence import digest
from gymact.models import FrozenModel, Standing

_CONTENT_DIGEST = r"^(?:sha256|blake3):[0-9a-f]{64}$"
_GIT_SHA = r"^[0-9a-f]{40}$"
EXPECTED_SCHEMA = "collective-skill-court.v1"
EXPECTED_AUTHORITY_CEILING = "OBSERVE|SELECT|CONSTRUCT"
EXPECTED_ADMISSION = "oracle_pass && noop_fail && mutation_rejection && !grants_do_authority"
EXPECTED_PROJECTIONS = {
    "sjira_work_order": "urn:seanchatmangpt:sjira:v1#WorkOrder",
    "sa2a_candidate": "https://spec.autofde.org/sa2a#Candidate",
}
EXPECTED_REQUIREMENTS = {
    "source_provenance",
    "exact_marketplace_pin",
    "exact_subject_pin",
    "replay_identity",
    "oracle_pass",
    "noop_fail",
    "mutation_rejection",
}


class MarketplaceContractBinding(FrozenModel):
    """Exact identity of the marketplace source used to manufacture the contract."""

    repository: Literal["seanchatmangpt/ggen-marketplace"]
    commit_sha: str = Field(pattern=_GIT_SHA)
    pack_name: Literal["collective-skill-court-pack"]
    pack_version: str = Field(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
    contract_digest: str = Field(pattern=_CONTENT_DIGEST)


class SkillCourtContract(FrozenModel):
    """Runtime projection of the marketplace-owned collective-skill contract.

    The marketplace key ``schema`` shadows ``BaseModel.schema``; it is carried as
    ``contract_schema`` under the ``schema`` alias and serialized by alias, so the canonical
    JSON (and therefore the contract digest) keeps the marketplace key.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_by_name=True, validate_by_alias=True
    )

    contract_schema: str = Field(alias="schema")
    authority_ceiling: str
    grants_do_authority: bool
    projections: dict[str, str]
    requires: dict[str, bool]
    admission: str

    @model_validator(mode="after")
    def enforce_marketplace_contract(self) -> Self:
        if self.contract_schema != EXPECTED_SCHEMA:
            raise ValueError("COLLECTIVE_SKILL_SCHEMA_MISMATCH")
        if self.authority_ceiling != EXPECTED_AUTHORITY_CEILING:
            raise ValueError("COLLECTIVE_SKILL_AUTHORITY_CEILING_MISMATCH")
        if self.grants_do_authority:
            raise ValueError("COLLECTIVE_SKILL_AMBIENT_DO_AUTHORITY")
        if self.projections != EXPECTED_PROJECTIONS:
            raise ValueError("COLLECTIVE_SKILL_PROJECTION_MISMATCH")
        if set(self.requires) != EXPECTED_REQUIREMENTS:
            raise ValueError("COLLECTIVE_SKILL_REQUIREMENT_SET_MISMATCH")
        if not all(self.requires.values()):
            raise ValueError("COLLECTIVE_SKILL_REQUIREMENT_WEAKENED")
        if self.admission != EXPECTED_ADMISSION:
            raise ValueError("COLLECTIVE_SKILL_ADMISSION_EXPRESSION_MISMATCH")
        return self


class SkillCourtProbe(FrozenModel):
    """One independently evidenced court probe result."""

    probe_id: str = Field(min_length=1)
    kind: Literal["oracle", "noop", "mutation"]
    observed_success: bool
    evidence_digest: str = Field(pattern=_CONTENT_DIGEST)


class CollectiveSkillCourtBundle(FrozenModel):
    """Provenance-bound input to a GymAct skill court.

    The bundle binds the marketplace contract, the sJira work identity, SA2A candidate/admission
    evidence, the exact world subject, and the discriminating probe observations.
    """

    bundle_id: str = Field(min_length=1)
    marketplace: MarketplaceContractBinding
    contract: SkillCourtContract
    source_skill_digest: str = Field(pattern=_CONTENT_DIGEST)
    source_court_receipt_digest: str = Field(pattern=_CONTENT_DIGEST)
    sjira_work_order_id: str = Field(min_length=1)
    sjira_base_sha: str = Field(pattern=_GIT_SHA)
    sa2a_candidate_digest: str = Field(pattern=_CONTENT_DIGEST)
    sa2a_admission_receipt_digest: str = Field(pattern=_CONTENT_DIGEST)
    exact_subject_sha: str = Field(pattern=_GIT_SHA)
    oracle: SkillCourtProbe
    noop: SkillCourtProbe
    mutations: tuple[SkillCourtProbe, ...]

    @model_validator(mode="after")
    def validate_bundle_identity(self) -> Self:
        expected_contract_digest = "blake3:" + digest(
            self.contract.model_dump(mode="json", by_alias=True)
        )
        if self.marketplace.contract_digest != expected_contract_digest:
            raise ValueError("COLLECTIVE_SKILL_CONTRACT_DIGEST_MISMATCH")
        if self.oracle.kind != "oracle":
            raise ValueError("COLLECTIVE_SKILL_ORACLE_KIND_MISMATCH")
        if self.noop.kind != "noop":
            raise ValueError("COLLECTIVE_SKILL_NOOP_KIND_MISMATCH")
        if not self.mutations:
            raise ValueError("COLLECTIVE_SKILL_MUTATION_PROBE_REQUIRED")
        if any(probe.kind != "mutation" for probe in self.mutations):
            raise ValueError("COLLECTIVE_SKILL_MUTATION_KIND_MISMATCH")
        probe_ids = [
            self.oracle.probe_id,
            self.noop.probe_id,
            *(probe.probe_id for probe in self.mutations),
        ]
        if len(probe_ids) != len(set(probe_ids)):
            raise ValueError("COLLECTIVE_SKILL_DUPLICATE_PROBE_ID")
        return self

    @property
    def bundle_digest(self) -> str:
        return "blake3:" + digest(self.model_dump(mode="json", by_alias=True))


class SkillCourtQualification(FrozenModel):
    """Construct-only admission result for one skill court bundle."""

    bundle_digest: str = Field(pattern=_CONTENT_DIGEST)
    admitted: bool
    standing: Standing
    reasons: tuple[str, ...]
    authority: Literal["none"] = "none"


class SkillBoundDecisionCourtRecord(FrozenModel):
    """DCM exploration evidence bound to the exact skill-court bundle."""

    bundle_digest: str = Field(pattern=_CONTENT_DIGEST)
    qualification: SkillCourtQualification
    decision_court: DecisionCourtRecord


class CollectiveSkillCourtEvaluator:
    """Qualify a collective-skill bundle and bind it to DCM exploration.

    This class exposes no selection or execute method. A successful qualification is evidence
    for bounded court exploration only and cannot cross the existing irreversible-cut/BRCE
    boundary.
    """

    def qualify(self, bundle: CollectiveSkillCourtBundle) -> SkillCourtQualification:
        reasons: list[str] = []
        if not bundle.oracle.observed_success:
            reasons.append("ORACLE_FAILED")
        if bundle.noop.observed_success:
            reasons.append("NOOP_PASSED")
        for mutation in bundle.mutations:
            if mutation.observed_success:
                reasons.append(f"MUTATION_SURVIVED:{mutation.probe_id}")

        admitted = not reasons
        return SkillCourtQualification(
            bundle_digest=bundle.bundle_digest,
            admitted=admitted,
            standing=Standing.STRUCTURAL if admitted else Standing.REFUSED,
            reasons=tuple(reasons) if reasons else ("COURT_CONFORMS",),
        )

    def admit_and_explore(
        self,
        bundle: CollectiveSkillCourtBundle,
        request: DecisionCourtRequest,
    ) -> SkillBoundDecisionCourtRecord:
        qualification = self.qualify(bundle)
        if not qualification.admitted:
            joined = ",".join(qualification.reasons)
            raise ValueError(f"COLLECTIVE_SKILL_COURT_REFUSED:{joined}")
        court = DCMDecisionCourt().admit_request(request)
        return SkillBoundDecisionCourtRecord(
            bundle_digest=bundle.bundle_digest,
            qualification=qualification,
            decision_court=court,
        )
