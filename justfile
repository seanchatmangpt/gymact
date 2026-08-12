# justfile — local mirror of .github/workflows/ci.yml (release verification contract)
#
# Each recipe corresponds to a CI boundary so local and remote admission exercise the
# same commands. The container recipe remains separate because it requires Docker.

set shell := ["bash", "-euo", "pipefail", "-c"]

default: all

all: lock test package docs

lock:
    uv lock
    uv lock --check

test version="":
    #!/usr/bin/env bash
    set -euo pipefail
    requested="{{version}}"
    if [[ -n "$requested" ]]; then
      uv sync --all-extras --group dev --python "$requested"
    else
      uv sync --all-extras --group dev
    fi
    py_minor="$(uv run python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    if [[ -f "${AUTOFDE_LAB:-$HOME/autofde-lab}/vendor/gyms/browsergym/browsergym/core/pyproject.toml" ]]; then
      uv pip install -e "${AUTOFDE_LAB:-$HOME/autofde-lab}/vendor/gyms/browsergym/browsergym/core"
    else
      uv pip install "browsergym-core @ git+https://github.com/ServiceNow/BrowserGym.git@9e779f087de9a65668b6974d11f9ce9816026e96#subdirectory=browsergym/core"
    fi
    uv run playwright install chromium
    uv run gymact validate-profile
    uv run python -c 'from gymact.gyms.browsergym import BROWSERGYM_CAPABILITIES; from gymact.semantic import ProfileAuthority; r = ProfileAuthority().validate_capabilities(BROWSERGYM_CAPABILITIES); print(r.model_dump_json()); assert r.conforms, r.report_text'
    if grep -RInE 'unittest\.mock|\bMock\b|\bpatch\b|monkeypatch' tests; then
      echo 'mock-grep: forbidden test seam found' >&2
      exit 1
    else
      echo 'mock-grep: zero matches'
    fi
    uv run coverage run -m pytest -v
    uv run coverage report
    uv run ruff check src tests
    uv run ruff format --check src tests

test-matrix:
    just test 3.11
    just test 3.12
    just test 3.13

