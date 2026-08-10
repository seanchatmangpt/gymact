#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Transport {
    pub id: &'static str,
    pub title: &'static str,
}

pub const TRANSPORTS: &[Transport] = &[
    Transport { id: "a2a", title: "A2A" },
    Transport { id: "bpmn", title: "BPMN" },
    Transport { id: "cli", title: "CLI" },
    Transport { id: "cloud_api", title: "Cloud API" },
    Transport { id: "http", title: "HTTP" },
    Transport { id: "mcp", title: "MCP" },
    Transport { id: "powl", title: "POWL" },
    Transport { id: "wasm", title: "WASM" },
];

pub fn semantic_round_trip(before: &str, after: &str) -> Result<(), &'static str> {
    if before == after {
        Ok(())
    } else {
        Err("REFUSED:SEMANTIC_TRANSPORT_DRIFT")
    }
}
