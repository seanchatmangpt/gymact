from __future__ import annotations

import hashlib

from .replica import ReplicaProjection

def audit_root(observations: tuple[ReplicaProjection, ...]) -> str:
    leaves = sorted(item.fingerprint for item in observations)
    if not leaves:
        return hashlib.sha256(b"").hexdigest()
    level = leaves
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            hashlib.sha256((level[index] + level[index + 1]).encode()).hexdigest()
            for index in range(0, len(level), 2)
        ]
    return level[0]
