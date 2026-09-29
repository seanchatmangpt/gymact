"""Portable SA2A contract for GymAct advice/evolution consumers."""
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Candidate:
    subject: str
    effect_id: str
    generation: int
    provider: str
    replay_key: str
    authority: str = "none"

    def admit(self, expected_subject: str, generation: int) -> None:
        if self.authority != "none": raise ValueError("authority_refused")
        if self.subject != expected_subject: raise ValueError("subject_mismatch")
        if self.generation != generation: raise ValueError("stale_candidate")
        if not self.effect_id or not self.replay_key: raise ValueError("identity_required")
