"""A2A v1 task transport adapter composed over :mod:`gymact.sa2a_envelope`.

Translates an A2A v1 task-shaped payload into an SA2A portable replanning
envelope, admits it through ``gymact.sa2a_envelope.admit_envelope`` with the
producer's ``contract_digest`` carried verbatim (this adapter never inspects,
recomputes, or substitutes the digest), surfaces admission refusals as typed
A2A ``task.failed`` terminal states, and projects an admitted envelope back
out as an A2A artifact carrying :class:`gymact.sa2a_evolution.SA2AEvolutionFeedback`.

Vocabulary check (per ``.claude/rules/ontology.md``): the A2A task/artifact
shapes are the wire vocabulary of the A2A v1 protocol surface; the payload
semantics are SA2A's own portable contract. No GymAct-owned classes were
needed — transport framing only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from gymact.sa2a_envelope import SA2AReplanEnvelope, admit_envelope
from gymact.sa2a_evolution import SA2AEvolutionFeedback, evolution_feedback

_A2A_TASK_FAILED = "failed"
_A2A_DATA_PART_KIND = "data"


def _extract_envelope_payload(task: dict[str, Any]) -> dict[str, Any]:
    """Extract the SA2A envelope JSON from an A2A v1 task's message parts."""
    context_id = task.get("contextId")
    task_id = task.get("taskId")
    if not isinstance(context_id, str) or not context_id:
        raise ValueError("A2A_CONTEXT_ID_REQUIRED")
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("A2A_TASK_ID_REQUIRED")

    message = task.get("message")
    if not isinstance(message, dict):
        raise ValueError("A2A_MESSAGE_REQUIRED")
    parts = message.get("parts")
    if not isinstance(parts, list):
        raise ValueError("A2A_MESSAGE_PARTS_REQUIRED")

    for part in parts:
        if not isinstance(part, dict) or part.get("kind") != _A2A_DATA_PART_KIND:
            continue
        data = part.get("data")
        if isinstance(data, dict) and data.get("schema") == "sa2a/replan-envelope/v1":
            return data

    raise ValueError("A2A_ENVELOPE_PART_NOT_FOUND")


def _task_failed(
    task_id: str, context_id: str, code: str, message: str
) -> dict[str, Any]:
    """A typed, terminal A2A ``task.failed`` state — never a silent no-op."""
    return {
        "id": task_id,
        "contextId": context_id,
        "status": {
            "state": _A2A_TASK_FAILED,
            "message": {
                "role": "agent",
                "parts": [
                    {
                        "kind": "text",
                        "text": message,
                        "metadata": {"errorCode": code},
                    }
                ],
            },
        },
    }


def a2a_task_to_envelope(
    task: dict[str, Any],
) -> SA2AReplanEnvelope | dict[str, Any]:
    """Admit the SA2A envelope carried by an A2A v1 task payload.

    Returns the admitted :class:`SA2AReplanEnvelope` on success, or a typed
    A2A ``task.failed`` terminal dict on refusal. The producer's
    ``contract_digest`` is passed to ``admit_envelope`` verbatim.
    """
    context_id = task.get("contextId")
    task_id = task.get("taskId")
    try:
        payload = _extract_envelope_payload(task)
    except ValueError as exc:
        return _task_failed(
            task_id if isinstance(task_id, str) else "",
            context_id if isinstance(context_id, str) else "",
            str(exc),
            f"SA2A transport refusal: {exc}",
        )

    try:
        return admit_envelope(payload)
    except ValidationError as exc:
        code = _refusal_code(exc)
        return _task_failed(task_id, context_id, code, f"SA2A transport refusal: {code}")


def _refusal_code(exc: ValidationError) -> str:
    """Surface the typed SA2A refusal reason (e.g. SA2A_EXACT_SUBJECT_MISMATCH)."""
    for error in exc.errors():
        message = str(error.get("msg", ""))
        ctx = error.get("ctx", {}) or {}
        for candidate in [message, str(ctx.get("error"))]:
            index = candidate.find("SA2A_")
            if index != -1:
                return candidate[index:].strip("'\"")
    return "SA2A_ENVELOPE_INVALID"


def envelope_to_artifact(
    value: SA2AReplanEnvelope | dict[str, Any],
) -> dict[str, Any]:
    """Project an admitted envelope as an A2A artifact carrying evolution feedback."""
    envelope = admit_envelope(value)
    feedback: SA2AEvolutionFeedback = evolution_feedback(envelope)
    return {
        "artifactId": f"sa2a-evolution-feedback-{feedback.receipt_id}",
        "name": "SA2A Evolution Feedback",
        "parts": [
            {
                "kind": _A2A_DATA_PART_KIND,
                "data": feedback.model_dump(mode="json"),
            }
        ],
    }
