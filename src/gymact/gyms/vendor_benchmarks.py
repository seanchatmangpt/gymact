"""Exact-pin providers for the vendor benchmark corpus.

The provider layer is deliberately small: each vendor keeps its own native CLI,
package, containers, cluster, emulator, or service. GymAct supplies the common
bounded contract around that collaborator: exact checkout admission, cwd-bound
native execution, authority-required DO capabilities, observation, verification,
and typed refusal/blocking when the collaborator is absent or at the wrong pin.

This is not command discovery and it is not a synthetic gym. A provider only
materializes after the real vendor checkout's Git HEAD equals the revision pinned
by AutoFDE Lab's ``docs/papers/gym-lock.ttl``.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

LOCK_SOURCE_REPO = "seanchatmangpt/autofde-lab"
LOCK_SOURCE_SHA = "dcc9947f713a719d9c0952f90b95b3f12a2f2cbe"
LOCK_SOURCE_PATH = "docs/papers/gym-lock.ttl"

VENDOR_REVISIONS: dict[str, str] = {
    "agentbench": "d1e4a10db08c87075c78972e48ecc182be03e2d5",
    "agentdojo": "089ed468cf3ed0322acc66b0211f26d9d90dbf60",
    "agentgym": "3ef9235d23e68e7c2920c5422ad957dc8ced5c6c",
    "agentlab": "cbc35a9bc0facaf731bc858c5825edbe757c719f",
    "aiopslab": "80901cc77de13a8fb35dc0e3feff78ca09fd6ae4",
    "androidworld": "3e50888527ef9f29b9157ecd537e408008bb1c85",
    "asb": "1f561dccf92d55302368fa67679b4ba9d9c8fdc4",
    "assetopsbench": "e11d1c1b2022db0396364a6d66e24168955a3bb7",
    # Not from AutoFDE Lab's gym-lock.ttl like the entries above/below --
    # awesome-ai-gyms is the user's own gym-discovery registry
    # (github.com/seanchatmangpt/awesome-ai-gyms), pinned directly against
    # its real main HEAD (fetched live via `gh api
    # repos/seanchatmangpt/awesome-ai-gyms/commits/main --jq .sha`, not
    # copied from gym-lock.ttl). See gymact.gym_index for the bridge that
    # reads this vendor's registry/gyms.tsv into ForwardBenchSubject rows.
    "awesome-ai-gyms": "e9320f82c1caf0fa15e53ba11b1416eb3a0f7e3a",
    "azuregoat": "b97045952e6df00de735a7f27fd7c4994dcfe8c0",
    "bountytasks": "1956e5fd4eff12034a5fbe0544482d2cf52bb5b0",
    "browsergym": "9e779f087de9a65668b6974d11f9ce9816026e96",
    "cloudfoxable": "fc49b7f637268031515ced9fee4b643d3e68db67",
    "cloudgoat": "abf1ba8f5e47d7ced750fdfa025d51c99f1a43ed",
    "crmarena": "a37d882c3a947f0330a907f513b90a7f08b9c532",
    "cube-harness": "126989d75eb156949af37cd182fe9b0d69d94434",
    "cube-standard": "9ca7c062d211450df05eb8318a1e847b5373b689",
    "cybench": "1097a7226eb034d3821208114da38f10b8627ab1",
    "cybergym-e2e": "b861317f11641b14ab6ba08b5179d0b044601057",
    "devops-gym": "9bbe3f0de632299faa9102b282ebc9ea4a516d67",
    "doomarena": "b80902f107b4d28194580352a59b3029f4a018b4",
    "enterprisebench": "6b3c501763645cbe1d7f314c6481643f6cd0c52e",
    "gcpgoat": "44605c4bff4b2da7611dfce78696bb53db6d8c54",
    "general-agentbench": "35f5c027c31ddcb3366b28674c6cb2957460c0e2",
    "harbor": "e485e8a6c538a3ba42fe890e61fbd14572c590aa",
    "inspect-evals": "b935c0e5cfa04710f016f925db75d8e81413e2cf",
    "itbench": "c8ad897d3ab455b3727c76b2467f0ad41b49c44b",
    "kubernetes-goat": "723a0db478f050d173d23b4ce5044b65bce0bdd0",
    "mcp-bench": "7a8eaeae83a842a2949080acc5473f65e1569daf",
    "mcp-universe": "48b453021694d9823d308627fb7f6b7edd29541a",
    "mcpmark": "cd45b7f57923b9b3985467f5139927575f83141c",
    "o11y-bench": "867100cb314cf12dee039c3ef5b2534ccfe56919",
    "osworld": "091f5ef1d5544bc74953c77875d5feb5bed30108",
    "qqr": "d5c5bafb86bdc2cf471d0e2bef4cb2e645daf3f8",
    "r2e-gym": "0d94c4eb9431cd195c55a7ea3abd54006c9a1735",
    "rcaeval": "4695aa69f4f1f57b9094ca04ff235908b73a8e24",
    "sadservers": "64a06f8531528e9c08911c96ff809f8dc41f86c2",
    "scuba": "b988d167004d7ea207332eff8d55b0691d8cadf9",
    "sec-bench": "31eb43485a3de47da260be0f978528b1f2314415",
    "sre-bench": "a85eecdbd09e7ab04ff9bd5b00ecd3e9bc4464c1",
    "st-webagentbench": "67f56dd7df9eca1646c9e49407b087e950aa1e77",
    "swe-bench": "f7bbbb2ccdf479001d6467c9e34af59e44a840f9",
    "tau2-bench": "668d3bcd135c02aa3438f987ef45735b7c163ee3",
    "terminal-bench": "2fd12b88aafdd04a52c298e3940bcb189f9766d6",
    "terminal-bench-pro": "874af409da6aafebccbf3bc5bb41a2fa4d78784d",
    "terragoat": "729f8da62c6a85ce4af5ad3d123de97776d954c4",
    "the-agent-company": "98b68ef82a47690c316f42fddb05baafaab56851",
    "toolsandbox": "165848b9a78cead7ca7fe7c89c688b58e6501219",
    "tua-bench": "3497fd320abcafaf4797424192c891a593fd7964",
    "webarena": "dce04686a56253aefba7b18a4fa0937cf1dc987b",
    "wonderbread": "ed052c67aeada04167cdfe92ff8de454aa94627a",
    "workarena": "a772230a94cf1caf4166b8ead3983f3b3786455b",
}


@dataclass(frozen=True, slots=True)
class VendorSpec:
    name: str
    revision: str

    @property
    def relative_root(self) -> Path:
        return Path("vendor") / "gyms" / self.name


VENDOR_SPECS: dict[str, VendorSpec] = {
    name: VendorSpec(name=name, revision=revision)
    for name, revision in VENDOR_REVISIONS.items()
}


@dataclass(frozen=True, slots=True)
class VendorAudit:
    name: str
    root: Path
    expected_revision: str
    observed_revision: str | None
    standing: str
    reason: str


class VendorAdmissionError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


def _default_lab_root() -> Path:
    configured = os.environ.get("AUTOFDE_LAB")
    return Path(configured).expanduser() if configured else Path.home() / "autofde-lab"


def vendor_root(name: str, *, lab_root: str | Path | None = None) -> Path:
    spec = VENDOR_SPECS.get(name)
    if spec is None:
        raise KeyError(f"UNSUPPORTED:UNKNOWN_VENDOR:{name}")
    root = Path(lab_root).expanduser() if lab_root is not None else _default_lab_root()
    return root / spec.relative_root


def _git_revision(root: Path) -> str | None:
    git = shutil.which("git")
    if git is None:
        return None
    process = subprocess.run(
        [git, "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        return None
    revision = process.stdout.strip().lower()
    return revision if len(revision) == 40 else None


def _audit_spec(spec: VendorSpec, checkout: Path) -> VendorAudit:
    if not checkout.is_dir():
        return VendorAudit(
            spec.name,
            checkout,
            spec.revision,
            None,
            "BLOCKED",
            "BLOCKED:VENDOR_CHECKOUT_MISSING",
        )
    if shutil.which("git") is None:
        return VendorAudit(
            spec.name,
            checkout,
            spec.revision,
            None,
            "BLOCKED",
            "BLOCKED:GIT_UNAVAILABLE",
        )
    observed = _git_revision(checkout)
    if observed is None:
        return VendorAudit(
            spec.name,
            checkout,
            spec.revision,
            None,
            "REFUSED",
            "REFUSED:VENDOR_CHECKOUT_NOT_GIT",
        )
    if observed != spec.revision:
        return VendorAudit(
            spec.name,
            checkout,
            spec.revision,
            observed,
            "REFUSED",
            "REFUSED:VENDOR_REVISION_MISMATCH",
        )
    return VendorAudit(
        spec.name,
        checkout.resolve(),
        spec.revision,
        observed,
        "PARTIAL_ALIVE",
        "PIN_ADMITTED",
    )


def audit_vendor(name: str, *, root: str | Path | None = None) -> VendorAudit:
    spec = VENDOR_SPECS.get(name)
    if spec is None:
        raise KeyError(f"UNSUPPORTED:UNKNOWN_VENDOR:{name}")
    checkout = Path(root).expanduser() if root is not None else vendor_root(name)
    return _audit_spec(spec, checkout)


def audit_all_vendors(*, lab_root: str | Path | None = None) -> tuple[VendorAudit, ...]:
    return tuple(
        audit_vendor(name, root=vendor_root(name, lab_root=lab_root))
        for name in sorted(VENDOR_SPECS)
    )


def _safe_argv(argv: Any) -> tuple[str, ...]:
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(item, str) and item for item in argv)
    ):
        raise TypeError("payload.argv must be a non-empty list of non-empty strings")
    executable = Path(argv[0])
    if executable.is_absolute() or ".." in executable.parts:
        raise VendorAdmissionError("REFUSED:COMMAND_ESCAPES_VENDOR_ROOT", argv[0])
    return tuple(argv)


class VendorBenchmarkEnvironment:
    def __init__(self, *, spec: VendorSpec, root: Path, timeout_seconds: float) -> None:
        self.environment_id = f"urn:gymact:{spec.name}:environment:{uuid4().hex}"
        self.requires_authority = True
        self.spec = spec
        self.root = root
        self.timeout_seconds = timeout_seconds
        self._closed = False
        self._last_result: dict[str, Any] = {}

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self):
        self._ensure_open()
        from gymact.models import Capability, Consequence

        return (
            Capability(
                iri=f"urn:gymact:{self.spec.name}:capability:run-native",
                title=f"Execute an exact-checkout {self.spec.name} native benchmark command",
                consequence=Consequence.DO,
                binding="run-native",
            ),
        )

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return {
            "vendor": self.spec.name,
            "revision": self.spec.revision,
            "root": str(self.root),
            "last_result": deepcopy(self._last_result),
        }

    async def run_native(self, argv: Any) -> dict[str, Any]:
        self._ensure_open()
        command = _safe_argv(argv)
        before_revision = _git_revision(self.root)
        if before_revision != self.spec.revision:
            raise VendorAdmissionError(
                "REFUSED:VENDOR_REVISION_DRIFT",
                f"expected={self.spec.revision},observed={before_revision}",
            )
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=self.root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise VendorAdmissionError("BLOCKED:NATIVE_COMMAND_UNAVAILABLE", command[0]) from exc
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout_seconds
            )
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise VendorAdmissionError(
                "BLOCKED:NATIVE_COMMAND_TIMEOUT",
                f"timeout_seconds={self.timeout_seconds}",
            ) from None
        after_revision = _git_revision(self.root)
        if after_revision != self.spec.revision:
            raise VendorAdmissionError(
                "REFUSED:VENDOR_REVISION_DRIFT",
                f"expected={self.spec.revision},observed={after_revision}",
            )
        result = {
            "argv": list(command),
            "returncode": int(process.returncode or 0),
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "revision": after_revision,
        }
        self._last_result = result
        return deepcopy(result)

    async def actuate(self, capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        if capability.binding != "run-native":
            raise ValueError(f"unsupported provider binding: {capability.binding}")
        return await self.run_native(payload.get("argv"))

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        observed = await self.observe()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {"last_result": deepcopy(self._last_result), "revision": self.spec.revision}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        if checkpoint.get("revision") != self.spec.revision:
            raise VendorAdmissionError("REFUSED:CHECKPOINT_REVISION_MISMATCH", self.spec.name)
        last_result = checkpoint.get("last_result", {})
        if not isinstance(last_result, dict):
            raise TypeError("checkpoint.last_result must be a mapping")
        self._last_result = deepcopy(last_result)

    async def teardown(self) -> None:
        self._closed = True


class VendorBenchmarkProvider:
    materialization_requires_authority = True

    def __init__(self, name: str) -> None:
        try:
            self.spec = VENDOR_SPECS[name]
        except KeyError as exc:
            raise KeyError(f"UNSUPPORTED:UNKNOWN_VENDOR:{name}") from exc
        self.name = name

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> VendorBenchmarkEnvironment:
        del scenario
        root_value = config.get("root")
        if root_value is not None and not isinstance(root_value, str):
            raise TypeError("config.root must be a string path when supplied")
        root = Path(root_value).expanduser() if root_value else vendor_root(self.name)
        audit = _audit_spec(self.spec, root)
        if audit.standing != "PARTIAL_ALIVE":
            raise VendorAdmissionError(audit.reason, str(audit.root))
        timeout = config.get("timeout_seconds", 300.0)
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or timeout <= 0
        ):
            raise TypeError("config.timeout_seconds must be a positive number")
        return VendorBenchmarkEnvironment(
            spec=self.spec,
            root=audit.root,
            timeout_seconds=float(timeout),
        )


def provider_for_vendor(name: str) -> VendorBenchmarkProvider:
    return VendorBenchmarkProvider(name)


def register_vendor_providers(
    runtime: Any, *, names: tuple[str, ...] | None = None
) -> tuple[str, ...]:
    selected = names if names is not None else tuple(sorted(VENDOR_SPECS))
    registered: list[str] = []
    for name in selected:
        provider = provider_for_vendor(name)
        runtime.register_provider(provider)
        registered.append(name)
    return tuple(registered)


VENDOR_PROVIDERS: dict[str, VendorBenchmarkProvider] = {
    name: VendorBenchmarkProvider(name) for name in sorted(VENDOR_SPECS)
}
