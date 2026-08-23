from __future__ import annotations

import hashlib
import random
from dataclasses import replace

from .currentness import ProjectionEpoch
from .semantic_type import SemanticType


def seeded_projection_drift(
    semantic_type: SemanticType,
    epoch: ProjectionEpoch,
    *,
    seed: int,
) -> tuple[SemanticType, ProjectionEpoch, str]:
    rng = random.Random(seed)
    mode = rng.choice(("constraint", "unit", "generation"))
    if mode == "constraint":
        digest = hashlib.sha256(f"{semantic_type.constraints_digest}:{seed}".encode()).hexdigest()
        return replace(semantic_type, constraints_digest=digest), epoch, mode
    if mode == "unit":
        unit = f"urn:qudt:unit:drift:{seed}"
        return replace(semantic_type, unit_iri=unit), epoch, mode
    new_projection = hashlib.sha256(f"{epoch.projection_digest}:{seed}".encode()).hexdigest()
    next_epoch = replace(
        epoch,
        generation=epoch.generation + 1,
        projection_digest=new_projection,
    )
    return semantic_type, next_epoch, mode
