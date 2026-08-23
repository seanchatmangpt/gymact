from dataclasses import dataclass

@dataclass(frozen=True)
class SimulationResult:
    trace: tuple[str, ...]
    terminal: str

def simulate(start: str, policy: dict[str, str], transitions: dict[tuple[str, str], str], max_steps: int=32) -> SimulationResult:
    state=start; trace=[]
    for _ in range(max_steps):
        if state not in policy: return SimulationResult(tuple(trace),state)
        action=policy[state]; key=(state,action)
        if key not in transitions: raise ValueError('REFUSED_INVALID_SIMULATION_EDGE')
        trace.append(action); state=transitions[key]
    raise ValueError('REFUSED_SIMULATION_BOUND_EXCEEDED')
