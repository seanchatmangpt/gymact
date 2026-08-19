//! Generated from `ggen/protocol-gym-pack/ontology.ttl`.
//! Do not hand-edit this projection. Change the admitted MCP ontology and rerun ggen.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct McpMethod {
    pub name: &'static str,
    pub facet: &'static str,
    pub lifecycle: &'static str,
    pub message_kind: &'static str,
    pub direction: &'static str,
    pub invocation: &'static str,
    pub control: &'static str,
    pub consequence: &'static str,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct McpExtensionMethod {
    pub name: &'static str,
    pub facet: &'static str,
    pub extension_id: &'static str,
    pub lifecycle: &'static str,
    pub consequence: &'static str,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct McpCapability {
    pub side: &'static str,
    pub key: &'static str,
    pub lifecycle: &'static str,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct McpMetadataField {
    pub key: &'static str,
    pub required: bool,
    pub lifecycle: &'static str,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct McpTransport {
    pub id: &'static str,
    pub lifecycle: &'static str,
    pub compatibility_only: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct McpProjectionTarget {
    pub id: &'static str,
    pub kind: &'static str,
    pub path: &'static str,
}

pub const MCP_PROTOCOL_VERSION: &str = "2026-07-28";


pub const MCP_CORE_METHODS: &[McpMethod] = &[
McpMethod {
        name: "completion/complete",
        facet: "completion",
        lifecycle: "active",
        message_kind: "request",
        direction: "client to server",
        invocation: "direct JSON-RPC",
        control: "application-controlled",
        consequence: "read-only",
    },
McpMethod {
        name: "elicitation/create",
        facet: "elicitation",
        lifecycle: "active",
        message_kind: "embedded input request",
        direction: "server intent embedded in result, client responds on retry/update",
        invocation: "embedded MRTR",
        control: "user-controlled",
        consequence: "interaction",
    },
McpMethod {
        name: "notifications/cancelled",
        facet: "base",
        lifecycle: "active",
        message_kind: "notification",
        direction: "bidirectional",
        invocation: "request-scoped notification",
        control: "protocol-controlled",
        consequence: "protocol bookkeeping",
    },
McpMethod {
        name: "notifications/message",
        facet: "logging",
        lifecycle: "deprecated",
        message_kind: "notification",
        direction: "server to client",
        invocation: "request-scoped notification",
        control: "protocol-controlled",
        consequence: "protocol bookkeeping",
    },
McpMethod {
        name: "notifications/progress",
        facet: "progress",
        lifecycle: "active",
        message_kind: "notification",
        direction: "bidirectional",
        invocation: "request-scoped notification",
        control: "protocol-controlled",
        consequence: "protocol bookkeeping",
    },
McpMethod {
        name: "notifications/prompts/list_changed",
        facet: "prompts",
        lifecycle: "active",
        message_kind: "notification",
        direction: "server to client",
        invocation: "long-lived stream",
        control: "user-controlled",
        consequence: "protocol bookkeeping",
    },
McpMethod {
        name: "notifications/resources/list_changed",
        facet: "resources",
        lifecycle: "active",
        message_kind: "notification",
        direction: "server to client",
        invocation: "long-lived stream",
        control: "application-controlled",
        consequence: "protocol bookkeeping",
    },
McpMethod {
        name: "notifications/resources/updated",
        facet: "resources",
        lifecycle: "active",
        message_kind: "notification",
        direction: "server to client",
        invocation: "long-lived stream",
        control: "application-controlled",
        consequence: "protocol bookkeeping",
    },
McpMethod {
        name: "notifications/subscriptions/acknowledged",
        facet: "subscriptions",
        lifecycle: "active",
        message_kind: "notification",
        direction: "server to client",
        invocation: "long-lived stream",
        control: "protocol-controlled",
        consequence: "protocol bookkeeping",
    },
McpMethod {
        name: "notifications/tools/list_changed",
        facet: "tools",
        lifecycle: "active",
        message_kind: "notification",
        direction: "server to client",
        invocation: "long-lived stream",
        control: "model-controlled",
        consequence: "protocol bookkeeping",
    },
McpMethod {
        name: "prompts/get",
        facet: "prompts",
        lifecycle: "active",
        message_kind: "request",
        direction: "client to server",
        invocation: "direct JSON-RPC",
        control: "user-controlled",
        consequence: "read-only",
    },
McpMethod {
        name: "prompts/list",
        facet: "prompts",
        lifecycle: "active",
        message_kind: "request",
        direction: "client to server",
        invocation: "direct JSON-RPC",
        control: "user-controlled",
        consequence: "read-only",
    },
McpMethod {
        name: "resources/list",
        facet: "resources",
        lifecycle: "active",
        message_kind: "request",
        direction: "client to server",
        invocation: "direct JSON-RPC",
        control: "application-controlled",
        consequence: "read-only",
    },
McpMethod {
        name: "resources/read",
        facet: "resources",
        lifecycle: "active",
        message_kind: "request",
        direction: "client to server",
        invocation: "direct JSON-RPC",
        control: "application-controlled",
        consequence: "read-only",
    },
McpMethod {
        name: "resources/templates/list",
        facet: "resources",
        lifecycle: "active",
        message_kind: "request",
        direction: "client to server",
        invocation: "direct JSON-RPC",
        control: "application-controlled",
        consequence: "read-only",
    },
McpMethod {
        name: "roots/list",
        facet: "roots",
        lifecycle: "deprecated",
        message_kind: "embedded input request",
        direction: "server intent embedded in result, client responds on retry/update",
        invocation: "embedded MRTR",
        control: "application-controlled",
        consequence: "read-only",
    },
McpMethod {
        name: "sampling/createMessage",
        facet: "sampling",
        lifecycle: "deprecated",
        message_kind: "embedded input request",
        direction: "server intent embedded in result, client responds on retry/update",
        invocation: "embedded MRTR",
        control: "model-controlled",
        consequence: "interaction",
    },
McpMethod {
        name: "server/discover",
        facet: "discovery",
        lifecycle: "active",
        message_kind: "request",
        direction: "client to server",
        invocation: "direct JSON-RPC",
        control: "protocol-controlled",
        consequence: "read-only",
    },
McpMethod {
        name: "subscriptions/listen",
        facet: "subscriptions",
        lifecycle: "active",
        message_kind: "request",
        direction: "client to server",
        invocation: "long-lived stream",
        control: "protocol-controlled",
        consequence: "protocol bookkeeping",
    },
McpMethod {
        name: "tools/call",
        facet: "tools",
        lifecycle: "active",
        message_kind: "request",
        direction: "client to server",
        invocation: "direct JSON-RPC",
        control: "model-controlled",
        consequence: "effect depends on selected tool/extension operation",
    },
McpMethod {
        name: "tools/list",
        facet: "tools",
        lifecycle: "active",
        message_kind: "request",
        direction: "client to server",
        invocation: "direct JSON-RPC",
        control: "model-controlled",
        consequence: "read-only",
    },
];

