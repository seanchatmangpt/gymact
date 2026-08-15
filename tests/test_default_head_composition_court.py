"""Post-merge composition court for the exact repository subject.

This is intentionally broader than a component unit test. It binds the four
merge-sensitive seams that produced real defects during the 2026-08-11
integration round: DCM algebra + Protocol coexistence, opaque-world observed
postconditions, ontology/TOGAF SHACL judgment, and live-provider observation
channels. A PR being green does not transfer standing to a new composition;
this court must execute against the composed head.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from gymact import GymAct, MaterializationIntent
from gymact.algebra import Actuator, Observer, Verifier, compose_paths, identity_path
from gymact.authority import AllowListAuthorityResolver
from gymact.combinatorial import PossibilityPath
from gymact.gyms.opaque_procedure import OpaqueProcedureProvider, _opaque_id
from gymact.models import ActuationIntent, Operation
from gymact.providers import MemoryEnvironment
from gymact.verification import ShaclPostconditionVerifier

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = "urn:gymact:authority:composition-court"


def test_dcm_algebra_and_environment_protocol_views_coexist() -> None:
    """Regression court for the real algebra.py merge clobber found post-merge."""
    edge = PossibilityPath(object_ids=("a", "b"), morphism_ids=("a-to-b",))
    composed = compose_paths(identity_path("a"), edge)
    assert composed.object_ids == ("a", "b")
    assert composed.morphism_ids == ("a-to-b",)

    env = MemoryEnvironment()
    assert isinstance(env, Observer)
    assert isinstance(env, Actuator)
    assert isinstance(env, Verifier)


async def test_opaque_world_goal_is_independently_observable_through_kernel() -> None:
    """Regression court for the real post-merge bug where opaque observe()
    omitted goal_reached, making kernel-owned verification impossible."""
    provider = OpaqueProcedureProvider()
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(provider)

    subject = "urn:gymact:composition-court:opaque-subject"
    materialized = await gym.materialize(
        MaterializationIntent(
            provider="opaque-procedure",
            config={
                "subject": subject,
                "initial_facts": [],
                "goal_facts": ["done"],
                "steps": [
                    {
                        "id": "finish",
                        "preconditions": [],
                        "establishes": ["done"],
                        "removes": [],
                    }
                ],
                "requires_authority": True,
            },
        )
    )
    assert materialized.accepted is True, materialized.receipt.reason
    assert materialized.episode is not None
    episode_id = materialized.episode.episode_id

    capability = _opaque_id(subject=subject, step_id="finish")
    acted = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=capability,
            authority_ref=AUTHORITY,
        )
    )
    assert acted.accepted is True, acted.receipt.reason

    observation = await gym.observe(episode_id)
    assert observation.state["goal_reached"] is True

    verification = await gym.verify(episode_id, {"goal_reached": True})
    assert verification.passed is True
    receipts = gym.episode_receipts(episode_id)
    assert receipts[-1].operation is Operation.VERIFY
    assert receipts[-1].verified is True

    await gym.teardown(episode_id, authority_ref=AUTHORITY)


def test_togaf_real_shacl_postcondition_verifier_admits_and_falsifies() -> None:
    """Exercise GymAct's injected SHACL judge against the real TOGAF court,
    rather than testing pyshacl directly and leaving the verifier unwired."""
    data_path = ROOT / "ggen" / "togaf-gym-pack" / "ontology.ttl"
    shapes_path = ROOT / "rust" / "togaf_gym" / "shapes.ttl"
    data = Graph().parse(data_path, format="turtle")
    verifier = ShaclPostconditionVerifier(shapes_path)

    passed, reason = verifier.judge({}, {"graph": data})
    assert passed is True
    assert reason == "VERIFIED:SHACL_CONFORMS"

    requirement = URIRef("urn:gymact:togaf:req:continuity")
    oslc_specified_by = URIRef("http://open-services.net/ns/rm#specifiedBy")
    data.remove((requirement, oslc_specified_by, None))
    passed, reason = verifier.judge({}, {"graph": data})
    assert passed is False
    assert reason.startswith("SHACL_VIOLATION:")
    assert (requirement, RDF.type, None) in data


def _observation_report() -> list[dict[str, object]]:
    script = ROOT / "scripts" / "check_observe_independence.py"
    spec = importlib.util.spec_from_file_location("check_observe_independence", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.build_report()


def test_known_live_external_observation_channels_cannot_silently_degrade_to_cache() -> None:
    """Promote the useful part of the advisory AST audit into a hard court:
    providers already proven to re-query a real external world must keep a
    detectable independent I/O path. Fully simulated worlds remain lawful and
    are not falsely required to perform external I/O."""
    report = _observation_report()
    by_file = {Path(str(row["file"])).name: row for row in report}
    required_live = {
        "codebase.py",
        "ggen.py",
        "kubernetes_reconciliation.py",
        "sregym.py",
        "terraform_docker_apply.py",
    }
    missing = sorted(required_live - set(by_file))
    assert missing == [], f"live observation providers disappeared from audit: {missing}"
    degraded = sorted(name for name in required_live if by_file[name]["has_io"] is not True)
    assert degraded == [], (
        "real external observe() path lost detectable independent I/O; "
        f"refuse cached/self-reported verification: {degraded}"
    )
