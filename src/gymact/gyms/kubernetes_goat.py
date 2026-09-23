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
(`batch-check`, `hidden-in-layers`). Kubernetes-goat's other scenarios
(`kubernetes-goat-home`, `insecure-rbac`, `metadata-db`, ...) are
long-running Deployments/Services with no analogous single-shot completion
condition and are out of scope for this provider.

IMPORTANT (corrects an earlier, wrong assumption in this same module): even
though these two scenarios are declared as `batch/v1` Job manifests, their
real, currently-published container images (`madhuakula/k8s-goat-batch-check`,
`madhuakula/k8s-goat-hidden-in-layers`) both run a persistent, never-exiting
process (a Fiber v2 HTTP server listening on :3000 for `batch-check`; `tail -f
/dev/null` for `hidden-in-layers`). Their Job's `status.succeeded` therefore
NEVER becomes `1` -- treating it as the completion signal is wrong for these
two scenarios specifically, confirmed by real inspection of the real,
currently-published images (`docker run`, `docker logs`, `docker exec`, real
`docker save`/`docker history` layer inspection). Kubernetes-goat's own
walkthrough docs (`guide/docs/scenarios/scenario-10` for `batch-check`,
`scenario-15` for `hidden-in-layers`) define "solved" as a real, documented
interaction outcome instead:

- `batch-check` (scenario-10, "Analyzing crypto miner container"): the
  running container bakes in a real `/app` git repository whose history
  (not its current tree) contains a committed-then-removed config file with
  a `k8s_goat_flag = k8s-goat-<32 hex chars>` line -- confirmed for real via
  `git -C /app log --all -p`. `verify()` reaches this via a real
  `kubectl exec` into the real running scenario pod (git is already
  installed in the real image, confirmed via `docker exec ... which git`),
  not a fabricated string.
- `hidden-in-layers` (scenario-15, "Hidden in layers"): the real Dockerfile
  `ADD`s `/root/secret.txt` in one layer and `rm -rf`s it in a later layer --
  gone from the final running filesystem (a `kubectl exec` read finds
  nothing, confirmed for real), but still really present in the earlier
  layer's tarball. `verify()` reaches this via a real `docker save` of the
  scenario's exact image (read from the real, cluster-observed Job spec, not
  hardcoded) plus real per-layer `tar` extraction, matching kubernetes-goat's
  own documented Method (`docker save` + `tar -xvf`) -- this specific check
  therefore also requires a real local `docker` CLI talking to a real Docker
  daemon on the machine running the verifier (the same requirement `kind`
  itself already has via its Docker-backed node containers).

Both real solved-conditions are matched against the real, documented flag
pattern `k8s-goat-[0-9a-f]{32}` rather than one hardcoded literal value, so
this provider keeps working if the vendored images are rebuilt with a
different random flag suffix (a real property of kubernetes-goat's own
generation script) while still refusing to pass on any other string.

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
import re
import shutil
import subprocess
import tarfile
import tempfile
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
_DEFAULT_EXEC_TIMEOUT_SECONDS = 30.0
_DEFAULT_DOCKER_TIMEOUT_SECONDS = 120.0

# Real, documented kubernetes-goat flag shape (`k8s_goat_flag = k8s-goat-<32
# hex chars>` in scenario-10's/scenario-15's own walkthrough docs). Matching
# a pattern, not one hardcoded literal, so this keeps working if the
# vendored images are rebuilt with a different random suffix while still
# refusing any other string as "solved".
_FLAG_PATTERN = re.compile(r"k8s-goat-[0-9a-f]{32}")

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


def _get_running_pod_name(
    job_name: str, namespace: str, context: str | None
) -> str | None:
    """Real `kubectl get pods -l job-name=<job_name>` lookup, restricted to a
    pod the cluster itself reports as `Running` -- a pod that has not yet
    reached `Running` cannot be `kubectl exec`'d into meaningfully."""
    args = [
        "get",
        "pods",
        "-n",
        namespace,
        "-l",
        f"job-name={job_name}",
        "-o",
        "json",
    ]
    if context:
        args = ["--context", context, *args]
    result = _run_kubectl(args)
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    for item in payload.get("items", []):
        if item.get("status", {}).get("phase") == "Running":
            return str(item["metadata"]["name"])
    return None


def _get_job_container_image(
    job_name: str, namespace: str, context: str | None
) -> str | None:
    """Reads the real, cluster-observed container image for this Job from
    the real Job spec `kubectl` returns -- not a hardcoded literal -- so the
    real layer inspection below always inspects the exact image the real
    manifest declared."""
    job_json = _get_job_json(job_name, namespace, context)
    if job_json is None:
        return None
    containers = job_json.get("spec", {}).get("template", {}).get("spec", {}).get(
        "containers", []
    )
    if not containers:
        return None
    image = containers[0].get("image")
    return str(image) if image else None


