"""Environment-evolution coordinator."""
from dataclasses import dataclass,field
@dataclass(frozen=True)
class EvolutionState:
 subject:str; epoch:int=0; excluded:frozenset[str]=field(default_factory=frozenset); evidence:tuple[str,...]=()
class EvolutionEngine:
 def fail_edge(self,s:EvolutionState,e:str)->EvolutionState:return EvolutionState(s.subject,s.epoch,s.excluded|{e},s.evidence)
 def advance(self,s:EvolutionState,edge:str,evidence:str)->EvolutionState:
  if edge in s.excluded: raise ValueError("excluded edge")
  return EvolutionState(s.subject,s.epoch+1,s.excluded,s.evidence+(evidence,))
