"""Real GymAct `Environment`/`EnvironmentProvider` that actuates
`platform-console`'s real `/api/castle/run` route over real HTTP, using a
real service-account `Authorization: Bearer pk_live_...` API key -- never a
human session cookie.

Scope for this first increment (per
`docs/DOD-v26.8.18-FDE-ACTUATION.md` §2 criterion 1 / §4 "Recommended first
real increment"): exactly one narrow, already-in-scope, read-only Castle
verb -- `inventory-components` -- via `POST /api/castle/run`
(`app/app/api/castle/run/route.ts`), resolved against that route's own
fixed `ALLOWED_CASTLE_VERBS` allowlist (`app/lib/castle.ts`). No write/
mutating capability is exposed by this provider. `verify()` polls the real
`GET /api/castle` job list (`app/app/api/castle/route.ts`) for the real Job
this run created, checking its real k8s-observed `status` field (never
trusting the POST's 201 alone), mirroring
`kubernetes_reconciliation.py`'s own "apply exit code is not convergence
evidence" discipline.

Credential contract (matches `app/lib/api-keys.ts` and
`app/middleware.ts` exactly, read in full before writing this module):
  - Header: `Authorization: Bearer pk_live_<43-char base64url>`.
  - Minted for real only via `POST /api/api-keys` (owner-role-gated,
    requires an existing human owner session -- this provider never mints
    its own key, it only consumes one an owner already minted).
  - Read here from the `PLATFORM_CONSOLE_API_KEY` environment variable --
    never hardcoded, never logged, never placed in a Receipt or evidence
    record in plaintext (only a stable, non-reversible reference/prefix is
    ever recorded).
  - `platform-console`'s middleware accepts this header on `/api/*` routes
    only (never page routes) and maps it, via `resolveApiKeyAuth`, onto the
    exact same `requireRole()` authorization path a session cookie uses --
    so a Bearer-authenticated call is gated by the console's own real RBAC,
    unchanged.

This module does not construct its own bypass of GymAct's
`AuthorityResolver`/`CapabilityScope` gates: every `actuate()` call here is
only ever reached through `GymAct.act()` (`kernel.py:569-835`), which
already runs both gates (`kernel.py:679-703` capability-scope check,
`kernel.py:705-762` authority decision) before this environment's
`actuate()` method is invoked at all. This class has no public entry point
that skips `GymAct`.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from uuid import uuid4

import anyio

from gymact.models import Capability, Consequence
from gymact.polling import poll_until_async

_DEFAULT_TIMEOUT_S = 10.0
_DEFAULT_VERIFY_TIMEOUT_S = 20.0
_POLL_INTERVAL_S = 2.0

# The one allowlisted, read-only Castle verb this narrow first increment
# actuates -- matches `ALLOWED_CASTLE_VERBS["inventory-components"]` in
# `app/lib/castle.ts` exactly. Deliberately not configurable: widening the
# verb set actuated here is a separate, later change, not a config knob.
_VERB_ID = "inventory-components"

PLATFORM_CONSOLE_CAPABILITIES = (
    Capability(
        iri="urn:gymact:platform-console:capability:run_inventory_components",
        title=(
            "Run platform-console's real, allowlisted read-only Castle verb "
            "'inventory-components' via POST /api/castle/run. Payload: {} "
            "(no fields accepted -- the verb id is fixed by this capability, "
            "never caller-supplied, matching the console's own server-side "
            "allowlist discipline)."
        ),
        consequence=Consequence.DO,
        binding="run_inventory_components",
    ),
    Capability(
        iri="urn:gymact:platform-console:capability:get_castle_jobs",
        title="Read platform-console's real Castle job list via GET /api/castle.",
        consequence=Consequence.READ,
        binding="get_castle_jobs",
    ),
)


class PlatformConsoleAuthError(RuntimeError):
    """Raised when the configured credential is missing or the console
    rejects it (401/403) -- distinct from a generic HTTP/network failure so
    a caller can tell 'no/invalid credential' apart from 'console
    unreachable'."""