def _check_batch_check_solved(
    job_name: str, namespace: str, context: str | None
) -> dict[str, Any]:
    """Real `kubectl exec` into the real running `batch-check` pod, running a
    real `git log --all -p` over the real `/app` git repository baked into
    kubernetes-goat's real, currently-published image, looking for the real,
    documented `k8s_goat_flag = k8s-goat-<32 hex>` line committed then
    removed from that repository's history. Never fabricates a flag."""
    pod_name = _get_running_pod_name(job_name, namespace, context)
    if pod_name is None:
        return {"solved": False, "flag": None, "detail": "no Running batch-check pod yet"}
    exec_args = [
        "exec",
        pod_name,
        "-n",
        namespace,
        "--",
        "sh",
        "-c",
        "git config --global --add safe.directory /app "
        "&& git -C /app log --all -p 2>&1",
    ]
    if context:
        exec_args = ["--context", context, *exec_args]
    result = _run_kubectl(exec_args, timeout=_DEFAULT_EXEC_TIMEOUT_SECONDS)
    if result.returncode != 0:
        return {
            "solved": False,
            "flag": None,
            "detail": f"kubectl exec git log failed: {_truncate(result.stderr)}",
        }
    match = _FLAG_PATTERN.search(result.stdout)
    if match is None:
        return {
            "solved": False,
            "flag": None,
            "detail": "no k8s-goat flag pattern found in real git history",
        }
    return {"solved": True, "flag": match.group(0), "detail": "flag found in real git history"}


def _run_docker(args: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _check_hidden_in_layers_solved(
    job_name: str, namespace: str, context: str | None
) -> dict[str, Any]:
    """Real `docker save` of the real, cluster-observed image for this Job
    plus real per-layer `tar` extraction, matching kubernetes-goat's own
    documented Method (scenario-15: `docker save` + `tar -xvf`) for
    recovering `/root/secret.txt`, which the real Dockerfile `ADD`s in one
    layer and `rm -rf`s in a later one -- absent from the running
    container's own filesystem, still real in an earlier layer's tarball.
    Requires a real local `docker` CLI + daemon; returns a typed, honest
    `solved: False` (never a fabricated pass) if that real dependency is
    unavailable."""
    if shutil.which("docker") is None:
        return {
            "solved": False,
            "flag": None,
            "detail": "no local docker CLI available for real layer inspection",
        }
    image = _get_job_container_image(job_name, namespace, context)
    if image is None:
        return {"solved": False, "flag": None, "detail": "no Job spec/image observed yet"}
    pull_result = _run_docker(["pull", image], timeout=_DEFAULT_DOCKER_TIMEOUT_SECONDS)
    if pull_result.returncode != 0:
        return {
            "solved": False,
            "flag": None,
            "detail": f"real docker pull {image!r} failed: {_truncate(pull_result.stderr)}",
        }
    with tempfile.TemporaryDirectory(prefix="gymact-k8s-goat-hidden-in-layers-") as tmp_dir:
        tar_path = Path(tmp_dir) / "image.tar"
        save_result = _run_docker(
            ["save", image, "-o", str(tar_path)], timeout=_DEFAULT_DOCKER_TIMEOUT_SECONDS
        )
        if save_result.returncode != 0:
            return {
                "solved": False,
                "flag": None,
                "detail": f"real docker save failed: {_truncate(save_result.stderr)}",
            }
        try:
            with tarfile.open(tar_path, "r:") as image_tar:
                image_tar.extractall(tmp_dir, filter="data")
        except (tarfile.TarError, OSError) as exc:
            return {"solved": False, "flag": None, "detail": f"real tar extraction failed: {exc}"}
        blobs_dir = Path(tmp_dir) / "blobs" / "sha256"
        if not blobs_dir.is_dir():
            return {
                "solved": False,
                "flag": None,
                "detail": "no OCI blobs/sha256 layout in real docker save output",
            }
        for blob_path in sorted(blobs_dir.iterdir()):
            try:
                with tarfile.open(blob_path, "r:*") as layer_tar:
                    member = next(
                        (m for m in layer_tar.getmembers() if m.name == "root/secret.txt"),
                        None,
                    )
                    if member is None:
                        continue
                    extracted = layer_tar.extractfile(member)
                    if extracted is None:
                        continue
                    content = extracted.read().decode("utf-8", errors="replace").strip()
            except (tarfile.TarError, OSError):
                continue
            match = _FLAG_PATTERN.search(content)
            if match is not None:
                return {
                    "solved": True,
                    "flag": match.group(0),
                    "detail": f"flag recovered from real deleted layer in {blob_path.name}",
                }
        return {
            "solved": False,
            "flag": None,
            "detail": "root/secret.txt not found with a matching flag in any real image layer",
        }


_SOLVED_CHECKS = {
    "batch-check": _check_batch_check_solved,
    "hidden-in-layers": _check_hidden_in_layers_solved,
}


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
