"""Chicago-style completeness check for `gymact.composition_inventory` -- "Court A":
inventory completeness, distinct from `test_composition_admission_chicago.py`'s "Court
B" (composition admission given a *fixed* inventory).

Mirrors `tests/test_registry_completeness_chicago.py`'s pattern exactly: mechanically
discover every real candidate component across the categories the composition-admission
gate cares about (gym providers, authority resolvers, capability scopes, postcondition
verifiers, effect ports / OCEL functions), then require each discovered candidate to be
EITHER

  (a) referenced as a `component_ref` in `gymact.composition_inventory.
      KNOWN_COMPONENT_CAPABILITIES`, OR
  (b) named in this file's own `_INTENTIONALLY_UNCATALOGED` allowlist with a real,
      specific reason string.

No collaborator here is faked: every discovery step is a real filesystem walk, `ast`
parse, or `glob`, and every assertion is against the real, current contents of
`gymact.composition_inventory` and `gymact.composition`. No monkeypatching, no mocked
imports -- nothing here needs an interaction-faking test double of any kind.
"""

from __future__ import annotations

import ast
from pathlib import Path

from gymact import composition_inventory

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "gymact"
GYMS_ROOT = SRC_ROOT / "gyms"
GGEN_ROOT = Path(__file__).resolve().parent.parent / "ggen"

_KNOWN_REFS: frozenset[str] = frozenset(
    c.component_ref for c in composition_inventory.KNOWN_COMPONENT_CAPABILITIES
)


# ---------------------------------------------------------------------------
# Category: gym *Provider classes (same AST-scan pattern as
# test_registry_completeness_chicago.py's `_real_provider_classes_under_gyms`).
# ---------------------------------------------------------------------------


def _real_provider_classes_under_gyms() -> dict[str, str]:
    """name -> dotted module path (module derived from file path, matching how
    these classes are actually imported elsewhere in this repo)."""
    found: dict[str, str] = {}
    for py_file in sorted(GYMS_ROOT.rglob("*.py")):
        if py_file.name == "__init__.py":
            continue
        tree = ast.parse(py_file.read_text(), filename=str(py_file))
        rel = py_file.relative_to(SRC_ROOT.parent).with_suffix("")
        module = ".".join(rel.parts)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith("Provider"):
                found[node.name] = f"{module}.{node.name}"
    return found


# ---------------------------------------------------------------------------
# Category: AuthorityResolver implementations. Real AST scan for classes whose
# body defines an `authorize` method and are not the Protocol itself
# (`gymact.authority.AuthorityResolver`, which has no method *bodies* to speak
# of beyond `...`).
# ---------------------------------------------------------------------------


def _real_authority_resolver_classes() -> dict[str, str]:
    found: dict[str, str] = {}
    for py_file in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(py_file.read_text(), filename=str(py_file))
        rel = py_file.relative_to(SRC_ROOT.parent).with_suffix("")
        module = ".".join(rel.parts)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.endswith("AuthorityResolver"):
                continue
            if node.name == "AuthorityResolver":
                continue  # the Protocol itself
            found[node.name] = f"{module}.{node.name}"
    return found


# ---------------------------------------------------------------------------
# Category: CapabilityScope implementations (mirrors the AuthorityResolver scan).
# ---------------------------------------------------------------------------


def _real_capability_scope_classes() -> dict[str, str]:
    found: dict[str, str] = {}
    for py_file in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(py_file.read_text(), filename=str(py_file))
        rel = py_file.relative_to(SRC_ROOT.parent).with_suffix("")
        module = ".".join(rel.parts)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.endswith("CapabilityScope"):
                continue
            if node.name == "CapabilityScope":
                continue  # the Protocol itself
            found[node.name] = f"{module}.{node.name}"
    return found


# ---------------------------------------------------------------------------
# Category: PostconditionVerifier implementations.
# ---------------------------------------------------------------------------


def _real_postcondition_verifier_classes() -> dict[str, str]:
    found: dict[str, str] = {}
    for py_file in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(py_file.read_text(), filename=str(py_file))
        rel = py_file.relative_to(SRC_ROOT.parent).with_suffix("")
        module = ".".join(rel.parts)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.endswith("Verifier"):
                continue
            # Only classes that actually define a `judge` method are real
            # PostconditionVerifier implementations, not unrelated *Verifier names.
            has_judge = any(
                isinstance(b, ast.FunctionDef) and b.name == "judge" for b in node.body
            )
            if not has_judge:
                continue
            found[node.name] = f"{module}.{node.name}"
    return found


