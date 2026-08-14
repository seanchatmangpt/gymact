# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Incremental OCEL 2.0 recording for :mod:`gymact.powl` pipelines.

Satisfies the ``OcelRecorderLike`` structural contract that
:mod:`gymact.powl.runner` (and, on the autofde-lab side,
``gymact_pipeline.py``'s ``run_pipeline`` caller) needs: a per-session
accumulator with ``record(activity=..., objects=..., outcome=...)`` called
once per real pipeline step, and ``close()`` returning a validated OCEL 2.0
JSON-shaped ``dict``.

Zero ``autofde_lab`` imports. This module is gymact-native: it reuses only
this repo's own real OCEL machinery --
:func:`gymact.ocel.validate_ocel_log` (checks a log against the real,
vendored OCEL 2.0 JSON Schema) and :func:`gymact.ocel.digest_ocel_log`
(real sha256 over the log's canonical JSON serialization). Both are
shape-agnostic: they operate on a raw OCEL2 JSON ``dict`` regardless of how
it was produced, so reusing them here does not require pulling in
:func:`gymact.ocel.receipts_to_ocel`'s `Receipt`-batch shape, which this
module's incremental, single-event-at-a-time recording does not match.

Deliberately narrower reuse than "reuse gymact.ocel wholesale" -- per this
design's own rejection of forcing every incremental call through a
synthetic ``Receipt``: ``receipts_to_ocel``, ``write_ocel_log``,
``MemoryReceiptLedger``, and ``evidence_graph`` are not used here, only the
two shape-agnostic functions named above.
"""

from __future__ import annotations

import datetime
import itertools
from typing import Any, Iterable, Mapping

from gymact.ocel import digest_ocel_log, validate_ocel_log

__all__ = ["GymactOcelSessionRecorder"]


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class GymactOcelSessionRecorder:
    """Incremental OCEL2-JSON-dict accumulator.

    Satisfies :class:`gymact.powl.spec.OcelRecorderLike` (a structural
    ``Protocol`` with ``record`` and ``close``) once ``gymact/powl/spec.py``
    exists; this module has no import-time dependency on that file, so it
    is usable standalone.

    Not thread-safe -- single-writer, the same discipline
    ``autofde_lab.ocel.mcp_instrumentation.OcelSessionRecorder`` documents
    for its own accumulator on the autofde-lab side. ``gymact.powl.runner``
    already serializes all ``.record()`` calls onto the calling thread (its
    concurrent-batch path finishes each worker's real execution before any
    OCEL recording happens), so this constraint is honored by construction
    at the one real call site, not merely documented here.
    """

    def __init__(self, session_id: str, *, server_name: str = "gymact-powl-runner") -> None:
        self._session_id = session_id
        self._declared_object_ids: set[str] = {session_id}
        self._event_counter = itertools.count()
        self._objects: list[dict[str, Any]] = [
            {
                "id": session_id,
                "type": "PowlSession",
                "attributes": [
                    {"name": "server", "value": server_name, "time": _utc_now_iso()}
                ],
            }
        ]
        self._object_types: dict[str, dict[str, Any]] = {
            "PowlSession": {"name": "PowlSession", "attributes": []}
        }
        self._events: list[dict[str, Any]] = []
        self._event_types: dict[str, dict[str, Any]] = {}

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def log(self) -> dict[str, Any]:
        """Unvalidated snapshot as of the last :meth:`record` call."""
        return self._build_log()

    def ensure_object(self, object_id: str, object_type: str) -> None:
        """Declare ``object_id`` (type ``object_type``) if not already present.

        Idempotent -- a real repeated call with the same ``object_id`` is a
        no-op, matching how :meth:`record` re-declares an object on every
        event that touches it without duplicating the underlying OCEL
        object entry.
        """
        if object_id in self._declared_object_ids:
            return
        self._declared_object_ids.add(object_id)
        self._objects.append({"id": object_id, "type": object_type, "attributes": []})
        self._object_types.setdefault(object_type, {"name": object_type, "attributes": []})

    def record(
        self,
        *,
        activity: str,
        objects: Iterable[tuple[str, str]],
        outcome: Mapping[str, Any],
    ) -> None:
        """Append one real OCEL event for one real pipeline-step occurrence.

        ``objects`` is ``(object_id, object_type)`` pairs for every real
        domain object this event touches, beyond the session object itself
        (which every event is linked to automatically, qualifier
        ``"PowlSession"``). ``outcome`` becomes the event's attributes --
        every key copied verbatim; values are coerced with ``str()``, since
        the real OCEL 2.0 JSON Schema (vendored at
        ``gymact/schemas/ocel20-schema.json``) requires every event
        attribute ``value`` to be a JSON string, not any JSON type -- the
        same convention :func:`gymact.ocel.receipts_to_ocel` already
        follows for its own attribute values (e.g. ``str(receipt.verified)``).
        """
        object_ids_and_types = [(self._session_id, "PowlSession")]
        object_ids_and_types.extend(objects)

        relationships = []
        for object_id, object_type in object_ids_and_types:
            self.ensure_object(object_id, object_type)
            relationships.append({"objectId": object_id, "qualifier": object_type})

        self._event_types.setdefault(activity, {"name": activity, "attributes": []})
        self._events.append(
            {
                "id": f"e{next(self._event_counter)}",
                "type": activity,
                "time": _utc_now_iso(),
                "attributes": [{"name": k, "value": str(v)} for k, v in outcome.items()],
                "relationships": relationships,
            }
        )

    def _build_log(self) -> dict[str, Any]:
        return {
            "eventTypes": list(self._event_types.values()),
            "objectTypes": list(self._object_types.values()),
            "events": list(self._events),
            "objects": list(self._objects),
        }

    def close(self) -> dict[str, Any]:
        """Validate against the real OCEL2 JSON Schema
        (:func:`gymact.ocel.validate_ocel_log`) before returning -- raises
        ``jsonschema.exceptions.ValidationError`` on a malformed log rather
        than returning it silently, matching
        ``autofde_lab.ocel.log.OcelLog.validate()``'s eager-raise contract
        on the autofde-lab side (this module has no import on that class;
        the contract is matched by convention, not by shared code).
        """
        log = self._build_log()
        validate_ocel_log(log)
        return log

    def digest(self) -> str:
        """Convenience: :func:`gymact.ocel.digest_ocel_log` over
        :meth:`close`'s output. Calling this validates the log as a side
        effect (via ``close()``) before digesting it."""
        return digest_ocel_log(self.close())
