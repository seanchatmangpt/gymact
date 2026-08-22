from dataclasses import dataclass
from typing import Callable,Any
@dataclass(frozen=True)
class RuntimeResult:
    runtime:str
    value:Any

def execute(runtime:str, fn:Callable[[dict],Any], payload:dict)->RuntimeResult:
    value=fn(dict(payload))
    return RuntimeResult(runtime,value)
