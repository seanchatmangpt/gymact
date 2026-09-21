"""Real CLI-contract coverage for `gymact explore` and `gymact execute`.

Closes a real gap: before this file, `tests/test_dcm_decision_court.py` was the
only test exercising `DCMDecisionCourt.admit_and_explore` / `.select`, and it
calls those methods on in-memory Python objects directly -- never through
`_read_json` / `DecisionCourtRequest.model_validate` / the real Typer app that
the installed `gymact` console script (`pyproject.toml` `[project.scripts]`:
`gymact = "gymact.cli:app"`) actually exposes to operators. This file drives
the same `explore`/`execute` commands the real `gymact` CLI serves, through
`typer.testing.CliRunner`, matching the pattern in
`tests/test_core.py::test_typer_cli_version_profile_export_and_demo` and
`tests/test_surfaces_sota.py::test_cli_contract_and_manufacturing_bundle_are_same_contract`.

`tests/fixtures/cli_explore_request.json` was generated once, for real, by
reusing `tests/test_dcm_decision_court.py::fixture()` (the same
`action_possibility_fragment(action, subject)` call from
`src/gymact/action_graph.py:41`) and serializing a real `DecisionCourtRequest`
with `.model_dump(mode="json")` -- see the generator this file's own test
re-derives inline via `_court_request_payload()`, kept in sync with the
committed fixture by `test_committed_fixture_matches_regenerated_payload`.

## `execute`: real, reproducible REFUSED -- not a forced success

`gymact.cli.execute` (src/gymact/cli.py:205) materializes a *brand new*
environment *inside the same CLI invocation* (src/gymact/cli.py:218) before
checking the request's static `subject.provider_ref` against
`episode.environment_id` (src/gymact/cli.py:232). Every builtin provider
(`MemoryProvider` included, src/gymact/providers.py:85:
`self.environment_id = f"urn:gymact:memory:environment:{uuid4().hex}"`)
assigns that id from a fresh `uuid4()` at materialization time -- it cannot be
known, guessed, or templated into a request file written *before* the CLI
call that creates it. Verified by reading the source (no override hook exists
anywhere in `MaterializationIntent`/`MemoryProvider.materialize`) and by one
real, executed probe run confirming the exact refusal below. `execute`'s
in-process (non-CLI) success path, by contrast, is real and covered by
`tests/test_combinatorial_receipt.py`: there, `subject.provider_ref` is built
*after* a real `runtime.materialize(...)` call, from the same live `episode`,
in the same runtime instance -- something a static, pre-written JSON request
file structurally cannot do for a single-shot CLI round trip.

So the one real, reachable, deterministic outcome of a single `gymact
execute <request.json>` round trip against the memory provider, using a
request built entirely from data available *before* that call, is
`standing=REFUSED, reason=SUBJECT_PROVIDER_IDENTITY_MISMATCH`. That is what
`test_cli_execute_reports_real_subject_provider_identity_mismatch` asserts:
a real, currently-true, regression-guarding fact about the shipped CLI
contract -- not a fabricated success. Closing the ALIVE/success execute path
would require a CLI-level design change (e.g. an `--episode-id` flag to
`execute` that attaches to an already-materialized episode instead of always
re-materializing) that is out of this closure's scope; see the worktree
report for `ga-explore-execute`.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gymact.cli import app
from gymact.combinatorial import AdmissionContext, ExplorationBounds
from gymact.dcm_runtime import DecisionCourtRequest
from tests.test_dcm_decision_court import fixture

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "cli_explore_request.json"


def _court_request_payload() -> dict[str, object]:
    """Rebuild the exact DecisionCourtRequest payload the fixture file holds.

    Reuses the same deterministic fixture() helper action_graph fragment call
    (src/gymact/action_graph.py:41) tests/test_dcm_decision_court.py already
    proves; used here only to assert the committed fixture has not drifted.
    """
    graph, start_id, action, _prepared, _grant = fixture()
    request = DecisionCourtRequest(
        graph=graph,
        start_ids=(start_id,),
        context=AdmissionContext(
            capability_refs=(action.capability_ref,),
            policy_refs=("urn:policy:auto",),
            current_revision="rev-1",
            execution_grant_ref="urn:grant:admitted",
        ),
        bounds=ExplorationBounds(),
    )
    return request.model_dump(mode="json")


def test_committed_fixture_matches_regenerated_payload() -> None:
    """The committed fixture is exactly fixture()'s graph, not hand-edited."""
    committed = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert committed == _court_request_payload()
    # Sanity: the start object really is the subject action_graph.py:41's
    # action_possibility_fragment(action, subject) placed in the graph.
    _graph, start_id, _action, _prepared, _grant = fixture()
    assert start_id in {item["object_id"] for item in committed["graph"]["objects"]}


