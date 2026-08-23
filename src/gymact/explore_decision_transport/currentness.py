from .calibration import Calibration
from .refusal import Refused


def current(models: list[Calibration]) -> Calibration:
    if not models:
        raise Refused("NO_TRANSPORT_MODEL")
    generation = max(model.generation for model in models)
    latest = [model for model in models if model.generation == generation]
    digests = {model.digest for model in latest}
    if len(digests) != 1:
        raise Refused("DIVERGENT_CURRENT_TRANSPORT")
    return latest[0]
