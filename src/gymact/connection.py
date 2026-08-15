"""Enterprise Connection v1 adapter for GymAct bounded exercise.

Binds a MANUFACTURE envelope to GymAct's real semantic manufacturing bundle.
It does not materialize or actuate a world and cannot upgrade request
acceptance into objective verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from gymact.manufacture import export_manufacturing_bundle

SCHEMA="urn:ggen:enterprise-connection:v1"; HEX40=re.compile(r"^[0-9a-f]{40}$")
class ConnectionRefusal(ValueError): pass

def canonical_bytes(value: Any)->bytes: return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
def sha256_bytes(data: bytes)->str: return "sha256:"+hashlib.sha256(data).hexdigest()

def _load_parent(path: Path):
    raw=path.read_bytes()
    try: env=json.loads(raw)
    except json.JSONDecodeError as exc: raise ConnectionRefusal(f"REFUSED:PARENT_JSON:{exc}") from exc
    if not isinstance(env,dict) or env.get("schema")!=SCHEMA: raise ConnectionRefusal("REFUSED:PARENT_SCHEMA")
    if raw!=canonical_bytes(env): raise ConnectionRefusal("REFUSED:PARENT_NON_CANONICAL")
    if env.get("stage")!="MANUFACTURE": raise ConnectionRefusal(f"REFUSED:PARENT_STAGE:{env.get('stage')!r}")
    if env.get("authority",{}).get("do_authority") is not False: raise ConnectionRefusal("REFUSED:PARENT_AMBIENT_ACTUATION")
    return env,raw

def export_exercise_connection(parent_path: Path,bundle_dir: Path,revision: str,out: Path)->dict[str,Any]:
    if not HEX40.fullmatch(revision): raise ConnectionRefusal(f"REFUSED:REVISION:{revision}")
    parent,parent_raw=_load_parent(parent_path); bundle_dir=bundle_dir.resolve(); exported=export_manufacturing_bundle(bundle_dir)
    expected={"profile.ttl","profile.shacl.ttl","runtime-contract.jcs.json"}
    if set(exported)!=expected: raise ConnectionRefusal("REFUSED:MANUFACTURING_BUNDLE_SURFACE:"+",".join(sorted(exported)))
    bundle_artifacts=[]; bundle_index={}
    for name,resource in sorted(exported.items()):
        data=resource.path.read_bytes(); digest=sha256_bytes(data)
        if digest!="sha256:"+resource.sha256: raise ConnectionRefusal(f"REFUSED:BUNDLE_DIGEST_DRIFT:{name}")
        bundle_index[name]=digest; bundle_artifacts.append({"path":f"gymact-bundle/{name}","role":"gymact:manufacturing-bundle","media_type":"text/turtle" if name.endswith(".ttl") else "application/json","digest":digest})
    bundle_set_digest=sha256_bytes(canonical_bytes(bundle_index))
    env={**parent,"stage":"EXERCISE","producer":{"repository":"seanchatmangpt/gymact","revision":revision,"component":"gymact.connection"},"subject":{**parent["subject"],"kind":"bounded-enterprise-architecture-exercise-input","revision":bundle_set_digest},"artifacts":parent["artifacts"]+bundle_artifacts,"authority":{"ceiling":"BOUNDED_GYM","do_authority":False},"standing":{"state":"PARTIAL_ALIVE","claim":"GYMACT_MANUFACTURING_BUNDLE_EXPORTED_AND_DIGEST_BOUND; WORLD_ACTUATION_NOT_EXECUTED; OBJECTIVE_VERIFICATION_NOT_ESTABLISHED"},"parent":{"digest":sha256_bytes(parent_raw),"producer":f"{parent['producer']['repository']}@{parent['producer']['revision']}"},"evidence":parent["evidence"]+[{"kind":"gymact-manufacturing-bundle","identity":"profile.ttl+profile.shacl.ttl+runtime-contract.jcs.json","digest":bundle_set_digest}],"next":[{"consumer":"seanchatmangpt/ggen-create","operation":"refine-from-exercise-evidence"}],"labels":{**parent["labels"],"gymact_bundle_digest":bundle_set_digest,"exercise_mode":"CONSTRUCT_ONLY_INPUT_BINDING"}}
    data=canonical_bytes(env); out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(data); return env

def main(argv=None)->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--parent",type=Path,required=True); parser.add_argument("--bundle-dir",type=Path,required=True); parser.add_argument("--revision",required=True); parser.add_argument("--out",type=Path,required=True); args=parser.parse_args(argv)
    try: env=export_exercise_connection(args.parent,args.bundle_dir,args.revision,args.out)
    except (ConnectionRefusal,OSError,ValueError) as exc: print(json.dumps({"standing":"REFUSED","error":str(exc)},sort_keys=True)); return 2
    print(json.dumps({"standing":env["standing"]["state"],"stage":env["stage"],"digest":sha256_bytes(args.out.read_bytes()),"out":str(args.out),"do_authority":False},sort_keys=True)); return 0

if __name__=="__main__": raise SystemExit(main())
