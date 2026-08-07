# justfile — local mirror of .github/workflows/test.yml ("v26.8.7 contract")
#
# Each recipe corresponds to a CI job so local and remote admission exercise the
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
    if [[ "$py_minor" != "3.13" ]]; then
      if [[ -f "${AUTOFDE_LAB:-$HOME/autofde-lab}/vendor/gyms/browsergym/browsergym/core/pyproject.toml" ]]; then
        uv pip install -e "${AUTOFDE_LAB:-$HOME/autofde-lab}/vendor/gyms/browsergym/browsergym/core"
      else
        uv pip install "browsergym-core @ git+https://github.com/ServiceNow/BrowserGym.git@9e779f087de9a65668b6974d11f9ce9816026e96#subdirectory=browsergym/core"
      fi
      uv run playwright install chromium
    else
      echo 'BrowserGym pin uses playwright==1.44 -> greenlet==3.0.3, which is not CPython 3.13 compatible.'
    fi
    uv run gymact validate-profile
    if [[ "$py_minor" != "3.13" ]]; then
      uv run python -c 'from gymact.gyms.browsergym import BROWSERGYM_CAPABILITIES; from gymact.semantic import ProfileAuthority; r = ProfileAuthority().validate_capabilities(BROWSERGYM_CAPABILITIES); print(r.model_dump_json()); assert r.conforms, r.report_text'
    else
      set +e
      uv run pytest --collect-only -q tests/test_browsergym_gym.py > /tmp/browsergym-standing.txt 2>&1
      standing_rc=$?
      set -e
      cat /tmp/browsergym-standing.txt
      test "$standing_rc" -ne 0
      grep -q 'LOCAL_GYM:browsergym-openended' /tmp/browsergym-standing.txt
      grep -q 'GYMACT_ALLOW_DEGRADED_STANDINGS' /tmp/browsergym-standing.txt
    fi
    if grep -RInE 'unittest\.mock|\bMock\b|\bpatch\b|monkeypatch' tests; then
      echo 'mock-grep: forbidden test seam found' >&2
      exit 1
    else
      echo 'mock-grep: zero matches'
    fi
    if [[ "$py_minor" == "3.13" ]]; then
      GYMACT_ALLOW_DEGRADED_STANDINGS=LOCAL_GYM:browsergym-openended uv run coverage run -m pytest -v
    else
      uv run coverage run -m pytest -v
    fi
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

# ggen-bridge-check — NOT a CI job, NOT part of `all`: this repo has no
# Rust toolchain and CI never sets one up (confirmed: none of
# .github/workflows/*.yml touch rust/cargo/ggen). Requires a real `ggen`
# binary on PATH (build one from the sibling `ggen` repo:
# `cargo build --release -p ggen-cli` there, then add its target/release/
# to PATH, or set GGEN_BIN to its exact path). Proves ggen/gymact-bridge-pack
# actually generates from ontology/profile.{ttl,shacl.ttl} (real symlinks
# into src/gymact/ontology/, not a copy) by running a real `ggen sync run`
# against a scratch consumer project, the same way
# ~/ggen/crates/ggen-engine/tests/gymact_bridge_pack_e2e.rs does from the
# Rust side.
ggen-bridge-check:
    #!/usr/bin/env bash
    set -euo pipefail
    GGEN_BIN="${GGEN_BIN:-ggen}"
    if ! command -v "$GGEN_BIN" >/dev/null 2>&1; then
        echo "ggen-bridge-check: no '$GGEN_BIN' binary on PATH." >&2
        echo "  Build one from the sibling ggen repo (cargo build --release -p ggen-cli)" >&2
        echo "  and either add target/release/ to PATH or set GGEN_BIN to its exact path." >&2
        exit 2
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
    echo "ggen-bridge-check: OK — all 4 expected files generated"

# job: container — Build and probe production container
#
# One shebang script for the whole recipe: `just` only honors `#!/...` as the
# recipe's first line — a shebang appearing mid-recipe is treated as a plain
# comment, and every other line then runs as its own separate `bash -c`
# invocation with no shared variables (bit us with `$cid` once already).
container:
    #!/usr/bin/env bash
    set -euo pipefail
    docker build --target production -t gymact:26.8.7 .
    docker run --rm gymact:26.8.7 version
    docker run --rm gymact:26.8.7 contract | grep -q 'contract_digest'
    cid="$(docker run -d -p 127.0.0.1:8000:8000 gymact:26.8.7)"
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
