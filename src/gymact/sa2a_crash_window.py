"""Crash-window classification for portable SA2A provider recovery."""
from __future__ import annotations
from enum import StrEnum
class CrashWindow(StrEnum):
    BEFORE_PROPOSAL="before_proposal"; AFTER_PROPOSAL="after_proposal"; UNKNOWN_OUTCOME="unknown_outcome"; AFTER_RECEIPT="after_receipt"
def recovery_for(window:CrashWindow)->str:
    return {CrashWindow.BEFORE_PROPOSAL:"reselect",CrashWindow.AFTER_PROPOSAL:"reconcile",CrashWindow.UNKNOWN_OUTCOME:"reconcile",CrashWindow.AFTER_RECEIPT:"replay_receipt"}[window]
