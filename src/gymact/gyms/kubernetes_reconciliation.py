"""Real GymAct `Environment`/`EnvironmentProvider` backed by a real local
Kubernetes cluster (`kind`, running on the real local Docker daemon via
colima) -- not simulated.

Unlike `cube_container_counter.py` (`materialize()` provisions a real Docker
container and probes it once via `container.exec`), this provider's harder
edge is `verify()`: a `kubectl apply` succeeding only means the API server
accepted the manifest, not that the pod is actually running. `verify()`
here polls REAL cluster-observed state (`kubectl get pod <name> -o json`,
checking the real `.status.phase` field) until it reaches `Running` (or a
bounded timeout elapses) -- it never treats `kubectl apply`'s zero exit code
as convergence evidence by itself.

No Python Kubernetes client library is used (none is a gymact dependency --
see pyproject.toml); this matches `discovered.py`'s subprocess pattern:
`kubectl apply -f -` / `kubectl get ... -o json` / `kubectl delete` are real
subprocess calls against a real cluster, with real captured stdout/stderr as
evidence. A subject that fails to converge reaches a real `BLOCKED` standing
via `actuate`/`verify`'s returned observation, not a fabricated success.

Requires a real, reachable Kubernetes cluster (`kubectl cluster-info` must
succeed against the current kubeconfig context) -- e.g. a local `kind` or
`k3d` cluster on top of the existing colima Docker daemon, or
`colima start --kubernetes`. Gated via `gymact.standing.require_standing` in
tests, never mocked when genuinely absent.
"""

from __future__ import annotations

import json
import subprocess
import time
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

_MAX_CAPTURED_OUTPUT = 4000
_DEFAULT_NAMESPACE = "default"
_POLL_INTERVAL_SECONDS = 1.0
_DEFAULT_VERIFY_TIMEOUT_SECONDS = 60.0
_DEFAULT_TEARDOWN_TIMEOUT_SECONDS = 60.0

KUBERNETES_RECONCILIATION_CAPABILITIES = (
    Capability(
        iri="urn:gymact:kubernetes-reconciliation:capability:scale_restart",
        title="Delete and reapply the pod manifest to force real rescheduling",
        consequence=Consequence.DO,
        binding="scale_restart",
    ),
    Capability(
        iri="urn:gymact:kubernetes-reconciliation:capability:get_status",
        title="Read the real cluster-observed pod phase",
        consequence=Consequence.READ,
        binding="get_status",
    ),
)


def _run_kubectl(
    args: list[str], *, input_text: str | None = None, timeout: float = 30.0
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["kubectl", *args],
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _truncate(text: str) -> str:
    return text[-_MAX_CAPTURED_OUTPUT:]


def _pod_manifest(name: str, namespace: str) -> str:
    """One minimal, real Pod manifest running kubernetes-goat's real
    `batch-check` scenario container image.

    Targets `madhuakula/k8s-goat-batch-check`, the image used by
    `scenarios/batch-check/job.yaml` in the real, checked-out
    https://github.com/madhuakula/kubernetes-goat repo (see
    `~/autofde-lab/vendor/gyms/kubernetes-goat`). `batch-check` was chosen as
    the smallest, safest real scenario in that repo: a single-container
    `batch/v1` Job with `restartPolicy: Never`, no attached Service, and none
    of hostPath volumes, `privileged: true`, `hostNetwork`, or NodePort
    Services that several other kubernetes-goat scenarios use (e.g.
    `system-monitor`, `health-check`). This provider expresses the same
    container as a bare `Pod` (rather than a `Job`/`Deployment`) to keep the
    existing materialize/verify/scale_restart/teardown Pod-phase-polling
    design unchanged.
    """
    return json.dumps(
        {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": {"app": "gymact-kubernetes-reconciliation"},
            },
            "spec": {
                "restartPolicy": "Never",
                "containers": [
                    {
                        "name": "batch-check",
                        "image": "madhuakula/k8s-goat-batch-check",
                    }
                ],
            },
        }
    )


def _get_pod_json(name: str, namespace: str) -> dict[str, Any] | None:
    """Real `kubectl get pod <name> -o json` against the real cluster.

    Returns None if the pod is not found (real "NotFound" observed state,
    e.g. after real deletion), the parsed pod object otherwise.
    """
    result = _run_kubectl(["get", "pod", name, "-n", namespace, "-o", "json"])
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _pod_phase(pod_json: dict[str, Any] | None) -> str:
    if pod_json is None:
        return "NotFound"
    return str(pod_json.get("status", {}).get("phase", "Unknown"))


