"""Wire-format court for SA2AReplanEnvelope's `schema` key.

`schema` shadows pydantic's deprecated `BaseModel.schema`; pydantic warns at class creation,
which is an error under this repo's `filterwarnings = ["error"]` and aborts test COLLECTION for
the whole run. The Python attribute is `schema_id` with wire alias `schema`; the dump must keep
the wire key because `sa2a_evolution` hashes `model_dump(mode="json")`: a renamed key would
silently change every envelope digest across runtimes.
"""

from __future__ import annotations

import subprocess
import sys

from gymact.sa2a_envelope import SA2A_REPLAN_SCHEMA, admit_envelope

BASE = {
    "schema": SA2A_REPLAN_SCHEMA,
    "contract_digest": "sha256:ff7643034ed101930e9c80df716df863b6ee6d14f3b29aff764209ad11dab80e",
    "exact_subject": {"counter": 1},
    "receipt_id": "receipt-1",
    "consequence": "executed",
    "decision": {"kind": "stop", "reason": "done", "authority": "none"},
}


def test_dump_keeps_the_portable_wire_key_and_round_trips() -> None:
    admitted = admit_envelope(dict(BASE))

    dumped = admitted.model_dump(mode="json")

    assert dumped["schema"] == SA2A_REPLAN_SCHEMA
    assert "schema_id" not in dumped
    assert admit_envelope(dumped) == admitted  # the dump re-admits: wire in == wire out


def test_python_name_is_not_accepted_on_the_wire() -> None:
    wire = {k: v for k, v in BASE.items() if k != "schema"} | {"schema_id": SA2A_REPLAN_SCHEMA}

    try:
        admit_envelope(wire)
    except Exception as exc:
        assert "schema" in str(exc)
    else:
        raise AssertionError("schema_id must not be admitted as a wire key")


def test_importing_the_module_raises_no_warning_under_error_policy() -> None:
    proc = subprocess.run(
        [sys.executable, "-W", "error", "-c", "import gymact.sa2a_envelope"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
