from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from .witness import WitnessKind
class RolloverStrategy(str, Enum): EAGER_ALL="EAGER_ALL"; QUORUM_MIGRATE="QUORUM_MIGRATE"; CRITICAL_PATH="CRITICAL_PATH"
@dataclass(frozen=True)
class StrategyResult:
    strategy:RolloverStrategy; complete:bool; satisfied:int; required:int
def evaluate(strategy:RolloverStrategy, frontier:dict[str,WitnessKind], consumers:tuple[str,...], critical:frozenset[str]=frozenset())->StrategyResult:
    discharged={k for k,v in frontier.items() if v in {WitnessKind.DISCHARGED,WitnessKind.RECOVERED}}
    if strategy is RolloverStrategy.EAGER_ALL: required=len(consumers); satisfied=len(discharged & set(consumers))
    elif strategy is RolloverStrategy.QUORUM_MIGRATE: required=len(consumers)//2+1; satisfied=len(discharged & set(consumers))
    else: required=len(critical); satisfied=len(discharged & critical)
    return StrategyResult(strategy,satisfied>=required,satisfied,required)