# ---------------------------------------------------------------------------
# Category: EffectPort implementations + the OCEL module-level functions the
# composition-admission gate treats as component suppliers.
# ---------------------------------------------------------------------------


def _real_effect_port_classes() -> dict[str, str]:
    found: dict[str, str] = {}
    for py_file in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(py_file.read_text(), filename=str(py_file))
        rel = py_file.relative_to(SRC_ROOT.parent).with_suffix("")
        module = ".".join(rel.parts)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.endswith("EffectPort"):
                continue
            if node.name == "EffectPort":
                continue  # the Protocol itself, if one exists under this name
            found[node.name] = f"{module}.{node.name}"
    return found


_OCEL_FUNCTIONS_TO_TRACK = ("receipts_to_ocel", "validate_ocel_log", "write_ocel_log")


def _real_ocel_functions() -> dict[str, str]:
    """Only the specific, named OCEL module-level functions the composition
    gate treats as capability suppliers (not every function in ocel.py --
    e.g. `_load_schema`/`digest_ocel_log` are real internal helpers, not
    independently composition-relevant capability suppliers)."""
    ocel_py = SRC_ROOT / "ocel.py"
    tree = ast.parse(ocel_py.read_text(), filename=str(ocel_py))
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in _OCEL_FUNCTIONS_TO_TRACK:
            found[node.name] = f"gymact.ocel.{node.name}"
    return found


# validate_ocel_log/write_ocel_log are jointly referenced under one combined
# component_ref ("gymact.ocel.validate_ocel_log+write_ocel_log") in the real
# inventory -- a deliberate, documented modeling choice (composition_inventory.py's
# own module docstring), not an omission. This constant records that combined form
# so the discovery-vs-inventory match below can recognize it.
_OCEL_COMBINED_REF = "gymact.ocel.validate_ocel_log+write_ocel_log"


# ---------------------------------------------------------------------------
# Category: ggen packs with real SPARQL gates under ggen/<pack>/gates/*.rq.
# ---------------------------------------------------------------------------


def _real_ggen_packs_with_gates() -> dict[str, str]:
    found: dict[str, str] = {}
    if not GGEN_ROOT.is_dir():
        return found
    for pack_dir in sorted(GGEN_ROOT.iterdir()):
        if not pack_dir.is_dir():
            continue
        gates_dir = pack_dir / "gates"
        if gates_dir.is_dir() and any(gates_dir.glob("*.rq")):
            found[pack_dir.name] = f"ggen/{pack_dir.name}"
    return found


# ---------------------------------------------------------------------------
# The allowlist. Every entry names a real, specific, honest reason -- no vague
# catch-all text, mirroring test_registry_completeness_chicago.py's
# `_INTENTIONALLY_UNREGISTERED` style exactly.
# ---------------------------------------------------------------------------

