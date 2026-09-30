"""Composition root for GymAct's authority-free SA2A consumer runtime."""
from dataclasses import dataclass, field
from .providers import ProviderRegistry
from .replay import ReplayIndex
from .receipts import Receipt, receipt_for
from .envelope import Envelope

@dataclass(slots=True)
class ConsumerRuntime:
    providers: ProviderRegistry
    replay: ReplayIndex = field(default_factory=ReplayIndex)

    def admit(self, envelope: Envelope, subject: str, generation: int) -> Envelope:
        envelope.candidate.admit(subject,generation)
        return self.providers.select(envelope)

    def seal(self, envelope: Envelope) -> Receipt:
        receipt=receipt_for(envelope); self.replay.record(receipt); return receipt
