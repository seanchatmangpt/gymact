from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import blake3
import rfc8785

from gymact.gyms.cloud_fidelity import (
    CloudFidelityResult,
    CloudTraceStep,
    FidelityDifference,
    JsonPath,
    compare_cloud_traces,
)


@dataclass(frozen=True, slots=True)
class CloudValuePrefixRule:
    """Require one public trace value to retain a provider-visible prefix."""

    path: JsonPath
    prefix: str


@dataclass(frozen=True, slots=True)
class CloudOperationContract:
    """Declarative admission contract for one public cloud operation.

    ``required_paths`` apply to every observed outcome. ``success_required_paths``
    apply only when the provider-visible ``error_code`` is ``None``. Keeping the
    conditions distinct prevents success response schemas from falsely refusing
    legitimate provider-error traces.
    """

    surface: str
    operation: str
    required_paths: tuple[JsonPath, ...] = ()
    success_required_paths: tuple[JsonPath, ...] = ()
    string_prefix_rules: tuple[CloudValuePrefixRule, ...] = ()
    allowed_status_codes: tuple[int | None, ...] = ()
    allowed_error_codes: tuple[str | None, ...] = ()


@dataclass(frozen=True, slots=True)
class CloudContractProfile:
    """Independent provider-contract evidence used to qualify fidelity traces."""

    name: str
    operations: tuple[CloudOperationContract, ...]


@dataclass(frozen=True, slots=True)
class CloudContractReceipt:
    digest: str
    operation_count: int


@dataclass(frozen=True, slots=True)
class CloudContractSource:
    """Content-addressed identity for the source used to author a contract profile."""

    uri: str
    digest: str
    media_type: str


@dataclass(frozen=True, slots=True)
class CloudContractEvidence:
    """Bind a declarative profile to the exact source bytes it claims to represent."""

    profile: CloudContractProfile
    source: CloudContractSource


@dataclass(frozen=True, slots=True)
class CloudContractEvidenceReceipt:
    digest: str
    profile_digest: str
    source_digest: str
    operation_count: int


@dataclass(frozen=True, slots=True)
class CloudContractResult:
    admitted: bool
    checked_steps: int
    differences: tuple[FidelityDifference, ...]


def _path_payload(path: JsonPath) -> list[str | int]:
    return list(path)


def _profile_payload(profile: CloudContractProfile) -> dict[str, Any]:
    operations = []
    for contract in sorted(profile.operations, key=lambda item: (item.surface, item.operation)):
        operations.append(
            {
                "surface": contract.surface,
                "operation": contract.operation,
                "required_paths": sorted(
                    (_path_payload(path) for path in contract.required_paths), key=repr
                ),
                "success_required_paths": sorted(
                    (_path_payload(path) for path in contract.success_required_paths), key=repr
                ),
                "string_prefix_rules": [
                    {"path": _path_payload(rule.path), "prefix": rule.prefix}
                    for rule in sorted(
                        contract.string_prefix_rules,
                        key=lambda rule: (repr(rule.path), rule.prefix),
                    )
                ],
                "allowed_status_codes": sorted(contract.allowed_status_codes, key=repr),
                "allowed_error_codes": sorted(contract.allowed_error_codes, key=repr),
            }
        )
    return {"name": profile.name, "operations": operations}


def receipt_cloud_contract_profile(profile: CloudContractProfile) -> CloudContractReceipt:
    """Bind a declarative contract profile to canonical JSON and BLAKE3."""

    canonical = rfc8785.dumps(_profile_payload(profile))
    return CloudContractReceipt(
        digest=blake3.blake3(canonical).hexdigest(),
        operation_count=len(profile.operations),
    )


def replay_cloud_contract_profile(
    profile: CloudContractProfile, receipt: CloudContractReceipt
) -> bool:
    """Recompute profile identity without granting any execution authority."""

    return receipt_cloud_contract_profile(profile) == receipt


