from __future__ import annotations
import json,sys
from pathlib import Path
from gymact.protocol_conformance import conform

def test_foreign_process_is_subject_not_gymact(tmp_path:Path):
    impl=tmp_path/"foreign.py"
    impl.write_text('import json,sys\nr=json.load(sys.stdin)\nprint(json.dumps({"disposition":"ADMITTED","code":"ALLOWED"} if r.get("authority")=="exact" and r.get("receipt_capable") else {"disposition":"REFUSED","code":"REFUSED:NO_STANDING"}))\n')
    vectors=tmp_path/"vectors.json"
    vectors.write_text(json.dumps([{"id":"allow","request":{"authority":"exact","receipt_capable":True},"expect":{"disposition":"ADMITTED","code":"ALLOWED"}},{"id":"refuse","request":{"authority":None,"receipt_capable":True},"expect":{"disposition":"REFUSED","code":"REFUSED:NO_STANDING"}}]))
    result=conform([sys.executable,str(impl)],vectors)
    assert result.standing=="PARTIAL_ALIVE"
    assert result.passed==("allow","refuse")

def test_failed_vector_cannot_be_promoted(tmp_path:Path):
    impl=tmp_path/"foreign.py"; impl.write_text('import json\nprint(json.dumps({"disposition":"ADMITTED","code":"ALLOWED"}))\n')
    vectors=tmp_path/"vectors.json"; vectors.write_text(json.dumps([{"id":"must-refuse","request":{},"expect":{"disposition":"REFUSED","code":"REFUSED:NO_STANDING"}}]))
    result=conform([sys.executable,str(impl)],vectors)
    assert result.standing=="BUILD_BROKEN"
    assert result.failures==("must-refuse",)