def test_cli_explore_admits_and_computes_real_irreversible_frontier() -> None:
    """`gymact explore` over the real fixture: real stdout, real RDF admission."""
    runner = CliRunner()
    result = runner.invoke(app, ["explore", str(FIXTURE_PATH)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)

    assert payload["rdf_validation"]["conforms"] is True
    assert payload["exploration"]["truncated"] is False
    frontier = payload["exploration"]["irreversible_frontier"]
    assert len(frontier) >= 1
    assert frontier[0]["admitted"] is True
    assert frontier[0]["path_id"]
    assert frontier[0]["morphism_id"]


def test_cli_execute_reports_real_subject_provider_identity_mismatch(
    tmp_path: Path,
) -> None:
    """Real execute() round trip using explore-derived path_id/morphism_id.

    See the module docstring for why REFUSED:SUBJECT_PROVIDER_IDENTITY_MISMATCH
    is the one real, reachable outcome of a single-shot CLI `execute` call
    against the memory provider, built from data known before that call.
    """
    runner = CliRunner()

    # (1)+(2): real explore run, real extracted path_id/morphism_id -- never
    # hand-guessed.
    explore_result = runner.invoke(app, ["explore", str(FIXTURE_PATH)])
    assert explore_result.exit_code == 0, explore_result.output
    explore_payload = json.loads(explore_result.stdout)
    frontier = explore_payload["exploration"]["irreversible_frontier"][0]
    real_path_id = frontier["path_id"]
    real_morphism_id = frontier["morphism_id"]
    assert real_path_id and real_morphism_id

    # (3): a real execute request, using src/gymact/cli.py's execute() body
    # (read in full) for the exact required top-level keys: action/subject/
    # grant/court/selection/payload/idempotency_key.
    _graph, _start_id, action, _prepared, grant = fixture()
    court_request_payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    execute_request = {
        "provider": "memory",
        "config": {"initial": {}, "requires_authority": False},
        "materialization_idempotency_key": "cli-execute-contract-test",
        "action": action.model_dump(mode="json"),
        "subject": {
            "semantic_id": "urn:subject:1",
            "provider_ref": "provider-subject",
            "revision": "rev-1",
        },
        "grant": grant.model_dump(mode="json"),
        "payload": {"x": 2},
        "idempotency_key": "exec-set-x",
        "court": court_request_payload,
        "selection": {
            "path_id": real_path_id,
            "morphism_id": real_morphism_id,
            "selector_ref": "urn:selector:cli-contract-test",
            "basis_refs": [],
        },
        "current_revision": "rev-1",
        "expected": {"x": 2},
    }
    request_path = tmp_path / "execute_request.json"
    request_path.write_text(json.dumps(execute_request), encoding="utf-8")

    # (4): real execute run via CliRunner -- a real, deterministic result.
    execute_result = runner.invoke(app, ["execute", str(request_path)])
    assert execute_result.exit_code == 0, execute_result.output
    execute_payload = json.loads(execute_result.stdout)

    # The materialization itself is real and ALIVE -- a fresh environment
    # really was created inside this call, with a real random environment_id.
    assert execute_payload["materialization"]["standing"] == "ALIVE"
    real_environment_id = execute_payload["materialization"]["episode"]["environment_id"]
    assert real_environment_id.startswith("urn:gymact:memory:environment:")
    # The request's static subject.provider_ref cannot equal that id -- it
    # was written before the id existed. This is the real, reproducible
    # execute() outcome for a single-shot CLI round trip against memory.
    assert real_environment_id != "provider-subject"
    assert execute_payload["standing"] == "REFUSED"
    assert execute_payload["reason"] == "SUBJECT_PROVIDER_IDENTITY_MISMATCH"