class PlatformConsoleEnvironment:
    """Wraps one real, already-running platform-console deployment.

    Every mutating request carries the real `Authorization: Bearer
    pk_live_...` header read from `PLATFORM_CONSOLE_API_KEY` at
    materialization time. No cookie is ever sent or accepted by this class.
    """

    requires_authority = True

    def __init__(self, *, base_url: str, api_key: str, timeout_s: float = _DEFAULT_TIMEOUT_S) -> None:
        if not api_key.startswith("pk_live_"):
            raise PlatformConsoleAuthError(
                "PLATFORM_CONSOLE_API_KEY does not match the real pk_live_ prefix "
                "minted by POST /api/api-keys (app/lib/api-keys.ts)"
            )
        self.base_url = base_url.rstrip("/") + "/"
        self._api_key = api_key
        self._timeout_s = timeout_s
        self.environment_id = f"urn:gymact:platform-console:environment:{uuid4().hex}"
        self._closed = False
        self._last_run_job_name: str | None = None

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return PLATFORM_CONSOLE_CAPABILITIES

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        self._ensure_open()
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            urljoin(self.base_url, path.lstrip("/")),
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                # Real service-account Bearer key, never a session cookie --
                # this is the entire point of this provider per the DoD.
                "Authorization": f"Bearer {self._api_key}",
            },
        )
        try:
            with urlopen(request, timeout=self._timeout_s) as response:
                status = response.status
                raw = response.read()
        except HTTPError as exc:
            status = exc.code
            raw = exc.read()
            if status in (401, 403):
                raise PlatformConsoleAuthError(
                    f"platform-console rejected the Bearer credential: HTTP {status}"
                ) from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"PLATFORM_CONSOLE_UNREACHABLE:{type(exc).__name__}") from exc
        try:
            value = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            value = {"raw": raw.decode("utf-8", errors="replace")}
        if not isinstance(value, dict):
            value = {"value": value}
        return status, value

    async def _async_request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, Any]]:
        return await anyio.to_thread.run_sync(lambda: self._request(method, path, payload))

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        _, body = await self._async_request("GET", "/api/castle")
        return body

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        binding = capability.binding
        if binding == "run_inventory_components":
            del payload  # capability fixes the verb id; no caller-supplied fields
            status, body = await self._async_request(
                "POST", "/api/castle/run", {"verbId": _VERB_ID}
            )
            job = body.get("job") if isinstance(body, dict) else None
            job_name = job.get("name") if isinstance(job, dict) else None
            if isinstance(job_name, str):
                self._last_run_job_name = job_name
            return {"status": status, "body": body, "job_name": job_name}
        if binding == "get_castle_jobs":
            status, body = await self._async_request("GET", "/api/castle")
            return {"status": status, "body": body}
        raise ValueError(f"unsupported platform-console binding: {binding}")

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Poll the real `GET /api/castle` job list until the job created by
        the last `run_inventory_components` actuation reaches a real
        terminal k8s-observed status (never trusting the POST's 201 alone),
        mirroring `kubernetes_reconciliation.py`'s poll-real-state
        discipline. `expected` may set `{"status": "Complete"}` (or any
        subset of one job's real fields) to require a stricter terminal
        state; an empty `expected` only requires the job to be observed at
        all with a real (non-Pending-forever) status.
        """
        self._ensure_open()
        job_name = self._last_run_job_name
        observed: dict[str, Any] = {}

        async def _check() -> bool:
            nonlocal observed
            _, body = await self._async_request("GET", "/api/castle")
            jobs = body.get("jobs") if isinstance(body, dict) else None
            match = None
            if isinstance(jobs, list) and job_name is not None:
                for item in jobs:
                    if isinstance(item, dict) and item.get("name") == job_name:
                        match = item
                        break
            observed = match or {}
            if not observed:
                return False
            if expected:
                return all(observed.get(key) == value for key, value in expected.items())
            return observed.get("status") in ("Complete", "Failed")

        passed = await poll_until_async(
            _check, timeout_seconds=_DEFAULT_VERIFY_TIMEOUT_S, interval_seconds=_POLL_INTERVAL_S
        )
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {"last_run_job_name": self._last_run_job_name}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        value = checkpoint.get("last_run_job_name")
        self._last_run_job_name = value if isinstance(value, str) else None

    async def teardown(self) -> None:
        # Real Castle Jobs are not deleted by this environment -- they are
        # platform-console's own audit-visible record of a real run, not
        # gymact-owned scratch state (unlike kubernetes_reconciliation.py's
        # own throwaway Pod). Nothing to clean up here.
        self._closed = True


class PlatformConsoleProvider:
    """GymAct `EnvironmentProvider` for a real platform-console deployment.

    `config` keys:
      - `base_url` (required): e.g. `https://platform-console.example.com`
        or a reachable test-tenant URL.
      - `api_key` (optional): overrides the `PLATFORM_CONSOLE_API_KEY`
        environment variable -- still never hardcoded by this module
        itself, only threaded through from whatever real secret store the
        caller reads it from.
      - `timeout_s` (optional, default 10.0).

    A real `GET /api/status` health probe (public per `middleware.ts`'s
    `PUBLIC_PATHS`) is issued at materialization time, matching
    `HTTPJSONProvider`'s own health-gate-before-admission discipline.
    """

    name = "platform-console"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> PlatformConsoleEnvironment:
        del scenario
        base_url = config.get("base_url")
        if not isinstance(base_url, str) or not base_url:
            raise ValueError("PROVIDER_CONFIGURATION_REQUIRED:base_url")
        api_key = config.get("api_key") or os.environ.get("PLATFORM_CONSOLE_API_KEY")
        if not isinstance(api_key, str) or not api_key:
            raise PlatformConsoleAuthError(
                "no credential: set PLATFORM_CONSOLE_API_KEY (a real key minted via "
                "POST /api/api-keys) or pass config.api_key"
            )
        timeout_s = float(config.get("timeout_s", _DEFAULT_TIMEOUT_S))
        environment = PlatformConsoleEnvironment(
            base_url=base_url, api_key=api_key, timeout_s=timeout_s
        )
        status, _ = await environment._async_request("GET", "/api/status")
        if status >= 500:
            raise RuntimeError(f"PLATFORM_CONSOLE_UNHEALTHY:HTTP_{status}")
        return environment
