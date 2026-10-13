"""Castle feed: gymact `Receipt` batch -> castle-ingestible OCEL ndjson.

The middle adapter between gymact's real receipt trail (see
`gymact.ocel.receipts_to_ocel`, the OCEL 2.0 official-schema export) and
castle's OCEL ingestion surface. Castle has exactly one OCEL JSON parser:
`castle::xaas_feed::parse_xaas_ndjson` (castle `src/xaas_feed.rs`), the
`:xaas_ocel_prefixed` dialect -- each ndjson line is a complete OCEL 2.0
document carrying all four top-level keys as arrays under `ocel:`-prefixed
names, with events `{id, type, time, attributes, relationships}` (closed
vocabulary), objects `{id, type, attributes}`, type declarations as
non-empty strings or `{"name": ...}`, ISO8601 zero-UTC event times, and
relationships exactly `{objectId, qualifier}` resolving to a declared
object.

ISOLATION LAW: this module imports only `gymact` + stdlib. No
`autofde_lab`, no `castle` import; the wire contract is re-stated here as
the converter's emission law and mirrored by `validate_castle_feed_line`
so a drift between this emitter and castle's parser is a test failure,
not a runtime surprise.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from gymact.models import Receipt

EVENT_KEYS = ("id", "type", "time", "attributes", "relationships")
OBJECT_KEYS = ("id", "type", "attributes")
TOP_KEYS = ("ocel:objectTypes", "ocel:eventTypes", "ocel:events", "ocel:objects")

#: Invariants: the feed confers no DO authority and is observation-only
#: provenance. Emitted on every event so castle-side consumers can gate on
#: them structurally.
AUTHORITY_ATTRIBUTE_VALUE = "none"
PROVENANCE_ATTRIBUTE_VALUE = "observation_only"

_UTC_ZERO_OFFSETS = ("Z", "+00:00", "-00:00")


class CastleFeedRefused(Exception):
    """Fail-closed: one or more typed violations; conversion is all-or-nothing."""

    def __init__(self, violations: list["Violation"]) -> None:
        self.violations = violations
        super().__init__(
            "; ".join(f"{v.path}: {v.reason}" for v in violations)
        )


class Violation:
    """One typed refusal: exact receipt path + structural reason."""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Violation({self.path!r}, {self.reason!r})"


def receipts_to_castle_ndjson(
    receipts: Sequence[Any],
    *,
    timestamps: Sequence[str] | None = None,
) -> str:
    """Convert one batch of real gymact `Receipt`s to castle ndjson lines.

    One line per receipt; each line is a complete OCEL 2.0 document in the
    `:xaas_ocel_prefixed` dialect castle's `parse_xaas_ndjson` accepts.
    Cross-line assembly follows castle's merge law: objects deduplicate by
    id (first occurrence wins), events concatenate in batch order.

    `timestamps` (optional, caller-supplied): one zero-UTC ISO8601 string
    per receipt, used as the event time instead of `Receipt.occurred_at`.
    Every emitted time is validated against castle's zero-UTC law before
    emission -- an unparseable time refuses the whole batch.

    Fail-closed: any malformed receipt refuses the WHOLE batch with typed
    `CastleFeedRefused` violations naming the exact path.
    """
    if not receipts:
        raise CastleFeedRefused(
            [Violation("receipts", "REFUSED:EMPTY_RECEIPT_BATCH: cannot build a feed from zero receipts")]
        )

    if timestamps is not None and len(timestamps) != len(receipts):
        raise CastleFeedRefused(
            [
                Violation(
                    "timestamps",
                    f"REFUSED:TIMESTAMP_BATCH_LENGTH_MISMATCH: got {len(timestamps)} "
                    f"timestamps for {len(receipts)} receipts",
                )
            ]
        )

    violations: list[Violation] = []
    for index, item in enumerate(receipts):
        if not isinstance(item, Receipt):
            violations.append(
                Violation(
                    f"receipts[{index}]",
                    f"REFUSED:NOT_A_GYMACT_RECEIPT: got {type(item).__name__}",
                )
            )
            continue
        if not (isinstance(item.receipt_id, str) and item.receipt_id):
            violations.append(
                Violation(
                    f"receipts[{index}].receipt_id",
                    "REFUSED:INVALID_RECEIPT_ID: must be a non-empty string",
                )
            )
        if not (isinstance(item.episode_id, str) and item.episode_id):
            violations.append(
                Violation(
                    f"receipts[{index}].episode_id",
                    "REFUSED:INVALID_EPISODE_ID: must be a non-empty string",
                )
            )
        event_time = item.occurred_at if timestamps is None else timestamps[index]
        if reason := _zero_utc_time_reason(event_time):
            violations.append(
                Violation(
                    f"receipts[{index}].{('occurred_at' if timestamps is None else 'timestamps')}[{index}]",
                    f"REFUSED:INVALID_EVENT_TIME: {reason}",
                )
            )

    if violations:
        raise CastleFeedRefused(violations)

    # Deterministic emission: attributes in a fixed order, objects sorted,
    # canonical JSON (sorted keys, compact separators). Two runs over the
    # same receipt batch produce identical bytes.
    lines: list[str] = []
    seen_object_ids: set[str] = set()
    for index, receipt in enumerate(receipts):
        assert isinstance(receipt, Receipt)  # validated above
        event_time = receipt.occurred_at if timestamps is None else timestamps[index]

        object_specs: list[tuple[str, str]] = [("episode", receipt.episode_id)]
        if receipt.subject_ref:
            object_specs.append(("environment", receipt.subject_ref))
        if receipt.capability_ref:
            object_specs.append(("capability", receipt.capability_ref))

        objects: list[dict[str, Any]] = []
        relationships: list[dict[str, str]] = []
        for obj_type, obj_id in object_specs:
            if obj_id in seen_object_ids:
                continue
            seen_object_ids.add(obj_id)
            objects.append({"id": obj_id, "type": obj_type, "attributes": {}})
            relationships.append({"objectId": obj_id, "qualifier": obj_type})

        attributes: dict[str, str] = {
            "authority": AUTHORITY_ATTRIBUTE_VALUE,
            "provenance": PROVENANCE_ATTRIBUTE_VALUE,
            "standing": str(receipt.standing.value),
        }
        if receipt.reason is not None:
            attributes["reason"] = receipt.reason
        if receipt.subject_ref:
            attributes["subject_ref"] = receipt.subject_ref

        event = {
            "id": receipt.receipt_id,
            "type": receipt.operation.value,
            "time": event_time,
            "attributes": attributes,
            "relationships": relationships,
        }

        doc = {
            "ocel:objectTypes": [{"name": t} for t in sorted({t for t, _ in object_specs})],
            "ocel:eventTypes": [{"name": receipt.operation.value}],
            "ocel:events": [event],
            "ocel:objects": objects,
        }
        lines.append(json.dumps(doc, sort_keys=True, separators=(",", ":")))

    return "\n".join(lines)


def validate_castle_feed_line(line: str) -> None:
    """Mirror castle's `parse_xaas_ndjson` line law; raise `CastleFeedRefused`.

    Emitter-side check (kept in lockstep with castle `src/xaas_feed.rs`):
    closed vocabulary, required keys, non-empty string ids, declared types,
    ISO8601 zero-UTC event time, attributes object, relationships exactly
    `{objectId, qualifier}` resolving to an object declared on the same
    line. Raises naming the exact violation; returns None on success.
    """
    violations: list[Violation] = []

    try:
        doc = json.loads(line)
    except json.JSONDecodeError as exc:
        raise CastleFeedRefused([Violation("line", f"malformed JSON: {exc}")]) from exc

    if not isinstance(doc, dict):
        raise CastleFeedRefused([Violation("line", "top level must be a JSON object")])

    for key in TOP_KEYS:
        if not isinstance(doc.get(key), list):
            violations.append(Violation(f"line.{key}", "must be an array"))

    event_type_names = _declaration_names(doc, "ocel:eventTypes", violations)
    object_type_names = _declaration_names(doc, "ocel:objectTypes", violations)

    objects: dict[str, str] = {}
    for i, obj in enumerate(doc.get("ocel:objects") or []):
        base = f"ocel:objects[{i}]"
        if not isinstance(obj, dict):
            violations.append(Violation(base, "must be a JSON object"))
            continue
        for key in obj:
            if key not in OBJECT_KEYS:
                violations.append(Violation(f"{base}.{key}", f"unexpected key '{key}' (closed vocabulary)"))
        for key in OBJECT_KEYS:
            if key not in obj:
                violations.append(Violation(f"{base}.{key}", "missing required key"))
        if violations and violations[-1].path.startswith(base):
            continue
        obj_id = obj.get("id")
        if not (isinstance(obj_id, str) and obj_id):
            violations.append(Violation(f"{base}.id", "must be a non-empty string"))
        elif obj_id in objects:
            violations.append(Violation(f"{base}.id", f"duplicate id '{obj_id}'"))
        else:
            objects[obj_id] = obj.get("type", "")

    events = doc.get("ocel:events") or []
    if not events:
        violations.append(Violation("ocel:events", "must carry at least one event"))

    for i, event in enumerate(events):
        base = f"ocel:events[{i}]"
        if not isinstance(event, dict):
            violations.append(Violation(base, "must be a JSON object"))
            continue
        for key in event:
            if key not in EVENT_KEYS:
                violations.append(Violation(f"{base}.{key}", f"unexpected key '{key}' (closed vocabulary)"))
        for key in EVENT_KEYS:
            if key not in event:
                violations.append(Violation(f"{base}.{key}", "missing required key"))

        event_id = event.get("id")
        if not (isinstance(event_id, str) and event_id):
            violations.append(Violation(f"{base}.id", "must be a non-empty string"))

        event_type = event.get("type")
        if not (isinstance(event_type, str) and event_type):
            violations.append(Violation(f"{base}.type", "must be a non-empty string"))
        elif event_type not in event_type_names:
            violations.append(
                Violation(f"{base}.type", f"'{event_type}' not declared in ocel:eventTypes")
            )

        time_value = event.get("time")
        if not isinstance(time_value, str):
            violations.append(
                Violation(f"{base}.time", "must be an ISO8601 string with zero UTC offset")
            )
        elif reason := _zero_utc_time_reason(time_value):
            violations.append(Violation(f"{base}.time", reason))

        if not isinstance(event.get("attributes"), dict):
            violations.append(Violation(f"{base}.attributes", "must be an object"))

        rels = event.get("relationships")
        if rels is not None:
            if not isinstance(rels, list):
                violations.append(Violation(f"{base}.relationships", "must be an array"))
            else:
                for j, rel in enumerate(rels):
                    if not isinstance(rel, dict) or set(rel) != {"objectId", "qualifier"}:
                        violations.append(
                            Violation(
                                f"{base}.relationships[{j}]",
                                "must be exactly {objectId, qualifier}, both strings",
                            )
                        )
                    elif (oid := rel["objectId"]) not in objects:
                        violations.append(
                            Violation(
                                f"{base}.relationships[{j}]",
                                f"objectId '{oid}' does not resolve to any object in ocel:objects",
                            )
                        )

    if violations:
        raise CastleFeedRefused(violations)


def _declaration_names(doc: dict[str, Any], key: str, violations: list[Violation]) -> set[str]:
    names: set[str] = set()
    for i, decl in enumerate(doc.get(key) or []):
        if isinstance(decl, str):
            if decl:
                names.add(decl)
            else:
                violations.append(Violation(f"{key}[{i}]", "must be a non-empty string"))
        elif isinstance(decl, dict) and set(decl) == {"name"} and isinstance(decl["name"], str) and decl["name"]:
            names.add(decl["name"])
        else:
            violations.append(
                Violation(
                    f"{key}[{i}]",
                    'malformed type declaration: must be a non-empty string or {"name": "..."}',
                )
            )
    return names


def _zero_utc_time_reason(t: str) -> str | None:
    """Zero-UTC ISO8601 law (`YYYY-MM-DDTHH:MM:SS(.fff...)?Z` / `+00:00`)."""
    if not isinstance(t, str) or len(t) < 20:
        return f"'{t}' is not a parseable ISO8601 time with zero UTC offset"
    if not (t[4] == "-" and t[7] == "-" and t[10] == "T" and t[13] == ":" and t[16] == ":"):
        return f"'{t}' is not a parseable ISO8601 time with zero UTC offset"
    for suffix in _UTC_ZERO_OFFSETS:
        if t.endswith(suffix):
            # `Z` requires at least seconds precision before it.
            if suffix == "Z" and len(t) < 20:
                return f"'{t}' is not a parseable ISO8601 time with zero UTC offset"
            return None
    return f"'{t}' is not a parseable ISO8601 time with zero UTC offset"
