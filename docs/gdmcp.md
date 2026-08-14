# gdmcp — Generated Deterministic MCP

`gdmcp` is GymAct's deterministic-first MCP execution profile. It does not create an autonomous agent and it does not add an actuation path.

For a known, exact-pinned subject, gdmcp compiles a source-grounded solution program into ordinary `ActuationIntent` values. Those intents still pass through GymAct's capability scope, authority resolver, provider boundary, independent observation, OCEL/receipt path, and BRCE consequence controls.

```text
known subject + exact revision + admitted bindings
    -> gdmcp deterministic program
    -> generated ActuationIntent sequence
    -> GymAct capability/authority gates
    -> existing MCP server/provider
    -> observed consequence / receipt

unknown subject | revision drift | binding drift
    -> REFUSED
    -> novelty belongs outside the DO path
```

## SREGym profile

The first profile uses SREGym's own exact-pinned recovery semantics as the solution source. The current pin is:

```text
SREGym/SREGym@ba07faf1a322f9b6d4a279643bb796aa2f36f64b
```

The registered `sregym` provider is `gymact.gyms.sregym_ontology.SregymOntologyProvider`, which wraps the existing `gymact.gyms.sregym.SregymVendorProvider` (delegating observation/actuation while sourcing `capabilities()` from the admitted `sregym_mcp_catalog` and adding strict IRI/binding/consequence admission checks, so stale hand-authored capability metadata in the physics module cannot become runtime standing). gdmcp itself is an **ADAPT/composition layer**, not another provider and not another MCP server. It compiles deterministic client-side calls to the already-real SREGym MCP surfaces.

The initial executable catalog intentionally covers only two of the 21 exact SREGym-Lite subjects:

- `wrong_dns_policy_astronomy_shop`
- `internal_traffic_policy_local_astronomy_shop`

Therefore the initial bounded deterministic projection ratio is:

```text
2 / 21 = 9.52%
```

That number is deliberately exposed by `sregym_lite_coverage()` rather than treating a compiler interface as benchmark completion. The remaining 19 Lite problems are `GDMCP_SOLUTION_UNKNOWN` until their upstream recovery semantics are projected into an admitted deterministic program.

## Laws

- MCP is transport, not reasoning.
- `llm_calls == 0` for every admitted gdmcp program.
- Generated does not mean authorized.
- A gdmcp program may use only an explicit capability allowlist.
- Runtime substitutions are typed and exact; the initial SREGym profile accepts only a Kubernetes namespace binding and validates it as an RFC 1123-style name before embedding it into commands.
- Upstream revision drift is `REFUSED:GDMCP_SUBJECT_DRIFT`.
- Unknown problem identity is `REFUSED:GDMCP_SOLUTION_UNKNOWN`; there is no LLM fallback in the actuation path.
- The same subject, bindings, authority reference, principal, and episode identity compile to the same program digest and idempotency keys.
- All real consequence remains behind GymAct/BRCE.

## Expansion

The intended expansion path is to move the solution catalog itself upstream into admitted semantic source and let `ggen` manufacture the gdmcp program data. The Python compiler should remain generic: adding a solved problem should add admitted data/evidence, not another reasoning branch.

As Process Intelligence discovers recurring exception classes, AutoFDE-Lab can construct and falsify a candidate repair, ggen can capitalize the admitted repair into the gdmcp catalog, and future occurrences then execute with zero generative inference.
