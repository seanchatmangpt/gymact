"""Real GymAct `Environment`/`EnvironmentProvider` for the actual vendored
**kubernetes-goat** scenarios (madhuakula/kubernetes-goat, pinned in
`~/autofde-lab/docs/papers/gym-lock.ttl` as `vendor-kubernetes-goat` at
revision `723a0db478f050d173d23b4ce5044b65bce0bdd0`).

Distinct from `kubernetes_reconciliation.py`: that provider expresses a
generic, gymact-authored Pod manifest (it happens to reuse one
kubernetes-goat container image, but does not apply kubernetes-goat's own
scenario manifests). This provider applies the REAL, checked-out
`scenarios/<name>/*.yaml` file from the admitted vendored checkout via
`kubectl apply -n <namespace> -f <real path>` -- no manifest is
reconstructed or fabricated here.

Scope of this provider: kubernetes-goat's `batch/v1` Job-shaped scenarios
(`batch-check`, `hidden-in-layers`). These were chosen because a Kubernetes
Job has a real, unambiguous, generic completion signal that this provider
does not have to invent: `status.succeeded == 1` on the real Job object
returned by `kubectl get job ... -o json`. Kubernetes-goat's other
scenarios (`kubernetes-goat-home`, `insecure-rbac`, `metadata-db`, ...) are
long-running Deployments/Services with no analogous single-shot completion
condition and are out of scope for this provider -- adding them would mean
inventing an ad hoc "solved" signal instead of reusing a real one, which
`.claude/rules/actuation-authority.md` (verified effect, not fabricated
pass/fail) and this repo's CLAUDE.md consequence law both rule out.

Per `.claude/rules/actuation-authority.md`, applying a kubernetes-goat
scenario deploys a real, intentionally-vulnerable workload onto a real
cluster -- a real consequential operation. `materialization_requires_authority`
is therefore `True` (unlike `kubernetes_reconciliation.py`'s benign reference
Pod), and the environment's own `requires_authority` is also `True` so the
`rerun_scenario` DO capability is authority-gated too. No Python Kubernetes
client library is used -- same real-subprocess `kubectl` pattern as
`kubernetes_reconciliation.py`.

Requires a real, reachable Kubernetes cluster on the current kubeconfig
context (e.g. local `kind`) AND a real vendored kubernetes-goat checkout on
disk (`config["checkout_path"]`) -- both are hard requirements with no
degraded fallback path other than `gymact.standing.require_standing`'s
named, visible skip in tests.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

_MAX_CAPTURED_OUTPUT = 4000
_POLL_INTERVAL_SECONDS = 2.0
_DEFAULT_VERIFY_TIMEOUT_SECONDS = 180.0
_DEFAULT_TEARDOWN_TIMEOUT_SECONDS = 120.0
_DEFAULT_NAMESPACE_TIMEOUT_SECONDS = 30.0

# Real, checked-out kubernetes-goat scenarios this provider supports, and the
# real Job name each scenario's own manifest declares (verified against the
# vendored checkout at the pinned revision -- see module docstring). Only
# batch/v1 Job scenarios are listed; see module docstring for why.
SUPPORTED_SCENARIOS: dict[str, dict[str, str]] = {
    "batch-check": {
        "manifest_relative_path": "scenarios/batch-check/job.yaml",
        "job_name": "batch-check-job",
    },
    "hidden-in-layers": {
        "manifest_relative_path": "scenarios/hidden-in-layers/deployment.yaml",
        "job_name": "hidden-in-layers",
    },
}

KUBERNETES_GOAT_CAPABILITIES = (
    Capability(
        iri="urn:gymact:kubernetes-goat:capability:get_job_status",
        title="Read the real cluster-observed Job status for this scenario",
        consequence=Consequence.READ,
        binding="get_job_status",
    ),
    Capability(
        iri="urn:gymact:kubernetes-goat:capability:get_logs",
        title="Read the real container logs for this scenario's Job pod(s)",
        consequence=Consequence.READ,
        binding="get_logs",
    ),
    Capability(
        iri="urn:gymact:kubernetes-goat:capability:rerun_scenario",
        title=(
            "Delete and reapply the real kubernetes-goat scenario manifest, "
            "forcing a real rerun of the vulnerable-scenario container"
        ),
        consequence=Consequence.DO,
        binding="rerun_scenario",
    ),
)


def _run_kubectl(
    args: list[str], *, timeout: float = 30.0
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["kubectl", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _truncate(text: str) -> str:
    return text[-_MAX_CAPTURED_OUTPUT:]


def _get_job_json(name: str, namespace: str, context: str | None) -> dict[str, Any] | None:
    """Real `kubectl get job <name> -o json` against the real cluster.

    Returns None on any non-zero exit (NotFound or otherwise) -- a real
    observed absence, not a fabricated default.
    """
    args = ["get", "job", name, "-n", namespace, "-o", "json"]
    if context:
        args = ["--context", context, *args]
    result = _run_kubectl(args)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _job_state(job_json: dict[str, Any] | None) -> dict[str, Any]:
    if job_json is None:
        return {"found": False, "succeeded": False, "failed": False, "active": 0}
    status = job_json.get("status", {})
    succeeded_count = int(status.get("succeeded", 0) or 0)
    failed_count = int(status.get("failed", 0) or 0)
    active_count = int(status.get("active", 0) or 0)
    return {
        "found": True,
        "succeeded": succeeded_count >= 1,
        "failed": failed_count >= 1,
        "active": active_count,
    }


def _get_namespace_json(name: str, context: str | None) -> dict[str, Any] | None:
    args = ["get", "namespace", name, "-o", "json"]
    if context:
        args = ["--context", context, *args]
    result = _run_kubectl(args)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


class KubernetesGoatEnvironment:
    """Wraps one real, namespace-isolated kubernetes-goat scenario applied to
    one real Kubernetes cluster from the real, checked-out manifest file."""

    def __init__(
        self,
        *,
        scenario: str,
        manifest_path: Path,
        job_name: str,
        namespace: str,
        kubeconfig_context: str | None,
        verify_timeout_seconds: float,
        teardown_timeout_seconds: float,
    ) -> None:
        self.environment_id = f"urn:gymact:kubernetes-goat:environment:{uuid4().hex}"
        # Deploying a real, deliberately-vulnerable kubernetes-goat workload
        # is a real consequential operation -- see
        # .claude/rules/actuation-authority.md. Always True; never
        # configurable down to False by a caller.
        self.requires_authority = True
        self._scenario = scenario
        self._manifest_path = manifest_path
        self._job_name = job_name
        self._namespace = namespace
        self._context = kubeconfig_context
        self._verify_timeout = verify_timeout_seconds
        self._teardown_timeout = teardown_timeout_seconds
        self._closed = False

        # Real namespace creation against the real cluster -- gives this
        # scenario instance a genuinely isolated, individually-teardownable
        # slice of the cluster.
        ns_args = ["create", "namespace", self._namespace]
        if self._context:
            ns_args = ["--context", self._context, *ns_args]
        ns_result = _run_kubectl(ns_args, timeout=_DEFAULT_NAMESPACE_TIMEOUT_SECONDS)
        if ns_result.returncode != 0:
            raise RuntimeError(
                f"kubectl create namespace failed for {self._namespace!r}: "
                f"{_truncate(ns_result.stderr)}"
            )

        # Real kubectl apply of the REAL, checked-out kubernetes-goat
        # manifest file -- not a reconstructed/fabricated manifest.
        apply_args = ["apply", "-n", self._namespace, "-f", str(self._manifest_path)]
        if self._context:
            apply_args = ["--context", self._context, *apply_args]
        apply_result = _run_kubectl(apply_args, timeout=30.0)
        self._last_apply = {
            "returncode": apply_result.returncode,
            "stdout": _truncate(apply_result.stdout),
            "stderr": _truncate(apply_result.stderr),
        }
        if apply_result.returncode != 0:
            # Real cleanup of the namespace we just created, so a failed
            # materialize does not leak cluster state.
            cleanup_args = ["delete", "namespace", self._namespace, "--ignore-not-found=true"]
            if self._context:
                cleanup_args = ["--context", self._context, *cleanup_args]
            _run_kubectl(cleanup_args, timeout=_DEFAULT_NAMESPACE_TIMEOUT_SECONDS)
            raise RuntimeError(
                f"kubectl apply failed for kubernetes-goat scenario {self._scenario!r} "
                f"(manifest {self._manifest_path}) in namespace {self._namespace!r}: "
                f"{_truncate(apply_result.stderr)}"
            )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return KUBERNETES_GOAT_CAPABILITIES

    def _kubectl_args(self, *args: str) -> list[str]:
        if self._context:
            return ["--context", self._context, *args]
        return list(args)

    def _state(self) -> dict[str, Any]:
        job_json = _get_job_json(self._job_name, self._namespace, self._context)
        state = _job_state(job_json)
        state.update(
            {
                "scenario": self._scenario,
                "job_name": self._job_name,
                "namespace": self._namespace,
            }
        )
        return state

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return self._state()

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        self._ensure_open()
        before = self._state()
        binding = capability.binding
        if binding == "get_job_status":
            after = self._state()
            return {"before": before, "after": after}
        if binding == "get_logs":
            logs_result = _run_kubectl(
                self._kubectl_args(
                    "logs",
                    "-n",
                    self._namespace,
                    "-l",
                    f"job-name={self._job_name}",
                    "--tail=200",
                    "--ignore-errors=true",
                ),
                timeout=30.0,
            )
            after = self._state()
            return {
                "before": before,
                "after": after,
                "logs": _truncate(logs_result.stdout),
                "logs_returncode": logs_result.returncode,
            }
        if binding == "rerun_scenario":
            # A real consequential action: delete the real Job (which also
            # deletes its Pods) and reapply the real manifest file, forcing
            # a genuine rerun of the vulnerable-scenario container.
            delete_result = _run_kubectl(
                self._kubectl_args(
                    "delete",
                    "job",
                    self._job_name,
                    "-n",
                    self._namespace,
                    "--wait=true",
                    "--ignore-not-found=true",
                ),
                timeout=self._teardown_timeout,
            )
            apply_result = _run_kubectl(
                self._kubectl_args(
                    "apply", "-n", self._namespace, "-f", str(self._manifest_path)
                ),
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
        raise ValueError(f"unsupported kubernetes-goat binding: {binding}")

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Poll REAL cluster-observed Job status (`status.succeeded`/`failed`)
        until it matches `expected` or a bounded timeout elapses. Image pulls
        for kubernetes-goat's scenario containers are real network operations
        the first time a given cluster runs them -- this never trusts
        `kubectl apply`'s exit code as completion evidence."""
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
        return {
            "scenario": self._scenario,
            "job_name": self._job_name,
            "namespace": self._namespace,
            "manifest_path": str(self._manifest_path),
        }

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        self._scenario = str(checkpoint["scenario"])
        self._job_name = str(checkpoint["job_name"])
        self._namespace = str(checkpoint["namespace"])
        self._manifest_path = Path(checkpoint["manifest_path"])

    async def teardown(self) -> None:
        if self._closed:
            return
        try:
            # Real namespace deletion against the real cluster -- cascades
            # to every resource this scenario created (Job, Pods, any
            # Service/ConfigMap the scenario manifest declared), matching
            # kubernetes_reconciliation.py's "poll real state until really
            # gone" teardown-verification pattern rather than trusting
            # kubectl delete's exit code.
            _run_kubectl(
                self._kubectl_args(
                    "delete", "namespace", self._namespace, "--ignore-not-found=true"
                ),
                timeout=self._teardown_timeout,
            )
            deadline = time.monotonic() + self._teardown_timeout
            while _get_namespace_json(self._namespace, self._context) is not None:
                if time.monotonic() >= deadline:
                    break
                time.sleep(_POLL_INTERVAL_SECONDS)
        finally:
            self._closed = True

    def is_really_deleted(self) -> bool:
        """Real post-teardown confirmation helper for tests: queries the real
        cluster directly for the scenario's namespace rather than trusting
        `teardown()`'s own bookkeeping."""
        return _get_namespace_json(self._namespace, self._context) is None


