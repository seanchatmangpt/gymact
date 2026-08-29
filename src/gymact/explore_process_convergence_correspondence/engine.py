from dataclasses import dataclass
from .trajectory import Trajectory
from .classifier import Strategy, classify
from .dependency import DependencyGraph
from .pareto import candidates, frontier
from .standing import Standing, standing
from .receipt import Receipt
from .authority import ActionClass, admit

@dataclass(frozen=True)
class Qualification:
    strategy: Strategy
    direction: str
    standing: Standing
    receipt: Receipt

def qualify(trajectory: Trajectory, graph: DependencyGraph, strategy: Strategy = Strategy.LYAPUNOV) -> Qualification:
    admit(ActionClass.CONSTRUCT)
    direction = classify(trajectory, strategy)
    result = standing(trajectory.epochs[-1], direction, graph)
    frontier(candidates(trajectory))
    body = {
        "schema": "gymact.explore-process-convergence/1",
        "subject": trajectory.epochs[-1].subject.subject,
        "generation": trajectory.epochs[-1].subject.generation,
        "strategy": strategy.value,
        "direction": direction.value,
        "standing": result.value,
        "actuation_performed": False,
    }
    return Qualification(strategy, direction.value, result, Receipt.issue(body))