_INTENTIONALLY_UNCATALOGED: dict[str, str] = {
    "SregymOntologyProvider": (
        "gymact.gyms.sregym_ontology.SregymOntologyProvider wraps the already-"
        "catalogued gymact.gyms.sregym.SregymVendorProvider (component_ref above), "
        "delegating observe()/actuate() and adding only IRI/binding/consequence "
        "admission checks sourced from the admitted sregym_mcp_catalog -- no new "
        "capability physics beyond what the wrapped provider already supplies. "
        "Registered as gymact's real `sregym` provider (registry.py) since the "
        "agent/gdmcp-sregym-deterministic-solutions merge; catalog entry gap found "
        "and named here rather than silently left uncaught."
    ),
    # -- gym Provider classes: optional-extra-gated, same real top-level-import
    # gating already documented in test_registry_completeness_chicago.py's
    # _INTENTIONALLY_UNREGISTERED for the same classes.
    "BrowserGymProvider": (
        "top-level `import browsergym.core`/`import gymnasium`, gated behind the "
        "optional 'gyms' extra -- not composition-evidenced until that extra is "
        "part of a real composition-admission decision."
    ),
    "GymnasiumProvider": (
        "top-level `import gymnasium`, gated behind the optional 'gyms' extra -- "
        "not yet composition-evidenced."
    ),
    "InspectEvalsProvider": (
        "top-level `from inspect_ai import ...`, gated behind the optional 'gyms' "
        "extra (inspect-ai) -- not yet composition-evidenced."
    ),
    "CubeCounterProvider": (
        "top-level `from counter_cube...` re-raised as ImportError when absent, "
        "gated behind the optional 'cube' extra (Python >=3.12 only) -- not yet "
        "composition-evidenced."
    ),
    "CubeContainerCounterProvider": (
        "top-level `from cube.infra_local import LocalInfraConfig` re-raised as "
        "ImportError when absent, gated behind the optional 'cube' extra plus "
        "Docker -- not yet composition-evidenced."
    ),
    "VendorBenchmarkProvider": (
        "generic vendor-benchmark dispatch surface, not a single fixed-capability "
        "gym -- capabilities are dispatched per-vendor at runtime, not a static "
        "module-level tuple this table's evidenced-capability-id shape assumes."
    ),
    "OpaqueProcedureProvider": (
        "capabilities are constructed per-instance from materialize()-time config "
        "(hidden_steps), not a fixed module-level tuple -- same static-capabilities-"
        "tuple mismatch as VendorBenchmarkProvider/OntologyDrivenProvider."
    ),
    "OntologyDrivenProvider": (
        "generic ontology-driven compiler, not a single fixed-capability gym -- "
        "requires per-domain configuration (pack_dir, task-family sets) at "
        "construction time and derives capabilities dynamically from a pack's "
        "ontology.ttl at materialize() time, not a static evidenced tuple."
    ),
    # -- gym Provider classes: real, buildable providers not yet given an
    # individually evidenced ComponentCapabilities entry. Each is a genuine
    # candidate for a future entry once its capabilities are actually composed
    # against in a real contract (the same discipline `explore-exploit.md`
    # already applies to lab-vs-admitted work) -- listed individually, not
    # under one blanket reason, so each can be closed independently.
    "ChatmanStateProvider": (
        "real, buildable simulated state-machine gym (src/gymact/gyms/"
        "chatman_state_gym.py) -- no ComponentCapabilities entry has yet been "
        "evidenced for it because no real composition-admission contract has been "
        "matched against it yet."
    ),
    "CloudSimProvider": (
        "real, buildable provider (src/gymact/gyms/provider.py, module literally "
        "named provider.py rather than cloudsim.py) -- not yet composition-"
        "evidenced against a real contract."
    ),
    "CloudTopologyProvider": (
        "real, buildable provider (src/gymact/gyms/cloud_topology_gym.py) -- not "
        "yet composition-evidenced against a real contract."
    ),
    "CodebaseProvider": (
        "real, buildable provider (src/gymact/gyms/codebase.py) -- not yet "
        "composition-evidenced against a real contract."
    ),
    "DevPortfolioProvider": (
        "real, buildable provider (src/gymact/gyms/dev_portfolio.py) -- not yet "
        "composition-evidenced against a real contract."
    ),
    "GenericDiscoveredProvider": (
        "generic discovery-driven dispatch surface (src/gymact/gyms/discovered.py) "
        "constructed from arbitrary discovered subprocess targets at runtime, not a "
        "single fixed-capability gym -- same static-capabilities-tuple mismatch as "
        "VendorBenchmarkProvider."
    ),
    "GgenLegacyVerifierProvider": (
        "real, buildable provider (src/gymact/gyms/ggen_legacy.py) -- not yet "
        "composition-evidenced against a real contract."
    ),
    "GgenProvider": (
        "real, buildable ggen-pack-materialization provider (src/gymact/gyms/"
        "ggen.py) -- not yet composition-evidenced against a real contract."
    ),
    "K8sResourceProvider": (
        "real, buildable provider (src/gymact/gyms/k8s_resource_gym.py) -- not yet "
        "composition-evidenced against a real contract."
    ),
    "LockAndKeyProvider": (
        "real, buildable provider (src/gymact/gyms/lock_and_key.py) -- not yet "
        "composition-evidenced against a real contract."
    ),
    "McpClientSessionProvider": (
        "real, buildable provider (src/gymact/gyms/mcp_client_session.py) -- not "
        "yet composition-evidenced against a real contract."
    ),
    "MulticloudProvider": (
        "real, buildable provider (src/gymact/gyms/multicloud.py) -- not yet "
        "composition-evidenced against a real contract."
    ),
    "ResourceFlowProvider": (
        "real, buildable provider (src/gymact/gyms/resource_flow.py) -- not yet "
        "composition-evidenced against a real contract."
    ),
    "SwitchboardProvider": (
        "real, buildable provider (src/gymact/gyms/switchboard.py) -- not yet "
        "composition-evidenced against a real contract."
    ),
    "TerraformDockerApplyProvider": (
        "real side-effecting provider (src/gymact/gyms/terraform_docker_apply.py, "
        "real `terraform apply`/`destroy`, requires_authority=True per "
        ".claude/rules/actuation-authority.md's 2026-08-08 fix) -- not yet given "
        "its own composition-admission ComponentCapabilities entry."
    ),
    "TerraformPlanProvider": (
        "real, buildable provider (src/gymact/gyms/terraform_plan.py) -- not yet "
        "composition-evidenced against a real contract."
    ),
    "CommerceDfcmProvider": (
        "first-class provider-neutral commerce world with 25 bounded executable "
        "capabilities while seven marketplace/legal DO edges are structurally absent "
        "from its provider surface; no static ComponentCapabilities claim is admitted "
        "until a real composition contract independently evidences which mechanisms "
        "this domain provider supplies."
    ),
    "DependencyWorldProvider": (
        "real dependency-world provider introduced for bounded dependency topology "
        "execution; it has not yet been matched to a real composition-admission "
        "contract, so Court A records the discovery without manufacturing an ALIVE "
        "ComponentCapabilities claim."
    ),
    "SharedDependencyWorldProvider": (
        "real shared dependency-world provider whose supplied capabilities depend on "
        "the admitted shared-world construction; no independently evidenced static "
        "ComponentCapabilities tuple exists yet."
    ),
    "PlatformConsoleProvider": (
        "real platform-console provider whose consequential surface requires a "
        "reachable configured test tenant; CI explicitly skips live execution when "
        "PLATFORM_CONSOLE_BASE_URL/API_KEY are absent, so source discovery alone is "
        "insufficient to manufacture composition ALIVE standing."
    ),
    # -- capability scopes / postcondition verifiers.
    "AllowAllCapabilityScope": (
        "the permissive default (src/gymact/agent.py:58-68) -- every principal "
        "may invoke every capability, so it is not a load-bearing capability "
        "supplier the way AllowListCapabilityScope's real grants map is; "
        "deliberately excluded from the evidenced-supplier table."
    ),
    "DspyTrustedMonitorVerifier": (
        "top-level-gated behind the optional 'dspy' extra (src/gymact/"
        "dspy_verifier.py raises a real ImportError when dspy is absent) -- not "
        "yet composition-evidenced."
    ),
    # -- ggen packs: RDF-admission gates over a domain's own graph, not runtime
    # capability suppliers -- structurally different from every category above,
    # so none is individually referenced by a component_ref. Named here so a
    # newly added pack is caught by test_allowlist_entries_are_real_discovered_
    # names_not_stale / test_every_ggen_pack_with_real_gates_is_documented rather
    # than silently going unaccounted.
    "swegym-e2e-pack": "SPARQL admission gate over swegym's own contract graph, not a runtime capability supplier.",
    "gymact-registry-pack": "SPARQL admission gate over the registry's own import-validity graph, not a runtime capability supplier.",
    "career-gym-pack": "SPARQL admission gate over career-gym's own profile/consent graph, not a runtime capability supplier.",
    "cloudsim-gym-pack": "SPARQL admission gate (no-custom-tbox) over cloudsim's own graph, not a runtime capability supplier.",
    "chatman-state-pack": "SPARQL admission gate over chatman-state's capability-validity graph, not a runtime capability supplier.",
    "cloud-topology-validation-pack": "SPARQL admission gate over cloud-topology's provider-policy graph, not a runtime capability supplier.",
    "gymact-bridge-pack": "SPARQL admission gate over the bridge pack's required/single-valued/no-custom-tbox graph, not a runtime capability supplier.",
    "post-agi-crown-pack": "SPARQL admission gate over the crown pack's pipeline/output graph, not a runtime capability supplier.",
    "k8s-resource-catalog-pack": "SPARQL admission gate over k8s-resource-catalog's resource-kind-validity graph, not a runtime capability supplier.",
    "protocol-gym-pack": "SPARQL admission gate over protocol-gym's capabilities/consequence graph, not a runtime capability supplier.",
    "codebase-gym-pack": "SPARQL admission gate over codebase-gym's required/single-valued/no-custom-tbox graph, not a runtime capability supplier.",
    "multicloud-gym-pack": "SPARQL admission gate over multicloud's required/single-valued/no-custom-tbox graph, not a runtime capability supplier.",
    "public-ontology-admission-pack": "SPARQL admission gate over public-ontology admission-completeness graph, not a runtime capability supplier.",
    "togaf-gym-pack": "SPARQL admission gate over togaf-gym's no-custom-tbox/ADM-phase/projection graph, not a runtime capability supplier.",
    "world-cyber-gym-pack": "SPARQL admission gates over the bounded synthetic cyber world's own graph, not a runtime capability supplier.",
    "sregym-e2e-pack": "SPARQL admission gate over sregym's own e2e contract graph, not a runtime capability supplier.",
    "consumer-bridge-pack-template": (
        "template pack (not a real consumer's admitted graph itself) with its own "
        "gates/*.rq -- a scaffold consumers copy, not a runtime capability "
        "supplier this table's component_ref shape models."
    ),
}