package:
    #!/usr/bin/env bash
    set -euo pipefail
    rm -rf dist /tmp/gymact-wheel /tmp/exported-profile /tmp/manufacturing-bundle
    uv build
    uvx twine check dist/*
    python3 -m venv /tmp/gymact-wheel
    /tmp/gymact-wheel/bin/pip install -q dist/*.whl
    /tmp/gymact-wheel/bin/gymact version
    /tmp/gymact-wheel/bin/gymact validate-profile
    /tmp/gymact-wheel/bin/gymact contract > /tmp/runtime-contract.json
    /tmp/gymact-wheel/bin/gymact export-profile /tmp/exported-profile
    /tmp/gymact-wheel/bin/gymact export-bundle /tmp/manufacturing-bundle
    test -s /tmp/exported-profile/profile.ttl
    test -s /tmp/exported-profile/profile.shacl.ttl
    test -s /tmp/manufacturing-bundle/profile.ttl
    test -s /tmp/manufacturing-bundle/profile.shacl.ttl
    test -s /tmp/manufacturing-bundle/runtime-contract.jcs.json
    /tmp/gymact-wheel/bin/python - <<'PY'
    import json
    from pathlib import Path
    from gymact import build_contract
    from gymact.evidence import canonical_bytes

    observed = json.loads(Path('/tmp/runtime-contract.json').read_text())
    assert observed['contract_digest'] == build_contract().contract_digest
    bundle = Path('/tmp/manufacturing-bundle/runtime-contract.jcs.json').read_bytes()
    assert bundle == canonical_bytes(build_contract().model_dump(mode='json'))
    PY

docs:
    uv sync --group dev
    uv run zensical build --clean

# Exact-head composition court. This exists because multiple individually real
# branches were merged in one integration round and the resulting composed
# main contained two real defects that no branch-local claim could rule out.
# The full test suite also executes this file; this named target makes the
# standing boundary cheap to run after any local merge/composition operation.
composition-court:
    uv run pytest -v tests/test_default_head_composition_court.py

# ggen-bridge-check — NOT a CI job, NOT part of `all`: requires a real `ggen`
# binary on PATH. The exact version is now a fail-closed manufacturing input,
# not an advisory convenience: GymAct's pinned CI capsule and marketplace
# qualification both execute ggen 26.8.11, so another local version is a
# different subject and cannot inherit their standing.
ggen-bridge-check:
    #!/usr/bin/env bash
    set -euo pipefail
    GGEN_BIN="${GGEN_BIN:-ggen}"
    if ! command -v "$GGEN_BIN" >/dev/null 2>&1; then
        echo "ggen-bridge-check: no '$GGEN_BIN' binary on PATH." >&2
        exit 2
    fi
    PINNED_VERSION="$(tr -d '[:space:]' < "$(pwd)/.ggen-version")"
    INSTALLED_VERSION="$("$GGEN_BIN" --version | head -n1 | awk '{print $2}')"
    if [ "$INSTALLED_VERSION" != "$PINNED_VERSION" ]; then
        echo "REFUSED:GGEN_VERSION_DRIFT:installed=$INSTALLED_VERSION pinned=$PINNED_VERSION" >&2
        exit 3
    fi
    PACK_ROOT="$(pwd)/ggen/gymact-bridge-pack"
    SCRATCH="$(mktemp -d)"
    trap 'rm -rf "$SCRATCH"' EXIT
    mkdir -p "$SCRATCH/consumer/templates" "$SCRATCH/consumer/shapes"
    printf '' > "$SCRATCH/consumer/ontology.ttl"
    cat > "$SCRATCH/consumer/ggen.toml" <<EOF
    [project]
    name = "consumer"

    [ontology]
    source = "ontology.ttl"

    [packs]
    gymact-bridge-pack = { path = "$PACK_ROOT" }

    [templates]
    dir = "templates"
    EOF
    cp "$PACK_ROOT/ontology/profile.shacl.ttl" "$SCRATCH/consumer/shapes/profile.shacl.ttl"
    (cd "$SCRATCH/consumer" && "$GGEN_BIN" sync run)
    for f in src/gymact_operation_catalog.rs src/gymact_mcp_tools.rs docs/gymact-bridge/reference.md tests/gymact_bridge_operation_catalog_proof.rs; do
        test -s "$SCRATCH/consumer/$f" || { echo "ggen-bridge-check: expected generated file missing: $f" >&2; exit 1; }
    done
    echo "ggen-bridge-check: OK — all 4 expected files generated with ggen $PINNED_VERSION"

# ggen-gates-check — NOT part of `all`: runs every ggen/*/gates/*.rq SPARQL
# gate against its own pack's ontology.ttl via rdflib.
ggen-gates-check:
    uv run python scripts/run_sparql_gates.py

# ocel-standing — human-facing batch report; the actual gate is pytest.
ocel-standing:
    uv run python scripts/ocel_standing.py reports/ocel

# capability-manifest — downstream reporting projection, not DO authority.
capability-manifest:
    uv run python scripts/capability_manifest.py

# The raw AST report remains advisory for genuinely simulated worlds. The
# exact-head composition court hard-fails if any of the five already-proven
# live external observation providers loses its independent I/O path.
observe-independence-check:
    uv run python scripts/check_observe_independence.py

container:
    #!/usr/bin/env bash
    set -euo pipefail
    docker build --target production -t gymact:ci-local .
    docker run --rm gymact:ci-local version
    docker run --rm gymact:ci-local contract | grep -q 'contract_digest'
    cid="$(docker run -d -p 127.0.0.1:8000:8000 gymact:ci-local)"
    trap 'docker rm -f "$cid" >/dev/null 2>&1 || true' EXIT
    for _ in $(seq 1 30); do
      if curl -fsS http://127.0.0.1:8000/health | grep -q 'ALIVE'; then
        curl -fsS http://127.0.0.1:8000/contract | grep -q 'RFC8785-JCS'
        curl -fsS http://127.0.0.1:8000/evidence | grep -q 'verified'
        exit 0
      fi
      sleep 1
    done
    docker logs "$cid"
    exit 1
