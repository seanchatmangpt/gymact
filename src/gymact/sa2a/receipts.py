"""Powerless consumer receipt."""
from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class Receipt:
    subject:str; effect_id:str; generation:int; provider:str; replay_key:str; outcome:str; authority:str="none"
    @property
    def identity(self):return (self.subject,self.effect_id,self.generation,self.replay_key)
def receipt_for(e):
    c=e.candidate; return Receipt(c.subject,c.effect_id,c.generation,c.provider,c.replay_key,e.outcome)
