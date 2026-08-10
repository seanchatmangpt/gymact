from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Effect(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    BIND = "BIND"
    UNBIND = "UNBIND"
    TRANSITION = "TRANSITION"
    INVOKE = "INVOKE"


@dataclass(frozen=True, slots=True)
class CloudOperation:
    cloud: str
    service: str
    operation: str
    effect: Effect
    scope: str
    region: str
    resource_type: str
    name: str
    resource_id: str | None
    properties: dict[str, Any]
    depends_on: tuple[str, ...]
    visibility_delay: int

    @classmethod
    def from_payload(cls, cloud: str, payload: dict[str, Any]) -> "CloudOperation":
        return cls(
            cloud=cloud,
            service=_required(payload, "service"),
            operation=_required(payload, "operation"),
            effect=Effect(_required(payload, "effect").upper()),
            scope=_optional(payload, "scope", "prod"),
            region=_optional(payload, "region", "us-east"),
            resource_type=_optional(payload, "resource_type", "resource"),
            name=_optional(payload, "name", "operation"),
            resource_id=_optional_nullable(payload, "resource_id"),
            properties=_object(payload, "properties"),
            depends_on=tuple(_strings(payload, "depends_on")),
            visibility_delay=_nonnegative_int(payload, "visibility_delay", 0),
        )


def normalize_quotas(value: object | None) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("config.quotas must be an object")
    result: dict[str, int] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not key:
            raise ValueError("quota keys must be non-empty strings")
        if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
            raise ValueError("quota values must be non-negative integers")
        result[key] = raw
    return result


def normalize_faults(value: object | None) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("config.faults must be an object")
    result: dict[str, int] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not key:
            raise ValueError("fault keys must be non-empty operation keys")
        if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
            raise ValueError("fault counts must be non-negative integers")
        result[key] = raw
    return result


def copy_json(value: Any) -> Any:
    return deepcopy(value)


def _required(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"payload.{key} must be a non-empty string")
    return value.strip()


def _optional(payload: dict[str, Any], key: str, default: str) -> str:
    value = payload.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"payload.{key} must be a non-empty string")
    return value.strip()


def _optional_nullable(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"payload.{key} must be a non-empty string when supplied")
    return value.strip()


def _object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key, {})
    if not isinstance(value, dict):
        raise TypeError(f"payload.{key} must be an object")
    return copy_json(value)


def _strings(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise TypeError(f"payload.{key} must be an array")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"payload.{key} entries must be non-empty strings")
        result.append(item.strip())
    return result


def _nonnegative_int(payload: dict[str, Any], key: str, default: int) -> int:
    value = payload.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"payload.{key} must be a non-negative integer")
    return value
