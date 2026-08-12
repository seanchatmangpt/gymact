from __future__ import annotations

from pathlib import Path
from gymact.connection import canonical_bytes,export_exercise_connection,sha256_bytes

def test_connection_binds_real_manufacturing_bundle_without_actuation(tmp_path: Path)->None:
    parent={"schema":"urn:ggen:enterprise-connection:v1","connection_id":"urn:test:connection","stage":"MANUFACTURE","producer":{"repository":"seanchatmangpt/ggen","revision":"a"*40,"component":"tools/architecture-foundry:ggen-foundry-connection"},"subject":{"id":"subject","kind":"enterprise-architecture-manufacture-plan","revision":"sha256:"+"0"*64},"architecture":{"graph":None,"capabilities":["global-cloud"],"constraints":["ZERO_UNRECEIPTED_ACTUATION"]},"packs":[],"artifacts":[],"authority":{"ceiling":"CONSTRUCT_ONLY","do_authority":False},"standing":{"state":"PARTIAL_ALIVE","claim":"manufacture plan"},"parent":{"digest":"sha256:"+"1"*64,"producer":"seanchatmangpt/ggen-marketplace@"+"b"*40},"evidence":[],"next":[{"consumer":"seanchatmangpt/gymact","operation":"exercise"}],"labels":{}}
    parent_path=tmp_path/"manufacture.json"; parent_raw=canonical_bytes(parent); parent_path.write_bytes(parent_raw); out_a=tmp_path/"exercise-a.json"; out_b=tmp_path/"exercise-b.json"
    first=export_exercise_connection(parent_path,tmp_path/"bundle-a","c"*40,out_a); second=export_exercise_connection(parent_path,tmp_path/"bundle-b","c"*40,out_b)
    assert out_a.read_bytes()==out_b.read_bytes(); assert first==second; assert first["stage"]=="EXERCISE"; assert first["authority"]=={"ceiling":"BOUNDED_GYM","do_authority":False}; assert first["parent"]["digest"]==sha256_bytes(parent_raw); assert first["standing"]["state"]=="PARTIAL_ALIVE"; roles=[item["role"] for item in first["artifacts"]]; assert roles==["gymact:manufacturing-bundle"]*3; assert {Path(item["path"]).name for item in first["artifacts"]}=={"profile.ttl","profile.shacl.ttl","runtime-contract.jcs.json"}