class KubernetesReconciliationEnvironment:
    """Wraps one real Pod on one real Kubernetes cluster.

    `materialize()` (via `__init__`) applies a real minimal manifest through
    a real `kubectl apply -f -` subprocess call against the real cluster
    identified by `kubeconfig_context` (or the current context if None).
    """

    def __init__(
        self,
        *,
        namespace: str = _DEFAULT_NAMESPACE,
        kubeconfig_context: str | None = None,
        requires_authority: bool = False,
        verify_timeout_seconds: float = _DEFAULT_VERIFY_TIMEOUT_SECONDS,
        teardown_timeout_seconds: float = _DEFAULT_TEARDOWN_TIMEOUT_SECONDS,
    ) -> None:
        self.environment_id = f"urn:gymact:kubernetes-reconciliation:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._namespace = namespace
        self._context = kubeconfig_context
        self._verify_timeout = verify_timeout_seconds
        self._teardown_timeout = teardown_timeout_seconds
        self._pod_name = f"gymact-kr-{uuid4().hex[:12]}"
        self._closed = False

        args = ["apply", "-f", "-"]
        if self._context:
            args = ["--context", self._context, *args]
        # Real kubectl apply against the real cluster.
        result = _run_kubectl(
            args, input_text=_pod_manifest(self._pod_name, self._namespace), timeout=30.0
        )
        self._last_apply = {
            "returncode": result.returncode,
            "stdout": _truncate(result.stdout),
            "stderr": _truncate(result.stderr),
        }
        if result.returncode != 0:
            raise RuntimeError(
                f"kubectl apply failed for pod {self._pod_name!r} in namespace "
                f"{self._namespace!r}: {_truncate(result.stderr)}"
            )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return KUBERNETES_RECONCILIATION_CAPABILITIES

    def _kubectl_args(self, *args: str) -> list[str]:
        if self._context:
            return ["--context", self._context, *args]
        return list(args)

    def _state(self) -> dict[str, Any]:
        pod_json = _get_pod_json(self._pod_name, self._namespace)
        phase = _pod_phase(pod_json)
        return {
            "pod_name": self._pod_name,
            "namespace": self._namespace,
            "phase": phase,
            "running": phase == "Running",
        }

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return self._state()

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        self._ensure_open()
        before = self._state()
        binding = capability.binding
        if binding == "get_status":
            after = self._state()
            return {"before": before, "after": after}
        if binding == "scale_restart":
            # A real consequential action: delete the real pod and reapply
            # the same manifest, forcing a real reschedule -- observed state
            # must genuinely transition (e.g. through NotFound) rather than
            # this being a no-op relabeled as an "action".
            delete_result = _run_kubectl(
                self._kubectl_args(
                    "delete", "pod", self._pod_name, "-n", self._namespace, "--wait=true"
                ),
                timeout=self._teardown_timeout,
            )
            apply_result = _run_kubectl(
                self._kubectl_args("apply", "-f", "-"),
                input_text=_pod_manifest(self._pod_name, self._namespace),
                timeout=30.0,
            )
            after = self._state()
            return {
                "before": before,
                "after": after,
                "delete_returncode": delete_result.returncode,
                "delete_stderr": _truncate(delete_result.stderr),
                "apply_returncode": apply_result.returncode,
                "apply_stderr": _truncate(apply_result.stderr),
            }
        raise ValueError(f"unsupported kubernetes reconciliation binding: {binding}")

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Poll REAL cluster-observed state until it matches `expected` or a
        bounded timeout elapses -- never trusts a prior `kubectl apply`'s
        exit code as convergence evidence by itself."""
        self._ensure_open()
        deadline = time.monotonic() + self._verify_timeout
        observed = self._state()
        while not all(observed.get(key) == value for key, value in expected.items()):
            if time.monotonic() >= deadline:
                break
            time.sleep(_POLL_INTERVAL_SECONDS)
            observed = self._state()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {"pod_name": self._pod_name, "namespace": self._namespace}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        self._pod_name = str(checkpoint["pod_name"])
        self._namespace = str(checkpoint["namespace"])

    async def teardown(self) -> None:
        if self._closed:
            return
        try:
            # Real kubectl delete against the real cluster.
            _run_kubectl(
                self._kubectl_args(
                    "delete",
                    "pod",
                    self._pod_name,
                    "-n",
                    self._namespace,
                    "--ignore-not-found=true",
                ),
                timeout=self._teardown_timeout,
            )
            # Poll real cluster-observed state until the pod is really gone,
            # bounded by _teardown_timeout -- a real deletion confirmation,
            # not just kubectl delete's exit code.
            deadline = time.monotonic() + self._teardown_timeout
            while _get_pod_json(self._pod_name, self._namespace) is not None:
                if time.monotonic() >= deadline:
                    break
                time.sleep(_POLL_INTERVAL_SECONDS)
        finally:
            self._closed = True

    def is_really_deleted(self) -> bool:
        """Real post-teardown confirmation helper for tests: queries the real
        cluster directly rather than trusting `teardown()`'s own bookkeeping."""
        return _get_pod_json(self._pod_name, self._namespace) is None


class KubernetesReconciliationProvider:
    """GymAct `EnvironmentProvider` that materializes real, Kubernetes-backed
    Pod environments against a real local cluster (kind/k3d/colima
    --kubernetes)."""

    name = "kubernetes-reconciliation"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> KubernetesReconciliationEnvironment:
        del scenario
        namespace = config.get("namespace", _DEFAULT_NAMESPACE)
        if not isinstance(namespace, str) or not namespace:
            raise TypeError("config.namespace must be a non-empty string")
        kubeconfig_context = config.get("kubeconfig_context")
        if kubeconfig_context is not None and not isinstance(kubeconfig_context, str):
            raise TypeError("config.kubeconfig_context must be a string or None")
        requires_authority = config.get("requires_authority", True)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")
        verify_timeout_seconds = config.get(
            "verify_timeout_seconds", _DEFAULT_VERIFY_TIMEOUT_SECONDS
        )
        if not isinstance(verify_timeout_seconds, (int, float)) or isinstance(
            verify_timeout_seconds, bool
        ):
            raise TypeError("config.verify_timeout_seconds must be a number")
        return KubernetesReconciliationEnvironment(
            namespace=namespace,
            kubeconfig_context=kubeconfig_context,
            requires_authority=requires_authority,
            verify_timeout_seconds=float(verify_timeout_seconds),
        )