def test_every_real_gym_provider_class_is_cataloged_or_allowlisted():
    provider_classes = _real_provider_classes_under_gyms()
    assert provider_classes, "expected to find real Provider classes under src/gymact/gyms"

    known_class_names = {ref.rsplit(".", 1)[-1] for ref in _KNOWN_REFS}

    unaccounted = [
        name
        for name in provider_classes
        if name not in known_class_names and name not in _INTENTIONALLY_UNCATALOGED
    ]
    assert unaccounted == [], (
        "the following real gym Provider classes are neither referenced as a "
        "component_ref in gymact.composition_inventory.KNOWN_COMPONENT_CAPABILITIES "
        "nor named in this test's _INTENTIONALLY_UNCATALOGED allowlist with a "
        f"reason: {sorted(unaccounted)} (module paths: "
        f"{[provider_classes[n] for n in unaccounted]})"
    )


def test_every_real_authority_resolver_is_cataloged_or_allowlisted():
    resolvers = _real_authority_resolver_classes()
    assert resolvers, "expected to find real AuthorityResolver implementations"

    known_class_names = {ref.rsplit(".", 1)[-1] for ref in _KNOWN_REFS}
    unaccounted = [
        name
        for name in resolvers
        if name not in known_class_names and name not in _INTENTIONALLY_UNCATALOGED
    ]
    assert unaccounted == [], (
        "the following real AuthorityResolver implementations are neither in the "
        f"composition inventory nor allowlisted: {sorted(unaccounted)} "
        f"(module paths: {[resolvers[n] for n in unaccounted]})"
    )