class KubernetesGoatProvider:
    """GymAct `EnvironmentProvider` that materializes real, namespace-isolated
    kubernetes-goat scenario environments against a real local cluster, from
    the real vendored kubernetes-goat checkout (pinned in gym-lock.ttl)."""

    name = "kubernetes-goat"
    # Deploying a real kubernetes-goat scenario is a real consequential
    # operation (a deliberately-vulnerable workload hits the cluster) -- see
    # .claude/rules/actuation-authority.md. Unlike
    # kubernetes_reconciliation.KubernetesReconciliationProvider, this is not
    # configurable down to False.
    materialization_requires_authority = True

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> KubernetesGoatEnvironment:
        if scenario is None or scenario not in SUPPORTED_SCENARIOS:
            raise ValueError(
                f"unsupported kubernetes-goat scenario {scenario!r}; supported: "
                f"{sorted(SUPPORTED_SCENARIOS)}"
            )
        checkout_path = config.get("checkout_path")
        if not isinstance(checkout_path, str) or not checkout_path:
            raise TypeError(
                "config.checkout_path must be a non-empty string pointing at the real, "
                "vendored kubernetes-goat checkout (see ~/autofde-lab/docs/papers/"
                "gym-lock.ttl's vendor-kubernetes-goat pin)"
            )
        checkout_root = Path(checkout_path)
        if not checkout_root.is_dir():
            raise FileNotFoundError(
                f"config.checkout_path {checkout_path!r} is not a real, existing directory"
            )
        scenario_meta = SUPPORTED_SCENARIOS[scenario]
        manifest_path = checkout_root / scenario_meta["manifest_relative_path"]
        if not manifest_path.is_file():
            raise FileNotFoundError(
                f"real kubernetes-goat manifest not found at {manifest_path} -- checkout at "
                f"{checkout_path!r} does not contain scenario {scenario!r}'s real manifest"
            )
        namespace = config.get("namespace")
        if namespace is not None and not isinstance(namespace, str):
            raise TypeError("config.namespace must be a string or None")
        if not namespace:
            namespace = f"gymact-k8s-goat-{uuid4().hex[:12]}"
        kubeconfig_context = config.get("kubeconfig_context")
        if kubeconfig_context is not None and not isinstance(kubeconfig_context, str):
            raise TypeError("config.kubeconfig_context must be a string or None")
        verify_timeout_seconds = config.get(
            "verify_timeout_seconds", _DEFAULT_VERIFY_TIMEOUT_SECONDS
        )
        if not isinstance(verify_timeout_seconds, (int, float)) or isinstance(
            verify_timeout_seconds, bool
        ):
            raise TypeError("config.verify_timeout_seconds must be a number")
        teardown_timeout_seconds = config.get(
            "teardown_timeout_seconds", _DEFAULT_TEARDOWN_TIMEOUT_SECONDS
        )
        if not isinstance(teardown_timeout_seconds, (int, float)) or isinstance(
            teardown_timeout_seconds, bool
        ):
            raise TypeError("config.teardown_timeout_seconds must be a number")
        return KubernetesGoatEnvironment(
            scenario=scenario,
            manifest_path=manifest_path,
            job_name=scenario_meta["job_name"],
            namespace=namespace,
            kubeconfig_context=kubeconfig_context,
            verify_timeout_seconds=float(verify_timeout_seconds),
            teardown_timeout_seconds=float(teardown_timeout_seconds),
        )
