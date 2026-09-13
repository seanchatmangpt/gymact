from __future__ import annotations

import json
from pathlib import Path


def test_dcm_evidence_overlay_refuses_false_alive() -> None:
    path = Path(__file__).parents[1] / "src" / "gymact" / "schemas" / "dcm-evidence-v26.8.7.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["current"]["implementation"] == "STRUCTURAL"
    assert data["current"]["end_to_end"] == "UNKNOWN"
    assert data["current"]["adopted"] is False
    assert data["evidence"]["cloud_dependency_capsule"] == "BLOCKED"
    witness = data["required_witness"]
    assert len(witness) >= 10
    assert any("complete non-truncated" in item for item in witness)
    assert any("exact action/subject/capability/verifier/effect" in item for item in witness)
    assert any("graph/closure/path/morphism/selection" in item for item in witness)
