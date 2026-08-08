"""Real network provider using an explicit JSON-over-HTTP executable-world contract."""
from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

import anyio

from gymact.models import Capability, Consequence


def _partial_match(observed: object, expected: object) -> bool:
    if isinstance(expected, dict):
        return isinstance(observed, dict) and all(
            key in observed and _partial_match(observed[key], value)
            for key, value in expected.items()
        )
    return observed == expected


HTTP_JSON_CAPABILITIES = (
    Capability(
        iri="urn:gymact:http-json:capability:set",
        title="Set a value through the admitted JSON-over-HTTP effector",
        consequence=Consequence.DO,
        binding="set",
    ),
    Capability(
        iri="urn:gymact:http-json:capability:delete",
        title="Delete a value through the admitted JSON-over-HTTP effector",
        consequence=Consequence.DO,
        binding="delete",
    ),
)


class HTTPJSONEnvironment:
    """Networked environment with mutation and observation on separate HTTP calls."""

    requires_authority = True

    def __init__(
        self,
        *,
        base_url: str,
        state_path: str = "/state",
        action_path: str = "/act",
        restore_path: str = "/restore",
        timeout_s: float = 5.0,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.state_path = state_path
        self.action_path = action_path
        self.restore_path = restore_path
        self.timeout_s = timeout_s
        self.environment_id = f"urn:gymact:http-json:environment:{uuid4().hex}"
        self._closed = False

    def _open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._open()
        return HTTP_JSON_CAPABILITIES

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._open()
        body = None if payload is None else json.dumps(payload, sort_keys=True).encode("utf-8")
        request = Request(
            urljoin(self.base_url, path.lstrip("/")),
            data=body,
            method=method,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout_s) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError(f"HTTP_PROVIDER_ERROR:{type(exc).__name__}") from exc
        value = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(value, dict):
            raise RuntimeError("HTTP_PROVIDER_RESPONSE_NOT_OBJECT")
        return value

    async def _async_request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await anyio.to_thread.run_sync(lambda: self._request(method, path, payload))

    async def observe(self) -> dict[str, Any]:
        return await self._async_request("GET", self.state_path)

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        if capability not in HTTP_JSON_CAPABILITIES:
            raise ValueError("UNSUPPORTED_OPERATION")
        return await self._async_request(
            "POST",
            self.action_path,
            {"operation": capability.binding, "payload": payload},
        )

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        observed = await self.observe()
        return _partial_match(observed, expected), observed

    async def checkpoint(self) -> dict[str, Any]:
        return {"state": await self.observe()}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        state = checkpoint.get("state")
        if not isinstance(state, dict):
            raise TypeError("checkpoint.state must be an object")
        await self._async_request("POST", self.restore_path, {"state": state})

    async def teardown(self) -> None:
        self._closed = True


class HTTPJSONProvider:
    """Provider for real network services implementing GymAct's tiny HTTP JSON profile."""

    name = "http-json"
    materialization_requires_authority = False

    async def materialize(
        self,
        *,
        scenario: str | None,
        config: dict[str, Any],
    ) -> HTTPJSONEnvironment:
        del scenario
        base_url = config.get("base_url")
        if not isinstance(base_url, str) or not base_url:
            raise ValueError("PROVIDER_CONFIGURATION_REQUIRED")
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("PROVIDER_CONFIGURATION_REQUIRED")
        timeout_s = float(config.get("timeout_s", 5.0))
        if timeout_s <= 0:
            raise ValueError("PROVIDER_CONFIGURATION_REQUIRED")
        environment = HTTPJSONEnvironment(
            base_url=base_url,
            state_path=str(config.get("state_path", "/state")),
            action_path=str(config.get("action_path", "/act")),
            restore_path=str(config.get("restore_path", "/restore")),
            timeout_s=timeout_s,
        )
        health_path = str(config.get("health_path", "/health"))
        health = await environment._async_request("GET", health_path)
        if health.get("ok") is not True:
            raise ValueError("PROVIDER_CONFIGURATION_REQUIRED")
        return environment