def digest_cloud_contract_source(source_document: bytes) -> str:
    """Content-address exact provider-contract source bytes without fetching them."""

    if not isinstance(source_document, bytes):
        raise TypeError("source_document must be bytes")
    return blake3.blake3(source_document).hexdigest()


def _evidence_payload(evidence: CloudContractEvidence) -> dict[str, Any]:
    profile_receipt = receipt_cloud_contract_profile(evidence.profile)
    return {
        "profile_digest": profile_receipt.digest,
        "operation_count": profile_receipt.operation_count,
        "source": {
            "uri": evidence.source.uri,
            "digest": evidence.source.digest,
            "media_type": evidence.source.media_type,
        },
    }


def receipt_cloud_contract_evidence(
    evidence: CloudContractEvidence,
) -> CloudContractEvidenceReceipt:
    """Bind profile identity and claimed source provenance into one replayable receipt."""

    profile_receipt = receipt_cloud_contract_profile(evidence.profile)
    canonical = rfc8785.dumps(_evidence_payload(evidence))
    return CloudContractEvidenceReceipt(
        digest=blake3.blake3(canonical).hexdigest(),
        profile_digest=profile_receipt.digest,
        source_digest=evidence.source.digest,
        operation_count=profile_receipt.operation_count,
    )


def replay_cloud_contract_evidence(
    evidence: CloudContractEvidence,
    receipt: CloudContractEvidenceReceipt,
) -> bool:
    """Replay evidence identity only; source authority is not implied by receipt equality."""

    return receipt_cloud_contract_evidence(evidence) == receipt


def validate_cloud_contract_source(
    evidence: CloudContractEvidence,
    source_document: bytes,
) -> CloudContractResult:
    """Fail closed unless the supplied source bytes match the declared provenance identity."""

    differences: list[FidelityDifference] = []
    source = evidence.source
    if not source.uri.strip():
        differences.append(
            FidelityDifference(
                None,
                ("contract_source", "uri"),
                "contract_source_uri_missing",
                "non-empty source identity",
                source.uri,
            )
        )
    if not source.media_type.strip():
        differences.append(
            FidelityDifference(
                None,
                ("contract_source", "media_type"),
                "contract_source_media_type_missing",
                "non-empty media type",
                source.media_type,
            )
        )
    actual_digest = digest_cloud_contract_source(source_document)
    if actual_digest != source.digest:
        differences.append(
            FidelityDifference(
                None,
                ("contract_source", "digest"),
                "contract_source_digest_mismatch",
                source.digest,
                actual_digest,
            )
        )
    return CloudContractResult(
        admitted=not differences,
        checked_steps=0,
        differences=tuple(differences),
    )


def _lookup_path(step: CloudTraceStep, path: JsonPath) -> tuple[bool, Any]:
    if not path:
        return False, None

    root = path[0]
    if root not in {"surface", "operation", "request", "response", "status_code", "error_code"}:
        return False, None

    value: Any = getattr(step, root)
    for token in path[1:]:
        if isinstance(token, int):
            if not isinstance(value, list) or token < 0 or token >= len(value):
                return False, None
            value = value[token]
            continue
        if not isinstance(value, dict) or token not in value:
            return False, None
        value = value[token]
    return True, value


def _profile_index(
    profile: CloudContractProfile,
    differences: list[FidelityDifference],
) -> dict[tuple[str, str], CloudOperationContract]:
    index: dict[tuple[str, str], CloudOperationContract] = {}
    for contract in profile.operations:
        identity = (contract.surface, contract.operation)
        if identity in index:
            differences.append(
                FidelityDifference(
                    None,
                    ("contract", contract.surface, contract.operation),
                    "duplicate_contract_operation",
                    "unique surface+operation",
                    identity,
                )
            )
            continue
        index[identity] = contract
    return index


def _validate_required_paths(
    *,
    index: int,
    step: CloudTraceStep,
    paths: Iterable[JsonPath],
    side: str,
    reason: str,
    differences: list[FidelityDifference],
) -> None:
    for path in paths:
        found, _ = _lookup_path(step, path)
        if not found:
            differences.append(
                FidelityDifference(index, path, f"{side}_{reason}", "present", None)
            )