def test_every_real_capability_scope_is_cataloged_or_allowlisted():
    scopes = _real_capability_scope_classes()
    assert scopes, "expected to find real CapabilityScope implementations"

    known_class_names = {ref.rsplit(".", 1)[-1] for ref in _KNOWN_REFS}
    unaccounted = [
        name
        for name in scopes
        if name not in known_class_names and name not in _INTENTIONALLY_UNCATALOGED
    ]
    assert unaccounted == [], (
        "the following real CapabilityScope implementations are neither in the "
        f"composition inventory nor allowlisted: {sorted(unaccounted)} "
        f"(module paths: {[scopes[n] for n in unaccounted]})"
    )


def test_every_real_postcondition_verifier_is_cataloged_or_allowlisted():
    verifiers = _real_postcondition_verifier_classes()
    assert verifiers, "expected to find real PostconditionVerifier implementations"

    known_class_names = {ref.rsplit(".", 1)[-1] for ref in _KNOWN_REFS}
    unaccounted = [
        name
        for name in verifiers
        if name not in known_class_names and name not in _INTENTIONALLY_UNCATALOGED
    ]
    assert unaccounted == [], (
        "the following real PostconditionVerifier implementations are neither in "
        f"the composition inventory nor allowlisted: {sorted(unaccounted)} "
        f"(module paths: {[verifiers[n] for n in unaccounted]})"
    )


