#!/usr/bin/env python3
"""Generate A2A v1 capability cards from GymAct's REAL runtime surfaces.

One card per transport surface (gymact.http, gymact.mcp, gymact.stream,
gymact.sa2a-transport). Skills are extracted programmatically from the live
objects -- never hand-transcribed:

- ``gymact.http``  : every route on the real ``FastAPI`` app's route table
  (``create_app().routes``, methods + path).
- ``gymact.mcp``   : every tool registered on the real ``FastMCP`` instance
  (``create_mcp().list_tools()``).
- ``gymact.stream``: every operation dispatched by
  ``gymact.surfaces.faststream.dispatch_stream_command``, extracted from the
  module's real source via AST (the ``operation == "<op>"`` branches).
- ``gymact.sa2a-transport``: the real public functions of
  ``gymact.sa2a_transport`` (``a2a_task_to_envelope``, ``envelope_to_artifact``)
  plus the typed SA2A refusal codes enforced by ``admit_envelope``.

Authority law is embedded in every card description: GymAct's kernel
(``GymAct._authority_decision``, ``src/gymact/kernel.py``) is the sole
authority gate -- no transport grants authority by itself -- and SA2A
envelope admission (``gymact.sa2a_envelope.admit_envelope``) refuses on
subject/contract mismatch with a typed code.

Usage::

    python scripts/gen_agent_cards.py            # write cards to priv/cards/
    python scripts/gen_agent_cards.py <out_dir>  # or an explicit directory

Determinism: two consecutive runs must be byte-identical (sorted keys,
sorted routes/tools/operations, no timestamps, no environment-dependent
content).
"""

from __future__ import annotations

import ast
import inspect
import re
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact.surfaces.fastapi import create_app  # noqa: E402
from gymact.surfaces.fastmcp import create_mcp  # noqa: E402
import gymact  # noqa: E402
import gymact.surfaces.faststream as faststream_module  # noqa: E402
import gymact.sa2a_transport as sa2a_transport_module  # noqa: E402
import gymact.sa2a_envelope as sa2a_envelope_module  # noqa: E402

AUTHORITY_LAW = (
    "Authority law: GymAct's kernel gate GymAct._authority_decision "
    "(src/gymact/kernel.py) is the sole authority boundary for every "
    "consequential operation (act/restore/teardown/materialize); a transport "
    "never grants authority by itself, and required authority is fail-closed "
    "unless the injected AuthorityResolver admits the exact operation. SA2A "
    "envelope admission (gymact.sa2a_envelope.admit_envelope) additionally "
    "refuses any envelope whose exact_subject or pinned contract_digest "
    "mismatches, surfacing a typed refusal (e.g. SA2A_EXACT_SUBJECT_MISMATCH) "
    "as an A2A task.failed terminal state."
)

_SA2A_REFUSAL_CODES = (
    "SA2A_EXACT_SUBJECT_REQUIRED",
    "SA2A_EXACT_SUBJECT_NONFINITE_NUMBER",
    "SA2A_EXACT_SUBJECT_MISMATCH",
    "SA2A_ENVELOPE_INVALID",
    "A2A_CONTEXT_ID_REQUIRED",
    "A2A_TASK_ID_REQUIRED",
    "A2A_MESSAGE_REQUIRED",
    "A2A_MESSAGE_PARTS_REQUIRED",
    "A2A_ENVELOPE_PART_NOT_FOUND",
)


def extract_http_routes() -> list[dict[str, str]]:
    """Extract every real route (method + path) from the live FastAPI app."""
    app = create_app()
    routes = []
    for route in app.routes:
        methods = getattr(route, "methods", None)
        if not methods:
            continue
        for method in sorted(methods - {"HEAD", "OPTIONS"}):
            routes.append({"method": method, "path": route.path})
    routes.sort(key=lambda item: (item["path"], item["method"]))
    return routes


def extract_mcp_tools() -> list[str]:
    """Extract every real registered tool name from the live FastMCP server."""
    mcp = create_mcp()
    tools = list(asyncio_run(mcp.list_tools()))
    return sorted(tool.name for tool in tools)


def asyncio_run(coro: Any) -> Any:
    import asyncio

    return asyncio.run(coro)


def extract_stream_operations() -> list[str]:
    """Extract the real dispatched operations via AST over the module source."""
    source = inspect.getsource(faststream_module)
    tree = ast.parse(source)
    operations = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
            continue
        test = node.test
        if (
            isinstance(test.left, ast.Name)
            and test.left.id == "operation"
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and isinstance(test.comparators[0].value, str)
        ):
            operations.add(test.comparators[0].value)
    return sorted(operations)


