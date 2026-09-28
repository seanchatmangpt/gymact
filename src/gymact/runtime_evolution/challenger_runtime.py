"""Deterministic challenger manufacture."""
from dataclasses import dataclass
@dataclass(frozen=True)
class Challenger:
 identity:str; subject:str; edge:str; mutation:str
def generate(subject:str,epoch:int,mutations:tuple[str,...])->list[Challenger]:
 return [Challenger(f"{subject}:{epoch}:{i}",subject,f"mutation:{m}",m) for i,m in enumerate(mutations)]
