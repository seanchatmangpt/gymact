# gymact-consumer-bridge-pack-template

A copy-and-customize `ggen` pack for an external system (e.g. `autofde-lab`, or any
other Python or Rust codebase) that:

1. registers itself as a real GymAct `EnvironmentProvider` (Python side — see
   `docs/integrations/consumer-setup.md` in the `gymact` repo for that half; this
   pack does not generate Python, per `gymact`'s own `.claude/rules/python-native.md`),
   and
2. wants a manufactured Rust operation catalog, MCP tool schema, and Markdown
   reference doc describing its own real capability surface — the same kind of
   projection `gymact`'s own `ggen/gymact-bridge-pack/` produces for GymAct's 4
   built-in operations, generalized to your system's operations instead.

This is **not** `gymact/ggen/gymact-bridge-pack/` itself — copy this
`consumer-bridge-pack-template/` directory into your own repo (as, say,
`ggen/gymact-bridge-pack/` there) and customize it. Do not point ggen at this
directory inside the `gymact` repo expecting it to describe your system.

## Setup (do these in order, in your own repo, after copying this directory)

### 1. Write your own `ontology.ttl`

Copy `ontology.ttl.example` to `ontology.ttl` and replace its two example
`sosa:Procedure` individuals with the real capabilities your `EnvironmentProvider`
implementation actually exposes. Declare zero new RDF vocabulary — only
`sosa:Procedure` instances, each with exactly one `dct:title` and one `dct:type`
drawn from GymAct's two real consequence-class IRIs
(`urn:gymact:consequence:read` / `urn:gymact:consequence:do`).

### 2. Fetch the real SHACL shape — never hand-copy it

This template's `shapes/` directory does not exist yet on purpose: unlike
`gymact`'s own internal bridge pack (which uses a real symlink, since the profile
and the pack live in the same repo), a consumer in a *separate* repo cannot
symlink across repo boundaries. Fetch a real, digest-verified copy instead, from
a real `gymact` checkout:

```bash
mkdir -p shapes
gymact export-profile /tmp/gymact-profile-export
cp /tmp/gymact-profile-export/profile.shacl.ttl shapes/profile.shacl.ttl
cp /tmp/gymact-profile-export/profile.ttl shapes/profile.ttl   # optional, for reference
```

`gymact export-profile` prints each exported file's real SHA-256 digest —
record it (e.g. in a `shapes/DIGESTS.txt` you commit alongside) so a later re-fetch
can be diffed to detect drift, the same purpose the real symlink serves inside the
`gymact` repo itself. Re-run this fetch whenever you upgrade your `gymact`
dependency version; do not assume the shape is stable across GymAct releases.

### 3. Pick your MCP tool namespace

The generated `gymact_consumer_mcp_tools.rs` template uses `consumer.` as a
placeholder tool-name prefix. Before syncing for real, replace it with your own
system's slug (e.g. `autofde.`) in `templates/mcp_tool_schema.rs.tmpl` and
`templates/operation_catalog_proof.rs.tmpl`'s matching `format!("consumer.{}", ...)`
call, so generated tool names don't collide with GymAct's own `gymact.*` MCP
surface if both are ever loaded into the same MCP client.

### 4. Sync

```bash
ggen sync run   # from the directory containing this pack's pack.toml
```

This generates, from your `ontology.ttl`, validated against the fetched
`shapes/profile.shacl.ttl`:

- `src/gymact_consumer_operation_catalog.rs` — a typed `OPERATIONS` table
- `src/gymact_consumer_mcp_tools.rs` — an MCP tool schema table
- `docs/gymact-bridge/reference.md` — a human-facing reference doc
- `tests/gymact_consumer_bridge_operation_catalog_proof.rs` — a cross-check proof
  that the two generated Rust modules and the reference doc all agree

A capability whose `dct:type` is not one of GymAct's two real consequence-class
IRIs is refused by the real SHACL shape at sync time, before any file is written
— the same fail-closed behavior GymAct enforces on its own capability data.

## What this pack does not do

- It does not generate your Python `EnvironmentProvider` implementation or your
  `gymact.providers` entry-point registration. Per `gymact`'s own
  `.claude/rules/python-native.md`, GymAct-side Python capabilities are
  hand-authored against mature Python libraries directly, never code-generated.
  See `docs/integrations/consumer-setup.md` in the `gymact` repo for that half of
  the integration.
- It does not grant authority. Whatever these generated `Do`-classified tools
  correspond to in your real system, your own runtime's `AuthorityResolver` (or
  equivalent) still gates them — this pack only classifies and documents, it does
  not enforce.
- It does not, by itself, produce OCEL standing evidence. Per `gymact`'s
  `.claude/rules/ocel-standing.md`, your integration is not "working" until a
  real end-to-end episode against your provider produces a real, conformant,
  `solved=True` OCEL 2.0 log — this pack only manufactures the capability-surface
  documentation/schema, not the runtime proof that it actually executes correctly.

## See also

- `docs/integrations/consumer-setup.md` (in the `gymact` repo) — the full
  integration guide, covering the Python `EnvironmentProvider` protocol, entry-point
  registration, authority injection, and OCEL standing
- `gymact/ggen/gymact-bridge-pack/` (in the `gymact` repo) — the pack this
  template was generalized from; read it for the worked example using GymAct's own
  4 built-in operations
- `~/gymact/.claude/rules/ontology.md` — why this pack declares zero new RDF
  vocabulary
- `~/gymact/.claude/rules/actuation-authority.md` — the authority model your own
  runtime must implement for any `Do`-classified capability