def extract_sa2a_transport_skills() -> list[dict[str, str]]:
    """The real public functions plus the typed refusal codes they surface."""
    return [
        {
            "name": "a2a_task_to_envelope",
            "id": "gymact.sa2a-transport.a2a-task-to-envelope",
            "tags": ["sa2a", "admission"],
            "description": (
                "Admit the SA2A replan envelope carried by an A2A v1 task "
                "payload. Admission is through admit_envelope with the "
                "producer's contract_digest carried verbatim; any refusal "
                "(subject mismatch, digest mismatch, malformed task framing) "
                "is a typed A2A task.failed terminal state, never a silent "
                "no-op. Refusal codes: "
                + ", ".join(_SA2A_REFUSAL_CODES)
                + "."
            ),
        },
        {
            "name": "envelope_to_artifact",
            "id": "gymact.sa2a-transport.envelope-to-artifact",
            "tags": ["sa2a", "projection"],
            "description": (
                "Re-admit and project an admitted SA2A envelope as an A2A "
                "artifact carrying SA2AEvolutionFeedback."
            ),
        },
    ]


def _slug(text: str) -> str:
    """Deterministic id-safe slug: lowercase, non-allowed chars -> '-'."""
    out = re.sub(r"[^A-Za-z0-9_-]+", "-", text).strip("-")
    return out.lower() or "op"


def build_card(card_id: str, name: str, description: str, skills: list[dict[str, Any]]) -> dict[str, Any]:
    binding = card_id.removeprefix("gymact.")
    return {
        "protocolVersion": "1.0",
        "name": name,
        "id": card_id,
        "description": f"{description} {AUTHORITY_LAW}",
        "version": gymact.__version__,
        "supportedInterfaces": [
            {"protocolVersion": "1.0", "protocolBinding": binding}
        ],
        "capabilities": {"streaming": False, "pushNotifications": False},
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "provider": {"organization": "gymact", "url": "urn:gymact"},
        "skills": skills,
    }


def build_cards() -> list[dict[str, Any]]:
    http_routes = extract_http_routes()
    mcp_tools = extract_mcp_tools()
    stream_ops = extract_stream_operations()

    http_skills = [
        {
            "name": f"{route['method']} {route['path']}",
            "id": f"gymact.http.{_slug(route['method'])}-{_slug(route['path'])}",
            "tags": (
                ["http", "consequence"]
                if route["method"] in {"POST", "DELETE", "PUT", "PATCH"}
                else ["http", "read"]
            ),
            "description": (
                f"{route['method']} endpoint on the GymAct HTTP surface."
                + (
                    " Consequential operations cross the kernel authority gate."
                    if route["method"] in {"POST", "DELETE", "PUT", "PATCH"}
                    else " Read-only observation; no authority required."
                )
            ),
        }
        for route in http_routes
        # FastAPI's self-generated documentation routes are framework
        # machinery, not GymAct skills.
        if route["path"] not in {"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}
    ]

    mcp_skill_list = [
        {
            "name": tool,
            "id": f"gymact.mcp.{_slug(tool)}",
            "tags": ["mcp"],
            "description": f"MCP tool on the GymAct MCP surface.",
        }
        for tool in mcp_tools
    ]

    stream_skill_list = [
        {
            "name": op,
            "id": f"gymact.stream.{_slug(op)}",
            "tags": ["stream"],
            "description": (
                "Broker-neutral stream operation on the GymAct FastStream "
                "surface; DO-class operations require a DCM selected cut."
            ),
        }
        for op in stream_ops
    ]

    return [
        build_card(
            "gymact.http",
            "GymAct HTTP Surface",
            "HTTP/OpenAPI projection of the GymAct runtime. DCM selected-cut "
            "execution (/episodes/{id}/actions/selected) is the canonical DO "
            "path.",
            http_skills,
        ),
        build_card(
            "gymact.mcp",
            "GymAct MCP Surface",
            "FastMCP tool surface over GymAct's semantic runtime; MCP is "
            "transport, never a reasoner. Default production surface is the "
            "ontology-admitted ten-tool bridge.",
            mcp_skill_list,
        ),
        build_card(
            "gymact.stream",
            "GymAct Stream Surface",
            "Broker-neutral FastStream command dispatch over the same runtime.",
            stream_skill_list,
        ),
        build_card(
            "gymact.sa2a-transport",
            "GymAct SA2A Transport Adapter",
            "A2A v1 task transport adapter composed over SA2A portable "
            "envelope admission; refusals are typed terminal states.",
            extract_sa2a_transport_skills(),
        ),
    ]


def write_cards(out_dir: Path) -> list[Path]:
    cards = build_cards()
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for card in cards:
        path = out_dir / f"{card['id']}.json"
        path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
        written.append(path)
    return written


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "priv" / "cards"
    written = write_cards(out_dir)
    counts = []
    for card in build_cards():
        counts.append(f"{card['id']}={len(card['skills'])}")
    print(f"gen_agent_cards: wrote {len(written)} cards ({', '.join(counts)}) to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
