"""Real local GymAct server for the cross-runtime GymActEx Chicago court."""

from __future__ import annotations

import os

import uvicorn

from gymact.providers import MemoryProvider
from gymact.runtime import GymAct
from gymact.surfaces.fastapi import create_app


def build_app():
    """Reference runtime, not ProductionGymAct, so the generic ACT port is exercisable."""
    runtime = GymAct()
    runtime.register_provider(MemoryProvider())
    return create_app(runtime)


app = build_app()


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.environ.get("GYMACT_CHICAGO_HOST", "127.0.0.1"),
        port=int(os.environ.get("GYMACT_CHICAGO_PORT", "8765")),
        log_level="warning",
    )
