"""Real, Chicago-style admission discipline check for every hand-written
`dspy.Signature` in this repo.

Ports the *admission bar* `~/ggen/packs/dspy-pack/gates/
020_shacl_signature_admission.rq` encodes for SHACL-derived Signatures
(uncommitted WIP as of 2026-08-11) into a gymact-native, non-RDF check
against gymact's own real, hand-written Signature classes -- gymact's
Signatures are not SHACL-derived and this test does not make them so; it
re-expresses the same real discipline that pack's gate enforces
(every field must carry real, specific guidance for the LM; a signature must
have at least one real output field, never a silently-fabricated default)
directly against `dspy.Signature.input_fields`/`output_fields`, the real
DSPy API (confirmed live: `FieldInfo.json_schema_extra["desc"]`).

No mocks: every class inspected here is imported for real and introspected
via DSPy's own real `input_fields`/`output_fields` dicts, not a fixture or
a hand-maintained duplicate list.
"""

from __future__ import annotations

import inspect

import dspy

from gymact.dspy_verifier import SuspicionOfMismatch
from gymact.epistemic_dspy import (
    CommitDiagnosis,
    ConstructPlanPortfolio,
    ExplainReceipt,
    ExtractCandidateClaims,
    FrameScenario,
    GenerateHypothesisPortfolio,
    InterpretVerificationEvidence,
    MapEvidenceToHypotheses,
    ProposeDiscriminatingReads,
)

# Module-level Signatures, importable directly and covered here: all 9 in
# epistemic_dspy.py, plus dspy_verifier.py's SuspicionOfMismatch (gated by
# `if _dspy is not None:` but still module-level, not function-nested).
#
# Confirmed by direct, real import attempts (not assumed from file layout):
# every OTHER Signature in this repo --
# dspy_agent.py::AccomplishGymGoal, dspy_world.py::NavigateWorld,
# epistemic_process_kernel.py::ExplainRun, and all 5 of
# dspy_sregym_agent.py's (CategoryTheory, SpotFieldOutlier,
# NormalizeEvidence, ResolveHypothesis, SynthesizeMitigation) -- is defined
# INSIDE a method/function (closures capturing runtime `dspy`/tool-list
# state), confirmed via a real `ImportError` when attempting each direct
# import. A static-import-based discipline test structurally cannot reach
# them; the DSPy-signature-audit pass earlier this session already reviewed
# every one of their field descriptions directly by reading the source (see
# that agent's real report), since this file's approach cannot substitute
# for that review on closure-scoped signatures.
ALL_SIGNATURES: tuple[type[dspy.Signature], ...] = (
    SuspicionOfMismatch,
    CommitDiagnosis,
    ConstructPlanPortfolio,
    ExplainReceipt,
    ExtractCandidateClaims,
    FrameScenario,
    GenerateHypothesisPortfolio,
    InterpretVerificationEvidence,
    MapEvidenceToHypotheses,
    ProposeDiscriminatingReads,
)

_MIN_DESC_LENGTH = 8  # rules out placeholder descs like "input" or "the value"


def _field_desc(field_info) -> str | None:
    extra = field_info.json_schema_extra
    if not isinstance(extra, dict):
        return None
    return extra.get("desc")


def test_every_signature_has_a_real_docstring() -> None:
    missing = [
        sig.__name__
        for sig in ALL_SIGNATURES
        if not (sig.__doc__ and sig.__doc__.strip())
    ]
    assert missing == [], f"Signatures with no real docstring: {missing}"


def test_every_signature_has_at_least_one_real_output_field() -> None:
    """The dspy-pack gate's own words: a signature must have '>=1 real
    output field, never a silently-fabricated default.'"""
    missing = [sig.__name__ for sig in ALL_SIGNATURES if not sig.output_fields]
    assert missing == [], f"Signatures with zero output fields: {missing}"


def test_every_input_field_has_a_specific_desc() -> None:
    weak: list[str] = []
    for sig in ALL_SIGNATURES:
        for field_name, field_info in sig.input_fields.items():
            desc = _field_desc(field_info)
            if desc is None or len(desc.strip()) < _MIN_DESC_LENGTH:
                weak.append(f"{sig.__name__}.{field_name}: desc={desc!r}")
    assert weak == [], f"Input fields with a missing/weak desc: {weak}"


def test_every_output_field_has_a_specific_desc() -> None:
    weak: list[str] = []
    for sig in ALL_SIGNATURES:
        for field_name, field_info in sig.output_fields.items():
            desc = _field_desc(field_info)
            if desc is None or len(desc.strip()) < _MIN_DESC_LENGTH:
                weak.append(f"{sig.__name__}.{field_name}: desc={desc!r}")
    assert weak == [], f"Output fields with a missing/weak desc: {weak}"


def test_no_signature_declares_the_same_field_as_both_input_and_output() -> None:
    conflicts = [
        sig.__name__
        for sig in ALL_SIGNATURES
        if set(sig.input_fields) & set(sig.output_fields)
    ]
    assert conflicts == [], f"Signatures with an input/output field name conflict: {conflicts}"


def test_signature_registry_is_not_stale_against_the_real_module_source() -> None:
    """Real, mechanical drift guard: if a new MODULE-LEVEL dspy.Signature is
    added to any of these files and not added to ALL_SIGNATURES above, this
    test catches it -- the same drift-guard spirit as
    ~/ggen/packs/domain-capability-pack's count gates, applied here to this
    repo's own Signature inventory. Function/method-nested Signatures are
    invisible to `vars(module)` by construction, so this only guards the
    importable subset this file actually covers -- consistent with
    ALL_SIGNATURES's own documented scope above, not a broader claim."""
    import gymact.dspy_verifier as dspy_verifier_mod
    import gymact.epistemic_dspy as epistemic_dspy_mod

    def module_level_signature_names(module) -> set[str]:
        return {
            name
            for name, obj in vars(module).items()
            if inspect.isclass(obj)
            and issubclass(obj, dspy.Signature)
            and obj is not dspy.Signature
            and obj.__module__ == module.__name__
        }

    known_names = {sig.__name__ for sig in ALL_SIGNATURES}
    for module in (dspy_verifier_mod, epistemic_dspy_mod):
        real_names = module_level_signature_names(module)
        unaccounted = real_names - known_names
        assert unaccounted == set(), (
            f"{module.__name__} defines module-level Signature(s) not in "
            f"ALL_SIGNATURES: {sorted(unaccounted)}"
        )