def test_every_real_effect_port_is_cataloged_or_allowlisted():
    ports = _real_effect_port_classes()
    assert ports, "expected to find real EffectPort implementations"

    known_class_names = {ref.rsplit(".", 1)[-1] for ref in _KNOWN_REFS}
    unaccounted = [
        name
        for name in ports
        if name not in known_class_names and name not in _INTENTIONALLY_UNCATALOGED
    ]
    assert unaccounted == [], (
        "the following real EffectPort implementations are neither in the "
        f"composition inventory nor allowlisted: {sorted(unaccounted)} "
        f"(module paths: {[ports[n] for n in unaccounted]})"
    )


def test_every_tracked_ocel_function_is_cataloged_or_allowlisted():
    functions = _real_ocel_functions()
    assert functions, "expected to find the tracked OCEL functions in gymact.ocel"

    unaccounted = [
        name
        for name, ref in functions.items()
        if ref not in _KNOWN_REFS
        and ref != _OCEL_COMBINED_REF
        and _OCEL_COMBINED_REF not in _KNOWN_REFS
        and name not in _INTENTIONALLY_UNCATALOGED
    ]
    # validate_ocel_log/write_ocel_log are jointly referenced; only flag a
    # function as unaccounted if neither its own ref nor the combined ref is
    # present in the inventory.
    truly_unaccounted = [
        name
        for name in unaccounted
        if functions[name] not in _KNOWN_REFS and _OCEL_COMBINED_REF not in _KNOWN_REFS
    ]
    assert truly_unaccounted == [], (
        "the following tracked OCEL functions are neither in the composition "
        f"inventory nor allowlisted: {sorted(truly_unaccounted)}"
    )


def test_every_ggen_pack_with_real_gates_is_documented():
    """ggen packs are not `component_ref`-shaped inventory entries (they gate
    RDF admission, not runtime capability supply) -- this is a lighter-weight
    real-discovery check that every pack with real SPARQL gates is at least
    named, with a real reason, in this file's own allowlist, so a new gated
    pack can never silently go unnoticed by Court A."""
    packs = _real_ggen_packs_with_gates()
    assert packs, "expected to find real ggen packs with gates/*.rq files"
    unaccounted = [name for name in packs if name not in _INTENTIONALLY_UNCATALOGED]
    assert unaccounted == [], (
        f"the following real ggen packs with gates/*.rq are not named in this "
        f"file's _INTENTIONALLY_UNCATALOGED allowlist: {sorted(unaccounted)}"
    )


def test_allowlist_entries_are_real_discovered_names_not_stale():
    """Mirrors test_registry_completeness_chicago.py's
    test_allowlist_entries_are_real_classes_not_stale_names: every allowlist key
    must correspond to a real, still-existing discovered candidate from one of
    the categories above -- no stale entries left behind after a class is
    renamed/removed or gets a real inventory entry added."""
    all_discovered = (
        set(_real_provider_classes_under_gyms())
        | set(_real_authority_resolver_classes())
        | set(_real_capability_scope_classes())
        | set(_real_postcondition_verifier_classes())
        | set(_real_effect_port_classes())
        | set(_real_ocel_functions())
        | set(_real_ggen_packs_with_gates())
    )
    stale = [name for name in _INTENTIONALLY_UNCATALOGED if name not in all_discovered]
    assert stale == [], (
        f"allowlist names no real discovered candidate anymore: {stale} -- remove "
        "the stale allowlist entry"
    )


def test_allowlist_and_inventory_do_not_overlap():
    known_class_names = {ref.rsplit(".", 1)[-1] for ref in _KNOWN_REFS}
    overlap = known_class_names & set(_INTENTIONALLY_UNCATALOGED)
    assert overlap == set(), (
        f"names {sorted(overlap)} are both referenced in "
        "KNOWN_COMPONENT_CAPABILITIES and listed as intentionally uncataloged -- "
        "the allowlist entry is stale, remove it"
    )
