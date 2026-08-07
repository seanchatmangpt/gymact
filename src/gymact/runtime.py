"""Public GymAct runtime over the hardened semantic kernel."""

from __future__ import annotations

import rfc8785

from gymact.kernel import BoundaryBlocked
from gymact.kernel import GymAct as _KernelGymAct


class GymAct(_KernelGymAct):
    """Public kernel with RFC8785 failures promoted to typed boundary standing."""

    def _ensure_input(self, value: object) -> None:
        try:
            super()._ensure_input(value)
        except rfc8785.CanonicalizationError as exc:
            raise BoundaryBlocked("INPUT_NOT_RFC8785_CANONICAL") from exc

    def _ensure_state(self, value: object) -> None:
        try:
            super()._ensure_state(value)
        except rfc8785.CanonicalizationError as exc:
            raise BoundaryBlocked("STATE_NOT_RFC8785_CANONICAL") from exc

    def _ensure_checkpoint(self, value: object) -> None:
        try:
            super()._ensure_checkpoint(value)
        except rfc8785.CanonicalizationError as exc:
            raise BoundaryBlocked("CHECKPOINT_NOT_RFC8785_CANONICAL") from exc


__all__ = ["BoundaryBlocked", "GymAct"]