pub const MCP_EXTENSION_METHODS: &[McpExtensionMethod] = &[
McpExtensionMethod {
        name: "notifications/tasks",
        facet: "tasks",
        extension_id: "io.modelcontextprotocol/tasks",
        lifecycle: "extension",
        consequence: "protocol bookkeeping",
    },
McpExtensionMethod {
        name: "tasks/cancel",
        facet: "tasks",
        extension_id: "io.modelcontextprotocol/tasks",
        lifecycle: "extension",
        consequence: "effect depends on selected tool/extension operation",
    },
McpExtensionMethod {
        name: "tasks/get",
        facet: "tasks",
        extension_id: "io.modelcontextprotocol/tasks",
        lifecycle: "extension",
        consequence: "read-only",
    },
McpExtensionMethod {
        name: "tasks/update",
        facet: "tasks",
        extension_id: "io.modelcontextprotocol/tasks",
        lifecycle: "extension",
        consequence: "interaction",
    },
];

pub const MCP_CAPABILITIES: &[McpCapability] = &[
McpCapability {
        side: "client",
        key: "elicitation",
        lifecycle: "active",
    },
McpCapability {
        side: "client",
        key: "extensions",
        lifecycle: "active",
    },
McpCapability {
        side: "client",
        key: "roots",
        lifecycle: "deprecated",
    },
McpCapability {
        side: "client",
        key: "sampling",
        lifecycle: "deprecated",
    },
McpCapability {
        side: "server",
        key: "completions",
        lifecycle: "active",
    },
McpCapability {
        side: "server",
        key: "extensions",
        lifecycle: "active",
    },
McpCapability {
        side: "server",
        key: "logging",
        lifecycle: "deprecated",
    },
McpCapability {
        side: "server",
        key: "prompts",
        lifecycle: "active",
    },
McpCapability {
        side: "server",
        key: "resources",
        lifecycle: "active",
    },
McpCapability {
        side: "server",
        key: "tools",
        lifecycle: "active",
    },
];

