"""Protocol discovery -> admitted GymSpec for MCP, A2A, and LSP.

This module does not generate per-subject Python providers. It normalizes
protocol self-description into one transport-neutral specification consumed
by the generic ProtocolGymEnvironment and by ggen's independent Rust/WIT
projection pack.

Discovery is structural evidence only. Advertised capability != safe action,
verified consequence, or ALIVE standing.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import Field, model_validator

from gymact.models import Capability, Consequence, FrozenModel, Standing


class ProtocolKind(StrEnum):
    MCP = "mcp"
    A2A = "a2a"
    LSP = "lsp"


class ProtocolCapabilitySpec(FrozenModel):
    semantic_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    binding: str = Field(min_length=1)
    consequence: Consequence
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    output_schema: dict[str, Any] | None = None
    advertised_by_subject: bool = True
    authority_required: bool = True
    verifier_ref: str | None = None

    def as_capability(self) -> Capability:
        return Capability(
            iri=self.semantic_id,
            title=self.title,
            consequence=self.consequence,
            binding=self.binding,
        )


class ProtocolGymSpec(FrozenModel):
    protocol: ProtocolKind
    subject_id: str = Field(min_length=1)
    subject_version: str | None = None
    endpoint_ref: str = Field(min_length=1)
    source_digest: str = Field(min_length=1)
    capabilities: tuple[ProtocolCapabilitySpec, ...]
    standing: Standing = Standing.STRUCTURAL

    @model_validator(mode="after")
    def structurally_admitted_only(self) -> "ProtocolGymSpec":
        if self.standing is Standing.ALIVE:
            raise ValueError("DISCOVERY_CANNOT_PREMARK_PROTOCOL_GYM_ALIVE")
        ids = [capability.semantic_id for capability in self.capabilities]
        if len(ids) != len(set(ids)):
            raise ValueError("DUPLICATE_PROTOCOL_CAPABILITY_ID")
        return self


@runtime_checkable
class ProtocolSession(Protocol):
    async def observe(self) -> dict[str, Any]: ...
    async def invoke(self, binding: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def checkpoint(self) -> dict[str, Any]: ...
    async def restore(self, checkpoint: dict[str, Any]) -> None: ...
    async def close(self) -> None: ...


class ProtocolGymEnvironment:
    """One generic runtime over an admitted ProtocolGymSpec and native session."""

    def __init__(self, spec: ProtocolGymSpec, session: ProtocolSession) -> None:
        if not isinstance(session, ProtocolSession):
            raise TypeError("session does not satisfy ProtocolSession")
        self.environment_id = f"urn:gymact:protocol-gym:environment:{uuid4().hex}"
        self.requires_authority = any(item.authority_required for item in spec.capabilities)
        self.spec = spec
        self._session = session
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return tuple(item.as_capability() for item in self.spec.capabilities)

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        observed = await self._session.observe()
        return {
            "protocol": self.spec.protocol.value,
            "subject_id": self.spec.subject_id,
            "source_digest": self.spec.source_digest,
            "standing": self.spec.standing.value,
            "observed": observed,
        }

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        declared = {item.binding: item for item in self.spec.capabilities}
        spec = declared.get(capability.binding)
        if spec is None or spec.semantic_id != capability.iri:
            raise ValueError("REFUSED:PROTOCOL_CAPABILITY_NOT_ADMITTED")
        return await self._session.invoke(spec.binding, payload)

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = await self.observe()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return await self._session.checkpoint()

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        await self._session.restore(checkpoint)

    async def teardown(self) -> None:
        if not self._closed:
            await self._session.close()
        self._closed = True


class ProtocolGymProvider:
    """One provider for all protocol-discovered subjects; no generated Python."""

    name = "protocol-gym"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> ProtocolGymEnvironment:
        del scenario
        spec = config.get("spec")
        session = config.get("session")
        if not isinstance(spec, ProtocolGymSpec):
            raise TypeError("config.spec must be ProtocolGymSpec")
        if not isinstance(session, ProtocolSession):
            raise TypeError("config.session must satisfy ProtocolSession")
        return ProtocolGymEnvironment(spec, session)


def _capability_id(protocol: ProtocolKind, subject_id: str, binding: str) -> str:
    safe_subject = subject_id.replace(" ", "-")
    safe_binding = binding.replace("/", ":").replace(" ", "-")
    return f"urn:gymact:protocol-gym:{protocol.value}:{safe_subject}:{safe_binding}"


def mcp_tools_to_gym_spec(
    *,
    subject_id: str,
    endpoint_ref: str,
    source_digest: str,
    tools: list[dict[str, Any]],
    subject_version: str | None = None,
) -> ProtocolGymSpec:
    """Normalize MCP tools/list output.

    MCP annotations are intentionally not trusted for READ/DO admission. Every
    discovered tool is a DO candidate requiring authority until an external
    admission policy proves otherwise.
    """
    capabilities: list[ProtocolCapabilitySpec] = []
    for tool in tools:
        name = str(tool["name"])
        schema = tool.get("inputSchema") or {"type": "object"}
        output = tool.get("outputSchema")
        capabilities.append(
            ProtocolCapabilitySpec(
                semantic_id=_capability_id(ProtocolKind.MCP, subject_id, name),
                title=str(tool.get("title") or tool.get("description") or name),
                binding=name,
                consequence=Consequence.DO,
                input_schema=dict(schema),
                output_schema=dict(output) if isinstance(output, dict) else None,
                authority_required=True,
            )
        )
    return ProtocolGymSpec(
        protocol=ProtocolKind.MCP,
        subject_id=subject_id,
        subject_version=subject_version,
        endpoint_ref=endpoint_ref,
        source_digest=source_digest,
        capabilities=tuple(capabilities),
    )


def a2a_card_to_gym_spec(
    *,
    card: dict[str, Any],
    source_digest: str,
    endpoint_ref: str | None = None,
) -> ProtocolGymSpec:
    """Normalize A2A AgentCard skills as authority-gated candidate actions."""
    subject_id = str(card["name"])
    interfaces = card.get("supportedInterfaces") or []
    resolved_endpoint = endpoint_ref
    if resolved_endpoint is None and interfaces:
        first = interfaces[0]
        if isinstance(first, dict):
            resolved_endpoint = str(first.get("url") or "")
    if not resolved_endpoint:
        resolved_endpoint = "urn:gymact:protocol-gym:a2a:endpoint:unspecified"
    capabilities: list[ProtocolCapabilitySpec] = []
    for skill in card.get("skills", []):
        skill_id = str(skill["id"])
        capabilities.append(
            ProtocolCapabilitySpec(
                semantic_id=_capability_id(ProtocolKind.A2A, subject_id, skill_id),
                title=str(skill.get("name") or skill.get("description") or skill_id),
                binding=skill_id,
                consequence=Consequence.DO,
                authority_required=True,
            )
        )
    return ProtocolGymSpec(
        protocol=ProtocolKind.A2A,
        subject_id=subject_id,
        subject_version=str(card.get("version")) if card.get("version") is not None else None,
        endpoint_ref=resolved_endpoint,
        source_digest=source_digest,
        capabilities=tuple(capabilities),
    )


_LSP_READ_CAPABILITIES: dict[str, str] = {
    "completionProvider": "textDocument/completion",
    "definitionProvider": "textDocument/definition",
    "documentSymbolProvider": "textDocument/documentSymbol",
    "hoverProvider": "textDocument/hover",
    "referencesProvider": "textDocument/references",
    "workspaceSymbolProvider": "workspace/symbol",
}
_LSP_DO_CAPABILITIES: dict[str, str] = {
    "codeActionProvider": "textDocument/codeAction",
    "executeCommandProvider": "workspace/executeCommand",
    "renameProvider": "textDocument/rename",
}


def lsp_initialize_to_gym_spec(
    *,
    subject_id: str,
    endpoint_ref: str,
    source_digest: str,
    initialize_result: dict[str, Any],
) -> ProtocolGymSpec:
    """Normalize LSP initialize ServerCapabilities into protocol-gym actions."""
    server_capabilities = initialize_result.get("capabilities") or {}
    server_info = initialize_result.get("serverInfo") or {}
    capabilities: list[ProtocolCapabilitySpec] = []
    for field, method in _LSP_READ_CAPABILITIES.items():
        if server_capabilities.get(field):
            capabilities.append(
                ProtocolCapabilitySpec(
                    semantic_id=_capability_id(ProtocolKind.LSP, subject_id, method),
                    title=method,
                    binding=method,
                    consequence=Consequence.READ,
                    authority_required=False,
                )
            )
    for field, method in _LSP_DO_CAPABILITIES.items():
        if server_capabilities.get(field):
            capabilities.append(
                ProtocolCapabilitySpec(
                    semantic_id=_capability_id(ProtocolKind.LSP, subject_id, method),
                    title=method,
                    binding=method,
                    consequence=Consequence.DO,
                    authority_required=True,
                )
            )
    return ProtocolGymSpec(
        protocol=ProtocolKind.LSP,
        subject_id=subject_id,
        subject_version=str(server_info.get("version")) if server_info.get("version") else None,
        endpoint_ref=endpoint_ref,
        source_digest=source_digest,
        capabilities=tuple(capabilities),
    )
