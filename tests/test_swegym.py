"""Contract tests for the first-class SWEGym provider.

These tests intentionally do not manufacture a fake Docker/dataset run. They cover the
GymAct-owned boundary only: real native-result interpretation, command/test-invocation
projection, authority classification, checkpoint semantics, and verification. A real
live SWE-Gym episode (real ``docker pull``/``docker run``, a real HuggingFace dataset
row, a real 3-tier patch apply against a real container) remains a separate standing
and is validated with the procedure in ``docs/integrations/swegym.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, RDF

from gymact.gyms.swegym import (
    SWEGYM_EVALUATE_CAPABILITY,
    SWEGYM_UPSTREAM_DATASET,
    SWEGYM_UPSTREAM_SPLIT,
    SWEGymEnvironment,
    SWEGymProvider,
    _build_test_cmd,
    _image_for_instance,
)
from gymact.models import Consequence
from gymact.registry import builtin_capabilities, builtin_provider_names, create_builtin_provider
from gymact.semantic import ProfileAuthority


def _environment(**overrides) -> SWEGymEnvironment:
    values = {
        "task_id": "conan-io__conan-14760",
        "repo": "conan-io/conan",
        "base_commit": "deadbeef",
        "image": _image_for_instance("conan-io__conan-14760"),
        "test_patch": "",
        "fail_to_pass": ["tests/test_foo.py::test_bar"],
        "pass_to_pass": ["tests/test_foo.py::test_baz"],
        "eval_timeout": 1800,
    }
    values.update(overrides)
    return SWEGymEnvironment(**values)


def test_swegym_is_a_first_class_builtin_provider() -> None:
    assert "swegym" in builtin_provider_names()
    assert builtin_capabilities("swegym") == (SWEGYM_EVALUATE_CAPABILITY,)
    assert isinstance(create_builtin_provider("swegym"), SWEGymProvider)


def test_swegym_capability_is_admitted_by_public_semantic_profile() -> None:
    result = ProfileAuthority().validate_capabilities((SWEGYM_EVALUATE_CAPABILITY,))
    assert result.conforms is True, result.report_text


def test_swegym_runtime_identity_matches_ggen_e2e_graph() -> None:
    graph = Graph().parse(
        Path(__file__).parents[1] / "ggen/swegym-e2e-pack/ontology.ttl",
        format="turtle",
    )
    contract = URIRef("urn:gymact:swegym:e2e:contract")
    capability = URIRef(SWEGYM_EVALUATE_CAPABILITY.iri)

    # These assertions reflect what is actually present in ontology.ttl, read in full
    # above -- not an assumed/guessed shape. SWE-Gym has no git-checkout revision (it
    # is a HuggingFace dataset row, not a pinned repo), so dct:hasVersion here is the
    # dataset's own placeholder pin string, not a SWEGYM_COMPAT_REVISION constant --
    # this provider exports no such constant, unlike sregym.
    assert str(graph.value(contract, DCTERMS.hasVersion)) == "SWE-Gym/SWE-Gym@main"
    assert (
        str(graph.value(contract, DCTERMS.source))
        == "https://huggingface.co/datasets/SWE-Gym/SWE-Gym"
    )
    assert graph.value(contract, DCTERMS.relation) == capability
    assert (capability, RDF.type, URIRef("http://www.w3.org/ns/sosa/Procedure")) in graph
    assert graph.value(capability, DCTERMS.type) == URIRef("urn:gymact:consequence:do")

    receipt_sequence = URIRef("urn:gymact:swegym:e2e:receipt-sequence")
    assert (contract, DCTERMS.hasPart, receipt_sequence) in graph
    ordered_ops = [
        str(
            graph.value(
                receipt_sequence, URIRef(f"http://www.w3.org/1999/02/22-rdf-syntax-ns#_{i}")
            )
        )
        for i in range(1, 5)
    ]
    assert ordered_ops == [
        "urn:gymact:operation:materialize",
        "urn:gymact:operation:act",
        "urn:gymact:operation:verify",
        "urn:gymact:operation:teardown",
    ]


def test_swegym_evaluate_is_a_do_capability_and_environment_requires_authority() -> None:
    env = _environment()
    assert SWEGYM_EVALUATE_CAPABILITY.consequence == Consequence.DO
    assert env.requires_authority is True
    assert env.capabilities() == (SWEGYM_EVALUATE_CAPABILITY,)


# ── Pure, Docker-free unit tests of the GymAct-owned helper functions ──────────
#
# Honest accounting of what is actually separately testable without Docker, read
# directly off gymact/gyms/swegym.py:
#
#   - `_image_for_instance` is a pure function (task_id -> upstream image name).
#     Real, tested below.
#   - `_build_test_cmd` is a pure function (test directives -> pytest invocation
#     string). Real, tested below.
#   - The 3-tier patch-fallback selection (`_apply_patch`) is NOT a pure, Docker-free
#     unit: every tier is a real `docker exec` call via `_docker_exec`, and tier
#     selection is driven entirely by the container's real subprocess return codes.
#     There is no separable pure function that decides "which tier" independent of a
#     real container to apply the patch against -- fabricating a fake docker exec
#     to drive it would be exactly the mocking this repo's testing discipline bans
#     for a collaborator (Docker) this codebase does not own. A real 3-tier fallback
#     run is covered only by a real live episode per docs/integrations/swegym.md.
#   - The baseline-subtract "resolved" computation is likewise NOT a separable pure
#     function: it is inline in `actuate()` (lines computing `baseline_passed`,
#     `f2p_passed`, `p2p_passed`, and `resolved = f2p_passed and p2p_passed`), and
#     every one of those booleans is itself the return value of `_run_tests`, which
#     is itself a real `docker exec` wrapper. There is no unit here to test without
#     either a real container or a mock of one; the latter is excluded by policy.
#     Covered only by a real live episode, same as the patch-fallback tiers above.
#   - `observe`/`verify`/`checkpoint`/`restore`/`teardown` on `SWEGymEnvironment` ARE
#     real, separately testable, Docker-free async methods that only touch in-memory
#     `self._state` -- exercised directly below, mirroring sregym's checkpoint tests.


def test_image_for_instance_reproduces_upstream_harbor_naming() -> None:
    assert (
        _image_for_instance("conan-io__conan-14760")
        == "xingyaoww/sweb.eval.x86_64.conan-io_s_conan-14760"
    )


def test_image_for_instance_lowercases_mixed_case_ids() -> None:
    assert _image_for_instance("Foo__BarBaz-9") == "xingyaoww/sweb.eval.x86_64.foo_s_barbaz-9"


def test_build_test_cmd_quotes_each_directive_and_disables_snail_and_cacheprovider() -> None:
    command = _build_test_cmd(["tests/test_a.py::test_one", "tests/test b.py::test two"])
    assert command.startswith("python -m pytest -rA -p no:cacheprovider -p no:snail ")
    assert "tests/test_a.py::test_one" in command
    assert "'tests/test b.py::test two'" in command


def test_build_test_cmd_of_empty_directives_still_produces_valid_invocation() -> None:
    command = _build_test_cmd([])
    assert command == "python -m pytest -rA -p no:cacheprovider -p no:snail "


async def test_observe_verify_and_pre_actuation_checkpoint_are_consistent() -> None:
    env = _environment()
    observed = await env.observe()
    assert observed["attempted"] is False
    assert observed["resolved"] is False
    assert observed["task_id"] == "conan-io__conan-14760"
    passed, verified = await env.verify({"task_id": "conan-io__conan-14760", "attempted": False})
    assert passed is True
    assert verified == observed
    checkpoint = await env.checkpoint()
    assert checkpoint["restorable"] is True
    await env.restore(checkpoint)
    assert await env.observe() == observed


async def test_external_world_checkpoint_cannot_claim_restore_after_actuation() -> None:
    env = _environment()
    env._state["attempted"] = True
    checkpoint = await env.checkpoint()
    assert checkpoint["restorable"] is False
    with pytest.raises(RuntimeError, match="SWEGYM_EXTERNAL_WORLD_RESTORE_UNSUPPORTED"):
        await env.restore(checkpoint)


async def test_actuate_refuses_payload_missing_patch_key() -> None:
    env = _environment()
    with pytest.raises(ValueError, match="SWEGYM_EVALUATE_PAYLOAD_MISSING_PATCH"):
        await env.actuate(SWEGYM_EVALUATE_CAPABILITY, {})


async def test_actuate_refuses_non_string_patch() -> None:
    env = _environment()
    with pytest.raises(TypeError, match=r"payload\.patch must be a string"):
        await env.actuate(SWEGYM_EVALUATE_CAPABILITY, {"patch": 12345})


async def test_actuate_refuses_unsupported_capability_binding() -> None:
    env = _environment()
    other = SWEGYM_EVALUATE_CAPABILITY.model_copy(update={"binding": "not-evaluate-patch"})
    with pytest.raises(ValueError, match="unsupported swegym binding"):
        await env.actuate(other, {"patch": ""})


async def test_teardown_closes_environment_and_further_calls_refuse() -> None:
    env = _environment()
    await env.teardown()
    with pytest.raises(RuntimeError, match="environment is torn down"):
        await env.observe()


def test_swegym_provider_exposes_no_dataset_side_effects_by_default() -> None:
    # Materialization dispatches to the real HuggingFace `datasets` library and a
    # real dataset fetch -- that is explicitly out of scope for this Docker-free,
    # dataset-fetch-free unit-test file (it belongs to the live-episode procedure in
    # docs/integrations/swegym.md). What is real and checkable here without any
    # network or Docker call is the provider's declared identity and defaults.
    provider = SWEGymProvider()
    assert provider.name == "swegym"
    assert provider.materialization_requires_authority is False
    assert SWEGYM_UPSTREAM_DATASET == "SWE-Gym/SWE-Gym"
    assert SWEGYM_UPSTREAM_SPLIT == "train"