pub const MCP_METADATA_FIELDS: &[McpMetadataField] = &[
McpMetadataField {
        key: "io.modelcontextprotocol/clientCapabilities",
        required: true,
        lifecycle: "active",
    },
McpMetadataField {
        key: "io.modelcontextprotocol/clientInfo",
        required: false,
        lifecycle: "active",
    },
McpMetadataField {
        key: "io.modelcontextprotocol/logLevel",
        required: false,
        lifecycle: "deprecated",
    },
McpMetadataField {
        key: "io.modelcontextprotocol/protocolVersion",
        required: true,
        lifecycle: "active",
    },
McpMetadataField {
        key: "io.modelcontextprotocol/serverInfo",
        required: false,
        lifecycle: "active",
    },
McpMetadataField {
        key: "io.modelcontextprotocol/subscriptionId",
        required: false,
        lifecycle: "active",
    },
McpMetadataField {
        key: "progressToken",
        required: false,
        lifecycle: "active",
    },
];

pub const MCP_TRANSPORTS: &[McpTransport] = &[
McpTransport {
        id: "legacy-http-sse",
        lifecycle: "deprecated",
        compatibility_only: true,
    },
McpTransport {
        id: "stdio",
        lifecycle: "active",
        compatibility_only: false,
    },
McpTransport {
        id: "streamable-http",
        lifecycle: "active",
        compatibility_only: false,
    },
];

pub const MCP_PROJECTION_TARGETS: &[McpProjectionTarget] = &[
McpProjectionTarget {
        id: "brce-map",
        kind: "authority",
        path: "generated/mcp/brce-map",
    },
McpProjectionTarget {
        id: "client-capabilities",
        kind: "manifest",
        path: "generated/mcp/client-capabilities.json",
    },
McpProjectionTarget {
        id: "conformance-fixtures",
        kind: "test",
        path: "generated/mcp/conformance",
    },
McpProjectionTarget {
        id: "extension-adapters",
        kind: "adapter",
        path: "generated/mcp/extensions",
    },
McpProjectionTarget {
        id: "header-policy",
        kind: "policy",
        path: "generated/mcp/header-policy",
    },
McpProjectionTarget {
        id: "json-schemas",
        kind: "schema",
        path: "generated/mcp/schema",
    },
McpProjectionTarget {
        id: "method-router",
        kind: "code",
        path: "generated/mcp/method-router",
    },
McpProjectionTarget {
        id: "mrtr-machine",
        kind: "state-machine",
        path: "generated/mcp/mrtr",
    },
McpProjectionTarget {
        id: "reference-docs",
        kind: "documentation",
        path: "rust/protocol_gym/docs/mcp-surface.md",
    },
McpProjectionTarget {
        id: "rust-verifier",
        kind: "proof-projection",
        path: "rust/protocol_gym/src/mcp_surface.rs",
    },
McpProjectionTarget {
        id: "server-capabilities",
        kind: "manifest",
        path: "generated/mcp/server-capabilities.json",
    },
McpProjectionTarget {
        id: "subscription-map",
        kind: "state-machine",
        path: "generated/mcp/subscriptions",
    },
McpProjectionTarget {
        id: "wit-abi",
        kind: "abi",
        path: "rust/protocol_gym/wit/mcp-surface.wit",
    },
];

pub const MCP_CORE_METHOD_COUNT: usize = MCP_CORE_METHODS.len();
pub const MCP_EXTENSION_METHOD_COUNT: usize = MCP_EXTENSION_METHODS.len();
