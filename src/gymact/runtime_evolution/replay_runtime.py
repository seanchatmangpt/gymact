"""Stable evolution replay keys."""

import hashlib
import json


def replay_key(subject: str, epoch: int, evidence: tuple[str, ...]) -> str:
    p = json.dumps(
        {"subject": subject, "epoch": epoch, "evidence": evidence},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(p.encode()).hexdigest()
