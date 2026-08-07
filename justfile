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
    uv sync --all-extras --group dev {{ if version != "" { "--python " + version } else { "" } }}
    uv run coverage run -m pytest
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
