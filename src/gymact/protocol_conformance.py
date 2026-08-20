"""Runtime-neutral process conformance runner.

GymAct is only an execution harness here: semantics live in the supplied vectors.
"""
from __future__ import annotations
from dataclasses import dataclass
import json, subprocess
from pathlib import Path
from typing import Sequence

@dataclass(frozen=True)
class ConformanceResult:
    implementation: tuple[str,...]
    vector_count: int
    passed: tuple[str,...]
    failures: tuple[str,...]
    @property
    def standing(self)->str: return "PARTIAL_ALIVE" if not self.failures and self.vector_count else "BUILD_BROKEN"

def _invoke(command:Sequence[str], request:dict)->dict:
    p=subprocess.run(list(command),input=json.dumps(request,sort_keys=True),text=True,capture_output=True,check=False,timeout=5)
    if p.returncode!=0: raise RuntimeError(f"BLOCKED:IMPLEMENTATION_EXIT:{p.returncode}")
    lines=[x for x in p.stdout.splitlines() if x.strip()]
    if len(lines)!=1: raise ValueError("REFUSED:NON_SINGLE_RESPONSE")
    out=json.loads(lines[0])
    if not isinstance(out,dict): raise ValueError("REFUSED:NON_OBJECT_RESPONSE")
    return out

def conform(command:Sequence[str], vectors_path:Path)->ConformanceResult:
    vectors=json.loads(vectors_path.read_text()); passed=[]; failures=[]
    for v in vectors:
        actual=_invoke(command,v["request"]); expected=v["expect"]
        if all(actual.get(k)==val for k,val in expected.items()): passed.append(v["id"])
        else: failures.append(v["id"])
    return ConformanceResult(tuple(command),len(vectors),tuple(passed),tuple(failures))