def validate_cloud_trace_contract(
    trace: Iterable[CloudTraceStep],
    profile: CloudContractProfile,
    *,
    side: str = "trace",
) -> CloudContractResult:
    """Fail closed unless every public step is admitted by the independent profile."""

    steps = tuple(trace)
    differences: list[FidelityDifference] = []
    contracts = _profile_index(profile, differences)

    for index, step in enumerate(steps):
        contract = contracts.get((step.surface, step.operation))
        if contract is None:
            differences.append(
                FidelityDifference(
                    index,
                    ("surface", "operation"),
                    f"{side}_contract_operation_unadmitted",
                    tuple(sorted(contracts)),
                    (step.surface, step.operation),
                )
            )
            continue

        _validate_required_paths(
            index=index,
            step=step,
            paths=contract.required_paths,
            side=side,
            reason="contract_missing_required_path",
            differences=differences,
        )
        if step.error_code is None:
            _validate_required_paths(
                index=index,
                step=step,
                paths=contract.success_required_paths,
                side=side,
                reason="contract_missing_success_required_path",
                differences=differences,
            )

        for rule in contract.string_prefix_rules:
            found, value = _lookup_path(step, rule.path)
            if not found or not isinstance(value, str) or not value.startswith(rule.prefix):
                differences.append(
                    FidelityDifference(
                        index,
                        rule.path,
                        f"{side}_contract_prefix_mismatch",
                        rule.prefix,
                        value if found else None,
                    )
                )

        if contract.allowed_status_codes and step.status_code not in contract.allowed_status_codes:
            differences.append(
                FidelityDifference(
                    index,
                    ("status_code",),
                    f"{side}_contract_status_unadmitted",
                    contract.allowed_status_codes,
                    step.status_code,
                )
            )

        if contract.allowed_error_codes and step.error_code not in contract.allowed_error_codes:
            differences.append(
                FidelityDifference(
                    index,
                    ("error_code",),
                    f"{side}_contract_error_unadmitted",
                    contract.allowed_error_codes,
                    step.error_code,
                )
            )

    return CloudContractResult(
        admitted=not differences,
        checked_steps=len(steps),
        differences=tuple(differences),
    )


def compare_cloud_traces_under_contract(
    reference: Iterable[CloudTraceStep],
    twin: Iterable[CloudTraceStep],
    profile: CloudContractProfile,
    **comparison_kwargs: Any,
) -> CloudFidelityResult:
    """Require independent contract admission before accepting trace equivalence."""

    reference_steps = tuple(reference)
    twin_steps = tuple(twin)
    reference_contract = validate_cloud_trace_contract(
        reference_steps, profile, side="reference"
    )
    twin_contract = validate_cloud_trace_contract(twin_steps, profile, side="twin")
    fidelity = compare_cloud_traces(reference_steps, twin_steps, **comparison_kwargs)
    differences = (
        *reference_contract.differences,
        *twin_contract.differences,
        *fidelity.differences,
    )
    return CloudFidelityResult(
        equivalent=not differences,
        compared_steps=fidelity.compared_steps,
        differences=tuple(differences),
    )


def compare_cloud_traces_under_evidence(
    reference: Iterable[CloudTraceStep],
    twin: Iterable[CloudTraceStep],
    evidence: CloudContractEvidence,
    source_document: bytes,
    **comparison_kwargs: Any,
) -> CloudFidelityResult:
    """Require source-bound contract evidence before the ordinary contract/equality courts."""

    reference_steps = tuple(reference)
    twin_steps = tuple(twin)
    source_result = validate_cloud_contract_source(evidence, source_document)
    qualified = compare_cloud_traces_under_contract(
        reference_steps,
        twin_steps,
        evidence.profile,
        **comparison_kwargs,
    )
    differences = (*source_result.differences, *qualified.differences)
    return CloudFidelityResult(
        equivalent=not differences,
        compared_steps=qualified.compared_steps,
        differences=tuple(differences),
    )
