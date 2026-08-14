# protocol-gym-pack

This is the compiled half of the Protocol → Gym compiler. A pack is mounted by a ggen
consumer; it is not itself the executable project.

The checked-in Gall consumer is `rust/protocol_gym/`. Replay directly with:

```bash
cd rust/protocol_gym
ggen sync run
cargo test
```

Its `ggen.toml` names the canonical pack and ontology by relative path. When the same
consumer is materialized through `GgenProvider`, `bundle_root` admits the containing
repository boundary; the provider preflights every declared ontology/template/pack
path, copies those dependencies into an isomorphic private bundle, and runs ggen only
from that copied consumer. A dependency or symlink resolving outside `bundle_root` is
refused before copying.

## MCP is an ontology, not a hand-maintained SDK surface

`ontology.ttl` now admits the MCP surface as a revisioned knowledge graph rather than a
single `mcp` string. The current profile is pinned to MCP `2026-07-28` and covers:

- the exact 21 core method/schema categories;
- JSON-RPC request/notification/result semantics and `resultType`;
- per-request client capabilities and `_meta` fields;
- server discovery and server capabilities;
- tools, resources, prompts, completions, elicitation, sampling and roots;
- MRTR (`input_required`) rather than modern server-to-client request RPC;
- progress, list-change notifications and `subscriptions/listen`;
- stdio, Streamable HTTP and compatibility-only legacy HTTP+SSE;
- `MCP-Protocol-Version`, `x-mcp-header`/`Mcp-Param-*`, and body/header mismatch refusal;
- JSON Schema 2020-12 tool-schema semantics;
- authorization as an ODRL-described transport policy, distinct from GymAct BRCE authority;
- lifecycle status (`active`, `deprecated`, `removed`, `extension`);
- the formal extension mechanism and the Tasks extension (`tasks/get`, `tasks/update`,
  `tasks/cancel`, `notifications/tasks`, task result/status lattice);
- explicit legacy compatibility facts such as `initialize`, `logging/setLevel`,
  `resources/subscribe`, legacy Tasks list/result, and `Mcp-Session-Id`;
- all ggen projection targets that must remain derived from this same semantic source.

The ontology deliberately does **not** say that a valid MCP `tools/call` grants authority.
`tools/call` is classified `ConditionalEffect`: the selected tool's admitted semantics decide
whether it is READ or DO. A GymAct DO projection still becomes an `ActuationIntent` and must
cross capability scope, authority admission, and BRCE.

Formally:

```text
MCP projection = ggen(AdmittedOntology ∩ ProtocolRevision ∩ TargetProfile)
DO             = GymActAuthority(MCP projection, admitted tool semantics)
```

`gates/mcp-surface.shacl.ttl` validates structural closure. The independent Python court
`tests/test_mcp_protocol_ontology.py` additionally checks that the modern method set is exactly
the upstream 2026-07-28 schema-reference set rather than merely internally self-consistent.

The pack owns **12 normal consumer-project outputs** after adding `src/mcp_surface.rs`. It
never manufactures Python protocol clients. Discovery evidence begins `STRUCTURAL`; generated
code does not inherit `ALIVE` standing until the consumer is actually regenerated, compiled,
and exercised against the exact admitted subject.
