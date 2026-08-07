# Python Rule: Compose, Don't Generate, the Python Ecosystem

## The rule

GymAct is a Python library. Python-side capabilities are built by depending on mature
Python libraries directly — never by code-generating what those libraries already derive
correctly from typed Python models.

`ggen` targets the Rust/WASM manufacturing boundary (see `ggen-boundary.md`). It does not
generate Pydantic models, FastAPI routes, FastMCP tool servers, Typer commands, or
FastStream brokers. Those come from the dependencies themselves, driven by one canonical
set of Pydantic types.

```
GymAct semantic profile (RDF/SHACL, read via rdflib/pyshacl)
                │
                ▼
        canonical Pydantic models         <- hand-written or dynamically
                │                              built from SHACL/JSON Schema,
      ┌─────────┼─────────┬────────────┐       but ONE source, reused below
      ▼         ▼         ▼            ▼
   FastAPI   FastMCP    Typer      FastStream
  (OpenAPI)   (MCP)     (CLI)     (AsyncAPI)
```

## Default dependency stack

| Concern | Library |
|---|---|
| typed models / JSON Schema | `pydantic` v2 |
| HTTP + OpenAPI | `fastapi` |
| MCP server/tools | `fastmcp` |
| CLI | `typer` |
| event brokers + AsyncAPI | `faststream` |
| RDF graph | `rdflib` |
| SHACL validation | `pyshacl` |
| HTTP client | `httpx` |
| concurrency | `anyio` |
| retries | `tenacity` |
| episodic-gym compatibility | `gymnasium` |
| multi-agent compatibility | `pettingzoo` |
| BPMN execution (optional) | `SpiffWorkflow` |

Benchmark ecosystems (CUBE, Harbor, Inspect, BrowserGym, etc.) are optional dependencies /
profile implementations behind `gymact.integrations.*`, never vendored or reimplemented.

## What NOT to build

- A custom schema-generation layer that duplicates what `fastapi`/`fastmcp`/`typer` already
  derive from Pydantic types.
- Bespoke wrappers that only forward to a dependency's own API with no added semantics.
- A second source of truth for a constraint that SHACL/ODRL already state — if the ontology
  says `minCount=1`, the Pydantic field is `Required`, not independently re-decided.

## Kernel size

The handwritten Python surface should stay small: a handful of `Protocol`s
(`EnvironmentProvider`, `Environment`, `Verifier`, `Evaluator`) plus the semantic layer
(`gymact.semantic`) and model layer (`gymact.model`). Everything under `gymact.surfaces.*`
(mcp.py, api.py, cli.py, stream.py) should be thin composition of the dependency's own
constructor over the shared Pydantic models — not independent logic.

## See also

- `.claude/rules/ggen-boundary.md`
- `~/.claude/rules/testing-chicago-style.md` — real FastAPI/FastMCP app instances in tests,
  not mocked framework internals
